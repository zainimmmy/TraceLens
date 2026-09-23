"""F3b: noise residual consistency.

A camera sensor leaves a fairly uniform noise pattern across a photo. We strip the image
content with a median filter, measure the local noise level in blocks, and flag blocks whose
noise is far from the rest of the image. Pasted or generated patches tend to be smoother or
noisier than their surroundings.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..imaging import normalize01
from .regions import mask_to_regions, robust_z

BLOCK = 32
MAX_SIDE = 2048
Z_THRESHOLD = 3.5


def analyze_noise(rgb: np.ndarray) -> dict:
    h0, w0 = rgb.shape[:2]
    scale = min(1.0, MAX_SIDE / max(h0, w0))
    work = rgb if scale == 1.0 else cv2.resize(rgb, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(work, cv2.COLOR_RGB2GRAY)
    residual = gray.astype(np.float32) - cv2.medianBlur(gray, 3).astype(np.float32)

    h, w = gray.shape
    gh, gw = h // BLOCK, w // BLOCK
    if gh < 2 or gw < 2:
        return {"inconsistent_blocks_share": 0.0, "suspicious_regions": 0, "regions": [], "map": np.zeros((h, w), np.float32)}

    res_blocks = residual[: gh * BLOCK, : gw * BLOCK].reshape(gh, BLOCK, gw, BLOCK)
    gray_blocks = gray[: gh * BLOCK, : gw * BLOCK].reshape(gh, BLOCK, gw, BLOCK).astype(np.float32)
    noise_std = res_blocks.std(axis=(1, 3))
    content_std = gray_blocks.std(axis=(1, 3))
    brightness = gray_blocks.mean(axis=(1, 3))

    # Flat, clipped or near-black blocks carry almost no sensor noise; exclude them from stats.
    valid = (content_std > 2.0) & (brightness > 12) & (brightness < 243)
    log_noise = np.log(noise_std + 1e-3)
    z = robust_z(log_noise, valid if valid.sum() >= 8 else None)
    mask = (np.abs(z) > Z_THRESHOLD) & valid

    regions = [r for r in mask_to_regions(mask, BLOCK, w, h, min_blocks=3) if r["share"] < 0.5]
    if scale != 1.0:
        for r in regions:
            r.update(x=round(r["x"] / scale), y=round(r["y"] / scale), width=round(r["width"] / scale), height=round(r["height"] / scale))

    heat = normalize01(np.clip(np.abs(z), 0, 8) * valid)
    heat = cv2.resize(heat, (gw * BLOCK, gh * BLOCK), interpolation=cv2.INTER_NEAREST)
    heat = cv2.copyMakeBorder(heat, 0, h - heat.shape[0], 0, w - heat.shape[1], cv2.BORDER_CONSTANT, value=0)
    heat = cv2.GaussianBlur(heat, (0, 0), BLOCK / 3)

    return {
        "median_noise_level": round(float(np.median(noise_std[valid])) if valid.any() else 0.0, 3),
        "inconsistent_blocks_share": round(float(mask.sum()) / max(int(valid.sum()), 1), 4),
        "suspicious_regions": len(regions),
        "regions": regions,
        "map": heat,
    }
