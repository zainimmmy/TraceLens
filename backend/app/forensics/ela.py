"""F3a: Error Level Analysis.

Re-compress the image as JPEG at a known quality and measure how much each area changes.
Areas that were pasted in or edited after the last save often recompress differently from
the rest of the picture. ELA is most meaningful for JPEG uploads; for PNG and WEBP we still
compute it but mark its reliability as low.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from ..imaging import normalize01
from .regions import mask_to_regions, robust_z

ELA_QUALITY = 90
BLOCK = 16
MAX_PIXELS = 16_000_000
Z_THRESHOLD = 4.0
MIN_ERROR = 4.0  # ignore regions whose mean error is tiny in absolute terms


def _prepare(rgb: np.ndarray) -> tuple[np.ndarray, bool]:
    h, w = rgb.shape[:2]
    if h * w <= MAX_PIXELS:
        return rgb, False
    scale = (MAX_PIXELS / (h * w)) ** 0.5
    img = Image.fromarray(rgb).resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    return np.asarray(img), True


def analyze_ela(rgb: np.ndarray, source_format: str) -> dict:
    work, downscaled = _prepare(rgb)
    h, w = work.shape[:2]

    buf = io.BytesIO()
    Image.fromarray(work).save(buf, "JPEG", quality=ELA_QUALITY)
    resaved = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))
    diff = np.abs(work.astype(np.int16) - resaved.astype(np.int16)).max(axis=2).astype(np.float32)

    gh, gw = h // BLOCK, w // BLOCK
    blocks = diff[: gh * BLOCK, : gw * BLOCK].reshape(gh, BLOCK, gw, BLOCK).mean(axis=(1, 3))
    z = robust_z(blocks)
    mask = (z > Z_THRESHOLD) & (blocks > MIN_ERROR)

    # A region covering most of the frame is a global property, not a local edit.
    regions = [r for r in mask_to_regions(mask, BLOCK, w, h) if r["share"] < 0.5]
    if downscaled:
        sx, sy = rgb.shape[1] / w, rgb.shape[0] / h
        for r in regions:
            r.update(x=round(r["x"] * sx), y=round(r["y"] * sy), width=round(r["width"] * sx), height=round(r["height"] * sy))

    outlier_energy = float(blocks[mask].sum()) / max(float(blocks.sum()), 1e-6)
    # Visualisation: amplify with a robust ceiling so a few hot pixels do not wash it out.
    ceiling = max(float(np.percentile(diff, 99.5)), 1.0)
    vis = normalize01(np.clip(diff / ceiling, 0, 1))

    return {
        "reliability": "normal" if source_format == "JPEG" else "low",
        "quality_used": ELA_QUALITY,
        "max_error_level": int(diff.max()),
        "mean_error_level": round(float(diff.mean()), 2),
        "suspicious_regions": len(regions),
        "regions": regions,
        "outlier_energy_share": round(outlier_energy, 4),
        "map": vis,
    }
