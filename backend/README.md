---
title: TraceLens API
emoji: 🔍
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Explainable AI image and manipulation forensics API
---

# TraceLens API

FastAPI backend for TraceLens. This folder is deployed as-is to a
Hugging Face Space (the YAML block above is the Space configuration).

* Interactive docs: `/docs`
* Health check: `/api/v1/health`

## Run locally

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000/docs.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `HF_MODEL_REPO` | unset | Model Hub repo to download `tracelens.onnx` + `model_meta.json` from at startup |
| `MODEL_DIR` | `./models` | Where the model files live |
| `GEMINI_API_KEY` | unset | Enables Gemini summaries (template summaries without it) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `MAX_PDF_MB` / `MAX_PDF_IMAGES` | `20` / `10` | PDF size limit and how many embedded images are analysed |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed frontend origins |
| `RATE_LIMIT_ANALYZE` | `12/minute` | Per-IP limit for `/analyze` |
| `TRUSTED_PROXY_HOPS` | `0` (`1` in Docker) | Proxies in front of the app, for client IP detection |

## Tests

```bash
pytest --cov
```
