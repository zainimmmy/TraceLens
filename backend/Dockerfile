# TraceLens API: Hugging Face Spaces (Docker SDK, free CPU tier) or any container host.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libgomp: ONNX Runtime threading; libglib: OpenCV
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

# Spaces run containers as uid 1000
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=user app ./app
COPY --chown=user models ./models

USER user
ENV PORT=7860 \
    MODEL_DIR=/home/user/app/models \
    TRUSTED_PROXY_HOPS=1

EXPOSE 7860
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s CMD curl -fsS http://localhost:${PORT}/api/v1/health || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1
