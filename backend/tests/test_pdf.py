from __future__ import annotations

import io

import pytest
from conftest import encode, natural_image
from fastapi.testclient import TestClient
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.imaging import ImageValidationError
from app.main import app
from app.pdf_document import count_revisions, document_signals, extract_pdf, is_pdf


def photoshop_jpeg() -> bytes:
    exif = Image.Exif()
    exif[0x0131] = "Adobe Photoshop 25.0"
    return encode(natural_image(640, 480), quality=88, exif=exif)


def make_pdf(images: list[bytes] = (), text: str = "Claim form", creator: str | None = None, encrypt: str | None = None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, encrypt=encrypt)
    c.drawString(50, 780, text)
    for i, data in enumerate(images):
        c.drawImage(ImageReader(io.BytesIO(data)), 50, 420 - i * 10, 300, 225)
        c.showPage()
    if creator:
        c.setCreator(creator)
    c.save()
    return buf.getvalue()


def codes(flags):
    return {f["code"] for f in flags}


def test_embedded_jpeg_is_extracted_byte_for_byte():
    jpg = photoshop_jpeg()
    _, pages, images, stats = extract_pdf(make_pdf([jpg]))
    assert pages == 1 and stats["mode"] == "embedded_images"
    assert images[0].embedded_format == "JPEG"
    assert images[0].data == jpg  # original compression and EXIF preserved


def test_small_and_duplicate_images_are_skipped():
    jpg = photoshop_jpeg()
    _, _, images, stats = extract_pdf(make_pdf([jpg, encode(natural_image(60, 60)), jpg]))
    assert len(images) == 1
    assert stats["skipped_small"] == 1 and stats["skipped_duplicate"] == 1


def test_image_limit_truncates(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_pdf_images", 1)
    pngs = [encode(natural_image(300, 200, seed), "PNG") for seed in (1, 2)]
    _, _, images, stats = extract_pdf(make_pdf(pngs))
    assert len(images) == 1 and stats["truncated"] is True
    assert images[0].embedded_format == "PNG"


def test_text_only_pdf_falls_back_to_rendered_pages():
    _, _, images, stats = extract_pdf(make_pdf([]))
    assert stats["mode"] == "rendered_pages"
    assert images[0].source == "rendered_page"
    assert Image.open(io.BytesIO(images[0].data)).width > 1000  # rendered at 150 DPI


def test_password_protected_pdf_is_rejected():
    with pytest.raises(ImageValidationError, match="password"):
        extract_pdf(make_pdf([], encrypt="secret"))


@pytest.mark.parametrize("data", [b"%PDF-1.7 garbage", b"not a pdf at all"])
def test_broken_pdf_is_rejected(data):
    with pytest.raises(ImageValidationError):
        extract_pdf(data)


def test_is_pdf():
    assert is_pdf(make_pdf([])) and not is_pdf(encode(natural_image()))


def test_revision_counting():
    pdf = make_pdf([])
    assert count_revisions(pdf) == 1
    assert count_revisions(pdf + b"\n1 0 obj\n<<>>\nendobj\nxref\n0 0\ntrailer\n<<>>\n%%EOF\n") == 2
    assert count_revisions(b"%PDF-1.7\n<</Linearized 1>>\n%%EOF\n...\n%%EOF") == 1


def test_document_signals():
    meta = {"Creator": "Adobe Photoshop 25", "Producer": "Acrobat", "CreationDate": "D:20260101090000Z", "ModDate": "D:20260305120000+01'00'"}
    info, flags = document_signals(b"%PDF-1.7 ... %%EOF ... %%EOF", meta)
    assert {"pdf_editor", "incremental_updates", "pdf_modified"} <= codes(flags)
    assert info["revisions"] == 2 and info["created"].startswith("2026-01-01")
    _, flags = document_signals(b"%PDF %%EOF", {"Producer": "Midjourney export"})
    assert "pdf_ai_tool" in codes(flags)
    _, flags = document_signals(b"%PDF %%EOF", {})
    assert codes(flags) == {"pdf_metadata_stripped"}


# ---------- API ----------

@pytest.fixture
def client(no_model):
    with TestClient(app) as c:
        yield c


def test_pdf_endpoint(client):
    pdf = make_pdf([photoshop_jpeg()], creator="Adobe Photoshop")
    r = client.post("/api/v1/analyze/pdf", files={"file": ("claim.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "pdf" and body["document"]["pages"] == 1
    assert "pdf_editor" in codes(body["document_flags"])
    # a claim PDF made in Photoshop is headlined as edited, even if its images look clean
    assert body["overall_verdict"] == "manipulated" and body["overall_basis"] == "document"
    item = body["items"][0]
    assert item["source"] == "embedded" and item["embedded_format"] == "JPEG"
    assert "editing_software" in codes(item["report"]["signals"]["metadata"]["flags"])
    assert item["report"]["images"]["original"].startswith("data:image/jpeg")


def test_pdf_endpoint_rendered_pages_are_labelled(client):
    body = client.post("/api/v1/analyze/pdf", files={"file": ("text.pdf", make_pdf([]), "application/pdf")}).json()
    assert body["extraction"]["mode"] == "rendered_pages"
    assert body["overall_basis"] == "images"  # no tool flags: revisions alone never escalate
    assert body["items"][0]["report"]["findings"][0]["signal"] == "pdf"


def test_pdf_endpoint_rejects_non_pdf(client):
    r = client.post("/api/v1/analyze/pdf", files={"file": ("x.pdf", encode(natural_image()), "application/pdf")})
    assert r.status_code == 415


def test_single_image_endpoint_points_pdfs_elsewhere(client):
    r = client.post("/api/v1/analyze", files={"file": ("doc.pdf", make_pdf([]), "application/pdf")})
    assert r.status_code == 415 and "/api/v1/analyze/pdf" in r.json()["detail"]


def test_batch_expands_pdfs(client):
    pdf = make_pdf([photoshop_jpeg(), encode(natural_image(300, 200, 5), "PNG")])
    files = [("files", ("claim.pdf", pdf, "application/pdf")), ("files", ("x.jpg", encode(natural_image()), "image/jpeg"))]
    body = client.post("/api/v1/analyze/batch", files=files).json()
    assert body["count"] == 3
    assert any(i["filename"].startswith("claim.pdf · Page 1") for i in body["items"])
