"""F5: plain-English summary.

Gemini (free tier) rewrites the structured findings into a short paragraph. Only the numeric
signals and findings are sent, never the image, so uploads stay private. When there is no API
key, the quota is exhausted, or the call fails, a deterministic template is used instead.
"""

from __future__ import annotations

import json
import logging

import httpx

from .config import settings

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT = """You are a digital forensics assistant writing for a non-technical reader
(an insurance adjuster, fraud analyst or journalist).

Write a 2 to 4 sentence summary of the analysis below.
Rules:
- State the verdict and confidence exactly as given. Never change or soften the verdict.
- Name the two or three most important reasons, in plain words.
- If the verdict is inconclusive, say what would help (for example, the original file).
- Do not use headings, bullet points, markdown or emojis.
- Do not claim certainty; the result is probabilistic evidence, not proof.

Analysis JSON:
{payload}
"""

STRENGTH_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def _payload(result: dict) -> dict:
    return {
        "verdict": result["verdict"],
        "verdict_label": result["verdict_label"],
        "confidence_percent": round(result["confidence"] * 100),
        "ai_probability_percent": None if result["ai_probability"] is None else round(result["ai_probability"] * 100),
        "manipulation_score_percent": round(result["manipulation_score"] * 100),
        "findings": [
            {"points_to": f["points_to"], "strength": f["strength"], "text": f["text"]}
            for f in result["findings"]
        ],
    }


def template_summary(result: dict) -> str:
    verdict, pct = result["verdict"], round(result["confidence"] * 100)
    key = sorted(
        (f for f in result["findings"] if f["points_to"] == verdict or (verdict == "inconclusive" and f["strength"] != "info")),
        key=lambda f: STRENGTH_ORDER.get(f["strength"], 9),
    )[:3]
    reasons = " ".join(f["text"] for f in key)

    if verdict == "ai_generated":
        opening = f"This image is likely AI generated ({pct}% confidence)."
    elif verdict == "manipulated":
        opening = f"This image shows signs of editing or manipulation ({pct}% confidence)."
    elif verdict == "real":
        opening = f"This image looks like an authentic, unedited photo ({pct}% confidence)."
    else:
        opening = "The evidence is mixed, so TraceLens cannot make a confident call on this image."
    closing = ""
    if verdict == "inconclusive":
        closing = " If possible, check the original file straight from the camera or sender, since re-sharing strips useful evidence."
    return f"{opening} {reasons}{closing}".strip()


def gemini_summary(result: dict) -> str | None:
    if not settings.gemini_api_key:
        return None
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(payload=json.dumps(_payload(result), indent=1))}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
    }
    try:
        resp = httpx.post(
            GEMINI_URL.format(model=settings.gemini_model),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=body,
            timeout=settings.gemini_timeout_s,
        )
        if resp.status_code != 200:
            log.warning("Gemini returned HTTP %s; using template summary", resp.status_code)
            return None
        parts = resp.json()["candidates"][0]["content"]["parts"]
        text = " ".join(p.get("text", "") for p in parts).strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        log.warning("Gemini summary failed (%s); using template summary", type(exc).__name__)
        return None
    # Guard rail: reject empty or runaway output.
    if not (20 <= len(text) <= 1200):
        return None
    return text


def summarize(result: dict, allow_llm: bool = True) -> tuple[str, str]:
    """Return ``(summary, source)`` where source is ``gemini`` or ``template``."""
    if allow_llm:
        text = gemini_summary(result)
        if text:
            return text, "gemini"
    return template_summary(result), "template"
