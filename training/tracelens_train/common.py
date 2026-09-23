"""Shared paths and helpers for the training pipeline.

The backend package is put on ``sys.path`` so training uses the *exact* preprocessing and
FFT features that the API serves with (no train/serve skew).
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

ARTIFACTS = Path(os.getenv("TRACELENS_ARTIFACTS", REPO_ROOT / "training" / "artifacts"))
ARTIFACTS.mkdir(parents=True, exist_ok=True)
# MLflow 3 no longer accepts a plain ./mlruns folder as the tracking store; SQLite is the
# recommended zero-setup backend. Run artifacts still go to ./mlruns next to it.
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///" + (REPO_ROOT / "training" / "mlflow.db").as_posix())
EXPERIMENT = "tracelens"

LABELS = {"real": 0, "ai": 1}


def seed_everything(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def setup_mlflow():
    import mlflow

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT)
    return mlflow
