"""Run every analysis module on one image, in parallel, and assemble the report."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from . import __version__
from .aggregator import aggregate
from .config import settings
from .forensics.classifier import get_classifier
from .forensics.ela import analyze_ela
from .forensics.frequency import analyze_frequency
from .forensics.metadata import analyze_metadata
from .forensics.noise import analyze_noise
from .imaging import LoadedImage, heat_overlay, load_image, resize_max_side, to_jpeg_data_url, to_png_data_url
from .summary import summarize

DISCLAIMER = (
    "Results are probabilistic and should not be treated as proof. "
    "Use TraceLens to support human judgment, never to replace it."
)

_pool = ThreadPoolExecutor(max_workers=max(1, settings.analysis_threads), thread_name_prefix="tracelens")
# Caps simultaneous analyses so a small server cannot run out of memory under parallel uploads.
_analysis_slots = threading.BoundedSemaphore(max(1, settings.max_concurrent_analyses))


def _timed(fn, *args):
    start = time.perf_counter()
    out = fn(*args)
    return out, round((time.perf_counter() - start) * 1000)


def _run_classifier(img: LoadedImage) -> dict:
    clf = get_classifier()
    if clf is None:
        return {"available": False, "ai_probability": None, "model": None}
    from PIL import Image

    pred = clf.predict(Image.fromarray(img.rgb))
    return {"available": True, **pred}


def analyze_bytes(data: bytes, filename: str | None = None, *, with_images: bool = True, allow_llm: bool = True) -> dict:
    with _analysis_slots:
        return _analyze(data, filename, with_images=with_images, allow_llm=allow_llm)


def _analyze(data: bytes, filename: str | None, *, with_images: bool, allow_llm: bool) -> dict:
    t0 = time.perf_counter()
    img = load_image(data)

    futures = {
        "classifier": _pool.submit(_timed, _run_classifier, img),
        "ela": _pool.submit(_timed, analyze_ela, img.rgb, img.format, img.downscaled),
        "noise": _pool.submit(_timed, analyze_noise, img.rgb),
        "metadata": _pool.submit(_timed, analyze_metadata, img.raw, img.pil, img.format, img.mime),
        "frequency": _pool.submit(_timed, analyze_frequency, img.rgb),
    }
    results, timings = {}, {}
    for name, fut in futures.items():
        results[name], timings[name] = fut.result()

    classifier = results["classifier"]
    ela, noise = results["ela"], results["noise"]
    cam = classifier.pop("heat", None)
    ela_map, noise_map = ela.pop("map"), noise.pop("map")

    verdict = aggregate(classifier, results["frequency"], ela, noise, results["metadata"])

    images: dict[str, str | None] = {}
    heatmap_url = None
    if with_images:
        preview = resize_max_side(img.rgb, settings.preview_max_side)
        images["original"] = to_jpeg_data_url(preview)
        if cam is not None:
            heatmap_url = to_png_data_url(heat_overlay(preview, cam))
        images["gradcam"] = heatmap_url
        images["ela"] = to_png_data_url(heat_overlay(preview, ela_map, alpha=0.6))
        images["noise"] = to_png_data_url(heat_overlay(preview, noise_map, alpha=0.5))

    t_sum = time.perf_counter()
    summary, summary_source = summarize(verdict, allow_llm=allow_llm)
    timings["summary"] = round((time.perf_counter() - t_sum) * 1000)
    timings["total"] = round((time.perf_counter() - t0) * 1000)

    return {
        "id": str(uuid.uuid4()),
        "filename": filename,
        "analyzed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        **{k: verdict[k] for k in ("verdict", "verdict_label", "confidence", "ai_probability",
                                   "ai_probability_source", "manipulation_score", "manipulation_breakdown", "verdict_basis")},
        "signals": {
            "classifier": classifier,
            "frequency": results["frequency"],
            "ela": ela,
            "noise": noise,
            "metadata": results["metadata"],
            "heatmap_url": heatmap_url,
        },
        "findings": verdict["findings"],
        "summary": summary,
        "summary_source": summary_source,
        "images": images,
        "image_info": {"format": img.format, "width": img.width, "height": img.height, "bytes": len(data),
                       "original_width": img.original_width, "original_height": img.original_height, "downscaled": img.downscaled},
        "timings_ms": timings,
        "version": __version__,
        "disclaimer": DISCLAIMER,
    }
