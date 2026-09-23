"""Weeks 3: fine-tune a timm CNN (EfficientNet-B0 main model, ResNet50 comparison).

  # main model
  python -m tracelens_train.train --arch efficientnet_b0 --epochs 8
  # comparison, logged side by side in MLflow
  python -m tracelens_train.train --arch resnet50 --epochs 8
  # cross-generator protocol: train without two generators, test on them later
  python -m tracelens_train.train --arch efficientnet_b0 --exclude-generators Midjourney,wukong --tag xgen

Saves ``artifacts/<arch>[_tag].pt`` (best validation AUC) plus validation logits for calibration.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

from .common import ARTIFACTS, seed_everything, setup_mlflow
from .data import EvalTransform, TrainTransform, make_dataset, read_manifest
from .metrics import binary_metrics


def build_model(arch: str, pretrained: bool = True):
    import timm

    return timm.create_model(arch, pretrained=pretrained, num_classes=1)


def predict_logits(model, loader, device) -> tuple[np.ndarray, np.ndarray]:
    import torch

    model.eval()
    logits, labels = [], []
    with torch.no_grad(), torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
        for x, y in loader:
            logits.append(model(x.to(device, non_blocking=True)).float().squeeze(1).cpu().numpy())
            labels.append(y.numpy())
    return np.concatenate(logits), np.concatenate(labels).astype(int)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=ARTIFACTS / "manifest.csv")
    ap.add_argument("--arch", default="efficientnet_b0")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--weight-decay", type=float, default=1e-2)
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-train", type=int, default=None, help="subsample train set (quick runs)")
    ap.add_argument("--generators", default="", help="comma list: only these AI generators in training")
    ap.add_argument("--exclude-generators", default="", help="comma list: hold these generators out of training")
    ap.add_argument("--no-pretrained", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    seed_everything(args.seed)

    import torch
    from torch.utils.data import DataLoader

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gens = {g for g in args.generators.split(",") if g} or None
    excl = {g for g in args.exclude_generators.split(",") if g} or None

    train_rows = read_manifest(args.manifest, {"train"}, gens, excl)
    val_rows = read_manifest(args.manifest, {"val"}, gens, excl)
    if args.max_train and len(train_rows) > args.max_train:
        rng = np.random.default_rng(args.seed)
        train_rows = [train_rows[i] for i in rng.choice(len(train_rows), args.max_train, replace=False)]
    n_ai = sum(r["label"] == "ai" for r in train_rows)
    print(f"device={device} train={len(train_rows)} (ai={n_ai}) val={len(val_rows)}")

    train_loader = DataLoader(make_dataset(train_rows, TrainTransform(args.size)), batch_size=args.batch_size, shuffle=True,
                              num_workers=args.workers, pin_memory=device.type == "cuda", drop_last=True, persistent_workers=args.workers > 0)
    val_loader = DataLoader(make_dataset(val_rows, EvalTransform(args.size)), batch_size=args.batch_size * 2,
                            num_workers=args.workers, pin_memory=device.type == "cuda")

    model = build_model(args.arch, pretrained=not args.no_pretrained).to(device)
    # Balance classes if the training set is skewed.
    pos_weight = torch.tensor([(len(train_rows) - n_ai) / max(n_ai, 1)], device=device)
    criterion = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    total_steps = args.epochs * len(train_loader)
    warmup = max(1, int(0.05 * total_steps))
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda s: min(1.0, (s + 1) / warmup) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / total_steps)))
    )
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")

    run_name = args.arch + (f"_{args.tag}" if args.tag else "")
    ckpt_path = ARTIFACTS / f"{run_name}.pt"
    mlflow = setup_mlflow()
    best_auc = -1.0
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({**vars(args), "manifest": str(args.manifest), "n_train": len(train_rows), "n_val": len(val_rows)})
        step = 0
        for epoch in range(args.epochs):
            model.train()
            t0, running = time.time(), 0.0
            for x, y in train_loader:
                x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                    loss = criterion(model(x).squeeze(1), y)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                running += loss.item()
                step += 1
                if step % 50 == 0:
                    mlflow.log_metric("train_loss", running / 50, step=step)
                    running = 0.0

            logits, labels = predict_logits(model, val_loader, device)
            m = binary_metrics(labels, 1 / (1 + np.exp(-logits)))
            mlflow.log_metrics({f"val_{k}": v for k, v in m.items() if isinstance(v, float)}, step=epoch)
            print(f"epoch {epoch + 1}/{args.epochs} val_acc={m['accuracy']:.4f} val_auc={m['roc_auc']:.4f} ({time.time() - t0:.0f}s)")
            if m["roc_auc"] > best_auc:
                best_auc = m["roc_auc"]
                torch.save({"arch": args.arch, "state_dict": model.state_dict(), "size": args.size, "val_metrics": m}, ckpt_path)
                np.savez(ARTIFACTS / f"{run_name}_val_logits.npz", logits=logits, labels=labels)

        mlflow.log_metric("best_val_auc", best_auc)
        (ARTIFACTS / f"{run_name}_train_summary.json").write_text(json.dumps({"best_val_auc": best_auc, "args": vars(args)}, default=str))
    print(f"Best val AUC {best_auc:.4f}; checkpoint {ckpt_path}")


if __name__ == "__main__":
    main()
