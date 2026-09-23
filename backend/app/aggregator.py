"""Combine every forensic signal into one verdict, a confidence, and a list of findings.

The rules are deliberately simple and readable, so an analyst can explain any verdict:

1. An explicit declaration (C2PA, XMP or a tool name in the metadata) that the image is AI
   generated wins outright.
2. Otherwise the calibrated classifier probability decides AI vs real, with an
   "inconclusive" band between 40% and 60% (PRD risk mitigation for false positives).
3. Localised ELA / noise anomalies plus editing traces in the metadata produce a separate
   manipulation score. A high score yields "manipulated" unless the image is AI generated.
"""

from __future__ import annotations

from .config import settings

VERDICT_LABELS = {
    "ai_generated": "Likely AI generated",
    "manipulated": "Likely edited or manipulated",
    "real": "Likely an authentic photo",
    "inconclusive": "Inconclusive",
}
AI_DECLARATION_FLAGS = {"ai_tool_declared", "xmp_ai_source", "c2pa_ai"}
METADATA_MANIPULATION_WEIGHTS = {
    "editing_software": 0.35,
    "c2pa_invalid": 0.30,
    "modified_after_capture": 0.20,
    "future_date": 0.10,
    "date_mismatch": 0.10,
}
MANIPULATION_THRESHOLD = 0.6
FFT_FALLBACK_SHRINK = 0.6  # the FFT baseline is weaker, so pull it towards 0.5


def _noisy_or(values: list[float]) -> float:
    remaining = 1.0
    for v in values:
        remaining *= 1.0 - max(0.0, min(1.0, v))
    return 1.0 - remaining


def manipulation_score(ela: dict, noise: dict, metadata: dict) -> tuple[float, dict]:
    parts: dict[str, float] = {}
    if ela.get("suspicious_regions"):
        s = min(1.0, ela["outlier_energy_share"] * 4 + 0.15)
        parts["ela"] = s * (1.0 if ela.get("reliability") == "normal" else 0.5)
    if noise.get("suspicious_regions"):
        parts["noise"] = min(1.0, noise["inconsistent_blocks_share"] * 5 + 0.1) * 0.8
    meta = sum(METADATA_MANIPULATION_WEIGHTS.get(f["code"], 0.0) for f in metadata.get("flags", []))
    if meta:
        parts["metadata"] = min(meta, 0.8)
    return round(_noisy_or(list(parts.values())), 4), {k: round(v, 3) for k, v in parts.items()}


def ai_probability(classifier: dict, frequency: dict) -> tuple[float | None, str | None]:
    if classifier.get("available"):
        return classifier["ai_probability"], "classifier"
    fft = frequency.get("baseline_ai_probability")
    if fft is not None:
        return round(0.5 + (fft - 0.5) * FFT_FALLBACK_SHRINK, 4), "fft_baseline"
    return None, None


def build_findings(classifier: dict, frequency: dict, ela: dict, noise: dict, metadata: dict,
                   p_ai: float | None, p_source: str | None) -> list[dict]:
    findings: list[dict] = []

    def add(signal: str, points_to: str, strength: str, text: str) -> None:
        findings.append({"signal": signal, "points_to": points_to, "strength": strength, "text": text})

    if p_ai is None:
        add("classifier", "neutral", "info", "The AI image classifier is not available on this server, so the verdict relies on forensics and metadata only.")
    else:
        name = "The classifier" if p_source == "classifier" else "The frequency-domain baseline model"
        pct = round(p_ai * 100)
        if p_ai >= settings.inconclusive_high:
            add("classifier", "ai_generated", "high" if p_ai >= 0.85 else "medium", f"{name} estimates a {pct}% chance the image is AI generated.")
        elif p_ai <= settings.inconclusive_low:
            add("classifier", "real", "high" if p_ai <= 0.15 else "medium", f"{name} estimates only a {pct}% chance the image is AI generated.")
        else:
            add("classifier", "neutral", "low", f"{name} is unsure ({pct}% AI), inside the inconclusive band.")

    if ela.get("suspicious_regions"):
        caveat = "" if ela.get("reliability") == "normal" else " ELA is less reliable on non-JPEG files."
        add("ela", "manipulated", "medium",
            f"Error Level Analysis found {ela['suspicious_regions']} region(s) that recompress differently from the rest of the image.{caveat}")
    else:
        add("ela", "real", "low", "Error Level Analysis shows a consistent compression level across the image.")

    if noise.get("suspicious_regions"):
        add("noise", "manipulated", "medium",
            f"The sensor-noise pattern is inconsistent in {noise['suspicious_regions']} region(s), which can indicate pasted or generated patches.")
    else:
        add("noise", "real", "low", "The noise pattern is consistent across the image.")

    strength_map = {"high": "high", "medium": "medium", "low": "low", "info": "info"}
    for f in metadata.get("flags", []):
        add("metadata", f["points_to"], strength_map.get(f["severity"], "low"), f["message"])

    return findings


def aggregate(classifier: dict, frequency: dict, ela: dict, noise: dict, metadata: dict) -> dict:
    flags = {f["code"] for f in metadata.get("flags", [])}
    p_ai, p_source = ai_probability(classifier, frequency)
    m_score, m_parts = manipulation_score(ela, noise, metadata)
    findings = build_findings(classifier, frequency, ela, noise, metadata, p_ai, p_source)
    lo, hi = settings.inconclusive_low, settings.inconclusive_high

    if flags & AI_DECLARATION_FLAGS:
        verdict, confidence = "ai_generated", max(0.95, p_ai or 0.0)
        basis = "metadata_declaration"
    elif p_ai is not None and p_ai >= hi:
        verdict, confidence, basis = "ai_generated", p_ai, p_source
    elif m_score >= MANIPULATION_THRESHOLD:
        verdict, confidence, basis = "manipulated", m_score, "forensics"
    elif p_ai is not None and p_ai <= lo:
        verdict, confidence, basis = "real", 1.0 - p_ai, p_source
        # Moderate manipulation evidence erodes confidence in "real".
        confidence *= 1.0 - 0.5 * m_score
        if confidence < 0.6:
            verdict = "inconclusive"
    else:
        verdict, basis = "inconclusive", p_source or "forensics"
        confidence = max(p_ai, 1 - p_ai) if p_ai is not None else 0.5

    return {
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS[verdict],
        "confidence": round(float(confidence), 4),
        "ai_probability": p_ai,
        "ai_probability_source": p_source,
        "manipulation_score": m_score,
        "manipulation_breakdown": m_parts,
        "verdict_basis": basis,
        "findings": findings,
    }
