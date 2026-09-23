"""Frequency-domain (FFT) features.

Many image generators leave periodic up-sampling artifacts that show up as peaks or an
unusual fall-off in the high-frequency part of the power spectrum. ``spectral_features`` is
the exact feature vector used by the week-2 logistic-regression baseline in
``training/tracelens_train/fft_baseline.py``; the backend reuses it so the baseline can act
as a lightweight fallback classifier when the CNN is not installed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from ..config import settings

FFT_SIZE = 256
N_BINS = 64
BASELINE_FILE = "fft_baseline.json"


def _center_crop_gray(rgb: np.ndarray, size: int = FFT_SIZE) -> np.ndarray:
    h, w = rgb.shape[:2]
    scale = size / min(h, w)
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    rgb = cv2.resize(rgb, (max(size, round(w * scale)), max(size, round(h * scale))), interpolation=interp)
    h, w = rgb.shape[:2]
    y, x = (h - size) // 2, (w - size) // 2
    return cv2.cvtColor(rgb[y : y + size, x : x + size], cv2.COLOR_RGB2GRAY).astype(np.float32)


def radial_profile(gray: np.ndarray, n_bins: int = N_BINS) -> np.ndarray:
    window = np.outer(np.hanning(gray.shape[0]), np.hanning(gray.shape[1]))
    spectrum = np.fft.fftshift(np.fft.fft2((gray - gray.mean()) * window))
    power = np.log1p(np.abs(spectrum) ** 2)
    h, w = power.shape
    yy, xx = np.indices(power.shape)
    r = np.hypot(yy - h / 2, xx - w / 2)
    r_norm = np.clip(r / (min(h, w) / 2), 0, 0.999)
    bins = (r_norm * n_bins).astype(int)
    sums = np.bincount(bins.ravel(), power.ravel(), minlength=n_bins)
    counts = np.bincount(bins.ravel(), minlength=n_bins)
    return (sums / np.maximum(counts, 1)).astype(np.float32)


def spectral_features(rgb: np.ndarray) -> np.ndarray:
    """1-D azimuthally averaged log power spectrum, normalised to remove overall brightness."""
    profile = radial_profile(_center_crop_gray(rgb))
    profile = profile - profile[1:4].mean()
    return profile


@lru_cache(maxsize=1)
def _load_baseline(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def analyze_frequency(rgb: np.ndarray) -> dict:
    profile = spectral_features(rgb)
    hi = profile[int(N_BINS * 0.75) :].mean()
    mid = profile[int(N_BINS * 0.25) : int(N_BINS * 0.5)].mean()
    result: dict = {"high_to_mid_ratio": round(float(hi - mid), 3), "baseline_ai_probability": None}

    baseline = _load_baseline(str(settings.model_dir / BASELINE_FILE))
    if baseline:
        x = (profile - np.asarray(baseline["mean"], np.float32)) / np.asarray(baseline["scale"], np.float32)
        z = float(x @ np.asarray(baseline["coef"], np.float32) + baseline["intercept"])
        result["baseline_ai_probability"] = round(1.0 / (1.0 + np.exp(-z)), 4)
    return result
