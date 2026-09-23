"""Week 8: evaluate the *exported* model through the exact serving code path.

Uses the backend's ``Classifier`` (ONNX Runtime, multi-crop, temperature scaling), so the
numbers in the README are the numbers users get. Reports:

* held-out test metrics (accuracy, precision, recall, F1, ROC AUC, ECE, confusion matrix)
* per-generator accuracy, including generators never seen in training (cross-generator)
* your own holdout set
* robustness: JPEG quality 75 and 50, 50% downscale (like a social media re-upload)

  python -m tracelens_train.evaluate --model-dir artifacts/export --unseen Midjourney,wukong
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from .common import ARTIFACTS
from .data import downscale, jpeg_compress, read_manifest
from .metrics import binary_metrics
from app.forensics.classifier import Classifier  # noqa: E402

PERTURBATIONS = {
    "clean": lambda im: im,
    "jpeg_q75": lambda im: jpeg_compress(im, 75),
    "jpeg_q50": lambda im: jpeg_compress(im, 50),
    "downscale_50": lambda im: downscale(im, 0.5),
}


def score(clf: Classifier, rows: list[dict], perturb) -> tuple[list[dict], np.ndarray, np.ndarray]:
    """Score every readable image. Returns the rows actually scored, so they stay aligned with ys/ps."""
    kept, ys, ps = [], [], []
    for i, r in enumerate(rows):
        try:
            with Image.open(r["path"]) as im:
                p = clf.predict(perturb(im.convert("RGB")))["ai_probability"]
        except Exception:
            continue
        kept.append(r)
        ys.append(int(r["label"] == "ai"))
        ps.append(p)
        if (i + 1) % 1000 == 0:
            print(f"    {i + 1}/{len(rows)}")
    return kept, np.asarray(ys), np.asarray(ps)


def per_generator(rows, ys, ps) -> dict:
    groups = defaultdict(list)
    for r, y, p in zip(rows, ys, ps, strict=True):
        groups[r["generator"]].append(int((p >= 0.5) == bool(y)))
    return {g: {"n": len(v), "accuracy": float(np.mean(v))} for g, v in sorted(groups.items())}


def markdown_table(results: dict) -> str:
    lines = ["| Set | N | Accuracy | AUC | F1 | ECE |", "|---|---|---|---|---|---|"]
    for name, m in results.items():
        if isinstance(m, dict) and "accuracy" in m:
            lines.append(f"| {name} | {m['n']} | {m['accuracy']:.3f} | {m['roc_auc']:.3f} | {m['f1']:.3f} | {m['ece']:.3f} |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=ARTIFACTS / "manifest.csv")
    ap.add_argument("--model-dir", type=Path, default=ARTIFACTS / "export")
    ap.add_argument("--unseen", default="", help="comma list of generators excluded from training")
    ap.add_argument("--max-per-set", type=int, default=5000)
    ap.add_argument("--skip-robustness", action="store_true")
    args = ap.parse_args()

    clf = Classifier(args.model_dir / "tracelens.onnx", args.model_dir / "model_meta.json")
    unseen = {g for g in args.unseen.split(",") if g}
    rng = np.random.default_rng(0)

    def sample(rows):
        if len(rows) <= args.max_per_set:
            return rows
        return [rows[i] for i in rng.choice(len(rows), args.max_per_set, replace=False)]

    test = sample(read_manifest(args.manifest, {"test"}))
    sets = {
        "test": test,
        "test_seen_generators": [r for r in test if r["label"] == "real" or r["generator"] not in unseen],
        "test_unseen_generators": [r for r in test if r["label"] == "real" or r["generator"] in unseen] if unseen else [],
        "holdout": sample(read_manifest(args.manifest, {"holdout"})),
    }

    results: dict = {}
    for name, rows in sets.items():
        if not rows:
            continue
        print(f"Evaluating {name} ({len(rows)} images)")
        kept, ys, ps = score(clf, rows, PERTURBATIONS["clean"])
        results[name] = binary_metrics(ys, ps)
        results[name]["per_generator"] = per_generator(kept, ys, ps)
        print(f"  acc={results[name]['accuracy']:.4f} auc={results[name]['roc_auc']:.4f}")

    if not args.skip_robustness:
        results["robustness"] = {}
        for pname, fn in PERTURBATIONS.items():
            if pname == "clean":
                continue
            print(f"Robustness: {pname}")
            _, ys, ps = score(clf, test[:2000], fn)
            results["robustness"][pname] = binary_metrics(ys, ps)

    out = ARTIFACTS / "evaluation.json"
    out.write_text(json.dumps(results, indent=2))
    table = markdown_table(results) + "\n\nRobustness (test subset):\n\n" + markdown_table(results.get("robustness", {}))
    (ARTIFACTS / "evaluation.md").write_text(table)
    print(table)

    # Publish the headline numbers with the model so /api/v1/health can report them.
    meta_path = args.model_dir / "model_meta.json"
    meta = json.loads(meta_path.read_text())
    meta["metrics"] = {
        k: {m: v[m] for m in ("n", "accuracy", "roc_auc", "f1", "ece")}
        for k, v in results.items() if isinstance(v, dict) and "accuracy" in v
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"Saved {out} and updated {meta_path}")


if __name__ == "__main__":
    main()
