"""Runtime settings, read from environment variables.

Every value has a safe default so the API boots with zero configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    # Upload limits (PRD: JPG, PNG, WEBP up to 10 MB)
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
    max_batch_files: int = int(os.getenv("MAX_BATCH_FILES", "20"))
    max_batch_bytes: int = int(os.getenv("MAX_BATCH_MB", "60")) * 1024 * 1024
    max_image_pixels: int = int(os.getenv("MAX_IMAGE_PIXELS", str(50_000_000)))
    # PDFs: analyse up to this many embedded images per document
    max_pdf_bytes: int = int(os.getenv("MAX_PDF_MB", "20")) * 1024 * 1024
    max_pdf_images: int = int(os.getenv("MAX_PDF_IMAGES", "10"))

    # Model
    model_dir: Path = Path(os.getenv("MODEL_DIR", Path(__file__).resolve().parent.parent / "models"))
    model_file: str = os.getenv("MODEL_FILE", "tracelens.onnx")
    meta_file: str = os.getenv("MODEL_META_FILE", "model_meta.json")
    # Optional: pull the model from the Hugging Face Model Hub on startup
    hf_model_repo: str | None = os.getenv("HF_MODEL_REPO") or None
    # Pin to a commit hash in production so a pushed model cannot silently change behaviour.
    hf_model_revision: str = os.getenv("HF_MODEL_REVISION", "main")
    hf_token: str | None = os.getenv("HF_TOKEN") or None

    # Verdict bands (PRD: "inconclusive" band between 40% and 60%)
    inconclusive_low: float = float(os.getenv("INCONCLUSIVE_LOW", "0.40"))
    inconclusive_high: float = float(os.getenv("INCONCLUSIVE_HIGH", "0.60"))

    # LLM summary (Gemini free tier, template fallback)
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_timeout_s: float = float(os.getenv("GEMINI_TIMEOUT_S", "8"))

    # Web
    cors_origins: list[str] = field(
        default_factory=lambda: _env_list("CORS_ORIGINS", "http://localhost:3000")
    )
    rate_limit_analyze: str = os.getenv("RATE_LIMIT_ANALYZE", "12/minute")
    rate_limit_batch: str = os.getenv("RATE_LIMIT_BATCH", "3/minute")
    rate_limit_pdf_analyze: str = os.getenv("RATE_LIMIT_PDF_ANALYZE", "4/minute")
    rate_limit_pdf: str = os.getenv("RATE_LIMIT_PDF", "20/minute")
    # Number of reverse proxies in front of the app that append to X-Forwarded-For.
    # Hugging Face Spaces sits behind one. 0 = use the socket address.
    trusted_proxy_hops: int = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))

    # Size of the preview / heatmap images returned in the report
    preview_max_side: int = int(os.getenv("PREVIEW_MAX_SIDE", "640"))


settings = Settings()
