---
license: mit
library_name: onnx
tags:
  - image-classification
  - ai-generated-image-detection
  - deepfake-detection
  - image-forensics
pipeline_tag: image-classification
---

# TraceLens detector (EfficientNet-B0, ONNX)

Binary classifier that estimates the probability that an image is AI generated. It powers the
F1 (classifier) and F2 (Grad-CAM) modules of TraceLens (_add your GitHub link_), an explainable
image forensics tool that combines this model with Error Level Analysis, noise analysis and
C2PA/EXIF provenance checks.

## Files

| File | Contents |
|---|---|
| `tracelens.onnx` | EfficientNet-B0 with two outputs: `logit` [N] (positive = AI) and `cam` [N, 7, 7] (Grad-CAM) |
| `model_meta.json` | Input size, normalisation, calibration temperature, evaluation metrics |
| `fft_baseline.json` | Logistic regression on FFT radial spectrum (baseline and fallback) |
| `evaluation.json` / `evaluation.md` | Full evaluation results |

## Intended use

Triage support for analysts (claims, fraud, trust and safety, journalism, digital forensics) who
must decide whether an image is authentic and explain that decision. Output is probabilistic
evidence and must be reviewed by a person.

**Out of scope:** sole basis for legal, employment, insurance or moderation decisions; video or
audio; identifying people.

## Training data

_Fill in after training._ Planned mix: CIFAKE (baseline), a GenImage subset covering several
generators (main training set), and a self-made holdout set of images from a free open model plus
the author's own phone photos, never used in training.

## Training procedure

* timm `efficientnet_b0`, ImageNet-pretrained, single-logit head, AdamW, cosine schedule, AMP
* Augmentation simulating online sharing: JPEG quality 30-100, down-scaling, blur, random crop and flip
* Compared against ResNet50 and an FFT + logistic regression baseline in MLflow
* Temperature scaling on the validation set
* Exported to ONNX (opset 17); outputs verified against PyTorch

## Preprocessing (must match exactly)

Resize so the shorter side is 224 (bicubic), take 224×224 crops along the long side (up to 3),
scale to [0, 1], normalise with ImageNet mean/std, run the model, divide logits by the
temperature, apply sigmoid, average across crops. See `backend/app/forensics/classifier.py`.

## Evaluation

_Fill in from `evaluation.md`._

| Set | N | Accuracy | AUC | F1 | ECE |
|---|---|---|---|---|---|
| Held-out test | | | | | |
| Unseen generators | | | | | |
| Own holdout | | | | | |
| Test, JPEG q50 | | | | | |
| Test, 50% downscale | | | | | |

## Limitations and risks

* Performance degrades on generators not represented in training; the unseen-generator row above is the honest estimate.
* Heavy recompression, screenshots and resizing remove artifacts the model relies on.
* Real photos with unusual processing (HDR, beauty filters, heavy denoising) can be flagged as AI.
* Grad-CAM shows where the model looked, not proof of manipulation.

## Ethics

TraceLens gives probabilistic evidence, not proof. It should support human judgment, never replace
it, especially when someone's reputation or money is at stake.
