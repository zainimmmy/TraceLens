"""Evaluate the classic forensic signals (ELA + noise + metadata) on CASIA v2.

CASIA v2 has authentic (Au) and tampered (Tp) images. This measures how well the API's
manipulation score separates them, so the manipulation verdict also has published numbers.

  python -m tracelens_train.evaluate_forensics --manifest artifacts/manifest.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .common import ARTIFACTS
from .metrics import binary_metrics
from app.aggregator import MANIPULATION_THRESHOLD, manipulation_score  # noqa: E402
from app.forensics.ela import analyze_ela  # noqa: E402
from app.forensics.metadata import analyze_metadata  # noqa: E402
from app.forensics.noise import analyze_noise  # noqa: E402
from app.imaging import load_image  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=ARTIFACTS / "manifest.csv")
    ap.add_argument("--max", type=int, default=3000)
    args = ap.parse_args()

    with args.manifest.open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["source"] == "casia"]
    if not rows:
        raise SystemExit("No CASIA rows in the manifest; run prepare_data with --casia")
    rng = np.random.default_rng(0)
    if len(rows) > args.max:
        rows = [rows[i] for i in rng.choice(len(rows), args.max, replace=False)]

    ys, scores = [], []
    for i, r in enumerate(rows):
        try:
            img = load_image(Path(r["path"]).read_bytes())
        except Exception:
            continue
        ela = analyze_ela(img.rgb, img.format)
        noise = analyze_noise(img.rgb)
        meta = analyze_metadata(img.raw, img.pil, img.format, img.mime)
        s, _ = manipulation_score(ela, noise, meta)
        ys.append(int(r["label"] == "tampered"))
        scores.append(s)
        if (i + 1) % 500 == 0:
            print(f"  {i + 1}/{len(rows)}")

    m = binary_metrics(np.asarray(ys), np.asarray(scores), threshold=MANIPULATION_THRESHOLD)
    m.pop("inconclusive_rate", None)
    (ARTIFACTS / "forensics_casia.json").write_text(json.dumps(m, indent=2))
    print(json.dumps({k: v for k, v in m.items() if k != "confusion_matrix"}, indent=2))


if __name__ == "__main__":
    main()
