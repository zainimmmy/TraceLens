"""Step 4: temperature scaling, so a 90% score means about 90%.

Fits a single scalar T on the validation logits saved by ``train.py`` by minimising negative
log-likelihood. The API divides every logit by T before the sigmoid.

  python -m tracelens_train.calibrate --run efficientnet_b0
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from .common import ARTIFACTS
from .metrics import expected_calibration_error


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    from scipy.optimize import minimize_scalar

    y = labels.astype(float)

    def nll(log_t: float) -> float:
        z = logits / np.exp(log_t)
        # numerically stable binary cross-entropy with logits
        return float(np.mean(np.maximum(z, 0) - z * y + np.log1p(np.exp(-np.abs(z)))))

    res = minimize_scalar(nll, bounds=(np.log(0.05), np.log(20.0)), method="bounded")
    return float(np.exp(res.x))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="efficientnet_b0", help="run name used by train.py")
    args = ap.parse_args()

    data = np.load(ARTIFACTS / f"{args.run}_val_logits.npz")
    logits, labels = data["logits"], data["labels"]
    t = fit_temperature(logits, labels)
    before = expected_calibration_error(labels, 1 / (1 + np.exp(-logits)))
    after = expected_calibration_error(labels, 1 / (1 + np.exp(-logits / t)))
    out = {"temperature": t, "ece_before": before, "ece_after": after}
    (ARTIFACTS / f"{args.run}_calibration.json").write_text(json.dumps(out, indent=2))
    print(f"T={t:.3f}  ECE {before:.4f} -> {after:.4f}")

    try:
        from .common import setup_mlflow

        mlflow = setup_mlflow()
        with mlflow.start_run(run_name=f"{args.run}_calibration"):
            mlflow.log_metrics(out)
    except Exception as exc:  # MLflow is optional for this step
        print(f"(MLflow logging skipped: {exc})")


if __name__ == "__main__":
    main()
