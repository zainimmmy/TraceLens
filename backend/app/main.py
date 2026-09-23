"""TraceLens REST API (F7). Interactive docs at /docs."""

from __future__ import annotations

import io
import logging
import zipfile
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import PurePosixPath

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.formparsers import MultiPartParser

from . import __version__
from .config import settings
from .forensics.classifier import classifier_status, get_classifier
from .imaging import ImageValidationError
from .pdf_document import analyze_pdf, extract_pdf, is_pdf
from .pipeline import DISCLAIMER, analyze_bytes
from .report_pdf import build_pdf
from .schemas import AnalysisReport, BatchItem, BatchReport, Health, PdfReport

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tracelens")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
UPLOAD_PATHS = ("/api/v1/analyze", "/api/v1/analyze/pdf", "/api/v1/analyze/batch", "/api/v1/report/pdf")
MAX_REQUEST_BYTES = settings.max_batch_bytes + 1024 * 1024
MAX_PDF_REQUEST_BYTES = 8 * 1024 * 1024

# Keep multipart uploads in RAM (never spooled to a temp file on disk). The middleware below
# rejects anything larger than this before the parser runs.
MultiPartParser.spool_max_size = MAX_REQUEST_BYTES
MultiPartParser.max_part_size = MAX_REQUEST_BYTES


def client_ip(request: Request) -> str:
    """Client address for rate limiting. Trusts only the proxies we are told about."""
    hops = settings.trusted_proxy_hops
    forwarded = request.headers.get("x-forwarded-for")
    if hops > 0 and forwarded:
        chain = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(chain) >= hops:
            return chain[-hops]
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip, headers_enabled=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_classifier()  # load (or download) the model once, not on the first request
    yield


app = FastAPI(
    title="TraceLens API",
    version=__version__,
    description=(
        "Explainable AI image and manipulation forensics. Upload an image to get a verdict, a calibrated "
        "confidence, a Grad-CAM heatmap, Error Level Analysis and noise maps, a metadata and C2PA provenance "
        "report, and a plain-English summary. Images are processed in memory and never stored.\n\n"
        f"**{DISCLAIMER}**"
    ),
    license_info={"name": "MIT"},
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limited(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Too many requests ({exc.detail}). Please wait a minute and try again."},
        headers={"Retry-After": "60"},
    )


@app.middleware("http")
async def guard_and_harden(request: Request, call_next):
    if request.method == "POST" and request.url.path in UPLOAD_PATHS:
        length = request.headers.get("content-length")
        if length is None:
            return JSONResponse(status_code=411, content={"detail": "A Content-Length header is required."})
        limit = MAX_PDF_REQUEST_BYTES if request.url.path.endswith("/pdf") else MAX_REQUEST_BYTES
        if not length.isdigit() or int(length) > limit:
            return JSONResponse(status_code=413, content={"detail": "The upload is too large."})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/api/v1/health", response_model=Health, tags=["system"])
def health() -> dict:
    """Health check for uptime monitoring, CI and keeping the free Space warm."""
    return {
        "status": "ok",
        "version": __version__,
        "classifier": classifier_status(),
        "llm_summaries": bool(settings.gemini_api_key),
    }


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"'{upload.filename}' is larger than {limit // (1024 * 1024)} MB.")
    return data


@app.post("/api/v1/analyze", response_model=AnalysisReport, tags=["analysis"])
@limiter.limit(settings.rate_limit_analyze)
async def analyze(request: Request, response: Response, file: UploadFile = File(..., description="JPG, PNG or WEBP, up to 10 MB")) -> dict:
    """Analyse one image and return the full forensic report."""
    data = await _read_limited(file, settings.max_upload_bytes)
    if is_pdf(data):
        raise HTTPException(status_code=415, detail="This is a PDF. Send PDFs to /api/v1/analyze/pdf.")
    try:
        return await run_in_threadpool(analyze_bytes, data, file.filename)
    except ImageValidationError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception:
        log.exception("Analysis failed")  # never log image bytes
        raise HTTPException(status_code=500, detail="Analysis failed. Please try a different image.") from None


@app.post("/api/v1/analyze/pdf", response_model=PdfReport, tags=["analysis"])
@limiter.limit(settings.rate_limit_pdf_analyze)
async def analyze_pdf_endpoint(
    request: Request, response: Response, file: UploadFile = File(..., description="A PDF, up to 20 MB")
) -> dict:
    """Analyse every embedded image in a PDF (original bytes, not re-rendered) plus the PDF's own
    integrity signals: saved revisions, creation vs modification date, and producing software.
    PDFs without embedded images are rendered page by page instead."""
    data = await _read_limited(file, settings.max_pdf_bytes)
    try:
        return await run_in_threadpool(analyze_pdf, data, file.filename)
    except ImageValidationError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception:
        log.exception("PDF analysis failed")
        raise HTTPException(status_code=500, detail="PDF analysis failed. Please try a different file.") from None


def _expand_pdf(name: str, data: bytes) -> list[tuple[str, bytes]]:
    try:
        _, _, images, _ = extract_pdf(data)
    except ImageValidationError as exc:
        raise HTTPException(status_code=415, detail=f"'{name}': {exc}") from exc
    return [(f"{name} · {img.name}", img.data) for img in images]


def _expand_zip(name: str, data: bytes) -> list[tuple[str, bytes]]:
    """Read images out of a zip entirely in memory, with zip-bomb limits."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=415, detail=f"'{name}' is not a valid zip file.") from exc
    out, total = [], 0
    with zf:
        for info in zf.infolist():
            path = PurePosixPath(info.filename)
            if info.is_dir() or path.name.startswith(".") or "__MACOSX" in path.parts:
                continue
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if len(out) >= settings.max_batch_files:
                break
            with zf.open(info) as fh:
                # Bounded read: never trust the declared size. Oversized entries are
                # reported per file by load_image.
                content = fh.read(settings.max_upload_bytes + 1)
            total += len(content)
            if total > settings.max_batch_bytes:
                raise HTTPException(status_code=413, detail="The zip expands to more data than a batch allows.")
            out.append((path.name, content))
    return out


@app.post("/api/v1/analyze/batch", response_model=BatchReport, tags=["analysis"])
@limiter.limit(settings.rate_limit_batch)
async def analyze_batch(
    request: Request,
    response: Response,
    files: list[UploadFile] = File(..., description="Up to 20 images, or zip / PDF files containing images"),
) -> dict:
    """Analyse up to 20 images and return a summary table (no heatmaps, template summaries)."""
    items: list[tuple[str, bytes]] = []
    for upload in files:
        name = upload.filename or "upload"
        if name.lower().endswith(".zip"):
            items += _expand_zip(name, await _read_limited(upload, settings.max_batch_bytes))
        elif name.lower().endswith(".pdf"):
            items += await run_in_threadpool(_expand_pdf, name, await _read_limited(upload, settings.max_pdf_bytes))
        else:
            items.append((name, await _read_limited(upload, settings.max_upload_bytes)))
    if not items:
        raise HTTPException(status_code=422, detail="No JPG, PNG, WEBP or PDF images were found in the upload.")
    if len(items) > settings.max_batch_files:
        raise HTTPException(status_code=422, detail=f"A batch can contain at most {settings.max_batch_files} images.")

    def run() -> list[BatchItem]:
        results = []
        for name, data in items:
            try:
                r = analyze_bytes(data, name, with_images=False, allow_llm=False)
                results.append(BatchItem(filename=name, **{k: r[k] for k in (
                    "verdict", "verdict_label", "confidence", "ai_probability", "manipulation_score", "summary")}))
            except ImageValidationError as exc:
                results.append(BatchItem(filename=name, error=str(exc)))
            except Exception:
                log.exception("Batch item failed")
                results.append(BatchItem(filename=name, error="Analysis failed."))
        return results

    results = await run_in_threadpool(run)
    counts = Counter(r.verdict or "error" for r in results)
    return {"count": len(results), "counts_by_verdict": dict(counts), "items": results, "disclaimer": DISCLAIMER}


@app.post("/api/v1/report/pdf", tags=["reports"], response_class=Response,
          responses={200: {"content": {"application/pdf": {}}, "description": "The PDF report"}})
@limiter.limit(settings.rate_limit_pdf)
async def report_pdf(request: Request, response: Response, report: dict) -> Response:
    """Build a downloadable PDF from a report JSON returned by `/api/v1/analyze`.

    This is a POST (the PRD sketch said GET) because the report travels in the request body;
    the server keeps no copy of any report, so there is nothing to GET by id.
    """
    if "verdict" not in report:
        raise HTTPException(status_code=422, detail="This does not look like a TraceLens report.")
    pdf = await run_in_threadpool(build_pdf, report)
    safe = "".join(c for c in str(report.get("filename") or "image") if c.isalnum() or c in "-_.")[:60] or "image"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="tracelens-report-{safe}.pdf"'})
