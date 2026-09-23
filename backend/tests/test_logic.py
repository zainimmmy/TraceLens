"""Classifier, aggregator and summary logic."""

from __future__ import annotations

import httpx
import numpy as np
import pytest
from PIL import Image

from app.aggregator import aggregate, manipulation_score
from app.config import settings
from app.forensics.classifier import classifier_status, crop_boxes, get_classifier
from app.summary import gemini_summary, summarize, template_summary

CLEAN_ELA = {"suspicious_regions": 0, "outlier_energy_share": 0.0, "reliability": "normal"}
CLEAN_NOISE = {"suspicious_regions": 0, "inconsistent_blocks_share": 0.0}
NO_FLAGS = {"flags": []}
NO_FFT = {"baseline_ai_probability": None}


def clf(p):
    return {"available": True, "ai_probability": p, "model": "m"}


def flags(*codes_and_targets):
    return {"flags": [{"code": c, "severity": "medium", "points_to": t, "message": c} for c, t in codes_and_targets]}


# ---------- classifier ----------

def test_crop_boxes_cover_long_axis():
    assert crop_boxes(224, 224, 224) == [(0, 0)]
    wide = crop_boxes(672, 224, 224)
    assert wide == [(0, 0), (224, 0), (448, 0)]
    tall = crop_boxes(224, 400, 224)
    assert tall[0] == (0, 0) and tall[-1] == (0, 176)


def test_classifier_bright_vs_dark(model_dir):
    model = get_classifier()
    assert model is not None and model.meta.name == "tiny_test_model"
    bright = model.predict(Image.fromarray(np.full((200, 300, 3), 250, np.uint8)))
    dark = model.predict(Image.fromarray(np.full((200, 300, 3), 5, np.uint8)))
    assert bright["ai_probability"] > 0.9
    assert dark["ai_probability"] < 0.4
    # 300x200 resized to shorter side 64 -> 96x64; the stitched CAM covers that frame
    assert bright["heat"].shape == (64, 96)
    assert 0.0 <= bright["heat"].min() and bright["heat"].max() <= 1.0


def test_classifier_temperature_softens_scores(model_dir):
    import json

    meta = json.loads((model_dir / "model_meta.json").read_text())
    meta["temperature"] = 10.0
    (model_dir / "model_meta.json").write_text(json.dumps(meta))
    bright = get_classifier().predict(Image.fromarray(np.full((64, 64, 3), 250, np.uint8)))
    assert 0.5 < bright["ai_probability"] < 0.9


def test_classifier_status_without_model(no_model):
    status = classifier_status()
    assert status["loaded"] is False and "No trained model" in status["reason"]


# ---------- aggregator ----------

def test_high_ai_probability_is_ai_generated():
    r = aggregate(clf(0.93), NO_FFT, CLEAN_ELA, CLEAN_NOISE, NO_FLAGS)
    assert r["verdict"] == "ai_generated" and r["confidence"] == pytest.approx(0.93)


def test_low_ai_probability_is_real():
    r = aggregate(clf(0.05), NO_FFT, CLEAN_ELA, CLEAN_NOISE, NO_FLAGS)
    assert r["verdict"] == "real" and r["confidence"] == pytest.approx(0.95)


def test_middle_band_is_inconclusive():
    r = aggregate(clf(0.5), NO_FFT, CLEAN_ELA, CLEAN_NOISE, NO_FLAGS)
    assert r["verdict"] == "inconclusive"


def test_metadata_declaration_overrides_classifier():
    r = aggregate(clf(0.1), NO_FFT, CLEAN_ELA, CLEAN_NOISE, flags(("c2pa_ai", "ai_generated")))
    assert r["verdict"] == "ai_generated" and r["confidence"] >= 0.95


def test_strong_forensics_yield_manipulated():
    ela = {"suspicious_regions": 2, "outlier_energy_share": 0.2, "reliability": "normal"}
    noise = {"suspicious_regions": 1, "inconsistent_blocks_share": 0.1}
    r = aggregate(clf(0.2), NO_FFT, ela, noise, flags(("editing_software", "manipulated")))
    assert r["verdict"] == "manipulated"
    assert set(r["manipulation_breakdown"]) == {"ela", "noise", "metadata"}


def test_moderate_forensics_erode_real_verdict():
    ela = {"suspicious_regions": 1, "outlier_energy_share": 0.05, "reliability": "normal"}
    r = aggregate(clf(0.3), NO_FFT, ela, CLEAN_NOISE, NO_FLAGS)
    assert r["verdict"] == "inconclusive"


def test_no_model_falls_back_to_fft_baseline():
    r = aggregate({"available": False}, {"baseline_ai_probability": 1.0}, CLEAN_ELA, CLEAN_NOISE, NO_FLAGS)
    assert r["ai_probability_source"] == "fft_baseline"
    assert r["ai_probability"] == pytest.approx(0.8)
    assert r["verdict"] == "ai_generated"


def test_no_model_and_no_baseline_is_inconclusive():
    r = aggregate({"available": False}, NO_FFT, CLEAN_ELA, CLEAN_NOISE, NO_FLAGS)
    assert r["verdict"] == "inconclusive" and r["ai_probability"] is None
    assert any("not available" in f["text"] for f in r["findings"])


def test_low_reliability_ela_counts_half():
    normal, _ = manipulation_score({"suspicious_regions": 1, "outlier_energy_share": 0.1, "reliability": "normal"}, CLEAN_NOISE, NO_FLAGS)
    low, _ = manipulation_score({"suspicious_regions": 1, "outlier_energy_share": 0.1, "reliability": "low"}, CLEAN_NOISE, NO_FLAGS)
    assert low == pytest.approx(normal / 2)


# ---------- summaries ----------

@pytest.mark.parametrize("p, expected", [(0.93, "likely AI generated"), (0.05, "authentic"), (0.5, "evidence is mixed")])
def test_template_summary(p, expected):
    text = template_summary(aggregate(clf(p), NO_FFT, CLEAN_ELA, CLEAN_NOISE, NO_FLAGS))
    assert expected in text


def test_summary_without_key_uses_template():
    result = aggregate(clf(0.93), NO_FFT, CLEAN_ELA, CLEAN_NOISE, NO_FLAGS)
    assert summarize(result)[1] == "template"


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


def test_gemini_summary_success(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    text = "This image is likely AI generated with 93% confidence because the classifier is confident."
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json)
        return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = aggregate(clf(0.93), NO_FFT, CLEAN_ELA, CLEAN_NOISE, NO_FLAGS)
    assert summarize(result) == (text, "gemini")
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert "base64" not in str(captured["body"])  # the image is never sent


@pytest.mark.parametrize("response", [FakeResponse(429, {}), FakeResponse(200, {"candidates": []})])
def test_gemini_failures_fall_back(monkeypatch, response):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    result = aggregate(clf(0.93), NO_FFT, CLEAN_ELA, CLEAN_NOISE, NO_FLAGS)
    assert gemini_summary(result) is None
    assert summarize(result)[1] == "template"


def test_gemini_network_error_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")

    def boom(*a, **k):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(httpx, "post", boom)
    assert summarize(aggregate(clf(0.93), NO_FFT, CLEAN_ELA, CLEAN_NOISE, NO_FLAGS))[1] == "template"
