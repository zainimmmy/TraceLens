"""Turn a block-level anomaly mask into a short list of bounding boxes."""

from __future__ import annotations

import cv2
import numpy as np


def mask_to_regions(
    mask: np.ndarray,
    block: int,
    img_w: int,
    img_h: int,
    min_blocks: int = 4,
    max_regions: int = 5,
) -> list[dict]:
    """``mask`` is a boolean grid where each cell covers ``block`` x ``block`` pixels.

    Returns the largest connected regions as pixel boxes in image coordinates, with a
    ``share`` field giving the fraction of the image each one covers.
    """
    if not mask.any():
        return []
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    regions = []
    for i in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area < min_blocks:
            continue
        px, py = x * block, y * block
        pw, ph = min(w * block, img_w - px), min(h * block, img_h - py)
        regions.append(
            {
                "x": px,
                "y": py,
                "width": pw,
                "height": ph,
                "share": round(area * block * block / float(img_w * img_h), 4),
            }
        )
    regions.sort(key=lambda r: r["share"], reverse=True)
    return regions[:max_regions]


def robust_z(values: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
    """Median/MAD z-score, robust to the outliers we are trying to find."""
    sample = values[valid] if valid is not None else values.ravel()
    if sample.size == 0:
        return np.zeros_like(values, dtype=np.float32)
    med = float(np.median(sample))
    mad = float(np.median(np.abs(sample - med))) * 1.4826
    mad = max(mad, 1e-6)
    return ((values - med) / mad).astype(np.float32)
