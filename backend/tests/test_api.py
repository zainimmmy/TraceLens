from __future__ import annotations

import io
import zipfile

import pytest
from conftest import encode, natural_image
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture
def client(model_dir):
    with TestClient(app) as c:
        yield c


def upload(client, data: bytes, name: str = "photo.jpg", mime: str = "image/jpeg"):
    return client.post("/api/v1/analyze", files={"file": (name, data, mime)})


def test_health(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["classifier"]["loaded"] is True
    assert body["llm_summaries"] is False


def test_root_redirects_to_docs(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/docs"


def test_openapi_lists_all_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/v1/analyze", "/api/v1/analyze/batch", "/api/v1/report/pdf", "/api/v1/health"} <= set(paths)


def test_analyze_returns_full_report(client):
    r = upload(client, encode(natural_image(640, 480)))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] in {"ai_generated", "manipulated", "real", "inconclusive"}
    assert 0 <= body["confidence"] <= 1
    assert body["signals"]["classifier"]["model"] == "tiny_test_model"
    assert body["signals"]["heatmap_url"].startswith("data:image/png;base64,")
    assert set(body["images"]) == {"original", "gradcam", "ela", "noise"}
    assert body["summary_source"] == "template"
    assert "probabilistic" in body["disclaimer"]
    assert r.headers["cache-control"] == "no-store"


def test_analyze_without_model_still_works(no_model):
    with TestClient(app) as c:
        body = upload(c, encode(natural_image())).json()
    assert body["signals"]["classifier"]["available"] is False
    assert body["images"]["gradcam"] is None


def test_analyze_rejects_non_image(client):
    r = upload(client, b"hello", "notes.txt", "text/plain")
    assert r.status_code == 415
    assert "not a readable image" in r.json()["detail"]


def test_analyze_rejects_large_upload(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 2000)
    r = upload(client, encode(natural_image(), "PNG"), "big.png", "image/png")
    assert r.status_code == 413


def test_request_size_guard(client):
    r = client.post("/api/v1/analyze", content=b"x", headers={"content-length": str(10**9), "content-type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413


def test_rate_limit(client):
    data = encode(natural_image(64, 64))
    codes = [upload(client, data).status_code for _ in range(14)]
    assert codes[0] == 200 and 429 in codes


def test_batch_with_files_and_zip(client):
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("a.png", encode(natural_image(), "PNG"))
        zf.writestr("__MACOSX/._a.png", b"junk")
        zf.writestr("readme.txt", b"ignored")
        zf.writestr("broken.jpg", b"not really a jpeg")
    files = [
        ("files", ("one.jpg", encode(natural_image()), "image/jpeg")),
        ("files", ("set.zip", zbuf.getvalue(), "application/zip")),
    ]
    r = client.post("/api/v1/analyze/batch", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 3
    names = {i["filename"]: i for i in body["items"]}
    assert set(names) == {"one.jpg", "a.png", "broken.jpg"}
    assert names["broken.jpg"]["error"] and names["one.jpg"]["verdict"]
    assert body["counts_by_verdict"]["error"] == 1


def test_batch_rejects_too_many(client, monkeypatch):
    monkeypatch.setattr(settings, "max_batch_files", 2)
    files = [("files", (f"{i}.jpg", encode(natural_image(64, 64)), "image/jpeg")) for i in range(3)]
    assert client.post("/api/v1/analyze/batch", files=files).status_code == 422


def test_batch_rejects_empty_zip(client):
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("notes.txt", b"no images here")
    r = client.post("/api/v1/analyze/batch", files=[("files", ("x.zip", zbuf.getvalue(), "application/zip"))])
    assert r.status_code == 422


def test_batch_rejects_bad_zip(client):
    r = client.post("/api/v1/analyze/batch", files=[("files", ("x.zip", b"PK-not-a-zip", "application/zip"))])
    assert r.status_code == 415


def test_pdf_from_report(client):
    report = upload(client, encode(natural_image(640, 480))).json()
    report["summary"] = "<b>markup</b> & <script>alert(1)</script> must be escaped"
    r = client.post("/api/v1/report/pdf", json=report)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert "attachment" in r.headers["content-disposition"]


def test_pdf_handles_hostile_input(client):
    report = {"verdict": "real", "filename": '../../etc/passwd"', "images": {"original": "data:image/png;base64,!!!"},
              "findings": ["not-a-dict", {"text": "x" * 10000}], "signals": "nope"}
    r = client.post("/api/v1/report/pdf", json=report)
    assert r.status_code == 200
    assert '"' not in r.headers["content-disposition"].split("filename=")[1].strip('"')
    assert "/" not in r.headers["content-disposition"]


def test_pdf_rejects_non_report(client):
    assert client.post("/api/v1/report/pdf", json={"hello": "world"}).status_code == 422


def test_client_ip_respects_proxy_hops(monkeypatch):
    from starlette.requests import Request

    from app.main import client_ip

    scope = {"type": "http", "headers": [(b"x-forwarded-for", b"6.6.6.6, 1.2.3.4")], "client": ("10.0.0.1", 1)}
    assert client_ip(Request(scope)) == "10.0.0.1"
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    assert client_ip(Request(scope)) == "1.2.3.4"  # the spoofable left entry is ignored
