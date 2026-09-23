"""Datasets and augmentations.

Training augmentations simulate what happens to images shared online (JPEG re-compression,
down-scaling, cropping, mild blur) so the classifier does not rely on fragile pixel-level
artifacts that disappear after one upload to social media.
"""

from __future__ import annotations

import csv
import io
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from .common import LABELS  # noqa: F401  (also puts backend/ on sys.path)
from app.forensics.classifier import IMAGENET_MEAN, IMAGENET_STD, ModelMeta, resize_shorter_side, to_tensor  # noqa: E402


def read_manifest(path: Path, splits: set[str], generators: set[str] | None = None, exclude_generators: set[str] | None = None) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["split"] not in splits or r["label"] not in ("real", "ai"):
                continue
            # Cross-generator protocol: filter AI images by generator; real images are always kept.
            if r["label"] == "ai":
                if generators and r["generator"] not in generators:
                    continue
                if exclude_generators and r["generator"] in exclude_generators:
                    continue
            rows.append(r)
    return rows


def jpeg_compress(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def downscale(img: Image.Image, factor: float) -> Image.Image:
    w, h = img.size
    return img.resize((max(32, int(w * factor)), max(32, int(h * factor))), Image.Resampling.BILINEAR)


class TrainTransform:
    def __init__(self, size: int = 224, p_jpeg: float = 0.5, p_resize: float = 0.3, p_blur: float = 0.1):
        self.size, self.p_jpeg, self.p_resize, self.p_blur = size, p_jpeg, p_resize, p_blur

    def __call__(self, img: Image.Image) -> np.ndarray:
        img = img.convert("RGB")
        if random.random() < self.p_resize:
            img = downscale(img, random.uniform(0.5, 1.0))
        if random.random() < self.p_blur:
            img = img.filter(ImageFilter.GaussianBlur(random.uniform(0.2, 1.2)))
        if random.random() < self.p_jpeg:
            img = jpeg_compress(img, random.randint(30, 100))
        # random crop at a random scale, same resize rule as serving
        img = resize_shorter_side(img, int(self.size * random.uniform(1.0, 1.5)))
        w, h = img.size
        x, y = random.randint(0, w - self.size), random.randint(0, h - self.size)
        img = img.crop((x, y, x + self.size, y + self.size))
        if random.random() < 0.5:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        return to_tensor(img, IMAGENET_MEAN, IMAGENET_STD)


class EvalTransform:
    """Single center crop with the serving resize rule (the API additionally averages extra crops)."""

    def __init__(self, size: int = 224):
        self.meta = ModelMeta(input_size=size)

    def __call__(self, img: Image.Image) -> np.ndarray:
        img = resize_shorter_side(img.convert("RGB"), self.meta.input_size)
        w, h = img.size
        s = self.meta.input_size
        x, y = (w - s) // 2, (h - s) // 2
        return to_tensor(img.crop((x, y, x + s, y + s)), IMAGENET_MEAN, IMAGENET_STD)


def make_dataset(rows: list[dict], transform):
    import torch
    from torch.utils.data import Dataset

    class ImageDataset(Dataset):
        def __len__(self):
            return len(rows)

        def __getitem__(self, i):
            r = rows[i]
            try:
                with Image.open(r["path"]) as im:
                    x = transform(im)
            except Exception:  # unreadable file: substitute a neighbour instead of crashing a long run
                return self[(i + 1) % len(rows)]
            return torch.from_numpy(np.ascontiguousarray(x)), torch.tensor(float(r["label"] == "ai"))

    return ImageDataset()
