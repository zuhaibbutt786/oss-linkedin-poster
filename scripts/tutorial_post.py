#!/usr/bin/env python3
"""
Once-a-week AI/ML PDF tutorial post for LinkedIn (personal profile).

- Runs daily via GitHub Actions; posts only ~once per week on a random day
- Topics: GenAI, classical ML, robotics, IoT, LLM in production, MLOps,
  Hugging Face, speech, vision, NLP
- Generates a short multi-page PDF (header + footer + Day N of 100) and posts it
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
from reportlab.lib.colors import HexColor, Color, white, black
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

LINKEDIN_VERSION = "202607"
STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "tutorial_state.json"
MIN_DAYS_BETWEEN = 6
FORCE_AFTER_DAYS = 8
SERIES_TOTAL = 100

# Brand palette (LinkedIn-friendly, high contrast)
NAVY = HexColor("#0B1B3A")
NAVY_SOFT = HexColor("#122447")
GOLD = HexColor("#E8B923")
BLUE = HexColor("#0A66C2")
SLATE = HexColor("#1E293B")
MUTED = HexColor("#64748B")
LIGHT_BG = HexColor("#F8FAFC")
CARD_BG = HexColor("#FFFFFF")
ACCENT_LINE = HexColor("#0A66C2")

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
        return {"last_posted_at": None, "posted_topics": [], "day_number": 0}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        data.setdefault("day_number", 0)
        return data
    except Exception:
        return {"last_posted_at": None, "posted_topics": [], "day_number": 0}


def save_state(state: dict, topic: str, day_number: int) -> None:
    topics = list(state.get("posted_topics") or [])
    topics.append(topic)
    out = {
        "last_posted_at": utcnow().isoformat(),
        "posted_topics": topics[-40:],
        "last_topic": topic,
        "day_number": day_number,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Saved tutorial state: day {day_number}, topic={topic}")


def should_post_today(state: dict, force: bool) -> bool:
    if force:
        print("FORCE_TUTORIAL=1 — posting now")
        return True
    last = state.get("last_posted_at")
    if not last:
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
    prompt = f"""Create a short professional tech tutorial as JSON for a LinkedIn PDF carousel.

Topic: {topic}
Audience: AI/ML engineers and practitioners

Return ONLY valid JSON (no markdown) with this shape:
{{
  "title": "short punchy title under 60 chars",
  "subtitle": "one sharp supporting line under 90 chars",
  "hook": "scroll-stopping LinkedIn opening line",
  "slides": [
    {{"heading": "slide title under 40 chars", "bullets": ["point 1", "point 2", "point 3"], "insight": "one italic insight line"}},
    ...
  ],
  "takeaway": "memorable closing line",
  "hashtags": ["AI", "MachineLearning", "GenAI", "MLOps"]
}}

Rules:
- Exactly 6 content slides (not counting cover/closing)
- 3 bullets per slide, max 16 words each, specific to the topic (not generic advice)
- insight line is optional but preferred
- Practical, accurate, zero fluff
- No markdown inside strings"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You write concise AI/ML carousel tutorials. JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=45,
        )
        if resp.status_code != 200:
            print("Groq error:", resp.status_code, resp.text[:300])
            return None
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
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
        "title": topic[:60],
        "subtitle": f"What practitioners actually need to know about {topic}.",
        "hook": f"Most people overcomplicate {topic}. Here is the practical version.",
        "slides": [
            {
                "heading": "Why it matters",
                "bullets": [
                    f"{topic} shows up in real production systems",
                    "Clear mental models beat buzzwords every time",
                    "Small reliable improvements compound fast",
                ],
                "insight": "Signal over noise is the real skill.",
            },
            {
                "heading": "Core idea",
                "bullets": [
                    "Start with the problem, not the model",
                    "Measure quality before scaling complexity",
                    "Prefer simple baselines you can debug",
                ],
                "insight": "If you cannot explain the baseline, do not ship the complex version.",
            },
            {
                "heading": "Practical steps",
                "bullets": [
                    "Define success metrics before writing code",
                    "Build a thin end-to-end pipeline first",
                    "Iterate with evaluation, not intuition",
                ],
                "insight": "A weak metric will quietly destroy a strong model.",
            },
            {
                "heading": "Common pitfalls",
                "bullets": [
                    "Overfitting to demo or notebook data",
                    "Ignoring latency, cost, and failure modes",
                    "Skipping monitoring after the first deploy",
                ],
                "insight": "Most ML failures are process failures, not model failures.",
            },
            {
                "heading": "Tools that help",
                "bullets": [
                    "Hugging Face for models, datasets, and eval",
                    "Strong offline eval sets beat fancy architectures",
                    "Automate training and deployment early",
                ],
                "insight": "Tooling should reduce friction, not hide errors.",
            },
            {
                "heading": "Production checklist",
                "bullets": [
                    "Version data, code, prompts, and models",
                    "Log inputs and outputs for debugging",
                    "Plan rollback before you ship",
                ],
                "insight": "Ship small. Measure honestly. Improve the proven bottleneck.",
            },
        ],
        "takeaway": "Ship small, measure honestly, and improve the bottleneck you can prove.",
        "hashtags": [
            "AI", "MachineLearning", "GenAI", "MLOps", "LLM",
            "DataScience", "HuggingFace", "NLP", "ComputerVision",
        ],
    }


def _wrap_text(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if c.stringWidth(trial, font, size) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_header_footer(
    c: canvas.Canvas,
    width: float,
    height: float,
    day_number: int,
    page_label: str,
    dark: bool = False,
) -> None:
    """Header + footer on every page."""
    header_h = 36
    footer_h = 34

    if dark:
        c.setFillColor(NAVY)
        c.rect(0, height - header_h, width, header_h, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(28, height - 22, "AI / ML MINI TUTORIAL")
        c.setFillColor(HexColor("#94A3B8"))
        c.setFont("Helvetica", 9)
        c.drawRightString(width - 28, height - 22, page_label)

        c.setFillColor(NAVY)
        c.rect(0, 0, width, footer_h, fill=1, stroke=0)
        c.setStrokeColor(GOLD)
        c.setLineWidth(2)
        c.line(0, footer_h, width, footer_h)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(28, 12, f"Day {day_number} of {SERIES_TOTAL}")
        c.setFillColor(HexColor("#94A3B8"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(width / 2, 12, "AI · ML · GenAI · MLOps · LLM")
        c.setFillColor(HexColor("#CBD5E1"))
        c.setFont("Helvetica", 8)
        c.drawRightString(width - 28, 12, "#LearnInPublic")
    else:
        c.setFillColor(LIGHT_BG)
        c.rect(0, height - header_h, width, header_h, fill=1, stroke=0)
        c.setStrokeColor(ACCENT_LINE)
        c.setLineWidth(3)
        c.line(0, height - header_h, width, height - header_h)
        c.setFillColor(BLUE)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(28, height - 22, "AI / ML MINI TUTORIAL")
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawRightString(width - 28, height - 22, page_label)

        c.setFillColor(NAVY)
        c.rect(0, 0, width, footer_h, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(28, 12, f"Day {day_number} of {SERIES_TOTAL}")
        c.setFillColor(HexColor("#94A3B8"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(width / 2, 12, "AI · ML · GenAI · MLOps · LLM")
        c.setFillColor(HexColor("#CBD5E1"))
        c.setFont("Helvetica", 8)
        c.drawRightString(width - 28, 12, "#LearnInPublic")


def _draw_cover(c: canvas.Canvas, width: float, height: float, content: dict, day_number: int) -> None:
    c.setFillColor(NAVY)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Gold accent bar top
    c.setFillColor(GOLD)
    c.rect(0, height - 8, width, 8, fill=1, stroke=0)

    # Day badge
    badge = f"Day {day_number} of {SERIES_TOTAL}"
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    bw = c.stringWidth(badge, "Helvetica-Bold", 11) + 28
    bx = (width - bw) / 2
    by = height - 90
    c.roundRect(bx, by, bw, 26, 4, stroke=1, fill=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, by + 8, badge)

    # Title
    title = content.get("title") or "AI / ML Tutorial"
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 32)
    y = height - 170
    for line in _wrap_text(c, title, "Helvetica-Bold", 32, width - 120):
        c.drawCentredString(width / 2, y, line)
        y -= 38

    # Gold underline
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(width / 2 - 60, y - 8, width / 2 + 60, y - 8)

    # Subtitle / hook
    sub = content.get("subtitle") or content.get("hook") or ""
    c.setFillColor(HexColor("#CBD5E1"))
    c.setFont("Helvetica", 14)
    y -= 40
    for line in _wrap_text(c, sub, "Helvetica", 14, width - 140):
        c.drawCentredString(width / 2, y, line)
        y -= 20

    # Bottom brand strip
    c.setFillColor(NAVY_SOFT)
    c.rect(0, 0, width, 48, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(0, 48, width, 48)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(28, 20, f"Day {day_number} of {SERIES_TOTAL}")
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, 20, "Swipe for practical takeaways  →")
    c.setFillColor(HexColor("#CBD5E1"))
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 28, 20, "#LearnInPublic")


def _draw_content_page(
    c: canvas.Canvas,
    width: float,
    height: float,
    slide: dict,
    index: int,
    total: int,
    day_number: int,
) -> None:
    # Background
    c.setFillColor(LIGHT_BG)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    _draw_header_footer(
        c, width, height, day_number,
        page_label=f"{index} / {total}",
        dark=False,
    )

    margin_x = 40
    top = height - 70
    bottom = 55

    # Number circle
    c.setFillColor(BLUE)
    c.circle(margin_x + 18, top - 18, 18, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(margin_x + 18, top - 23, str(index))

    # Heading
    heading = slide.get("heading") or f"Point {index}"
    c.setFillColor(SLATE)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin_x + 48, top - 26, heading[:55])

    # Accent line under heading
    c.setStrokeColor(GOLD)
    c.setLineWidth(3)
    c.line(margin_x, top - 42, margin_x + 80, top - 42)

    # Content card
    card_top = top - 60
    card_bottom = bottom + 10
    card_h = card_top - card_bottom
    c.setFillColor(CARD_BG)
    c.setStrokeColor(HexColor("#E2E8F0"))
    c.setLineWidth(1)
    c.roundRect(margin_x, card_bottom, width - 2 * margin_x, card_h, 10, fill=1, stroke=1)

    bullets = slide.get("bullets") or []
    y = card_top - 36
    for b in bullets[:5]:
        # Bullet dot
        c.setFillColor(BLUE)
        c.circle(margin_x + 28, y + 4, 4, fill=1, stroke=0)
        c.setFillColor(SLATE)
        c.setFont("Helvetica", 13)
        max_w = width - 2 * margin_x - 60
        lines = _wrap_text(c, b, "Helvetica", 13, max_w)
        for j, line in enumerate(lines):
            c.drawString(margin_x + 42, y - j * 17, line)
        y -= max(28, 17 * len(lines) + 10)

    insight = (slide.get("insight") or "").strip()
    if insight and y > card_bottom + 40:
        c.setStrokeColor(HexColor("#E2E8F0"))
        c.setLineWidth(1)
        c.line(margin_x + 24, y + 8, width - margin_x - 24, y + 8)
        c.setFillColor(BLUE)
        c.setFont("Helvetica-Oblique", 11)
        for line in _wrap_text(c, insight, "Helvetica-Oblique", 11, width - 2 * margin_x - 50):
            c.drawString(margin_x + 28, y - 12, line)
            y -= 16


def _draw_closing(c: canvas.Canvas, width: float, height: float, content: dict, day_number: int) -> None:
    c.setFillColor(NAVY)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, height - 8, width, 8, fill=1, stroke=0)

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, height - 90, "KEY TAKEAWAY")

    takeaway = content.get("takeaway") or "Ship small. Measure honestly."
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 20)
    y = height - 150
    for line in _wrap_text(c, takeaway, "Helvetica-Bold", 20, width - 120):
        c.drawCentredString(width / 2, y, line)
        y -= 28

    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(width / 2 - 40, y - 10, width / 2 + 40, y - 10)

    tags = content.get("hashtags") or []
    tag_str = "  ".join(f"#{t.lstrip('#')}" for t in tags[:8])
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 11)
    y -= 50
    for line in _wrap_text(c, tag_str, "Helvetica", 11, width - 100):
        c.drawCentredString(width / 2, y, line)
        y -= 16

    c.setFillColor(HexColor("#CBD5E1"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, 100, "Save this if it was useful.")

    # Footer bar
    c.setFillColor(NAVY_SOFT)
    c.rect(0, 0, width, 48, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(0, 48, width, 48)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(28, 20, f"Day {day_number} of {SERIES_TOTAL}")
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, 20, "AI · ML · GenAI · MLOps · LLM")
    c.setFillColor(HexColor("#CBD5E1"))
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 28, 20, "#LearnInPublic")


def build_pdf(content: dict, day_number: int) -> bytes:
    """Professional LinkedIn-style carousel PDF with header/footer on every page."""
    buffer = BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    slides = list(content.get("slides") or [])[:8]
    total_content = len(slides)

    # Cover
    _draw_cover(c, width, height, content, day_number)
    c.showPage()

    # Content slides
    for i, slide in enumerate(slides, start=1):
        _draw_content_page(c, width, height, slide, i, total_content, day_number)
        c.showPage()

    # Closing
    _draw_closing(c, width, height, content, day_number)
    c.showPage()

    c.save()
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


def build_caption(content: dict, day_number: int) -> str:
    tags = " ".join(f"#{t.lstrip('#')}" for t in (content.get("hashtags") or [])[:10])
    return f"""{content.get('hook') or content['title']}

Day {day_number} of {SERIES_TOTAL} — a short practical AI/ML tutorial you can swipe through.

{content['title']}

Save it for later.

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

    day_number = int(state.get("day_number") or 0) + 1
    if day_number > SERIES_TOTAL:
        day_number = 1  # cycle series

    topic = pick_topic(state)
    print(f"Day {day_number}/{SERIES_TOTAL} | Topic: {topic}")
    content = generate_tutorial_with_groq(topic) or fallback_tutorial(topic)

    print("Building PDF...")
    pdf_bytes = build_pdf(content, day_number)
    print(f"PDF size: {len(pdf_bytes)} bytes")

    print("Getting person URN...")
    author_urn = get_person_urn(access_token)
    print(f"Author: {author_urn}")

    print("Uploading document to LinkedIn...")
    document_urn = upload_document(access_token, author_urn, pdf_bytes)
    print(f"Document URN: {document_urn}")

    caption = build_caption(content, day_number)
    print("\n--- Caption ---")
    print(caption)
    print("---------------\n")

    post_document(access_token, author_urn, caption, document_urn, content["title"])
    save_state(state, topic, day_number)
    print("Done.")


if __name__ == "__main__":
    main()
