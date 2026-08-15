#!/usr/bin/env python3
"""
Auto-post a relevant open-source project to LinkedIn (personal profile).
- Uses Groq (if GROQ_API_KEY is set) for viral hooks + longer captions
- Tries to attach a repo social/preview image when possible
- Topics: Data Science, ML, AI, GenAI, NLP, Research, Audio AI, Vision AI, IoT, Big Data
"""

import os
import random
import sys
from datetime import datetime, timedelta
from io import BytesIO

import requests

# ---------- Config ----------
LINKEDIN_VERSION = "202607"
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
]

MIN_STARS = 200
CREATED_AFTER = (datetime.utcnow() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")

FALLBACK_HOOKS = [
    "This open-source project is quietly changing how people build AI systems.",
    "If you work with AI or data, you need to see this repository.",
    "Most people still don't know about this powerful open-source tool.",
    "Here's a high-signal open-source project worth your attention.",
    "This is one of the most practical AI/ML repos I've seen recently.",
    "Stop scrolling — this open-source project is actually useful.",
    "A clean, well-maintained open-source project that solves a real problem.",
    "Developers building in AI should bookmark this.",
]


def get_person_urn(access_token: str) -> str:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
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
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": 20}
    resp = requests.get("https://api.github.com/search/repositories", headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json().get("items", [])


def pick_project() -> dict:
    topic = random.choice(TOPICS)
    q = f"{topic} stars:>{MIN_STARS} created:>{CREATED_AFTER}"
    print(f"Searching GitHub for: {q}")
    repos = search_github_repos(q, token=os.getenv("GITHUB_TOKEN"))
    if not repos:
        q = f"{topic} stars:>{MIN_STARS}"
        print(f"Fallback search: {q}")
        repos = search_github_repos(q, token=os.getenv("GITHUB_TOKEN"))
    if not repos:
        raise RuntimeError("No suitable repositories found")

    candidates = [
        r for r in repos
        if r.get("description") and not r.get("archived") and r.get("stargazers_count", 0) >= MIN_STARS
    ] or repos
    repo = random.choice(candidates[:8])
    print(f"Selected: {repo['full_name']} ({repo['stargazers_count']} stars)")
    return repo


def generate_with_groq(repo: dict) -> str | None:
    """Use Groq to write a viral LinkedIn caption."""
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
- Then 2–4 short paragraphs expanding on why it matters for AI / ML / Data Science people
- Keep it professional but punchy, not salesy
- End with the GitHub URL on its own line
- Add 6–10 relevant hashtags at the end
- Total length: about 120–220 words
- Do NOT use markdown, asterisks, or bullet points
- Write only the post text, nothing else"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are an expert LinkedIn content writer for AI and open-source audiences."},
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
        print(f"Groq failed, using fallback: {e}")
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

This project stands out because it is practical, actively maintained, and useful for people working in AI, machine learning, and data science. Whether you are building models, exploring new tools, or looking for high-quality open source to learn from, repositories like this are worth following.

⭐ {stars_str} stars  |  💻 {lang}

{url}

#OpenSource #MachineLearning #AI #DataScience #GenAI #NLP #ComputerVision #BigData #Research #Developers""".strip()


def upload_image_to_linkedin(access_token: str, author_urn: str, image_url: str) -> str | None:
    """Download image and upload to LinkedIn. Returns image URN or None."""
    try:
        img_resp = requests.get(image_url, timeout=20)
        if img_resp.status_code != 200 or len(img_resp.content) < 1000:
            return None
        content_type = img_resp.headers.get("Content-Type", "image/png")
        if "jpeg" in content_type or "jpg" in content_type:
            content_type = "image/jpeg"
        else:
            content_type = "image/png"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "Linkedin-Version": LINKEDIN_VERSION,
        }
        init_payload = {
            "initializeUploadRequest": {
                "owner": author_urn,
            }
        }
        init = requests.post(
            "https://api.linkedin.com/rest/images?action=initializeUpload",
            headers=headers,
            json=init_payload,
            timeout=20,
        )
        if init.status_code not in (200, 201):
            print("Image init failed:", init.status_code, init.text[:200])
            return None

        data = init.json().get("value", {})
        upload_url = data.get("uploadUrl")
        image_urn = data.get("image")
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
    """Best-effort social / open-graph style image for the repo."""
    # GitHub opengraph image
    full_name = repo.get("full_name")
    if full_name:
        return f"https://opengraph.githubassets.com/1/{full_name}"
    owner = repo.get("owner") or {}
    return owner.get("avatar_url")


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
        payload["content"] = {
            "media": {
                "id": image_urn,
            }
        }

    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers=headers,
        json=payload,
        timeout=20,
    )

    if resp.status_code not in (200, 201):
        # Retry without image if media caused the failure
        if image_urn and resp.status_code >= 400:
            print("Post with image failed, retrying text-only...")
            payload.pop("content", None)
            resp = requests.post(
                "https://api.linkedin.com/rest/posts",
                headers=headers,
                json=payload,
                timeout=20,
            )
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
        print("Getting LinkedIn person URN...")
        author_urn = get_person_urn(access_token)
        print(f"Author: {author_urn}")

        print("Picking a relevant open-source project...")
        repo = pick_project()

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
        print("Done.")

    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
