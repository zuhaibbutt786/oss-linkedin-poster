#!/usr/bin/env python3
"""
Auto-post a relevant open-source project to LinkedIn (personal profile).
Topics: Data Science, ML, AI, GenAI, NLP, Research, Audio AI, Vision AI, IoT, Big Data, Open Source.
"""

import os
import random
import sys
from datetime import datetime, timedelta

import requests




# ---------- Config ----------
LINKEDIN_VERSION = "202405"  # YYYYMM format – update if needed
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

# Prefer relatively recent + high-quality projects
MIN_STARS = 200
CREATED_AFTER = (datetime.utcnow() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")  # last ~2 years


def get_person_urn(access_token: str) -> str:
    """Get the authenticated member's person URN."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    # Prefer OpenID userinfo if available
    resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers=headers,
        timeout=15,
    )
    if resp.status_code == 200:
        data = resp.json()
        sub = data.get("sub")
        if sub:
            return f"urn:li:person:{sub}"

    # Fallback to /v2/me
    resp = requests.get(
        "https://api.linkedin.com/v2/me",
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    person_id = data.get("id")
    if not person_id:
        raise RuntimeError("Could not retrieve LinkedIn person ID")
    return f"urn:li:person:{person_id}"


def search_github_repos(query: str, token: str | None = None) -> list:
    """Search GitHub for repositories matching the query."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": 20,
    }
    resp = requests.get(url, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json().get("items", [])


def pick_project(access_token: str | None = None) -> dict:
    """Pick one interesting project from the topic list."""
    topic = random.choice(TOPICS)
    # Build a good search query
    q = f"{topic} stars:>{MIN_STARS} created:>{CREATED_AFTER}"
    print(f"Searching GitHub for: {q}")

    repos = search_github_repos(q, token=os.getenv("GITHUB_TOKEN"))
    if not repos:
        # Fallback broader search
        q = f"{topic} stars:>{MIN_STARS}"
        print(f"Fallback search: {q}")
        repos = search_github_repos(q, token=os.getenv("GITHUB_TOKEN"))

    if not repos:
        raise RuntimeError("No suitable repositories found")

    # Prefer repos that look actively maintained and have a description
    candidates = [
        r for r in repos
        if r.get("description") and not r.get("archived") and r.get("stargazers_count", 0) >= MIN_STARS
    ]
    if not candidates:
        candidates = repos

    repo = random.choice(candidates[:8])  # pick from top few
    print(f"Selected: {repo['full_name']} ({repo['stargazers_count']} stars)")
    return repo


def create_post_text(repo: dict) -> str:
    """Generate a professional LinkedIn post."""
    name = repo["full_name"]
    desc = (repo.get("description") or "").strip()
    stars = repo.get("stargazers_count", 0)
    lang = repo.get("language") or "N/A"
    url = repo["html_url"]

    # Format large numbers nicely
    if stars >= 1000:
        stars_str = f"{stars/1000:.1f}k"
    else:
        stars_str = str(stars)

    post = f"""🚀 Open-source gem for the AI / Data Science community

{name}

{desc}

⭐ {stars_str} stars | 💻 {lang}

{url}

#OpenSource #MachineLearning #AI #DataScience #GenAI #NLP #ComputerVision #BigData #IoT #Research"""
    return post.strip()


def post_to_linkedin(access_token: str, author_urn: str, commentary: str) -> str:
    """Create an organic text post on the personal profile."""
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

    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers=headers,
        json=payload,
        timeout=20,
    )

    if resp.status_code not in (200, 201):
        print("LinkedIn API error:", resp.status_code, resp.text)
        resp.raise_for_status()

    # Post ID is returned in the x-restli-id header
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

        text = create_post_text(repo)
        print("\n--- Post text ---")
        print(text)
        print("-----------------\n")

        post_to_linkedin(access_token, author_urn, text)
        print("Done.")

    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
