"""Downloadable PDF report (ReportLab).

The input is a report JSON sent back by the client, so it is untrusted: every string is
escaped before it reaches ReportLab's mini-markup, and only small base64 PNG/JPEG data URLs
are embedded.
"""

from __future__ import annotations

import base64
import binascii
import io
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

MAX_IMAGE_BYTES = 3 * 1024 * 1024
VERDICT_COLORS = {
    "ai_generated": colors.HexColor("#b42318"),
    "manipulated": colors.HexColor("#b54708"),
    "real": colors.HexColor("#067647"),
    "inconclusive": colors.HexColor("#475467"),
}
IMAGE_TITLES = [("original", "Original"), ("gradcam", "Classifier heatmap (Grad-CAM)"), ("ela", "Error Level Analysis"), ("noise", "Noise consistency")]


def _t(value, limit: int = 2000) -> str:
    return escape(str(value if value is not None else "n/a")[:limit], quote=False)


def _yes_no(value) -> str:
    return "Yes" if value is True else "No" if value is False else "n/a"


def _pct(value) -> str:
    try:
        return f"{round(float(value) * 100)}%"
    except (TypeError, ValueError):
        return "n/a"


def _decode_image(data_url: str | None, width: float) -> RLImage | None:
    if not isinstance(data_url, str):
        return None
    for prefix in ("data:image/png;base64,", "data:image/jpeg;base64,"):
        if data_url.startswith(prefix):
            try:
                raw = base64.b64decode(data_url[len(prefix):], validate=True)
            except (binascii.Error, ValueError):
                return None
            if len(raw) > MAX_IMAGE_BYTES:
                return None
            try:
                from PIL import Image

                # Re-encode as JPEG: keeps the PDF small and drops anything odd in the upload.
                with Image.open(io.BytesIO(raw)) as im:
                    w, h = im.size
                    out = io.BytesIO()
                    im.convert("RGB").save(out, "JPEG", quality=85)
                out.seek(0)
                return RLImage(out, width=width, height=width * h / w)
            except Exception:
                return None
    return None


def build_pdf(report: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="TraceLens forensic report", author="TraceLens")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#475467"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    verdict = str(report.get("verdict", "inconclusive"))
    vcolor = VERDICT_COLORS.get(verdict, colors.black)
    big = ParagraphStyle("verdict", parent=styles["Title"], fontSize=18, textColor=vcolor, alignment=0, spaceAfter=2)

    story = [
        Paragraph("TraceLens forensic report", styles["Heading1"]),
        Paragraph(f"File: {_t(report.get('filename'))} &nbsp;·&nbsp; Analysed: {_t(report.get('analyzed_at'))} &nbsp;·&nbsp; Report ID: {_t(report.get('id'))}", small),
        Spacer(1, 6),
        Paragraph(_t(report.get("verdict_label", verdict)), big),
        Paragraph(
            f"Confidence {_pct(report.get('confidence'))} &nbsp;·&nbsp; AI probability {_pct(report.get('ai_probability'))}"
            f" &nbsp;·&nbsp; Manipulation score {_pct(report.get('manipulation_score'))}",
            body,
        ),
        Spacer(1, 6),
        Paragraph("Summary", h2),
        Paragraph(_t(report.get("summary")), body),
    ]

    findings = report.get("findings") or []
    if isinstance(findings, list) and findings:
        story.append(Paragraph("Findings", h2))
        rows = [["Signal", "Points to", "Strength", "Detail"]]
        for f in findings[:30]:
            if isinstance(f, dict):
                rows.append([_t(f.get("signal"), 30), _t(f.get("points_to"), 30), _t(f.get("strength"), 20), Paragraph(_t(f.get("text"), 500), small)])
        table = Table(rows, colWidths=[22 * mm, 26 * mm, 18 * mm, 108 * mm], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f4f7")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d5dd")),
        ]))
        story.append(table)

    images = report.get("images") or {}
    if isinstance(images, dict):
        cells = []
        for key, title in IMAGE_TITLES:
            img = _decode_image(images.get(key), 80 * mm)
            if img:
                cells.append([Paragraph(title, small), img])
        if cells:
            story.append(Paragraph("Visual evidence", h2))
            rows = []
            for i in range(0, len(cells), 2):
                pair = [Table([[title], [img]]) for title, img in cells[i : i + 2]]
                rows.append(pair + [""] * (2 - len(pair)))
            story.append(Table(rows, colWidths=[87 * mm, 87 * mm]))

    meta = ((report.get("signals") or {}).get("metadata") or {}) if isinstance(report.get("signals"), dict) else {}
    if isinstance(meta, dict) and meta:
        story.append(Paragraph("Metadata and provenance", h2))
        camera = meta.get("camera") or {}
        c2pa = meta.get("c2pa_manifest")
        dates = meta.get("dates") or {}
        rows = [
            ["EXIF present", _yes_no(meta.get("exif_present"))],
            ["Camera", _t(" ".join(str(v) for v in (camera.get("make"), camera.get("model")) if v) or "none") if isinstance(camera, dict) else "none"],
            ["Software tag", _t(meta.get("software_tag") or "none")],
            ["Captured / modified", _t(f"{dates.get('original') or '-'} / {dates.get('modified') or '-'}") if isinstance(dates, dict) else "-"],
            ["GPS data present", _yes_no(meta.get("gps_present"))],
            ["C2PA credentials", _t("none" if not c2pa else ("valid" if isinstance(c2pa, dict) and c2pa.get("validated") else "present, not validated"))],
        ]
        t = Table(rows, colWidths=[40 * mm, 134 * mm], hAlign="LEFT")
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d5dd"))]))
        story.append(t)

    story += [Spacer(1, 12), Paragraph(_t(report.get("disclaimer") or "Results are probabilistic and should not be treated as proof."), small)]
    doc.build(story)
    return buf.getvalue()
