"""Build one manifest CSV (path, label, generator, source, split) from the raw datasets.

Supported layouts (point each flag at the folder you downloaded):

  --cifake   CIFAKE (Kaggle: birdy654/cifake-real-and-ai-generated-synthetic-images)
             <root>/{train,test}/{REAL,FAKE}/*.jpg
  --genimage GenImage subset, one folder per generator, e.g.
             <root>/stable_diffusion_v_1_4/{train,val}/{ai,nature}/*.png
  --holdout  Your own holdout set (never used in training)
             <root>/real/*  (your phone photos)   <root>/ai/<generator_name>/*
  --casia    CASIA v2 (used only to evaluate the ELA / noise manipulation signals)
             <root>/{Au,Tp}/*

Example (Kaggle):
  python -m tracelens_train.prepare_data --genimage /kaggle/input/genimage-tiny \
      --cifake /kaggle/input/cifake-real-and-ai-generated-synthetic-images \
      --holdout /kaggle/input/tracelens-holdout --out artifacts/manifest.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from .common import ARTIFACTS

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def images_in(folder: Path):
    if not folder.exists():
        return
    for p in sorted(folder.rglob("*")):
        if p.suffix.lower() in IMAGE_EXT and p.is_file():
            yield p


def scan_cifake(root: Path, limit: int | None):
    for split_dir, split in (("train", "train"), ("test", "test")):
        for cls, label in (("REAL", "real"), ("FAKE", "ai")):
            for i, p in enumerate(images_in(root / split_dir / cls)):
                if limit and i >= limit:
                    break
                yield {"path": p, "label": label, "generator": "cifake_sd14" if label == "ai" else "cifar10", "source": "cifake", "split": split}


def scan_genimage(root: Path, limit: int | None):
    for gen_dir in sorted(d for d in root.iterdir() if d.is_dir()):
        for split_dir, split in (("train", "train"), ("val", "test")):
            for cls, label in (("ai", "ai"), ("nature", "real")):
                for i, p in enumerate(images_in(gen_dir / split_dir / cls)):
                    if limit and i >= limit:
                        break
                    yield {"path": p, "label": label, "generator": gen_dir.name if label == "ai" else f"{gen_dir.name}_real",
                           "source": "genimage", "split": split}


def scan_holdout(root: Path):
    for p in images_in(root / "real"):
        yield {"path": p, "label": "real", "generator": "own_photos", "source": "holdout", "split": "holdout"}
    ai_root = root / "ai"
    for p in images_in(ai_root):
        gen = p.relative_to(ai_root).parts[0] if len(p.relative_to(ai_root).parts) > 1 else "own_generated"
        yield {"path": p, "label": "ai", "generator": gen, "source": "holdout", "split": "holdout"}


def scan_casia(root: Path):
    for cls, label in (("Au", "authentic"), ("Tp", "tampered")):
        for p in images_in(root / cls):
            yield {"path": p, "label": label, "generator": "casia", "source": "casia", "split": "forensics"}


def carve_val(rows: list[dict], fraction: float, seed: int) -> None:
    """Move a stratified slice of train rows into a validation split (used for early stopping and calibration)."""
    rng = random.Random(seed)
    by_key: dict[tuple, list[dict]] = {}
    for r in rows:
        if r["split"] == "train":
            by_key.setdefault((r["source"], r["label"], r["generator"]), []).append(r)
    for group in by_key.values():
        rng.shuffle(group)
        for r in group[: max(1, int(len(group) * fraction))]:
            r["split"] = "val"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cifake", type=Path)
    ap.add_argument("--genimage", type=Path)
    ap.add_argument("--holdout", type=Path)
    ap.add_argument("--casia", type=Path)
    ap.add_argument("--limit-per-class", type=int, default=None, help="cap images per class/generator (quick experiments)")
    ap.add_argument("--val-fraction", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=ARTIFACTS / "manifest.csv")
    args = ap.parse_args()

    rows: list[dict] = []
    if args.cifake:
        rows += scan_cifake(args.cifake, args.limit_per_class)
    if args.genimage:
        rows += scan_genimage(args.genimage, args.limit_per_class)
    if args.holdout:
        rows += scan_holdout(args.holdout)
    if args.casia:
        rows += scan_casia(args.casia)
    if not rows:
        ap.error("no images found; pass at least one dataset folder")
    carve_val(rows, args.val_fraction, args.seed)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "label", "generator", "source", "split"])
        writer.writeheader()
        for r in rows:
            writer.writerow({**r, "path": str(r["path"])})

    summary: dict[tuple, int] = {}
    for r in rows:
        key = (r["split"], r["source"], r["label"])
        summary[key] = summary.get(key, 0) + 1
    print(f"Wrote {len(rows)} rows to {args.out}")
    for (split, source, label), n in sorted(summary.items()):
        print(f"  {split:10s} {source:10s} {label:10s} {n:7d}")


if __name__ == "__main__":
    main()
