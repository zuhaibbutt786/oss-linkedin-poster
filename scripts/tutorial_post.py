#!/usr/bin/env python3
"""
Once-a-week AI/ML PDF tutorial post for LinkedIn (personal profile).

- Runs daily via GitHub Actions; posts only ~once per week on a random day
- Topics: GenAI, classical ML, robotics, IoT, LLM in production, MLOps,
  Hugging Face, speech, vision, NLP
- Generates a short multi-page PDF and publishes it as a LinkedIn document post
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

LINKEDIN_VERSION = "202607"
STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "tutorial_state.json"
MIN_DAYS_BETWEEN = 6
FORCE_AFTER_DAYS = 8

TOPICS = [
    "Generative AI fundamentals",
    "Classical machine learning algorithms",
    "LLMs in production",
    "MLOps best practices",
    "Hugging Face models and pipelines",
    "Speech and audio AI models",
    "Computer vision for practitioners",
    "NLP techniques that still matter",
    "Robotics and embodied AI basics",
    "IoT + edge AI",
    "RAG systems explained simply",
    "Fine-tuning vs prompt engineering",
    "Evaluating LLM quality",
    "Vector databases for AI apps",
    "Safety and guardrails for GenAI",
    "Deploying models with FastAPI",
    "Feature stores and training pipelines",
    "Multimodal AI (vision + language)",
    "Time series forecasting with ML",
    "Reinforcement learning intuition",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"last_posted_at": None, "posted_topics": []}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_posted_at": None, "posted_topics": []}


def save_state(state: dict, topic: str) -> None:
    topics = list(state.get("posted_topics") or [])
    topics.append(topic)
    state = {
        "last_posted_at": utcnow().isoformat(),
        "posted_topics": topics[-40:],
        "last_topic": topic,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Saved tutorial state for topic: {topic}")


def should_post_today(state: dict, force: bool) -> bool:
    if force:
        print("FORCE_TUTORIAL=1 — posting now")
        return True
    last = state.get("last_posted_at")
    if not last:
        # First run: ~15% chance so it doesn't always fire day 1
        roll = random.random() < 0.15
        print(f"No previous tutorial. Random roll: {'post' if roll else 'skip'}")
        return roll
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except Exception:
        return True
    days = (utcnow() - last_dt).total_seconds() / 86400
    print(f"Days since last tutorial: {days:.1f}")
    if days < MIN_DAYS_BETWEEN:
        print("Too soon — skip")
        return False
    if days >= FORCE_AFTER_DAYS:
        print("Past force window — post")
        return True
    # Random day in the 6–8 day window
    chance = (days - MIN_DAYS_BETWEEN + 1) / (FORCE_AFTER_DAYS - MIN_DAYS_BETWEEN + 1)
    roll = random.random() < chance
    print(f"Random weekly window chance={chance:.2f} → {'post' if roll else 'skip'}")
    return roll


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


def pick_topic(state: dict) -> str:
    used = set(state.get("posted_topics") or [])
    pool = [t for t in TOPICS if t not in used] or TOPICS
    return random.choice(pool)


def generate_tutorial_with_groq(topic: str) -> dict | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    prompt = f"""Create a short professional tech tutorial as JSON for LinkedIn PDF carousel.

Topic: {topic}
Audience: AI/ML engineers and practitioners

Return ONLY valid JSON (no markdown) with this shape:
{{
  "title": "short catchy title under 70 chars",
  "hook": "one sentence LinkedIn hook",
  "slides": [
    {{"heading": "slide title", "bullets": ["point 1", "point 2", "point 3"]}},
    ...
  ],
  "takeaway": "one closing takeaway line",
  "hashtags": ["AI", "MachineLearning", ...]
}}

Rules:
- Exactly 6 to 8 slides
- 3 short bullets per slide (max 18 words each)
- Practical, accurate, no hype
- No code blocks inside JSON strings
- Focus on actionable knowledge"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "You write concise AI/ML tutorials. Reply with JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 1800,
            },
            timeout=45,
        )
        if resp.status_code != 200:
            print("Groq error:", resp.status_code, resp.text[:300])
            return None
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = json.loads(raw)
        if not data.get("slides") or not data.get("title"):
            return None
        print("Generated tutorial content with Groq")
        return data
    except Exception as e:
        print(f"Groq tutorial generation failed: {e}")
        return None


def fallback_tutorial(topic: str) -> dict:
    return {
        "title": topic[:70],
        "hook": f"A practical mini-guide on {topic} for AI builders.",
        "slides": [
            {
                "heading": "Why this matters",
                "bullets": [
                    f"{topic} shows up in real production systems",
                    "Clear mental models beat buzzwords",
                    "Small improvements compound in ML systems",
                ],
            },
            {
                "heading": "Core idea",
                "bullets": [
                    "Start with the problem, not the model",
                    "Measure quality before scaling complexity",
                    "Prefer simple baselines you can debug",
                ],
            },
            {
                "heading": "Practical steps",
                "bullets": [
                    "Define success metrics up front",
                    "Build a thin end-to-end pipeline first",
                    "Iterate with evaluation, not vibes",
                ],
            },
            {
                "heading": "Common pitfalls",
                "bullets": [
                    "Overfitting to demo data",
                    "Ignoring latency and cost",
                    "Skipping monitoring after deploy",
                ],
            },
            {
                "heading": "Tools & ecosystem",
                "bullets": [
                    "Hugging Face for models and datasets",
                    "Strong eval sets beat fancy architectures",
                    "Automate training and deployment where possible",
                ],
            },
            {
                "heading": "Production checklist",
                "bullets": [
                    "Version data, code, and models",
                    "Log inputs/outputs for debugging",
                    "Plan rollback before you ship",
                ],
            },
        ],
        "takeaway": "Ship small, measure honestly, and improve the bottleneck you can prove.",
        "hashtags": [
            "AI",
            "MachineLearning",
            "GenAI",
            "MLOps",
            "LLM",
            "DataScience",
            "HuggingFace",
            "NLP",
            "ComputerVision",
        ],
    }


def build_pdf(content: dict) -> bytes:
    """Create a landscape multi-page PDF tutorial."""
    buffer = BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TTitle",
        parent=styles["Title"],
        fontSize=26,
        textColor=HexColor("#0f172a"),
        spaceAfter=12,
        leading=30,
    )
    h_style = ParagraphStyle(
        "THead",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=HexColor("#0a66c2"),
        spaceAfter=14,
        leading=24,
    )
    body_style = ParagraphStyle(
        "TBody",
        parent=styles["Normal"],
        fontSize=14,
        textColor=HexColor("#1e293b"),
        leading=20,
        spaceAfter=8,
    )
    footer_style = ParagraphStyle(
        "TFoot",
        parent=styles["Normal"],
        fontSize=10,
        textColor=HexColor("#64748b"),
    )

    story = []

    # Cover
    story.append(Spacer(1, 1.2 * inch))
    story.append(Paragraph("AI / ML Mini Tutorial", ParagraphStyle(
        "Badge", parent=body_style, fontSize=12, textColor=HexColor("#0a66c2")
    )))
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph(content["title"], title_style))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(content.get("hook") or "", body_style))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("Swipe through for practical takeaways →", footer_style))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("For builders in AI, ML, GenAI, MLOps & applied research", footer_style))

    from reportlab.platypus import PageBreak

    for i, slide in enumerate(content.get("slides") or [], start=1):
        story.append(PageBreak())
        story.append(Paragraph(f"{i}. {slide.get('heading', 'Key point')}", h_style))
        story.append(Spacer(1, 0.15 * inch))
        for b in slide.get("bullets") or []:
            story.append(Paragraph(f"• {b}", body_style))
            story.append(Spacer(1, 0.08 * inch))

    # Closing
    story.append(PageBreak())
    story.append(Paragraph("Key takeaway", h_style))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(content.get("takeaway") or "Keep learning and ship thoughtfully.", body_style))
    story.append(Spacer(1, 0.4 * inch))
    tags = "  ".join(f"#{t.lstrip('#')}" for t in (content.get("hashtags") or [])[:8])
    story.append(Paragraph(tags, footer_style))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("Save this post if it was useful.", footer_style))

    doc.build(story)
    return buffer.getvalue()


def upload_document(access_token: str, author_urn: str, pdf_bytes: bytes) -> str:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": LINKEDIN_VERSION,
    }
    init = requests.post(
        "https://api.linkedin.com/rest/documents?action=initializeUpload",
        headers=headers,
        json={"initializeUploadRequest": {"owner": author_urn}},
        timeout=20,
    )
    if init.status_code not in (200, 201):
        raise RuntimeError(f"Document init failed: {init.status_code} {init.text[:300]}")
    value = init.json().get("value", {})
    upload_url = value.get("uploadUrl")
    document_urn = value.get("document")
    if not upload_url or not document_urn:
        raise RuntimeError("Missing uploadUrl or document URN")

    up = requests.put(
        upload_url,
        data=pdf_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/pdf",
        },
        timeout=90,
    )
    if up.status_code not in (200, 201):
        raise RuntimeError(f"Document upload failed: {up.status_code} {up.text[:200]}")

    # Wait until AVAILABLE
    doc_id = document_urn.split(":")[-1]
    encoded = requests.utils.quote(document_urn, safe="")
    for attempt in range(12):
        time.sleep(2)
        st = requests.get(
            f"https://api.linkedin.com/rest/documents/{encoded}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Linkedin-Version": LINKEDIN_VERSION,
            },
            timeout=15,
        )
        if st.status_code == 200:
            status = st.json().get("status")
            print(f"Document status: {status}")
            if status == "AVAILABLE":
                return document_urn
        else:
            print(f"Status check {attempt}: {st.status_code}")
    print("Document not confirmed AVAILABLE; posting anyway")
    return document_urn


def post_document(
    access_token: str,
    author_urn: str,
    commentary: str,
    document_urn: str,
    title: str,
) -> str:
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
        "content": {
            "media": {
                "id": document_urn,
                "title": title[:200],
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers=headers,
        json=payload,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        print("LinkedIn document post error:", resp.status_code, resp.text)
        resp.raise_for_status()
    post_id = resp.headers.get("x-restli-id", "unknown")
    print(f"Tutorial posted! ID: {post_id}")
    return post_id


def build_caption(content: dict) -> str:
    tags = " ".join(f"#{t.lstrip('#')}" for t in (content.get("hashtags") or [])[:10])
    return f"""{content.get('hook') or content['title']}

A short practical tutorial you can swipe through.

Topic: {content['title']}

Save it for later and share with someone building in AI/ML.

{tags}""".strip()


def main() -> None:
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not access_token:
        print("ERROR: LINKEDIN_ACCESS_TOKEN is not set")
        sys.exit(1)

    force = os.getenv("FORCE_TUTORIAL", "").strip() in ("1", "true", "yes")
    state = load_state()

    if not should_post_today(state, force):
        print("No tutorial today.")
        sys.exit(0)

    topic = pick_topic(state)
    print(f"Topic: {topic}")
    content = generate_tutorial_with_groq(topic) or fallback_tutorial(topic)

    print("Building PDF...")
    pdf_bytes = build_pdf(content)
    print(f"PDF size: {len(pdf_bytes)} bytes")

    print("Getting person URN...")
    author_urn = get_person_urn(access_token)
    print(f"Author: {author_urn}")

    print("Uploading document to LinkedIn...")
    document_urn = upload_document(access_token, author_urn, pdf_bytes)
    print(f"Document URN: {document_urn}")

    caption = build_caption(content)
    print("\n--- Caption ---")
    print(caption)
    print("---------------\n")

    post_document(access_token, author_urn, caption, document_urn, content["title"])
    save_state(state, topic)
    print("Done.")


if __name__ == "__main__":
    main()
