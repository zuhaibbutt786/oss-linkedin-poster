#!/usr/bin/env python3
"""
Auto-post open-source projects to LinkedIn (personal profile).

Sources:
  - GitHub Search API (broad tech topics)
  - https://www.opensourceprojects.dev/rss

Features:
  - Groq viral captions (optional GROQ_API_KEY)
  - Repo Open Graph image when possible
  - Never posts the same repo twice (data/posted_repos.json)
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import requests

LINKEDIN_VERSION = "202607"
POSTED_FILE = Path(__file__).resolve().parent.parent / "data" / "posted_repos.json"
OSP_RSS = "https://www.opensourceprojects.dev/rss"

# Broad tech topics
TOPICS = [
    "machine learning",
    "deep learning",
    "generative ai",
    "llm",
    "nlp",
    "computer vision",
    "audio ai",
    "speech recognition",
    "data science",
    "big data",
    "iot",
    "artificial intelligence",
    "open source ai",
    "research",
    "typescript",
    "javascript",
    "react",
    "nextjs",
    "nodejs",
    "python",
    "golang",
    "rust",
    "kubernetes",
    "docker",
    "devops",
    "cloud",
    "aws",
    "serverless",
    "database",
    "postgres",
    "redis",
    "api",
    "cli",
    "developer tools",
    "security",
    "cybersecurity",
    "blockchain",
    "webassembly",
    "mobile",
    "android",
    "ios",
    "flutter",
    "frontend",
    "backend",
    "fullstack",
    "observability",
    "monitoring",
    "testing",
    "automation",
]

MIN_STARS = 150
CREATED_AFTER = (datetime.utcnow() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")

FALLBACK_HOOKS = [
    "This open-source project deserves more attention than it gets.",
    "If you build software for a living, bookmark this repository.",
    "Most people still don't know about this powerful open-source tool.",
    "Here's a high-signal open-source project worth your time.",
    "A clean, practical open-source project that solves a real problem.",
    "Stop scrolling — this repo is actually useful.",
    "Developers should know about this open-source project.",
    "Found a high-quality open-source project that deserves more eyes.",
]


def load_posted() -> set[str]:
    if not POSTED_FILE.exists():
        return set()
    try:
        data = json.loads(POSTED_FILE.read_text(encoding="utf-8"))
        return set(data.get("posted") or [])
    except Exception:
        return set()


def save_posted(posted: set[str], new_name: str) -> None:
    posted.add(new_name)
    POSTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Keep list bounded
    items = sorted(posted)[-500:]
    POSTED_FILE.write_text(
        json.dumps({"posted": items, "updated_at": datetime.utcnow().isoformat() + "Z"}, indent=2),
        encoding="utf-8",
    )
    print(f"Recorded posted repo: {new_name} (total tracked: {len(items)})")


def get_person_urn(access_token: str) -> str:
    headers = {"Authorization": f"Bearer {access_token}", "X-Restli-Protocol-Version": "2.0.0"}
    resp = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=15)
    if resp.status_code == 200:
        sub = resp.json().get("sub")
        if sub:
            return f"urn:li:person:{sub}"
    resp = requests.get("https://api.linkedin.com/v2/me", headers=headers, timeout=15)
    resp.raise_for_status()
    person_id = resp.json().get("id")
    if not person_id:
        raise RuntimeError("Could not retrieve LinkedIn person ID")
    return f"urn:li:person:{person_id}"


def search_github_repos(query: str, token: str | None = None) -> list:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": 25}
    resp = requests.get(
        "https://api.github.com/search/repositories",
        headers=headers,
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def fetch_osp_projects() -> list[dict]:
    """Parse opensourceprojects.dev RSS into GitHub-like repo dicts."""
    projects = []
    try:
        resp = requests.get(OSP_RSS, timeout=20, headers={"User-Agent": "OSS-LinkedIn-Poster/1.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            desc = (item.findtext("description") or "").strip()
            # Strip HTML-ish bits lightly
            desc_plain = re.sub(r"<[^>]+>", " ", desc)
            desc_plain = re.sub(r"\s+", " ", desc_plain).strip()

            m = re.search(r"https://github\.com/([\w.-]+)/([\w.-]+)", desc + " " + title)
            if not m:
                continue
            full_name = f"{m.group(1)}/{m.group(2).rstrip('/')}"
            image = None
            enc = item.find("enclosure")
            if enc is not None:
                image = enc.get("url")
            if not image:
                image = f"https://opengraph.githubassets.com/1/{full_name}"

            projects.append(
                {
                    "full_name": full_name,
                    "html_url": f"https://github.com/{full_name}",
                    "description": title or desc_plain[:280],
                    "stargazers_count": 0,
                    "language": None,
                    "source": "opensourceprojects.dev",
                    "image_url": image,
                    "archived": False,
                }
            )
        print(f"Fetched {len(projects)} projects from opensourceprojects.dev RSS")
    except Exception as e:
        print(f"OSP RSS fetch failed: {e}")
    return projects


def enrich_from_github(repo: dict, token: str | None = None) -> dict:
    """Fill stars/language/description from GitHub API when missing."""
    if repo.get("stargazers_count") and repo.get("language"):
        return repo
    try:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        r = requests.get(
            f"https://api.github.com/repos/{repo['full_name']}",
            headers=headers,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            repo["stargazers_count"] = data.get("stargazers_count", 0)
            repo["language"] = data.get("language")
            repo["description"] = data.get("description") or repo.get("description")
            repo["archived"] = data.get("archived", False)
            repo["html_url"] = data.get("html_url") or repo.get("html_url")
    except Exception as e:
        print(f"Enrich failed for {repo.get('full_name')}: {e}")
    return repo


def pick_project(posted: set[str]) -> dict:
    candidates: list[dict] = []

    # 1) opensourceprojects.dev
    for p in fetch_osp_projects():
        if p["full_name"].lower() not in {x.lower() for x in posted}:
            candidates.append(p)

    # 2) GitHub search across random tech topics
    topics = random.sample(TOPICS, k=min(4, len(TOPICS)))
    for topic in topics:
        q = f"{topic} stars:>{MIN_STARS} created:>{CREATED_AFTER}"
        print(f"Searching GitHub: {q}")
        try:
            items = search_github_repos(q, token=os.getenv("GITHUB_TOKEN"))
            for r in items:
                name = r.get("full_name") or ""
                if name.lower() in {x.lower() for x in posted}:
                    continue
                if r.get("archived"):
                    continue
                if not r.get("description"):
                    continue
                r["source"] = "github"
                candidates.append(r)
        except Exception as e:
            print(f"GitHub search error: {e}")

    if not candidates:
        raise RuntimeError("No unposted projects found from any source")

    # Prefer a mix; shuffle and pick
    random.shuffle(candidates)
    # Prefer higher stars when available
    candidates.sort(key=lambda x: x.get("stargazers_count") or 0, reverse=True)
    pool = candidates[:15]
    repo = random.choice(pool)
    repo = enrich_from_github(repo, token=os.getenv("GITHUB_TOKEN"))
    print(f"Selected: {repo['full_name']} (source={repo.get('source')}, stars={repo.get('stargazers_count')})")
    return repo


def generate_with_groq(repo: dict) -> str | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    name = repo["full_name"]
    desc = (repo.get("description") or "").strip()
    stars = repo.get("stargazers_count", 0)
    lang = repo.get("language") or "N/A"
    url = repo["html_url"]

    prompt = f"""Write a LinkedIn post about this open-source GitHub project.

Project: {name}
Description: {desc}
Stars: {stars}
Language: {lang}
URL: {url}

Rules:
- Start with a strong viral hook (1 short line that stops the scroll)
- Then 2–4 short paragraphs on why it matters for developers / tech people
- Professional but punchy, not salesy
- End with the GitHub URL on its own line
- Add 6–10 relevant hashtags at the end
- Length about 120–220 words
- No markdown, asterisks, or bullet points
- Write only the post text"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert LinkedIn content writer for developers and open-source audiences.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.85,
                "max_tokens": 500,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            print("Groq API error:", resp.status_code, resp.text[:300])
            return None
        text = resp.json()["choices"][0]["message"]["content"].strip()
        print("Generated caption with Groq")
        return text
    except Exception as e:
        print(f"Groq failed: {e}")
        return None


def create_post_text_fallback(repo: dict) -> str:
    name = repo["full_name"]
    desc = (repo.get("description") or "").strip()
    stars = repo.get("stargazers_count", 0)
    lang = repo.get("language") or "N/A"
    url = repo["html_url"]
    stars_str = f"{stars/1000:.1f}k" if stars >= 1000 else str(stars)
    hook = random.choice(FALLBACK_HOOKS)

    return f"""{hook}

🚀 {name}

{desc}

This project stands out because it is practical, actively maintained, and useful for builders across the stack — from AI and data to cloud, DevOps, and developer tools. High-quality open source like this is worth following whether you are learning, shipping products, or exploring new ideas.

⭐ {stars_str} stars  |  💻 {lang}

{url}

#OpenSource #GitHub #Developers #SoftwareEngineering #AI #MachineLearning #DataScience #DevOps #Cloud #Programming""".strip()


def upload_image_to_linkedin(access_token: str, author_urn: str, image_url: str) -> str | None:
    try:
        img_resp = requests.get(image_url, timeout=20)
        if img_resp.status_code != 200 or len(img_resp.content) < 1000:
            return None
        content_type = img_resp.headers.get("Content-Type", "image/png")
        content_type = "image/jpeg" if "jpeg" in content_type or "jpg" in content_type else "image/png"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "Linkedin-Version": LINKEDIN_VERSION,
        }
        init = requests.post(
            "https://api.linkedin.com/rest/images?action=initializeUpload",
            headers=headers,
            json={"initializeUploadRequest": {"owner": author_urn}},
            timeout=20,
        )
        if init.status_code not in (200, 201):
            print("Image init failed:", init.status_code, init.text[:200])
            return None
        data = init.json().get("value", {})
        upload_url, image_urn = data.get("uploadUrl"), data.get("image")
        if not upload_url or not image_urn:
            return None

        up = requests.put(
            upload_url,
            data=img_resp.content,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": content_type},
            timeout=60,
        )
        if up.status_code not in (200, 201):
            print("Image upload failed:", up.status_code)
            return None
        print(f"Uploaded image: {image_urn}")
        return image_urn
    except Exception as e:
        print(f"Image upload skipped: {e}")
        return None


def get_repo_image_url(repo: dict) -> str | None:
    if repo.get("image_url"):
        return repo["image_url"]
    full_name = repo.get("full_name")
    if full_name:
        return f"https://opengraph.githubassets.com/1/{full_name}"
    return (repo.get("owner") or {}).get("avatar_url")


def post_to_linkedin(access_token: str, author_urn: str, commentary: str, image_urn: str | None = None) -> str:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": LINKEDIN_VERSION,
    }
    payload = {
        "author": author_urn,
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if image_urn:
        payload["content"] = {"media": {"id": image_urn}}

    resp = requests.post("https://api.linkedin.com/rest/posts", headers=headers, json=payload, timeout=20)
    if resp.status_code not in (200, 201) and image_urn:
        print("Post with image failed, retrying text-only...")
        payload.pop("content", None)
        resp = requests.post("https://api.linkedin.com/rest/posts", headers=headers, json=payload, timeout=20)
    if resp.status_code not in (200, 201):
        print("LinkedIn API error:", resp.status_code, resp.text)
        resp.raise_for_status()

    post_id = resp.headers.get("x-restli-id", "unknown")
    print(f"Successfully posted! ID: {post_id}")
    return post_id


def main():
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not access_token:
        print("ERROR: LINKEDIN_ACCESS_TOKEN secret is not set.")
        sys.exit(1)

    try:
        posted = load_posted()
        print(f"Already posted: {len(posted)} repos")

        print("Getting LinkedIn person URN...")
        author_urn = get_person_urn(access_token)
        print(f"Author: {author_urn}")

        print("Picking project (GitHub + opensourceprojects.dev)...")
        repo = pick_project(posted)

        text = generate_with_groq(repo) or create_post_text_fallback(repo)
        print("\n--- Post text ---")
        print(text)
        print("-----------------\n")

        image_urn = None
        img_url = get_repo_image_url(repo)
        if img_url:
            print(f"Trying repo image: {img_url}")
            image_urn = upload_image_to_linkedin(access_token, author_urn, img_url)

        post_to_linkedin(access_token, author_urn, text, image_urn)
        save_posted(posted, repo["full_name"])
        print("Done.")

    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
