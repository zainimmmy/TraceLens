# TraceLens training pipeline

Everything that produces the model the API serves. Runs on free GPUs (Kaggle about 30 GPU hours a
week, or Colab). The easiest path is the notebook: [`notebooks/tracelens_kaggle.ipynb`](notebooks/tracelens_kaggle.ipynb).

The scripts import the backend's own preprocessing and FFT feature code, so training, evaluation
and serving can never drift apart.

## Steps

| Step | Command | Output |
|---|---|---|
| 1. Manifest | `python -m tracelens_train.prepare_data --cifake ... --genimage ... --holdout ...` | `artifacts/manifest.csv` |
| 2. Baseline | `python -m tracelens_train.fft_baseline` | `artifacts/fft_baseline.json` |
| 3. Main model | `python -m tracelens_train.train --arch efficientnet_b0` | `artifacts/efficientnet_b0.pt` |
| 3b. Comparison | `python -m tracelens_train.train --arch resnet50` | `artifacts/resnet50.pt` |
| 4. Calibration | `python -m tracelens_train.calibrate --run efficientnet_b0` | temperature in `artifacts/*_calibration.json` |
| 5. Export | `python -m tracelens_train.export_onnx --run efficientnet_b0` | `artifacts/export/tracelens.onnx`, `model_meta.json` |
| 6. Evaluate | `python -m tracelens_train.evaluate --unseen Midjourney,wukong` | `artifacts/evaluation.{json,md}` |
| 6b. Forensics on CASIA | `python -m tracelens_train.evaluate_forensics` | `artifacts/forensics_casia.json` |
| 7. Publish | `python -m tracelens_train.push_to_hub --repo you/tracelens-detector` | Hugging Face model repo |

Run every command from the `training/` folder. MLflow runs are stored in `training/mlflow.db`
(artifacts in `training/mlruns`); view them with `mlflow ui --backend-store-uri sqlite:///mlflow.db`.

## Cross-generator test

Train without some generators and evaluate on them:

```bash
python -m tracelens_train.train --arch efficientnet_b0 --exclude-generators Midjourney,wukong
python -m tracelens_train.evaluate --unseen Midjourney,wukong
```

`evaluate.py` reports `test_seen_generators` and `test_unseen_generators` separately.

## Your own holdout set

The part interviewers remember. Make a folder like this and upload it to Kaggle as a private dataset:

```
holdout/
  real/                 your own phone photos (varied scenes, lighting, compression)
  ai/
    flux_schnell/       images you generated with a free open model
    sdxl_turbo/
```

## Using the model locally

Copy `artifacts/export/tracelens.onnx`, `artifacts/export/model_meta.json` and (optionally)
`artifacts/fft_baseline.json` into `backend/models/`, then restart the API.
