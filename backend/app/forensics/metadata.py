"""F4: EXIF, XMP, PNG text chunks and C2PA content credentials.

Looks for three kinds of evidence:

* declarations: an AI tool, or a C2PA manifest, that says outright the image was generated
* editing traces: an editor in the Software/CreatorTool tag, or a modify date after capture
* absence: no camera metadata at all (weak evidence, social media strips it too)

GPS coordinates are never copied into the report; we only say whether they are present.
"""

from __future__ import annotations

import io
import json
import logging
import re
from datetime import datetime, timedelta

from PIL import ExifTags, Image

log = logging.getLogger(__name__)

# A match here overrides the verdict to "AI generated", so every entry must be specific enough
# not to appear in an ordinary photo caption (e.g. "firefly", "runway", "aurora", or Spanish
# "imagen" alone would flag real photos).
AI_GENERATOR_HINTS = [
    "dall-e", "dall·e", "dalle", "openai", "chatgpt", "midjourney", "stable diffusion",
    "stablediffusion", "sdxl", "comfyui", "automatic1111", "novelai", "invokeai", "fooocus",
    "adobe firefly", "google imagen", "made with google ai", "leonardo.ai", "ideogram",
    "black forest labs", "flux.1", "runwayml", "bing image creator", "microsoft designer",
    "dreamstudio", "playground ai", "krea.ai", "recraft", "nightcafe", "craiyon",
]
EDITING_SOFTWARE_HINTS = [
    "photoshop", "gimp", "lightroom", "affinity", "pixelmator", "snapseed", "facetune",
    "picsart", "canva", "paint.net", "capture one", "luminar", "photopea", "meitu", "lensa",
    "remini", "photodirector", "fotor", "polarr",
]
# PNG text keys written by popular diffusion front-ends
AI_PNG_KEYS = {"parameters", "prompt", "workflow", "invokeai_metadata", "sd-metadata", "dream", "negative_prompt"}
# IPTC digital source types (used by C2PA and XMP) that declare synthetic media
AI_SOURCE_TYPES = {"trainedalgorithmicmedia", "compositewithtrainedalgorithmicmedia", "algorithmicmedia"}

EXIF_DATE_FMT = "%Y:%m:%d %H:%M:%S"
MAX_VALUE_LEN = 200


def _clean(value) -> str | int | float | None:
    if isinstance(value, bytes):
        return None  # binary blobs (MakerNote, thumbnails) are not useful to a reader
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace("\x00", "")
    return text[:MAX_VALUE_LEN] if text else None


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.strptime(text.strip()[:19], EXIF_DATE_FMT)
    except ValueError:
        return None


def _find_hint(text: str, hints: list[str]) -> str | None:
    low = text.lower()
    for hint in hints:
        if hint in low:
            return hint
    return None


def _read_exif(pil: Image.Image) -> dict:
    exif = pil.getexif()
    tags: dict[str, object] = {}
    for tag_id, value in exif.items():
        name = ExifTags.TAGS.get(tag_id, str(tag_id))
        if name in ("GPSInfo", "ExifOffset"):
            continue
        cleaned = _clean(value)
        if cleaned is not None:
            tags[name] = cleaned
    try:
        for tag_id, value in exif.get_ifd(ExifTags.IFD.Exif).items():
            name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if name == "MakerNote":
                continue
            cleaned = _clean(value)
            if cleaned is not None:
                tags[name] = cleaned
    except Exception as exc:  # malformed IFD: keep what we already read
        log.debug("Could not read EXIF sub-IFD: %s", exc)
    gps_present = False
    try:
        gps_present = bool(exif.get_ifd(ExifTags.IFD.GPSInfo))
    except Exception as exc:
        log.debug("Could not read GPS IFD: %s", exc)
    return {"tags": tags, "gps_present": gps_present}


def _read_xmp(raw: bytes) -> dict:
    start = raw.find(b"<x:xmpmeta")
    if start == -1:
        return {}
    end = raw.find(b"</x:xmpmeta>", start)
    if end == -1:
        return {}
    xmp = raw[start : end + 12].decode("utf-8", errors="ignore")
    out: dict[str, str] = {}
    for key in ("CreatorTool", "DigitalSourceType", "Credit", "HistorySoftwareAgent", "softwareAgent"):
        m = re.search(rf"{key}(?:=\"([^\"]+)\"|>([^<]+)<)", xmp)
        if m:
            out[key] = (m.group(1) or m.group(2)).strip()[:MAX_VALUE_LEN]
    return out


def _read_png_text(pil: Image.Image) -> dict:
    text = getattr(pil, "text", None) or {}
    info = {k: v for k, v in pil.info.items() if isinstance(v, str)}
    merged = {**info, **text}
    return {k: v[:MAX_VALUE_LEN] for k, v in merged.items()}


def _has_c2pa_marker(raw: bytes) -> bool:
    # C2PA manifests are stored in JUMBF boxes labelled "c2pa".
    return b"jumb" in raw and b"c2pa" in raw


def _read_c2pa(raw: bytes, mime: str) -> dict | None:
    if not _has_c2pa_marker(raw):
        return None
    result: dict = {"present": True, "validated": False}
    try:
        import c2pa  # type: ignore

        with c2pa.Reader(mime, io.BytesIO(raw)) as reader:
            store = json.loads(reader.json())
        active = store.get("manifests", {}).get(store.get("active_manifest", ""), {})
        result["claim_generator"] = _clean(
            active.get("claim_generator")
            or ", ".join(g.get("name", "") for g in active.get("claim_generator_info", []) if isinstance(g, dict))
        )
        sig = active.get("signature_info", {}) or {}
        result["signed_by"] = _clean(sig.get("issuer") or sig.get("common_name"))
        result["signed_at"] = _clean(sig.get("time"))
        statuses = store.get("validation_status") or []
        result["validation_errors"] = [_clean(s.get("code")) for s in statuses if isinstance(s, dict)][:10]
        result["validated"] = not result["validation_errors"]

        source_types, actions = set(), []
        for assertion in active.get("assertions", []):
            label = assertion.get("label", "")
            if label.startswith("c2pa.actions"):
                for action in assertion.get("data", {}).get("actions", []):
                    actions.append(_clean(action.get("action")))
                    dst = action.get("digitalSourceType") or ""
                    if dst:
                        source_types.add(dst.rsplit("/", 1)[-1])
        result["actions"] = [a for a in actions if a][:15]
        result["digital_source_types"] = sorted(source_types)
        result["declares_ai"] = any(s.lower() in AI_SOURCE_TYPES for s in source_types)
    except Exception as exc:
        log.info("C2PA manifest could not be parsed: %s", exc)
        result["error"] = "A C2PA manifest is present but could not be parsed or verified."
    return result


def analyze_metadata(raw: bytes, pil: Image.Image, fmt: str, mime: str) -> dict:
    exif = _read_exif(pil)
    tags = exif["tags"]
    xmp = _read_xmp(raw)
    png_text = _read_png_text(pil) if fmt == "PNG" else {}
    c2pa_info = _read_c2pa(raw, mime)

    flags: list[dict] = []

    def flag(code: str, severity: str, message: str, points_to: str) -> None:
        flags.append({"code": code, "severity": severity, "points_to": points_to, "message": message})

    software = tags.get("Software") or xmp.get("CreatorTool") or png_text.get("Software")
    software = str(software) if software else None

    # 1. Declarations of AI generation
    ai_hint = None
    haystacks = [
        ("software tag", software or ""),
        ("XMP", " ".join(xmp.values())),
        ("EXIF", " ".join(str(tags.get(k, "")) for k in ("Artist", "ImageDescription", "Make", "Model", "UserComment"))),
        ("PNG text", " ".join(f"{k} {v}" for k, v in png_text.items())),
    ]
    for source, text in haystacks:
        hit = _find_hint(text, AI_GENERATOR_HINTS)
        if hit:
            ai_hint = {"source": source, "match": hit}
            break
    ai_png_keys = sorted(k for k in png_text if k.lower() in AI_PNG_KEYS)
    if ai_png_keys and not ai_hint:
        ai_hint = {"source": "PNG text", "match": ", ".join(ai_png_keys)}
    if ai_hint:
        flag("ai_tool_declared", "high", f"The {ai_hint['source']} mentions an AI image tool ({ai_hint['match']}).", "ai_generated")

    dst = xmp.get("DigitalSourceType", "").rsplit("/", 1)[-1]
    if dst.lower() in AI_SOURCE_TYPES:
        flag("xmp_ai_source", "high", f"XMP metadata declares the digital source type '{dst}'.", "ai_generated")

    if c2pa_info:
        if c2pa_info.get("declares_ai"):
            flag("c2pa_ai", "high", "The C2PA content credentials declare this image as AI generated.", "ai_generated")
        elif c2pa_info.get("validated"):
            flag("c2pa_valid", "info", "Valid C2PA content credentials are attached; review the recorded edit history.", "real")
        elif c2pa_info.get("error") or c2pa_info.get("validation_errors"):
            flag("c2pa_invalid", "medium", "C2PA content credentials are present but did not validate, which can mean the file was altered after signing.", "manipulated")

    # 2. Editing traces
    editor = _find_hint(software or "", EDITING_SOFTWARE_HINTS)
    if editor:
        flag("editing_software", "medium", f"The file was last saved by editing software ({software}).", "manipulated")

    original = _parse_date(tags.get("DateTimeOriginal"))
    modified = _parse_date(tags.get("DateTime"))
    digitized = _parse_date(tags.get("DateTimeDigitized"))
    if original and modified and modified - original > timedelta(minutes=1):
        flag("modified_after_capture", "medium", f"The file was modified {modified - original} after it was captured.", "manipulated")
    if original and digitized and abs(digitized - original) > timedelta(minutes=1):
        flag("date_mismatch", "low", "The capture and digitised dates disagree.", "manipulated")
    now = datetime.now()
    if any(d and d > now + timedelta(days=1) for d in (original, modified, digitized)):
        flag("future_date", "medium", "A metadata date is in the future, so the dates are unreliable.", "manipulated")

    # 3. Camera presence or absence
    make, model = tags.get("Make"), tags.get("Model")
    exif_present = bool(tags)
    if not exif_present and not c2pa_info:
        flag(
            "metadata_stripped", "low",
            "There is no camera metadata. AI images usually have none, but social media and messaging apps also strip it.",
            "ai_generated",
        )
    elif make or model:
        flag("camera_present", "info", f"Camera metadata is present ({' '.join(str(x) for x in (make, model) if x)}). It can be forged, so treat it as weak evidence.", "real")

    return {
        "exif_present": exif_present,
        "camera": {"make": make, "model": model} if (make or model) else None,
        "software_tag": software,
        "dates": {
            "original": tags.get("DateTimeOriginal"),
            "digitized": tags.get("DateTimeDigitized"),
            "modified": tags.get("DateTime"),
        },
        "gps_present": exif["gps_present"],
        "xmp": xmp or None,
        "png_text_keys": sorted(png_text) or None,
        "c2pa_manifest": c2pa_info,
        "ai_generator_hint": ai_hint,
        "flags": flags,
        "exif": {k: v for k, v in list(tags.items())[:60]},
    }
