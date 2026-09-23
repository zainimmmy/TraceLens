"""PDF support: analyse the images inside a PDF, plus the PDF's own integrity signals.

Forensics must run on the *original* embedded images, not on a re-rendered page: rendering
throws away the JPEG compression history (ELA) and the EXIF block (metadata). So we:

1. extract embedded images, keeping JPEG streams byte-for-byte (DCTDecode is a complete JPEG);
2. only if a PDF has no usable embedded images (text or vector PDF), render its first pages,
   and mark those results as less reliable;
3. check document-level signals: incremental updates (edits appended after the first save),
   creation vs modification date, and the producing/editing software.

pdfium (via pypdfium2) is the PDF engine used by Chrome. It is not thread-safe, so every call
into it happens under a module-level lock; the image analysis itself runs outside the lock.
"""

from __future__ import annotations

import hashlib
import io
import re
import threading
from dataclasses import dataclass
from datetime import datetime

from .config import settings
from .forensics.metadata import AI_GENERATOR_HINTS
from .imaging import ImageValidationError

MIN_IMAGE_SIDE = 100  # skip icons, logos and decorations
MAX_PAGES_SCANNED = 50
RENDER_PAGES = 5
RENDER_DPI = 150
PDF_EDITOR_HINTS = [
    "photoshop", "illustrator", "gimp", "canva", "ilovepdf", "smallpdf", "sejda", "pdfescape",
    "pdf-xchange", "foxit phantompdf", "foxit pdf editor", "nitro", "pdffiller", "dochub",
    "inkscape", "libreoffice draw", "pdf candy", "soda pdf",
]
VERDICT_SEVERITY = {"ai_generated": 3, "manipulated": 2, "inconclusive": 1, "real": 0}

_pdfium_lock = threading.Lock()


@dataclass
class ExtractedImage:
    name: str
    page: int  # 1-based
    source: str  # "embedded" or "rendered_page"
    embedded_format: str  # "JPEG" (original bytes), "PNG" (re-encoded) or "rendered"
    data: bytes


def is_pdf(data: bytes) -> bool:
    return data[:1024].lstrip().startswith(b"%PDF-")


def count_revisions(raw: bytes) -> int:
    """Number of saved revisions. Each incremental update appends a new ``%%EOF``.

    Linearized ("fast web view") files legitimately carry one extra marker.
    """
    eofs = raw.count(b"%%EOF")
    if b"/Linearized" in raw[:2048]:
        eofs -= 1
    return max(1, eofs)


def _parse_pdf_date(value: str | None) -> datetime | None:
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value.removeprefix("D:"))[:14]
    for fmt, n in (("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12), ("%Y%m%d", 8)):
        if len(digits) >= n:
            try:
                return datetime.strptime(digits[:n], fmt)
            except ValueError:
                return None
    return None


def _to_png(pil_image) -> bytes:
    buf = io.BytesIO()
    pil_image.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def _extract_one(img_obj) -> tuple[bytes, str] | None:
    """Original JPEG bytes when possible, otherwise a lossless PNG of the decoded pixels."""
    from PIL import Image

    buf = io.BytesIO()
    try:
        img_obj.extract(buf, fb_format="png")
        data = buf.getvalue()
    except Exception:
        data = b""
    if data.startswith(b"\xff\xd8"):
        return data, "JPEG"
    try:
        if data:  # JPEG 2000 or PIL-re-encoded PNG
            with Image.open(io.BytesIO(data)) as im:
                return _to_png(im), "PNG"
        return _to_png(img_obj.get_bitmap(render=False).to_pil()), "PNG"
    except Exception:
        return None


def _read_pdf(data: bytes) -> tuple[dict, int, list[ExtractedImage], dict]:
    import pypdfium2 as pdfium

    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        msg = str(exc).lower()
        if "password" in msg:
            raise ImageValidationError("This PDF is password protected. Remove the password and try again.") from exc
        raise ImageValidationError("The file is not a readable PDF.") from exc

    images: list[ExtractedImage] = []
    stats = {"images_found": 0, "skipped_small": 0, "skipped_duplicate": 0, "truncated": False}
    try:
        meta = {k: v for k, v in doc.get_metadata_dict(skip_empty=True).items() if isinstance(v, str)}
        page_count = len(doc)
        seen: set[str] = set()
        for index in range(min(page_count, MAX_PAGES_SCANNED)):
            page = doc[index]
            try:
                n_on_page = 0
                for obj in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]):
                    stats["images_found"] += 1
                    w, h = obj.get_px_size()
                    if min(w, h) < MIN_IMAGE_SIDE or w * h > settings.max_image_pixels:
                        stats["skipped_small"] += 1
                        continue
                    if len(images) >= settings.max_pdf_images:
                        stats["truncated"] = True
                        continue
                    extracted = _extract_one(obj)
                    if not extracted:
                        continue
                    blob, fmt = extracted
                    digest = hashlib.sha256(blob).hexdigest()
                    if digest in seen:  # same logo/photo reused on several pages
                        stats["skipped_duplicate"] += 1
                        continue
                    seen.add(digest)
                    n_on_page += 1
                    images.append(ExtractedImage(f"Page {index + 1} · image {n_on_page}", index + 1, "embedded", fmt, blob))
            finally:
                page.close()
        if page_count > MAX_PAGES_SCANNED:
            stats["truncated"] = True

        stats["mode"] = "embedded_images"
        if not images:  # text or vector PDF: fall back to rendering pages
            stats["mode"] = "rendered_pages"
            for index in range(min(page_count, RENDER_PAGES)):
                page = doc[index]
                try:
                    pil = page.render(scale=RENDER_DPI / 72).to_pil()
                    images.append(ExtractedImage(f"Page {index + 1} (rendered)", index + 1, "rendered_page", "rendered", _to_png(pil)))
                finally:
                    page.close()
            stats["truncated"] = page_count > RENDER_PAGES
        return meta, page_count, images, stats
    finally:
        doc.close()


def document_signals(raw: bytes, meta: dict) -> tuple[dict, list[dict]]:
    flags: list[dict] = []

    def flag(code: str, severity: str, message: str, points_to: str) -> None:
        flags.append({"code": code, "severity": severity, "points_to": points_to, "message": message})

    revisions = count_revisions(raw)
    created, modified = _parse_pdf_date(meta.get("CreationDate")), _parse_pdf_date(meta.get("ModDate"))
    tools = " ".join(meta.get(k, "") for k in ("Creator", "Producer"))
    low = tools.lower()

    ai_hit = next((h for h in AI_GENERATOR_HINTS if h in low), None)
    if ai_hit:
        flag("pdf_ai_tool", "high", f"The PDF was produced with an AI tool ({ai_hit}).", "ai_generated")
    for field in ("Creator", "Producer"):
        value = meta.get(field, "")
        if any(h in value.lower() for h in PDF_EDITOR_HINTS):
            flag("pdf_editor", "medium", f"The PDF's {field.lower()} is editing software ({value.strip()[:80]}).", "manipulated")
            break
    if revisions > 1:
        flag(
            "incremental_updates", "medium",
            f"The PDF has {revisions} saved revisions: content was changed after it was first saved. "
            "Digital signatures and form filling also do this, so check what changed.",
            "manipulated",
        )
    if created and modified and (modified - created).total_seconds() > 60:
        flag("pdf_modified", "low", f"The PDF was modified {modified - created} after it was created.", "manipulated")
    if not meta.get("Producer") and not meta.get("Creator"):
        flag("pdf_metadata_stripped", "info", "The PDF has no producer or creator information.", "neutral")

    info = {
        "title": meta.get("Title"),
        "author": meta.get("Author"),
        "creator": meta.get("Creator"),
        "producer": meta.get("Producer"),
        "created": created.isoformat(sep=" ") if created else meta.get("CreationDate"),
        "modified": modified.isoformat(sep=" ") if modified else meta.get("ModDate"),
        "revisions": revisions,
    }
    return info, flags


def extract_pdf(data: bytes) -> tuple[dict, int, list[ExtractedImage], dict]:
    """Thread-safe wrapper around pdfium. Returns (metadata, page count, images, stats)."""
    if len(data) > settings.max_pdf_bytes:
        raise ImageValidationError(f"The PDF is larger than {settings.max_pdf_bytes // (1024 * 1024)} MB.")
    if not is_pdf(data):
        raise ImageValidationError("The file is not a PDF.")
    with _pdfium_lock:
        return _read_pdf(data)


def analyze_pdf(data: bytes, filename: str | None) -> dict:
    from .pipeline import DISCLAIMER, analyze_bytes

    meta, page_count, images, stats = extract_pdf(data)
    info, flags = document_signals(data, meta)
    info["pages"] = page_count

    items = []
    for img in images:
        try:
            report = analyze_bytes(img.data, f"{filename or 'document.pdf'} · {img.name}", allow_llm=False)
        except ImageValidationError as exc:
            items.append({"name": img.name, "page": img.page, "source": img.source, "embedded_format": img.embedded_format,
                          "report": None, "error": str(exc)})
            continue
        if img.source == "rendered_page":
            report["findings"].insert(0, {
                "signal": "pdf", "points_to": "neutral", "strength": "info",
                "text": "This is a rendered PDF page, not an original photo, so ELA, noise and camera metadata are much less meaningful.",
            })
        items.append({"name": img.name, "page": img.page, "source": img.source, "embedded_format": img.embedded_format,
                      "report": report, "error": None})

    verdicts = [i["report"]["verdict"] for i in items if i["report"]]
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v] = counts.get(v, 0) + 1
    overall = max(verdicts, key=VERDICT_SEVERITY.__getitem__) if verdicts else "inconclusive"
    overall_basis = "images"
    # Tool-based document signals can raise the headline. Incremental saves alone do not,
    # because digital signatures and form filling also append revisions.
    doc_codes = {f["code"] for f in flags}
    for code, verdict in (("pdf_ai_tool", "ai_generated"), ("pdf_editor", "manipulated")):
        if code in doc_codes and VERDICT_SEVERITY[verdict] > VERDICT_SEVERITY[overall]:
            overall, overall_basis = verdict, "document"
            break
    flagged = sum(1 for v in verdicts if v in ("ai_generated", "manipulated"))

    if not items:
        summary = "No images could be analysed in this PDF."
    elif stats["mode"] == "rendered_pages":
        summary = (f"This PDF has no embedded photos, so {len(items)} page(s) were rendered and analysed. "
                   "Rendered pages carry little forensic evidence; rely mainly on the document checks.")
    else:
        summary = f"{flagged} of {len(items)} embedded image(s) show signs of AI generation or editing."
    if flags:
        worst = sorted(flags, key=lambda f: ["high", "medium", "low", "info"].index(f["severity"]))[0]
        summary += f" Document check: {worst['message']}"

    return {
        "filename": filename,
        "kind": "pdf",
        "overall_verdict": overall,
        "overall_basis": overall_basis,
        "counts_by_verdict": counts,
        "summary": summary,
        "document": info,
        "document_flags": flags,
        "extraction": {**stats, "images_analyzed": len(items)},
        "items": items,
        "disclaimer": DISCLAIMER,
    }
