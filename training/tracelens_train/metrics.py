"""Evaluation metrics shared by every training and evaluation script."""

from __future__ import annotations

import numpy as np


def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 15) -> float:
    """How far predicted probabilities are from observed frequencies (0 = perfectly calibrated)."""
    conf = np.where(p >= 0.5, p, 1 - p)
    correct = (p >= 0.5).astype(int) == y
    edges = np.linspace(0.5, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (conf > lo) & (conf <= hi)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)


def binary_metrics(y_true, p_ai, threshold: float = 0.5) -> dict:
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

    y = np.asarray(y_true).astype(int)
    p = np.asarray(p_ai, dtype=float)
    pred = (p >= threshold).astype(int)
    out = {
        "n": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else float("nan"),
        "ece": expected_calibration_error(y, p),
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1]).tolist(),  # rows: true real, true ai
    }
    # Share of images the API would call "inconclusive" (40-60% band)
    out["inconclusive_rate"] = float(((p > 0.4) & (p < 0.6)).mean())
    return out
