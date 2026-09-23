"""F1 + F2: the fine-tuned CNN classifier (ONNX Runtime) and its class activation heatmap.

Model contract (produced by ``training/tracelens_train/export_onnx.py``):

* input ``image``: float32 ``[N, 3, S, S]``, normalised with ``mean``/``std`` from the meta file
* output ``logit``: float32 ``[N]``, positive means "AI generated"
* output ``cam``: float32 ``[N, h, w]``, the class activation map for the AI class

The CAM is computed inside the exported graph as ``sum_k w_k * A_k`` over the last conv
feature maps. For a network whose head is global-average-pool + linear (EfficientNet,
ResNet), this is exactly Grad-CAM up to a constant factor, because the gradient of the
logit with respect to each feature map is the constant ``w_k / (h * w)``. That lets us serve
Grad-CAM on CPU with ONNX Runtime and no PyTorch.

``model_meta.json`` next to the model holds the input size, normalisation, the temperature
used for calibration and the published evaluation metrics.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..config import settings

log = logging.getLogger(__name__)

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
MAX_CROPS = 3


@dataclass
class ModelMeta:
    name: str = "efficientnet_b0_v1"
    input_size: int = 224
    mean: tuple[float, float, float] = IMAGENET_MEAN
    std: tuple[float, float, float] = IMAGENET_STD
    temperature: float = 1.0
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> ModelMeta:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            name=data.get("name", cls.name),
            input_size=int(data.get("input_size", cls.input_size)),
            mean=tuple(data.get("mean", IMAGENET_MEAN)),
            std=tuple(data.get("std", IMAGENET_STD)),
            temperature=float(data.get("temperature", 1.0)),
            metrics=data.get("metrics", {}),
        )


def resize_shorter_side(img: Image.Image, size: int) -> Image.Image:
    """Resize so the shorter side equals ``size``. Shared with training (no train/serve skew)."""
    w, h = img.size
    scale = size / min(w, h)
    new = (max(size, round(w * scale)), max(size, round(h * scale)))
    return img.resize(new, Image.Resampling.BICUBIC)


def crop_boxes(width: int, height: int, size: int, max_crops: int = MAX_CROPS) -> list[tuple[int, int]]:
    """Top-left corners of square crops that together cover the long axis of the image."""
    long_side = max(width, height)
    n = min(max_crops, max(1, math.ceil(long_side / size - 0.15)))
    if n == 1:
        offsets = [(long_side - size) // 2]
    else:
        offsets = [round(i * (long_side - size) / (n - 1)) for i in range(n)]
    return [(o, 0) if width >= height else (0, o) for o in offsets]


def to_tensor(img: Image.Image, mean, std) -> np.ndarray:
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    arr = (arr - np.asarray(mean, dtype=np.float32)) / np.asarray(std, dtype=np.float32)
    return arr.transpose(2, 0, 1)


def preprocess(img: Image.Image, meta: ModelMeta) -> tuple[np.ndarray, list[tuple[int, int]], tuple[int, int]]:
    """Return a batch of normalised crops, their offsets, and the resized image size."""
    resized = resize_shorter_side(img.convert("RGB"), meta.input_size)
    w, h = resized.size
    s = meta.input_size
    boxes = crop_boxes(w, h, s)
    batch = np.stack([to_tensor(resized.crop((x, y, x + s, y + s)), meta.mean, meta.std) for x, y in boxes])
    return batch.astype(np.float32), boxes, (w, h)


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


class Classifier:
    def __init__(self, model_path: Path, meta_path: Path):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        self.meta = ModelMeta.load(meta_path)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.has_cam = "cam" in self.output_names

    def predict(self, img: Image.Image) -> dict[str, Any]:
        batch, boxes, (rw, rh) = preprocess(img, self.meta)
        outputs = dict(zip(self.output_names, self.session.run(None, {self.input_name: batch}), strict=True))
        logits = np.asarray(outputs["logit"], dtype=np.float32).reshape(-1)
        # Temperature scaling (calibration), then average the per-crop probabilities.
        probs = sigmoid(logits / max(self.meta.temperature, 1e-3))
        ai_probability = float(np.mean(probs))

        heat = None
        if self.has_cam:
            heat = self._stitch_cam(np.asarray(outputs["cam"], dtype=np.float32), boxes, rw, rh)

        return {
            "ai_probability": round(ai_probability, 4),
            "crop_probabilities": [round(float(p), 4) for p in probs],
            "model": self.meta.name,
            "heat": heat,
        }

    def _stitch_cam(self, cams: np.ndarray, boxes, rw: int, rh: int) -> np.ndarray:
        import cv2

        s = self.meta.input_size
        acc = np.zeros((rh, rw), dtype=np.float32)
        weight = np.zeros((rh, rw), dtype=np.float32)
        for cam, (x, y) in zip(cams, boxes, strict=True):
            up = cv2.resize(cam, (s, s), interpolation=cv2.INTER_LINEAR)
            acc[y : y + s, x : x + s] += up
            weight[y : y + s, x : x + s] += 1
        acc = acc / np.maximum(weight, 1)
        acc = np.maximum(acc, 0)  # ReLU, as in Grad-CAM: keep evidence *for* the AI class
        peak = float(acc.max())
        return acc / peak if peak > 1e-8 else acc


_lock = threading.Lock()
_classifier: Classifier | None = None
_load_error: str | None = None
_loaded = False


def _maybe_download() -> None:
    if not settings.hf_model_repo:
        return
    target = settings.model_dir / settings.model_file
    if target.exists():
        return
    try:
        from huggingface_hub import hf_hub_download

        settings.model_dir.mkdir(parents=True, exist_ok=True)
        for name in (settings.model_file, settings.meta_file):
            hf_hub_download(
                repo_id=settings.hf_model_repo,
                filename=name,
                local_dir=settings.model_dir,
                revision=settings.hf_model_revision,
                token=settings.hf_token,
            )
        log.info("Downloaded model from %s", settings.hf_model_repo)
    except Exception as exc:  # network or auth failure: run without the classifier
        log.warning("Could not download model from %s: %s", settings.hf_model_repo, exc)


def get_classifier() -> Classifier | None:
    """Lazy, thread-safe singleton. Returns None when no model is available."""
    global _classifier, _load_error, _loaded
    if _loaded:
        return _classifier
    with _lock:
        if _loaded:
            return _classifier
        _maybe_download()
        model_path = settings.model_dir / settings.model_file
        if model_path.exists():
            try:
                _classifier = Classifier(model_path, settings.model_dir / settings.meta_file)
                log.info("Loaded classifier %s", _classifier.meta.name)
            except Exception as exc:
                _load_error = f"Model failed to load: {exc}"
                log.exception("Classifier failed to load")
        else:
            _load_error = "No trained model is installed on this server."
        _loaded = True
        return _classifier


def classifier_status() -> dict[str, Any]:
    clf = get_classifier()
    if clf is None:
        return {"loaded": False, "reason": _load_error}
    return {"loaded": True, "model": clf.meta.name, "metrics": clf.meta.metrics}


def reset_for_tests() -> None:
    global _classifier, _load_error, _loaded
    with _lock:
        _classifier, _load_error, _loaded = None, None, False
