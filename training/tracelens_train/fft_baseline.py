"""Week 2 baseline: logistic regression on FFT radial-spectrum features.

Sets a floor for the CNN and shows classical ML. The fitted model is saved as
``fft_baseline.json``; the API loads it as a fallback when the CNN is not installed.

  python -m tracelens_train.fft_baseline --manifest artifacts/manifest.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .common import ARTIFACTS, seed_everything, setup_mlflow
from .data import read_manifest
from .metrics import binary_metrics
from app.forensics.frequency import spectral_features  # noqa: E402  (backend on path via .common)


def featurize(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    feats, labels = [], []
    for i, r in enumerate(rows):
        try:
            with Image.open(r["path"]) as im:
                feats.append(spectral_features(np.asarray(im.convert("RGB"))))
            labels.append(int(r["label"] == "ai"))
        except Exception:
            continue
        if (i + 1) % 2000 == 0:
            print(f"  featurized {i + 1}/{len(rows)}")
    return np.stack(feats), np.asarray(labels)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=ARTIFACTS / "manifest.csv")
    ap.add_argument("--max-train", type=int, default=20000)
    ap.add_argument("--out", type=Path, default=ARTIFACTS / "fft_baseline.json")
    args = ap.parse_args()
    seed_everything()

    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    train = read_manifest(args.manifest, {"train", "val"})
    np.random.shuffle(train)
    train = train[: args.max_train]
    test = read_manifest(args.manifest, {"test"})
    holdout = read_manifest(args.manifest, {"holdout"})

    print(f"Featurizing {len(train)} train images")
    x_train, y_train = featurize(train)
    pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    pipe.fit(x_train, y_train)

    mlflow = setup_mlflow()
    with mlflow.start_run(run_name="fft_logreg_baseline"):
        mlflow.log_params({"model": "fft_logreg", "n_train": len(y_train), "features": x_train.shape[1]})
        results = {}
        for name, rows in (("test", test), ("holdout", holdout)):
            if not rows:
                continue
            x, y = featurize(rows)
            m = binary_metrics(y, pipe.predict_proba(x)[:, 1])
            results[name] = m
            mlflow.log_metrics({f"{name}_{k}": v for k, v in m.items() if isinstance(v, (int, float))})
            print(f"{name}: acc={m['accuracy']:.3f} auc={m['roc_auc']:.3f}")

        scaler, lr = pipe.named_steps["standardscaler"], pipe.named_steps["logisticregression"]
        payload = {
            "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist(),
            "coef": lr.coef_[0].tolist(),
            "intercept": float(lr.intercept_[0]),
            "metrics": results,
        }
        args.out.write_text(json.dumps(payload), encoding="utf-8")
        mlflow.log_artifact(str(args.out))
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
