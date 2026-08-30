#!/usr/bin/env python3
"""
Once-a-week AI/ML PDF tutorial post for LinkedIn (personal profile).

Dense carousel pages: steps, code hacks, methods — no large empty gaps.
Header + footer every page. Footer: Day N of 100 | #LearnWithZuhaib
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
from reportlab.pdfgen import canvas

LINKEDIN_VERSION = "202607"
STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "tutorial_state.json"
MIN_DAYS_BETWEEN = 6
FORCE_AFTER_DAYS = 8
SERIES_TOTAL = 100
BRAND_TAG = "#LearnWithZuhaib"

NAVY = HexColor("#0B1B3A")
NAVY_SOFT = HexColor("#122447")
GOLD = HexColor("#E8B923")
BLUE = HexColor("#0A66C2")
SLATE = HexColor("#1E293B")
MUTED = HexColor("#64748B")
LIGHT_BG = HexColor("#F1F5F9")
CARD_BG = HexColor("#FFFFFF")
CODE_BG = HexColor("#0F172A")
CODE_FG = HexColor("#E2E8F0")
CODE_GREEN = HexColor("#4ADE80")
CODE_YELLOW = HexColor("#FDE047")
GREEN = HexColor("#16A34A")
ORANGE = HexColor("#EA580C")
PURPLE = HexColor("#7C3AED")

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
    prompt = f"""Create a dense how-to LinkedIn PDF carousel tutorial as JSON.

Topic: {topic}
Audience: AI/ML practitioners who want actionable methods and code hacks

Return ONLY valid JSON (no markdown fences) with this shape:
{{
  "title": "punchy how-to title under 55 chars",
  "subtitle": "what you will learn in one line",
  "hook": "scroll-stopping opening line",
  "slides": [
    {{
      "type": "steps|code|method|tips",
      "heading": "short heading under 36 chars",
      "steps": ["action 1", "action 2", "action 3", "action 4", "action 5"],
      "code": "2-5 line python snippet or empty string",
      "hack": "one practical pro tip",
      "why": "one line why this works",
      "extra": ["bonus tip A", "bonus tip B"]
    }}
  ],
  "takeaway": "memorable closing line",
  "hashtags": ["AI", "MachineLearning", "GenAI", "MLOps", "Python"]
}}

Rules:
- Exactly 6 slides
- Each slide MUST have 4-5 steps (fill the page)
- At least 2 slides with non-empty code
- extra: 2 short bonus tips per slide
- Topic-specific, no fluff, no markdown inside strings
- code uses \\n for newlines"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "You write dense how-to AI/ML carousels with code and steps. JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.65,
                "max_tokens": 3200,
            },
            timeout=50,
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
        "title": f"How to ship {topic[:40]}",
        "subtitle": "Steps, code hacks, and methods you can use today.",
        "hook": f"Skip the theory dump. Here is a practical how-to for {topic}.",
        "slides": [
            {
                "type": "steps",
                "heading": "Do this first",
                "steps": [
                    "Define the success metric before any model work",
                    "Collect a small labeled slice you can evaluate by hand",
                    "Run a dead-simple baseline and log the score",
                    "Write down known failure cases up front",
                    "Only then add complexity if the metric demands it",
                ],
                "code": "",
                "hack": "If you cannot measure it in 10 minutes, the metric is wrong.",
                "why": "Baselines stop you from celebrating noise.",
                "extra": ["Keep a living scoreboard in the repo README", "Revisit the metric when users change"],
            },
            {
                "type": "code",
                "heading": "Minimal eval loop",
                "steps": [
                    "Load predictions and labels from one file",
                    "Compute one primary metric only",
                    "Print failures, not only averages",
                    "Save a CSV of the worst 20 cases",
                    "Block merge if metric drops vs baseline",
                ],
                "code": "from sklearn.metrics import f1_score\ny_true, y_pred = labels, preds\nprint('f1', f1_score(y_true, y_pred, average='macro'))\n# also print 5 misclassified samples",
                "hack": "Always print 5 failure cases next to the metric.",
                "why": "Averages hide the bugs users will feel.",
                "extra": ["Track metric by slice (lang, length, class)", "Fail CI on silent metric regression"],
            },
            {
                "type": "method",
                "heading": "Production method",
                "steps": [
                    "Wrap inference behind a versioned API",
                    "Log input hash, model version, latency",
                    "Add a kill switch / rollback path",
                    "Alert on metric drift weekly",
                    "Document the on-call owner in the README",
                ],
                "code": "",
                "hack": "Ship behind a feature flag on day one.",
                "why": "Most ML incidents are deploy incidents.",
                "extra": ["Canary 5% traffic before full rollout", "Keep last-good model artifact pinned"],
            },
            {
                "type": "code",
                "heading": "HF quickstart hack",
                "steps": [
                    "Pin model revision for reproducibility",
                    "Use pipeline for the first prototype",
                    "Batch inputs when latency becomes an issue",
                    "Cache tokenizer outputs where possible",
                    "Move hot paths to a dedicated inference service",
                ],
                "code": "from transformers import pipeline\nclf = pipeline('text-classification', model='model-id', revision='main')\nprint(clf('example input')[0])",
                "hack": "Pin revision= so deploys are reproducible.",
                "why": "Silent model updates break prod quietly.",
                "extra": ["Store model id + revision in config", "Smoke-test the pipeline in CI"],
            },
            {
                "type": "tips",
                "heading": "Hacks that save time",
                "steps": [
                    "Cache embeddings; recompute only deltas",
                    "Prefer smaller models until quality plateaus",
                    "Write the eval set before the training script",
                    "Document known failure modes in the README",
                    "Time-box experiments to one clear question",
                ],
                "code": "",
                "hack": "One golden test case > ten vague unit tests.",
                "why": "Speed comes from fewer surprises, not more GPUs.",
                "extra": ["Delete unused notebooks monthly", "Name experiments by hypothesis, not date"],
            },
            {
                "type": "steps",
                "heading": "Ship checklist",
                "steps": [
                    "Metric + baseline recorded",
                    "Latency budget measured on real hardware",
                    "Logging and rollback ready",
                    "Owner named for the first week on-call",
                    "User-facing failure message defined",
                ],
                "code": "",
                "hack": "No owner = no production system.",
                "why": "Process is part of the model.",
                "extra": ["Screenshot the first successful prod call", "Schedule a 7-day post-ship review"],
            },
        ],
        "takeaway": "Methods beat motivation. Measure, baseline, ship small, iterate.",
        "hashtags": [
            "AI", "MachineLearning", "GenAI", "MLOps", "LLM",
            "Python", "HuggingFace", "DataScience",
        ],
    }


def _wrap_text(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list[str]:
    words = (text or "").replace("\t", " ").split()
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


def _draw_icon_chip(c: canvas.Canvas, x: float, y: float, label: str, color: HexColor) -> None:
    c.setFillColor(color)
    c.roundRect(x, y, 54, 18, 3, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + 27, y + 5, label)


def _draw_header_footer(
    c: canvas.Canvas,
    width: float,
    height: float,
    day_number: int,
    page_label: str,
) -> None:
    header_h = 28
    footer_h = 26

    c.setFillColor(NAVY)
    c.rect(0, height - header_h, width, header_h, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(18, height - 18, "AI / ML HOW-TO TUTORIAL")
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 18, height - 18, page_label)

    c.setFillColor(NAVY)
    c.rect(0, 0, width, footer_h, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(0, footer_h, width, footer_h)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(18, 9, f"Day {day_number} of {SERIES_TOTAL}")
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 9, "Steps · Code · Methods · Hacks")
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(width - 18, 9, BRAND_TAG)


def _draw_code_box(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    w: float,
    code: str,
    max_lines: int = 6,
) -> float:
    lines = [ln for ln in (code or "").replace("\\n", "\n").split("\n") if ln.strip()]
    lines = lines[:max_lines]
    if not lines:
        return y_top

    line_h = 12
    pad_top = 18
    pad_bot = 8
    box_h = pad_top + pad_bot + line_h * len(lines)
    y_bot = y_top - box_h

    c.setFillColor(CODE_BG)
    c.roundRect(x, y_bot, w, box_h, 5, fill=1, stroke=0)

    for i, col in enumerate([HexColor("#FF5F56"), HexColor("#FFBD2E"), HexColor("#27C93F")]):
        c.setFillColor(col)
        c.circle(x + 10 + i * 11, y_top - 8, 2.5, fill=1, stroke=0)

    c.setFillColor(HexColor("#64748B"))
    c.setFont("Helvetica", 7)
    c.drawRightString(x + w - 6, y_top - 10, "code")

    ty = y_top - 22
    for ln in lines:
        c.setFillColor(CODE_GREEN if ln.strip().startswith("#") else CODE_FG)
        if "print" in ln or "return" in ln:
            c.setFillColor(CODE_YELLOW)
        c.setFont("Courier", 8.5)
        while c.stringWidth(ln, "Courier", 8.5) > w - 16 and len(ln) > 3:
            ln = ln[:-1]
        c.drawString(x + 8, ty, ln)
        ty -= line_h

    return y_bot


def _draw_cover(c: canvas.Canvas, width: float, height: float, content: dict, day_number: int) -> None:
    c.setFillColor(NAVY)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, height - 5, width, 5, fill=1, stroke=0)
    c.setFillColor(NAVY_SOFT)
    c.rect(0, 0, 14, height, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(14, 0, 3, height, fill=1, stroke=0)

    badge = f"Day {day_number} of {SERIES_TOTAL}"
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    bw = c.stringWidth(badge, "Helvetica-Bold", 10) + 20
    c.roundRect(40, height - 55, bw, 20, 3, stroke=1, fill=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, height - 49, badge)

    _draw_icon_chip(c, 40, height - 88, "STEPS", BLUE)
    _draw_icon_chip(c, 100, height - 88, "CODE", GREEN)
    _draw_icon_chip(c, 160, height - 88, "HACKS", ORANGE)
    _draw_icon_chip(c, 220, height - 88, "METHOD", PURPLE)

    title = content.get("title") or "AI / ML How-To"
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 26)
    y = height - 130
    for line in _wrap_text(c, title, "Helvetica-Bold", 26, width - 90):
        c.drawString(40, y, line)
        y -= 30

    c.setStrokeColor(GOLD)
    c.setLineWidth(3)
    c.line(40, y - 2, 110, y - 2)

    sub = content.get("subtitle") or content.get("hook") or ""
    c.setFillColor(HexColor("#CBD5E1"))
    c.setFont("Helvetica", 12)
    y -= 22
    for line in _wrap_text(c, sub, "Helvetica", 12, width - 90):
        c.drawString(40, y, line)
        y -= 16

    # Fill lower half with "What you get" cards — kills empty navy space
    y -= 16
    cards = [
        ("01", "Steps", "Clear actions you can run today"),
        ("02", "Code", "Copy-paste snippets that work"),
        ("03", "Hacks", "Shortcuts from real production"),
        ("04", "Methods", "Repeatable shipping process"),
    ]
    card_w = (width - 40 - 40 - 18) / 2
    card_h = 52
    gap = 10
    for i, (num, label, desc) in enumerate(cards):
        col = i % 2
        row = i // 2
        cx = 40 + col * (card_w + gap)
        cy = y - row * (card_h + gap) - card_h
        c.setFillColor(NAVY_SOFT)
        c.roundRect(cx, cy, card_w, card_h, 6, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(cx + 12, cy + 30, num)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(cx + 40, cy + 30, label)
        c.setFillColor(HexColor("#94A3B8"))
        c.setFont("Helvetica", 9)
        c.drawString(cx + 12, cy + 12, desc)

    c.setFillColor(NAVY_SOFT)
    c.rect(0, 0, width, 36, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(0, 36, width, 36)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(22, 14, f"Day {day_number} of {SERIES_TOTAL}")
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 14, "Swipe → step-by-step · code · methods")
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(width - 22, 14, BRAND_TAG)


def _draw_content_page(
    c: canvas.Canvas,
    width: float,
    height: float,
    slide: dict,
    index: int,
    total: int,
    day_number: int,
) -> None:
    """Flow layout: pack everything from the top — no floating empty middle."""
    c.setFillColor(LIGHT_BG)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    _draw_header_footer(c, width, height, day_number, f"{index}/{total}")

    margin = 16
    top = height - 36
    bottom = 32
    usable_h = top - bottom - 6

    # White panel fills full usable area
    c.setFillColor(CARD_BG)
    c.roundRect(margin, bottom, width - 2 * margin, usable_h, 6, fill=1, stroke=0)

    stype = (slide.get("type") or "steps").lower()
    accent = {"code": GREEN, "method": PURPLE, "tips": ORANGE}.get(stype, BLUE)
    c.setFillColor(accent)
    c.rect(margin, bottom, 5, usable_h, fill=1, stroke=0)

    # Header row
    c.setFillColor(accent)
    c.circle(margin + 22, top - 20, 11, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(margin + 22, top - 23, str(index))

    heading = slide.get("heading") or f"Step {index}"
    c.setFillColor(SLATE)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin + 40, top - 24, heading[:50])
    _draw_icon_chip(c, width - margin - 62, top - 28, stype.upper()[:6], accent)

    y = top - 42
    inner_x = margin + 12
    inner_w = width - 2 * margin - 22

    steps = list(slide.get("steps") or slide.get("bullets") or [])[:5]
    extra = list(slide.get("extra") or [])[:2]
    code = (slide.get("code") or "").strip()
    hack = (slide.get("hack") or "").strip()
    why = (slide.get("why") or slide.get("insight") or "").strip()

    # Pre-measure approximate heights so we can size step rows to fill space
    n_steps = max(len(steps), 1)
    code_lines = [ln for ln in code.replace("\\n", "\n").split("\n") if ln.strip()][:5] if code else []
    code_h = (18 + 8 + 12 * len(code_lines)) if code_lines else 0
    hack_h = 34 if (hack or why) else 0
    extra_h = 22 if extra else 0
    gaps = 4 * (n_steps + 2)
    remaining = y - bottom - 10 - code_h - hack_h - extra_h - gaps
    row_h = max(22, min(36, remaining / n_steps))

    for n, step in enumerate(steps, start=1):
        c.setFillColor(HexColor("#F1F5F9"))
        c.roundRect(inner_x, y - row_h + 4, inner_w, row_h - 2, 3, fill=1, stroke=0)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(inner_x + 6, y - 12, f"{n}.")
        c.setFillColor(SLATE)
        c.setFont("Helvetica", 10)
        lines = _wrap_text(c, step, "Helvetica", 10, inner_w - 36)
        ty = y - 12
        for ln in lines[:2]:
            c.drawString(inner_x + 24, ty, ln)
            ty -= 11
        y -= row_h

    if code_lines:
        y -= 2
        y = _draw_code_box(c, inner_x, y, inner_w, code, max_lines=5) - 4

    if extra:
        c.setFillColor(HexColor("#ECFDF5"))
        eh = 18 + 12 * len(extra)
        c.roundRect(inner_x, y - eh, inner_w, eh, 3, fill=1, stroke=0)
        c.setFillColor(GREEN)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(inner_x + 8, y - 12, "BONUS")
        c.setFillColor(SLATE)
        c.setFont("Helvetica", 9)
        ty = y - 12
        for tip in extra:
            c.drawString(inner_x + 48, ty, f"• {tip}"[:90])
            ty -= 12
        y -= eh + 3

    # HACK / WHY directly under content (not pinned to bottom)
    if hack or why:
        c.setFillColor(HexColor("#EEF2FF"))
        strip_h = 32 if (hack and why) else 18
        c.roundRect(inner_x, y - strip_h - 2, inner_w, strip_h, 3, fill=1, stroke=0)
        ty = y - 12
        if hack:
            c.setFillColor(PURPLE)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(inner_x + 8, ty, "HACK")
            c.setFillColor(SLATE)
            c.setFont("Helvetica", 9)
            c.drawString(inner_x + 40, ty, hack[:95])
            ty -= 13
        if why:
            c.setFillColor(PURPLE)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(inner_x + 8, ty, "WHY")
            c.setFillColor(SLATE)
            c.setFont("Helvetica", 9)
            c.drawString(inner_x + 40, ty, why[:95])


def _draw_closing(c: canvas.Canvas, width: float, height: float, content: dict, day_number: int) -> None:
    c.setFillColor(NAVY)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, height - 5, width, 5, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, 0, 6, height, fill=1, stroke=0)

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(32, height - 50, "KEY TAKEAWAY")

    takeaway = content.get("takeaway") or "Methods beat motivation."
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 16)
    y = height - 80
    for line in _wrap_text(c, takeaway, "Helvetica-Bold", 16, width - 70):
        c.drawString(32, y, line)
        y -= 20

    y -= 8
    checks = [
        "Measure before you model",
        "Baseline before you scale",
        "Log before you celebrate",
        "Rollback before you ship",
        "Name an owner before go-live",
        "Review after 7 days in prod",
    ]
    # 2-column checklist fills space
    col_w = (width - 64 - 12) / 2
    for i, item in enumerate(checks):
        col = i % 2
        row = i // 2
        cx = 32 + col * (col_w + 12)
        cy = y - row * 36 - 28
        c.setFillColor(NAVY_SOFT)
        c.roundRect(cx, cy, col_w, 30, 4, fill=1, stroke=0)
        c.setFillColor(GREEN)
        c.circle(cx + 14, cy + 15, 7, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(cx + 14, cy + 12, "✓")
        c.setFillColor(HexColor("#E2E8F0"))
        c.setFont("Helvetica", 10)
        c.drawString(cx + 28, cy + 11, item)

    tags = content.get("hashtags") or []
    tag_str = "  ".join(f"#{t.lstrip('#')}" for t in tags[:8])
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 9)
    c.drawString(32, 52, tag_str[:100])

    c.setFillColor(NAVY_SOFT)
    c.rect(0, 0, width, 34, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(0, 34, width, 34)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(22, 13, f"Day {day_number} of {SERIES_TOTAL}")
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 13, "Save · Share · Ship")
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(width - 22, 13, BRAND_TAG)


def build_pdf(content: dict, day_number: int) -> bytes:
    buffer = BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    slides = list(content.get("slides") or [])[:8]
    total = len(slides)

    _draw_cover(c, width, height, content, day_number)
    c.showPage()

    for i, slide in enumerate(slides, start=1):
        _draw_content_page(c, width, height, slide, i, total, day_number)
        c.showPage()

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
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/pdf"},
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
        if st.status_code == 200 and st.json().get("status") == "AVAILABLE":
            print("Document status: AVAILABLE")
            return document_urn
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
        "content": {"media": {"id": document_urn, "title": title[:200]}},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    resp = requests.post(
        "https://api.linkedin.com/rest/posts", headers=headers, json=payload, timeout=30
    )
    if resp.status_code not in (200, 201):
        print("LinkedIn document post error:", resp.status_code, resp.text)
        resp.raise_for_status()
    post_id = resp.headers.get("x-restli-id", "unknown")
    print(f"Tutorial posted! ID: {post_id}")
    return post_id


def build_caption(content: dict, day_number: int) -> str:
    tags = " ".join(f"#{t.lstrip('#')}" for t in (content.get("hashtags") or [])[:8])
    return f"""{content.get('hook') or content['title']}

Day {day_number} of {SERIES_TOTAL} — step-by-step methods, code hacks, and practical how-tos.

{content['title']}

Swipe through and save.

{tags} {BRAND_TAG}""".strip()


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
        day_number = 1

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
