from __future__ import annotations

import io
import json

import cv2
import numpy as np
import pytest
from conftest import encode, natural_image
from PIL import Image, PngImagePlugin

from app.forensics.ela import analyze_ela
from app.forensics.frequency import N_BINS, analyze_frequency, spectral_features
from app.forensics.metadata import analyze_metadata
from app.forensics.noise import analyze_noise
from app.imaging import ImageValidationError, heat_overlay, load_image


def spliced_jpeg() -> bytes:
    base = np.asarray(Image.open(io.BytesIO(encode(natural_image(640, 480, 1), quality=60))).convert("RGB")).copy()
    patch = natural_image(160, 120, 7).astype(int) + np.random.default_rng(3).normal(0, 10, (120, 160, 3))
    base[200:320, 300:460] = np.clip(patch, 0, 255).astype(np.uint8)
    return encode(base, quality=92)


def meta_for(data: bytes) -> dict:
    img = load_image(data)
    return analyze_metadata(img.raw, img.pil, img.format, img.mime)


def codes(meta: dict) -> set[str]:
    return {f["code"] for f in meta["flags"]}


# ---------- image loading ----------

@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_load_accepts_supported_formats(fmt):
    img = load_image(encode(natural_image(), fmt))
    assert img.format == fmt
    assert img.rgb.shape == (240, 320, 3)


@pytest.mark.parametrize(
    "data, message",
    [
        (b"", "empty"),
        (b"definitely not an image", "not a readable image"),
        (encode(natural_image(), "GIF"), "Only JPG, PNG and WEBP"),
        (encode(natural_image(20, 20), "PNG"), "too small"),
    ],
    ids=["empty", "text", "gif", "tiny"],
)
def test_load_rejects_bad_input(data, message):
    with pytest.raises(ImageValidationError, match=message):
        load_image(data)


def test_load_rejects_oversized(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_upload_bytes", 1000)
    with pytest.raises(ImageValidationError, match="larger than"):
        load_image(encode(natural_image(), "PNG"))


def test_exif_orientation_is_applied():
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees
    img = load_image(encode(natural_image(320, 240), exif=exif))
    assert img.rgb.shape[:2] == (320, 240)


def test_heat_overlay_matches_image_size():
    out = heat_overlay(natural_image(), np.random.rand(8, 8))
    assert out.shape == (240, 320, 3) and out.dtype == np.uint8


# ---------- ELA ----------

def test_ela_clean_image_has_no_regions():
    result = analyze_ela(load_image(encode(natural_image(640, 480), quality=85)).rgb, "JPEG")
    assert result["suspicious_regions"] == 0
    assert result["reliability"] == "normal"
    assert result["map"].shape == (480, 640)


def test_ela_finds_spliced_region():
    result = analyze_ela(load_image(spliced_jpeg()).rgb, "JPEG")
    assert result["suspicious_regions"] >= 1
    r = result["regions"][0]
    # the region should overlap the pasted patch (x 300-460, y 200-320)
    assert r["x"] < 460 and r["x"] + r["width"] > 300 and r["y"] < 320 and r["y"] + r["height"] > 200


def test_ela_marks_png_as_low_reliability():
    assert analyze_ela(natural_image(), "PNG")["reliability"] == "low"


# ---------- noise ----------

def test_noise_finds_smoothed_patch():
    rgb = natural_image(640, 480, 2).astype(np.float32) + np.random.default_rng(5).normal(0, 8, (480, 640, 3))
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    rgb[100:260, 100:300] = cv2.GaussianBlur(rgb[100:260, 100:300], (0, 0), 3)
    result = analyze_noise(rgb)
    assert result["suspicious_regions"] >= 1
    r = result["regions"][0]
    assert r["x"] < 300 and r["x"] + r["width"] > 100


def test_noise_clean_image_is_consistent():
    assert analyze_noise(natural_image(640, 480))["suspicious_regions"] == 0


def test_noise_handles_tiny_images():
    result = analyze_noise(natural_image(40, 40))
    assert result["suspicious_regions"] == 0


# ---------- frequency ----------

def test_spectral_features_shape():
    assert spectral_features(natural_image()).shape == (N_BINS,)


def test_frequency_uses_baseline_when_present(model_dir):
    (model_dir / "fft_baseline.json").write_text(json.dumps(
        {"mean": [0.0] * N_BINS, "scale": [1.0] * N_BINS, "coef": [0.0] * N_BINS, "intercept": 2.0}
    ))
    result = analyze_frequency(natural_image())
    assert result["baseline_ai_probability"] == pytest.approx(0.8808, abs=1e-3)


# ---------- metadata ----------

def test_metadata_stripped_jpeg():
    meta = meta_for(encode(natural_image()))
    assert meta["exif_present"] is False
    assert "metadata_stripped" in codes(meta)


def test_metadata_camera_and_editing_traces():
    exif = Image.Exif()
    exif[0x010F] = "Canon"
    exif[0x0110] = "EOS 80D"
    exif[0x0131] = "Adobe Photoshop 25.0"
    exif[0x0132] = "2026:05:02 10:00:00"
    exif[0x8825] = {1: "N"}
    ifd = exif.get_ifd(0x8769)
    ifd[0x9003] = "2026:05:01 09:00:00"
    meta = meta_for(encode(natural_image(), exif=exif))
    found = codes(meta)
    assert {"camera_present", "editing_software", "modified_after_capture"} <= found
    assert meta["camera"] == {"make": "Canon", "model": "EOS 80D"}
    assert meta["gps_present"] is True


def test_metadata_detects_stable_diffusion_png():
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", "a cat, Steps: 20, Sampler: Euler a, Model: sdxl")
    meta = meta_for(encode(natural_image(), "PNG", pnginfo=info))
    assert "ai_tool_declared" in codes(meta)
    assert meta["ai_generator_hint"]["source"] == "PNG text"


@pytest.mark.parametrize("caption", ["Aurora over a firefly meadow", "Imagen de la pasarela (runway)", "Leonardo at the Gemini show"])
def test_ordinary_captions_are_not_ai_declarations(caption):
    exif = Image.Exif()
    exif[0x010E] = caption  # ImageDescription
    assert "ai_tool_declared" not in codes(meta_for(encode(natural_image(), exif=exif)))


def test_metadata_detects_xmp_digital_source_type():
    xmp = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF><rdf:Description '
        'Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"/>'
        "</rdf:RDF></x:xmpmeta>"
    )
    info = PngImagePlugin.PngInfo()
    info.add_itxt("XML:com.adobe.xmp", xmp)
    meta = meta_for(encode(natural_image(), "PNG", pnginfo=info))
    assert "xmp_ai_source" in codes(meta)


def test_metadata_flags_future_dates():
    exif = Image.Exif()
    exif[0x0132] = "2999:01:01 00:00:00"
    assert "future_date" in codes(meta_for(encode(natural_image(), exif=exif)))


def test_c2pa_marker_without_valid_manifest_is_reported():
    data = encode(natural_image()) + b"jumb....c2pa-garbage"
    meta = meta_for(data)
    assert meta["c2pa_manifest"]["present"] is True
    assert "c2pa_invalid" in codes(meta)
