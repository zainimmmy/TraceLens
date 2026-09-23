"""Response models. They drive the OpenAPI docs at /docs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Verdict = Literal["ai_generated", "manipulated", "real", "inconclusive"]


class Finding(BaseModel):
    signal: str = Field(examples=["classifier"])
    points_to: str = Field(examples=["ai_generated"])
    strength: Literal["high", "medium", "low", "info"]
    text: str


class Signals(BaseModel):
    classifier: dict[str, Any]
    frequency: dict[str, Any]
    ela: dict[str, Any]
    noise: dict[str, Any]
    metadata: dict[str, Any]
    heatmap_url: str | None = Field(None, description="Grad-CAM overlay as a PNG data URL")


class AnalysisReport(BaseModel):
    id: str
    filename: str | None
    analyzed_at: str
    verdict: Verdict
    verdict_label: str
    confidence: float = Field(ge=0, le=1, description="Probability that the verdict is correct")
    ai_probability: float | None = Field(None, description="Calibrated probability the image is AI generated")
    ai_probability_source: str | None
    manipulation_score: float
    manipulation_breakdown: dict[str, float]
    verdict_basis: str
    signals: Signals
    findings: list[Finding]
    summary: str
    summary_source: Literal["gemini", "template"]
    images: dict[str, str | None] = Field(description="original, gradcam, ela and noise images as data URLs")
    image_info: dict[str, Any]
    timings_ms: dict[str, int]
    version: str
    disclaimer: str


class PdfItem(BaseModel):
    name: str = Field(examples=["Page 2 · image 1"])
    page: int
    source: Literal["embedded", "rendered_page"]
    embedded_format: str = Field(description="JPEG = original bytes from the PDF; PNG = decoded pixels; rendered = page render")
    report: AnalysisReport | None
    error: str | None


class PdfReport(BaseModel):
    filename: str | None
    kind: Literal["pdf"]
    overall_verdict: Verdict = Field(description="The most concerning verdict among the images, or from the PDF itself")
    overall_basis: Literal["images", "document"] = Field(description="Whether the headline comes from an image or from the PDF's own signals")
    counts_by_verdict: dict[str, int]
    summary: str
    document: dict[str, Any] = Field(description="PDF metadata: pages, creator, producer, dates, saved revisions")
    document_flags: list[dict[str, Any]]
    extraction: dict[str, Any]
    items: list[PdfItem]
    disclaimer: str


class BatchItem(BaseModel):
    filename: str
    verdict: Verdict | None = None
    verdict_label: str | None = None
    confidence: float | None = None
    ai_probability: float | None = None
    manipulation_score: float | None = None
    summary: str | None = None
    error: str | None = None


class BatchReport(BaseModel):
    count: int
    counts_by_verdict: dict[str, int]
    items: list[BatchItem]
    disclaimer: str


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    classifier: dict[str, Any]
    llm_summaries: bool
