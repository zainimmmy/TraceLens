from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.config import settings
from app.forensics import classifier as clf_module
from app.forensics.frequency import _load_baseline

TINY_INPUT = 64


def natural_image(w: int = 320, h: int = 240, seed: int = 0) -> np.ndarray:
    """A photo-like test image: smooth gradients, some shapes, and mild sensor-like noise."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    base = np.stack([
        100 + 80 * np.sin(xx / 37.0) * np.cos(yy / 53.0),
        120 + 60 * np.cos(xx / 29.0 + yy / 41.0),
        90 + 70 * np.sin((xx + yy) / 61.0),
    ], axis=-1)
    base[h // 4 : h // 2, w // 5 : w // 3] += 40
    base += rng.normal(0, 4, size=base.shape)
    return np.clip(base, 0, 255).astype(np.uint8)


def encode(rgb: np.ndarray, fmt: str = "JPEG", **kwargs) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, fmt, **kwargs)
    return buf.getvalue()


def build_tiny_onnx(path: Path, input_size: int = TINY_INPUT) -> None:
    """A tiny ONNX model that follows the TraceLens contract (``logit`` + ``cam``).

    Bright images produce a high AI logit, dark images a low one, so tests can steer it.
    """
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    stride = input_size // 8
    conv_w = np.full((4, 3, stride, stride), 1.0 / (3 * stride * stride), dtype=np.float32)
    head_w = np.full((4, 1), 2.0, dtype=np.float32)
    head_b = np.array([-1.0], dtype=np.float32)
    inits = [
        numpy_helper.from_array(conv_w, "conv_w"),
        numpy_helper.from_array(head_w, "head_w"),
        numpy_helper.from_array(head_b, "head_b"),
        numpy_helper.from_array(head_w.reshape(1, 4, 1, 1), "cam_w"),
        numpy_helper.from_array(np.array([1], dtype=np.int64), "axis1"),
    ]
    nodes = [
        helper.make_node("Conv", ["image", "conv_w"], ["conv"], strides=[stride, stride]),
        helper.make_node("Relu", ["conv"], ["feats"]),
        helper.make_node("GlobalAveragePool", ["feats"], ["pooled"]),
        helper.make_node("Flatten", ["pooled"], ["flat"]),
        helper.make_node("MatMul", ["flat", "head_w"], ["mm"]),
        helper.make_node("Add", ["mm", "head_b"], ["logit2d"]),
        helper.make_node("Squeeze", ["logit2d", "axis1"], ["logit"]),
        helper.make_node("Mul", ["feats", "cam_w"], ["weighted"]),
        helper.make_node("ReduceSum", ["weighted", "axis1"], ["cam"], keepdims=0),
    ]
    graph = helper.make_graph(
        nodes, "tiny_tracelens",
        [helper.make_tensor_value_info("image", TensorProto.FLOAT, ["N", 3, input_size, input_size])],
        [
            helper.make_tensor_value_info("logit", TensorProto.FLOAT, ["N"]),
            helper.make_tensor_value_info("cam", TensorProto.FLOAT, ["N", 8, 8]),
        ],
        inits,
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    onnx.save(model, str(path))


@pytest.fixture
def model_dir(tmp_path, monkeypatch):
    """Point the app at a temp model dir containing the tiny ONNX model."""
    build_tiny_onnx(tmp_path / "tracelens.onnx")
    (tmp_path / "model_meta.json").write_text(json.dumps({
        "name": "tiny_test_model", "input_size": TINY_INPUT, "temperature": 1.0, "metrics": {"auc": 0.5},
    }))
    monkeypatch.setattr(settings, "model_dir", tmp_path)
    clf_module.reset_for_tests()
    _load_baseline.cache_clear()
    yield tmp_path
    clf_module.reset_for_tests()
    _load_baseline.cache_clear()


@pytest.fixture
def no_model(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "model_dir", tmp_path / "empty")
    monkeypatch.setattr(settings, "hf_model_repo", None)
    clf_module.reset_for_tests()
    _load_baseline.cache_clear()
    yield
    clf_module.reset_for_tests()
    _load_baseline.cache_clear()


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    from app.main import limiter

    limiter.reset()
    yield
