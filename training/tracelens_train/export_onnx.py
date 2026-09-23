"""Step 5: export the best checkpoint to ONNX (with the Grad-CAM output) and verify it.

The exported graph has two outputs:

* ``logit`` [N]: raw logit, positive means AI generated
* ``cam`` [N, h, w]: sum_k w_k * A_k over the final conv feature maps. For a
  global-average-pool + linear head this equals Grad-CAM up to a constant, so the API
  gets Grad-CAM heatmaps from ONNX Runtime on CPU with no PyTorch.

  python -m tracelens_train.export_onnx --run efficientnet_b0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .common import ARTIFACTS

MAX_MODEL_MB = 100


def build_wrapper(model):
    import torch

    class ExportWrapper(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, x):
            feats = self.m.forward_features(x)
            logit = self.m.forward_head(feats).squeeze(1)
            weight = self.m.get_classifier().weight[0]
            cam = torch.einsum("bchw,c->bhw", feats, weight)
            return logit, cam

    return ExportWrapper(model).eval()


def export(wrapper, size: int, out: Path) -> None:
    import torch

    dummy = torch.randn(2, 3, size, size)
    kwargs = dict(
        input_names=["image"],
        output_names=["logit", "cam"],
        dynamic_axes={"image": {0: "N"}, "logit": {0: "N"}, "cam": {0: "N"}},
        opset_version=17,
    )
    try:
        torch.onnx.export(wrapper, (dummy,), str(out), dynamo=False, **kwargs)
    except TypeError:  # older torch without the dynamo flag
        torch.onnx.export(wrapper, (dummy,), str(out), **kwargs)
    except Exception as exc:  # newer torch without the legacy exporter
        print(f"Legacy ONNX exporter unavailable ({exc}); using the dynamo exporter")
        torch.onnx.export(wrapper, (dummy,), str(out), dynamo=True, **kwargs)


def verify(wrapper, onnx_path: Path, size: int) -> tuple[float, float, float]:
    """Compare ONNX Runtime with PyTorch on a batch of 3 (also exercises the dynamic batch axis).

    Errors are *relative*: float32 carries about 7 significant digits, so a logit of 200,000
    legitimately differs by a few units between runtimes. Returns (logit error, cam error,
    largest absolute logit).
    """
    import onnxruntime as ort
    import torch

    x = (torch.rand(3, 3, size, size) - 0.45) / 0.23  # roughly the range of normalised images
    with torch.no_grad():
        ref_logit, ref_cam = (t.numpy() for t in wrapper(x))
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    logit, cam = sess.run(["logit", "cam"], {"image": x.numpy()})
    logit_err = float((np.abs(logit - ref_logit) / np.maximum(1.0, np.abs(ref_logit))).max())
    cam_err = float(np.abs(cam - ref_cam).max() / max(1.0, float(np.abs(ref_cam).max())))
    return logit_err, cam_err, float(np.abs(ref_logit).max())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="efficientnet_b0")
    ap.add_argument("--name", default=None, help="model name reported by the API, e.g. efficientnet_b0_v1")
    ap.add_argument("--out-dir", type=Path, default=ARTIFACTS / "export")
    args = ap.parse_args()

    import torch

    from .train import build_model

    ckpt = torch.load(ARTIFACTS / f"{args.run}.pt", map_location="cpu", weights_only=False)
    model = build_model(ckpt["arch"], pretrained=False)
    model.load_state_dict(ckpt["state_dict"])
    wrapper = build_wrapper(model.eval())

    args.out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = args.out_dir / "tracelens.onnx"
    export(wrapper, ckpt["size"], onnx_path)
    logit_err, cam_err, logit_scale = verify(wrapper, onnx_path, ckpt["size"])
    diff = max(logit_err, cam_err)
    size_mb = onnx_path.stat().st_size / 1e6
    print(f"ONNX saved to {onnx_path} ({size_mb:.1f} MB); PyTorch vs ONNX relative difference: "
          f"logit {logit_err:.1e}, Grad-CAM {cam_err:.1e}")
    if diff > 1e-3:
        raise SystemExit("ONNX output does not match PyTorch output")
    if logit_scale > 100:
        print(f"WARNING: on images unlike the training data this model outputs extreme logits (up to {logit_scale:,.0f}); "
              "healthy models stay around +/-20. Its scores will be overconfident on such images. "
              "Train on more varied data (GenImage, your holdout set) to fix this.")
    if size_mb > MAX_MODEL_MB:
        raise SystemExit(f"Model is {size_mb:.0f} MB, over the {MAX_MODEL_MB} MB budget")

    calib_path = ARTIFACTS / f"{args.run}_calibration.json"
    temperature = json.loads(calib_path.read_text())["temperature"] if calib_path.exists() else 1.0
    meta = {
        "name": args.name or f"{ckpt['arch']}_v1",
        "arch": ckpt["arch"],
        "input_size": ckpt["size"],
        "mean": [0.485, 0.456, 0.406],
        "std": [0.229, 0.224, 0.225],
        "temperature": temperature,
        "onnx_relative_diff": diff,
        "metrics": {"validation": ckpt.get("val_metrics", {})},
    }
    (args.out_dir / "model_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Wrote model_meta.json (temperature={temperature:.3f})")


if __name__ == "__main__":
    main()
