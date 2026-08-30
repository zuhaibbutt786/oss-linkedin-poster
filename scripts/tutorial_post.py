#!/usr/bin/env python3
"""
Once-a-week AI/ML PDF tutorial post for LinkedIn (personal profile).

Portrait A4, large readable text, dense packing (no empty gaps).
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
from reportlab.lib.pagesizes import A4
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
    "KV cache and why your LLM is slow",
    "Tokenization tricks models hide from you",
    "Quantization INT8 INT4 without breaking quality",
    "LoRA vs QLoRA vs full fine-tune tradeoffs",
    "RAG chunking strategies that actually retrieve",
    "Embedding model choice nobody explains",
    "Attention masks and causal bugs in code",
    "FlashAttention and memory bandwidth reality",
    "vLLM continuous batching internals",
    "Speculative decoding for faster inference",
    "Prompt caching and prefix reuse in APIs",
    "Tool calling JSON schema failure modes",
    "Structured output with constrained decoding",
    "Eval harnesses beyond BLEU and accuracy",
    "Data leakage in LLM benchmarks",
    "Synthetic data pipelines that do not collapse",
    "Gradient checkpointing and VRAM math",
    "Mixed precision fp16 bf16 loss spikes",
    "Distributed training NCCL gotchas",
    "ONNX TensorRT export silent accuracy drops",
    "Vision transformer patch size hacks",
    "CLIP style contrastive training tricks",
    "Whisper decoding temperature and timestamps",
    "Vector DB HNSW vs IVF when to switch",
    "Hybrid search BM25 plus dense rerank",
    "Agent memory short-term vs long-term design",
    "Guardrails that fail under adversarial prompts",
    "Streaming tokens and partial JSON parsing",
    "Cost control tokens per request budgets",
    "Reproducible seeds across CUDA and dataloaders",
]

SYSTEM_PROMPT = """You are a senior AI engineer writing for builders who already know the basics.
You never write textbook fluff. You write coding-side secrets, sharp methods, and copy-pasteable Python.
You prefer: real APIs (transformers, torch, vllm, fastapi, numpy), real failure modes, real metrics.
You avoid: vague motivation, corporate buzzwords, "leverage AI", empty frameworks.
Reply with valid JSON only. No markdown fences."""


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


def build_content_prompt(topic: str) -> str:
    return f"""Write a LinkedIn PDF carousel every serious AI/ML coder should want to save.

TOPIC: {topic}

Goal: coding-side insights most people miss — not intro theory.

Return ONLY this JSON shape (no markdown):
{{
  "title": "curiosity title under 50 chars",
  "subtitle": "one concrete promise",
  "hook": "1 line that stops an AI engineer",
  "slides": [
    {{
      "type": "steps|code|method|tips",
      "heading": "sharp heading under 32 chars",
      "steps": ["action 1", "action 2", "action 3", "action 4"],
      "code": "2-4 lines real Python or empty string",
      "hack": "one non-obvious pro tip",
      "why": "one line causal why",
      "extra": ["bonus tip A", "bonus tip B"]
    }}
  ],
  "takeaway": "one memorable engineering rule",
  "hashtags": ["AI", "MachineLearning", "LLM", "Python", "MLOps"]
}}

HARD RULES:
1. Exactly 6 slides. Mix: at least 2 code, 2 steps, 1 method, 1 tips.
2. Each slide has exactly 4 steps. Specific to {topic} (KV cache, logits, tokenizer, CUDA, etc.).
3. At least 3 slides with real Python code (torch, transformers, numpy…). Use \\n for newlines.
4. Ban: leverage, delve, landscape, game-changer, empower, seamless, cutting-edge.
5. Insider energy. JSON only."""


def generate_tutorial_with_groq(topic: str) -> dict | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_content_prompt(topic)},
                ],
                "temperature": 0.75,
                "max_tokens": 3200,
            },
            timeout=55,
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
        data["hashtags"] = [t.lstrip("#") for t in (data.get("hashtags") or [])][:10]
        print("Generated tutorial content with Groq")
        return data
    except Exception as e:
        print(f"Groq tutorial generation failed: {e}")
        return None


def fallback_tutorial(topic: str) -> dict:
    return {
        "title": f"What seniors know about {topic[:32]}",
        "subtitle": "Coding-side details intro blogs skip.",
        "hook": f"Most tutorials on {topic} skip what breaks in production.",
        "slides": [
            {
                "type": "steps",
                "heading": "Measure before you tune",
                "steps": [
                    "Log tokens/sec and peak VRAM on a fixed batch",
                    "Record p50 and p95 latency — not only the mean",
                    "Freeze a 50-example golden set before any change",
                    "Refuse to ship if you cannot reproduce the metric",
                ],
                "code": "import time, torch\nt0=time.time(); out=model.generate(**batch)\nprint('tok/s', n/(time.time()-t0))\nprint('vram_gb', torch.cuda.max_memory_allocated()/1e9)",
                "hack": "Optimize the slow percentile, not the happy-path mean.",
                "why": "Users feel p95; dashboards often show the mean.",
                "extra": ["Pin CUDA versions in a lockfile", "Save generate() kwargs with the metric"],
            },
            {
                "type": "code",
                "heading": "See the logits",
                "steps": [
                    "Take last-step logits before sampling",
                    "Apply temperature then top_p in that order",
                    "Print top-10 tokens when output looks weird",
                    "Compare greedy vs sampled on the same prompt",
                ],
                "code": "logits = outputs.logits[0, -1]\nprobs = torch.softmax(logits/temp, dim=-1)\ntopv, topi = torch.topk(probs, 10)\nprint(list(zip(tokenizer.convert_ids_to_tokens(topi), topv.tolist())))",
                "hack": "When quality dies, inspect tokens — not only the string.",
                "why": "String bugs often start as mass on the wrong token ids.",
                "extra": ["Log eos probability on long runs", "Unit-test sampling alone"],
            },
            {
                "type": "method",
                "heading": "Ship a thin path first",
                "steps": [
                    "One /infer endpoint with a version header",
                    "Reject over-limit inputs early",
                    "Stream tokens; parse partial JSON carefully",
                    "Hard timeout plus a safe fallback response",
                ],
                "code": "",
                "hack": "Version the prompt template like model weights.",
                "why": "Prompt drift is a silent model change.",
                "extra": ["Log prompt hash every request", "Canary new prompts at 5%"],
            },
            {
                "type": "code",
                "heading": "Eval that catches lies",
                "steps": [
                    "Slice table: easy, hard, adversarial",
                    "Score with task metrics, not vibes",
                    "Regression gate in CI",
                    "Review 20 failures by hand every week",
                ],
                "code": "from sklearn.metrics import f1_score\nprint('macro_f1', f1_score(y_true, y_pred, average='macro'))\nfor i in fail_idx[:5]:\n    print(texts[i], '->', y_pred[i], 'gold', y_true[i])",
                "hack": "Averages without failure cases are theater.",
                "why": "Models fail on clusters; means hide the cluster.",
                "extra": ["Version the eval set", "Block merges on silent drops"],
            },
            {
                "type": "tips",
                "heading": "VRAM and speed truths",
                "steps": [
                    "Batch size limited by activation memory",
                    "Checkpointing trades compute for memory",
                    "bf16 is safer than fp16 for many LLM trains",
                    "Profile with real sequence length mix",
                ],
                "code": "",
                "hack": "Bottleneck is usually memory bandwidth, not FLOPs.",
                "why": "Attention is memory-bound on long context.",
                "extra": ["Print memory_summary after a step", "Ignore notebook timings for SLOs"],
            },
            {
                "type": "steps",
                "heading": "Production checklist",
                "steps": [
                    "Pin model id + revision + tokenizer",
                    "Log request id, latency, token counts",
                    "Rollback path to last-good artifact",
                    "Name an owner for the first week",
                ],
                "code": "",
                "hack": "If nobody owns the metric, it is a demo.",
                "why": "Production is process wrapped around weights.",
                "extra": ["Smoke-test generate on deploy", "Alert on refusal spikes"],
            },
        ],
        "takeaway": "Measure tokens, inspect logits, version prompts, ship behind metrics.",
        "hashtags": ["AI", "MachineLearning", "LLM", "Python", "MLOps", "GenAI"],
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
    c.roundRect(x, y, 62, 22, 4, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(x + 31, y + 6, label)


def _draw_header_footer(
    c: canvas.Canvas, width: float, height: float, day_number: int, page_label: str
) -> None:
    header_h = 36
    footer_h = 34

    c.setFillColor(NAVY)
    c.rect(0, height - header_h, width, header_h, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18, height - 23, "AI / ML HOW-TO")
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 18, height - 23, page_label)

    c.setFillColor(NAVY)
    c.rect(0, 0, width, footer_h, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2.5)
    c.line(0, footer_h, width, footer_h)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(16, 12, f"Day {day_number} of {SERIES_TOTAL}")
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, 12, "Steps · Code · Hacks")
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(width - 16, 12, BRAND_TAG)


def _draw_code_box(
    c: canvas.Canvas, x: float, y_top: float, w: float, code: str, max_lines: int = 5
) -> float:
    lines = [ln for ln in (code or "").replace("\\n", "\n").split("\n") if ln.strip()]
    lines = lines[:max_lines]
    if not lines:
        return y_top

    line_h = 15
    pad_top = 22
    pad_bot = 10
    box_h = pad_top + pad_bot + line_h * len(lines)
    y_bot = y_top - box_h

    c.setFillColor(CODE_BG)
    c.roundRect(x, y_bot, w, box_h, 6, fill=1, stroke=0)

    for i, col in enumerate([HexColor("#FF5F56"), HexColor("#FFBD2E"), HexColor("#27C93F")]):
        c.setFillColor(col)
        c.circle(x + 12 + i * 14, y_top - 10, 3.5, fill=1, stroke=0)

    c.setFillColor(HexColor("#64748B"))
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(x + w - 8, y_top - 12, "code")

    ty = y_top - 28
    for ln in lines:
        c.setFillColor(CODE_GREEN if ln.strip().startswith("#") else CODE_FG)
        if "print" in ln or "return" in ln:
            c.setFillColor(CODE_YELLOW)
        c.setFont("Courier-Bold", 10)
        while c.stringWidth(ln, "Courier-Bold", 10) > w - 18 and len(ln) > 3:
            ln = ln[:-1]
        c.drawString(x + 10, ty, ln)
        ty -= line_h

    return y_bot


def _draw_cover(c: canvas.Canvas, width: float, height: float, content: dict, day_number: int) -> None:
    c.setFillColor(NAVY)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, height - 8, width, 8, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, 0, 8, height, fill=1, stroke=0)

    badge = f"Day {day_number} of {SERIES_TOTAL}"
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    bw = c.stringWidth(badge, "Helvetica-Bold", 13) + 28
    c.roundRect(28, height - 70, bw, 28, 5, stroke=1, fill=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(42, height - 62, badge)

    _draw_icon_chip(c, 28, height - 110, "STEPS", BLUE)
    _draw_icon_chip(c, 100, height - 110, "CODE", GREEN)
    _draw_icon_chip(c, 172, height - 110, "HACKS", ORANGE)
    _draw_icon_chip(c, 244, height - 110, "METHOD", PURPLE)

    title = content.get("title") or "AI / ML How-To"
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 28)
    y = height - 170
    for line in _wrap_text(c, title, "Helvetica-Bold", 28, width - 60):
        c.drawString(28, y, line)
        y -= 34

    c.setStrokeColor(GOLD)
    c.setLineWidth(4)
    c.line(28, y - 4, 120, y - 4)

    sub = content.get("subtitle") or content.get("hook") or ""
    c.setFillColor(HexColor("#CBD5E1"))
    c.setFont("Helvetica", 14)
    y -= 28
    for line in _wrap_text(c, sub, "Helvetica", 14, width - 60):
        c.drawString(28, y, line)
        y -= 20

    # 4 stacked cards — fill portrait space
    y -= 20
    cards = [
        ("01", "STEPS", "Clear actions you can run today"),
        ("02", "CODE", "Copy-paste Python that works"),
        ("03", "HACKS", "Shortcuts from real production"),
        ("04", "METHODS", "Repeatable shipping process"),
    ]
    card_h = 56
    gap = 10
    for num, label, desc in cards:
        c.setFillColor(NAVY_SOFT)
        c.roundRect(28, y - card_h, width - 56, card_h, 8, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(44, y - 24, num)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(88, y - 22, label)
        c.setFillColor(HexColor("#94A3B8"))
        c.setFont("Helvetica", 12)
        c.drawString(88, y - 42, desc)
        y -= card_h + gap

    c.setFillColor(NAVY_SOFT)
    c.rect(0, 0, width, 42, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2.5)
    c.line(0, 42, width, 42)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20, 16, f"Day {day_number} of {SERIES_TOTAL}")
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, 16, "Swipe for code + hacks")
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 20, 16, BRAND_TAG)


def _draw_content_page(
    c: canvas.Canvas,
    width: float,
    height: float,
    slide: dict,
    index: int,
    total: int,
    day_number: int,
) -> None:
    """Portrait page: large text, content stacked tight from top to bottom."""
    c.setFillColor(LIGHT_BG)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    _draw_header_footer(c, width, height, day_number, f"{index}/{total}")

    margin = 16
    top = height - 44
    bottom = 42
    usable_h = top - bottom

    c.setFillColor(CARD_BG)
    c.roundRect(margin, bottom, width - 2 * margin, usable_h, 8, fill=1, stroke=0)

    stype = (slide.get("type") or "steps").lower()
    accent = {"code": GREEN, "method": PURPLE, "tips": ORANGE}.get(stype, BLUE)
    c.setFillColor(accent)
    c.rect(margin, bottom, 7, usable_h, fill=1, stroke=0)

    # Title row
    c.setFillColor(accent)
    c.circle(margin + 28, top - 26, 16, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(margin + 28, top - 31, str(index))

    heading = slide.get("heading") or f"Step {index}"
    c.setFillColor(SLATE)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin + 52, top - 32, heading[:36])
    _draw_icon_chip(c, width - margin - 72, top - 38, stype.upper()[:6], accent)

    y = top - 56
    inner_x = margin + 14
    inner_w = width - 2 * margin - 26

    steps = list(slide.get("steps") or slide.get("bullets") or [])[:4]
    extra = list(slide.get("extra") or [])[:2]
    code = (slide.get("code") or "").strip()
    hack = (slide.get("hack") or "").strip()
    why = (slide.get("why") or slide.get("insight") or "").strip()

    n_steps = max(len(steps), 1)
    code_lines = [ln for ln in code.replace("\\n", "\n").split("\n") if ln.strip()][:4] if code else []
    code_h = (22 + 10 + 15 * len(code_lines)) if code_lines else 0
    hack_h = 48 if (hack or why) else 0
    extra_h = 40 if extra else 0
    # Fill almost all remaining height with step rows
    remaining = y - bottom - 12 - code_h - hack_h - extra_h - 8
    row_h = max(38, min(56, remaining / n_steps))

    for n, step in enumerate(steps, start=1):
        c.setFillColor(HexColor("#F1F5F9"))
        c.roundRect(inner_x, y - row_h + 4, inner_w, row_h - 4, 5, fill=1, stroke=0)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(inner_x + 10, y - 22, f"{n}.")
        c.setFillColor(SLATE)
        c.setFont("Helvetica", 13)
        lines = _wrap_text(c, step, "Helvetica", 13, inner_w - 42)
        ty = y - 22
        for ln in lines[:2]:
            c.drawString(inner_x + 32, ty, ln)
            ty -= 16
        y -= row_h

    if code_lines:
        y -= 4
        y = _draw_code_box(c, inner_x, y, inner_w, code, max_lines=4) - 6

    if extra:
        c.setFillColor(HexColor("#ECFDF5"))
        eh = 18 + 16 * len(extra)
        c.roundRect(inner_x, y - eh, inner_w, eh, 5, fill=1, stroke=0)
        c.setFillColor(GREEN)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(inner_x + 10, y - 16, "BONUS")
        c.setFillColor(SLATE)
        c.setFont("Helvetica", 12)
        ty = y - 16
        for tip in extra:
            c.drawString(inner_x + 70, ty, f"• {tip}"[:70])
            ty -= 16
        y -= eh + 6

    if hack or why:
        c.setFillColor(HexColor("#EEF2FF"))
        strip_h = 44 if (hack and why) else 24
        c.roundRect(inner_x, y - strip_h, inner_w, strip_h, 5, fill=1, stroke=0)
        ty = y - 16
        if hack:
            c.setFillColor(PURPLE)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(inner_x + 10, ty, "HACK")
            c.setFillColor(SLATE)
            c.setFont("Helvetica", 12)
            for ln in _wrap_text(c, hack, "Helvetica", 12, inner_w - 60)[:1]:
                c.drawString(inner_x + 58, ty, ln)
            ty -= 18
        if why:
            c.setFillColor(PURPLE)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(inner_x + 10, ty, "WHY")
            c.setFillColor(SLATE)
            c.setFont("Helvetica", 12)
            for ln in _wrap_text(c, why, "Helvetica", 12, inner_w - 55)[:1]:
                c.drawString(inner_x + 52, ty, ln)


def _draw_closing(
    c: canvas.Canvas, width: float, height: float, content: dict, day_number: int
) -> None:
    c.setFillColor(NAVY)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, height - 8, width, 8, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, 0, 8, height, fill=1, stroke=0)

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(28, height - 60, "KEY TAKEAWAY")

    takeaway = content.get("takeaway") or "Measure tokens, inspect logits, version prompts."
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 18)
    y = height - 100
    for line in _wrap_text(c, takeaway, "Helvetica-Bold", 18, width - 60):
        c.drawString(28, y, line)
        y -= 24

    y -= 12
    checks = [
        "Measure tokens and VRAM first",
        "Inspect logits when output breaks",
        "Version prompts like model weights",
        "Gate merges on real eval slices",
        "Pin model id + revision",
        "Own the metric for 7 days post-ship",
    ]
    for item in checks:
        c.setFillColor(NAVY_SOFT)
        c.roundRect(28, y - 40, width - 56, 36, 6, fill=1, stroke=0)
        c.setFillColor(GREEN)
        c.circle(50, y - 22, 10, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(50, y - 26, "✓")
        c.setFillColor(HexColor("#E2E8F0"))
        c.setFont("Helvetica", 13)
        c.drawString(70, y - 26, item)
        y -= 46

    tags = content.get("hashtags") or []
    tag_str = "  ".join(f"#{t.lstrip('#')}" for t in tags[:6])
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 11)
    c.drawString(28, 58, tag_str[:70])

    c.setFillColor(NAVY_SOFT)
    c.rect(0, 0, width, 40, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2.5)
    c.line(0, 40, width, 40)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20, 15, f"Day {day_number} of {SERIES_TOTAL}")
    c.setFillColor(HexColor("#94A3B8"))
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, 15, "Save · Share · Ship")
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 20, 15, BRAND_TAG)


def build_pdf(content: dict, day_number: int) -> bytes:
    buffer = BytesIO()
    width, height = A4  # portrait
    c = canvas.Canvas(buffer, pagesize=A4)

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

Day {day_number} of {SERIES_TOTAL} — coding-side AI details most tutorials skip.

{content['title']}

Swipe for steps, real Python, and production hacks.

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
