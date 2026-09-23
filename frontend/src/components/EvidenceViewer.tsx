"use client";

import { useState } from "react";
import type { AnalysisReport, Region } from "@/lib/types";

type Layer = "gradcam" | "ela" | "noise";

const LAYERS: Record<Layer, { label: string; explain: string }> = {
  gradcam: {
    label: "Classifier heatmap",
    explain:
      "Grad-CAM: warmer areas are the parts of the image that pushed the classifier towards “AI generated”. It shows where the model looked, not proof of editing.",
  },
  ela: {
    label: "Error Level Analysis",
    explain:
      "The image is re-saved as a JPEG and compared with itself. Pasted or edited areas often recompress differently and stand out as bright patches. Boxes mark statistically unusual regions.",
  },
  noise: {
    label: "Noise consistency",
    explain:
      "Camera sensors leave an even noise pattern. Warm areas have noise that does not match the rest of the photo, which can indicate pasted, retouched or generated patches.",
  },
};

function Boxes({ regions, width, height, color }: { regions: Region[]; width: number; height: number; color: string }) {
  return (
    <>
      {regions.map((r, i) => (
        <div
          key={i}
          className={`absolute border-2 rounded-sm ${color}`}
          style={{
            left: `${(r.x / width) * 100}%`,
            top: `${(r.y / height) * 100}%`,
            width: `${(r.width / width) * 100}%`,
            height: `${(r.height / height) * 100}%`,
          }}
        />
      ))}
    </>
  );
}

export default function EvidenceViewer({ report }: { report: AnalysisReport }) {
  const available = (Object.keys(LAYERS) as Layer[]).filter((l) => report.images[l]);
  const [layer, setLayer] = useState<Layer>(available[0] ?? "ela");
  const [opacity, setOpacity] = useState(100);
  const [showBoxes, setShowBoxes] = useState(true);
  const { width, height } = report.image_info;
  const regions = layer === "ela" ? report.signals.ela.regions : layer === "noise" ? report.signals.noise.regions : [];
  const overlay = report.images[layer];

  return (
    <section className="card p-5 sm:p-6" data-testid="evidence-viewer">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h3 className="font-semibold">Visual evidence</h3>
        <div role="tablist" className="flex flex-wrap gap-1 bg-surface-2 p-1 rounded-lg text-sm">
          {available.map((l) => (
            <button
              key={l}
              role="tab"
              aria-selected={layer === l}
              onClick={() => setLayer(l)}
              className={`px-3 py-1 rounded-md transition-colors ${layer === l ? "bg-surface shadow-sm font-medium" : "text-muted hover:text-text"}`}
            >
              {LAYERS[l].label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <figure>
          <div className="checker rounded-lg overflow-hidden border border-border">
            {/* eslint-disable-next-line @next/next/no-img-element -- data URL from the API */}
            <img src={report.images.original} alt="Uploaded image" className="w-full h-auto block" />
          </div>
          <figcaption className="text-xs text-muted mt-2">Original</figcaption>
        </figure>
        <figure>
          <div className="checker rounded-lg overflow-hidden border border-border relative">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={report.images.original} alt="" className="w-full h-auto block" />
            {overlay && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={overlay}
                alt={`${LAYERS[layer].label} overlay`}
                className="absolute inset-0 w-full h-full"
                style={{ opacity: opacity / 100 }}
              />
            )}
            {showBoxes && regions.length > 0 && (
              <Boxes regions={regions} width={width} height={height} color="border-white shadow-[0_0_0_1px_rgba(0,0,0,0.6)]" />
            )}
          </div>
          <figcaption className="text-xs text-muted mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
            <span>{LAYERS[layer].label}</span>
            <label className="inline-flex items-center gap-2">
              Overlay
              <input
                type="range"
                min={0}
                max={100}
                value={opacity}
                onChange={(e) => setOpacity(Number(e.target.value))}
                className="w-24 accent-[var(--accent)]"
                aria-label="Overlay opacity"
              />
            </label>
            {regions.length > 0 && (
              <label className="inline-flex items-center gap-1.5">
                <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />
                {regions.length} region{regions.length === 1 ? "" : "s"}
              </label>
            )}
          </figcaption>
        </figure>
      </div>
      <p className="text-sm text-muted mt-4 leading-relaxed">{LAYERS[layer].explain}</p>
      {layer === "ela" && report.signals.ela.reliability === "low" && (
        <p className="text-xs text-edit mt-2">This file is not a JPEG, so Error Level Analysis is less reliable here.</p>
      )}
    </section>
  );
}
