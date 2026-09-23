"""Image decoding, validation and small helpers shared by the forensic modules.

Uploaded bytes live only in memory. Nothing in this module touches disk.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import settings

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

# Guard against decompression bombs (a tiny file that expands to gigapixels).
Image.MAX_IMAGE_PIXELS = settings.max_image_pixels


class ImageValidationError(ValueError):
    """Raised when an upload is not an image we accept. Message is user-safe."""


@dataclass
class LoadedImage:
    raw: bytes  # original bytes, needed for metadata and ELA
    format: str  # JPEG / PNG / WEBP
    mime: str
    pil: Image.Image  # the decoded file as-is (first frame, original mode)
    rgb: np.ndarray  # H x W x 3 uint8, EXIF orientation applied
    width: int
    height: int


def load_image(data: bytes) -> LoadedImage:
    if not data:
        raise ImageValidationError("The file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise ImageValidationError(
            f"The file is larger than {settings.max_upload_bytes // (1024 * 1024)} MB."
        )
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()  # structural check without full decode
        pil = Image.open(io.BytesIO(data))
        fmt = (pil.format or "").upper()
        if fmt not in ALLOWED_FORMATS:
            raise ImageValidationError("Only JPG, PNG and WEBP images are supported.")
        pil.seek(0)  # animated WEBP/PNG: analyse the first frame
        pil.load()
    except ImageValidationError:
        raise
    except Image.DecompressionBombError as exc:
        raise ImageValidationError("The image dimensions are too large to analyse.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageValidationError("The file is not a readable image.") from exc

    oriented = ImageOps.exif_transpose(pil.copy())
    rgb = np.asarray(oriented.convert("RGB"), dtype=np.uint8)
    h, w = rgb.shape[:2]
    if min(h, w) < 32:
        raise ImageValidationError("The image is too small to analyse (minimum 32 px).")

    return LoadedImage(
        raw=data,
        format=fmt,
        mime=ALLOWED_FORMATS[fmt],
        pil=pil,
        rgb=rgb,
        width=w,
        height=h,
    )


def resize_max_side(rgb: np.ndarray, max_side: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    scale = max_side / max(h, w)
    if scale >= 1:
        return rgb
    return cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)


def to_png_data_url(rgb: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    if not ok:  # pragma: no cover - cv2 only fails on invalid arrays
        raise RuntimeError("PNG encoding failed")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def to_jpeg_data_url(rgb: np.ndarray, quality: int = 85) -> str:
    ok, buf = cv2.imencode(
        ".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality]
    )
    if not ok:  # pragma: no cover
        raise RuntimeError("JPEG encoding failed")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def heat_overlay(rgb: np.ndarray, heat: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """Blend a [0, 1] heat map over an RGB image using the JET colour map."""
    h, w = rgb.shape[:2]
    heat = cv2.resize(heat.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    heat_u8 = np.uint8(np.clip(heat, 0, 1) * 255)
    colored = cv2.cvtColor(cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)
    return cv2.addWeighted(rgb, 1 - alpha, colored, alpha, 0)


def normalize01(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32)
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-8:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)
