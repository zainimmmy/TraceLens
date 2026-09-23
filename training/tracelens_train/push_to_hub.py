"""Publish the exported model, FFT baseline and model card to the Hugging Face Model Hub.

  export HF_TOKEN=hf_...            # a *write* token from huggingface.co/settings/tokens
  python -m tracelens_train.push_to_hub --repo your-username/tracelens-detector
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from .common import ARTIFACTS, REPO_ROOT


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="e.g. your-username/tracelens-detector")
    ap.add_argument("--model-dir", type=Path, default=ARTIFACTS / "export")
    ap.add_argument("--private", action="store_true")
    args = ap.parse_args()

    from huggingface_hub import HfApi

    staging = ARTIFACTS / "hub_upload"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    for name in ("tracelens.onnx", "model_meta.json"):
        shutil.copy(args.model_dir / name, staging / name)
    for extra in ("fft_baseline.json", "evaluation.json", "evaluation.md", "forensics_casia.json"):
        if (ARTIFACTS / extra).exists():
            shutil.copy(ARTIFACTS / extra, staging / extra)
    shutil.copy(REPO_ROOT / "docs" / "MODEL_CARD.md", staging / "README.md")

    api = HfApi(token=os.environ.get("HF_TOKEN"))
    api.create_repo(args.repo, repo_type="model", private=args.private, exist_ok=True)
    api.upload_folder(folder_path=str(staging), repo_id=args.repo, repo_type="model", commit_message="Upload TraceLens model")
    print(f"Uploaded to https://huggingface.co/{args.repo}")


if __name__ == "__main__":
    main()
