"use client";

import { useState, type ReactNode } from "react";
import type { AnalysisReport, Region } from "@/lib/types";
import SectionLabel from "./SectionLabel";

type Layer = "gradcam" | "ela" | "noise";

const LAYERS: Record<Layer, { label: string; explain: string }> = {
  gradcam: {
    label: "Classifier heatmap",
    explain:
      "Grad-CAM. Warmer areas are the parts of the image that pushed the classifier towards “AI generated”. It shows where the model looked, not proof of editing.",
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

function Frame({ caption, children }: { caption: ReactNode; children: ReactNode }) {
  return (
    <figure>
      <div className="checker border border-border relative overflow-hidden">{children}</div>
      <figcaption className="label text-[10px] mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">{caption}</figcaption>
    </figure>
  );
}

function Boxes({ regions, width, height }: { regions: Region[]; width: number; height: number }) {
  return (
    <>
      {regions.map((r, i) => (
        <div
          key={i}
          className="absolute border border-accent shadow-[0_0_0_1px_rgba(0,0,0,0.7)]"
          style={{
            left: `${(r.x / width) * 100}%`,
            top: `${(r.y / height) * 100}%`,
            width: `${(r.width / width) * 100}%`,
            height: `${(r.height / height) * 100}%`,
          }}
        >
          <span className="absolute -top-4 left-0 font-mono text-[9px] text-accent bg-bg/80 px-1">R{i + 1}</span>
        </div>
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
    <section className="panel p-5 sm:p-6" data-testid="evidence-viewer">
      <SectionLabel num="03">Visual evidence</SectionLabel>
      <div role="tablist" className="flex flex-wrap border-b border-border mb-4 -mt-1">
        {available.map((l) => (
          <button
            key={l}
            role="tab"
            aria-selected={layer === l}
            onClick={() => setLayer(l)}
            className={`px-3 py-2 -mb-px border-b-2 font-mono text-[11px] uppercase tracking-[0.12em] transition-colors ${
              layer === l ? "border-accent text-text" : "border-transparent text-muted hover:text-text"
            }`}
          >
            {LAYERS[l].label}
          </button>
        ))}
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <Frame caption={<span>Source</span>}>
          {/* eslint-disable-next-line @next/next/no-img-element -- data URL from the API */}
          <img src={report.images.original} alt="Uploaded image" className="w-full h-auto block" />
        </Frame>
        <Frame
          caption={
            <>
              <span className="text-text">{LAYERS[layer].label}</span>
              <label className="inline-flex items-center gap-2">
                Overlay
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={opacity}
                  onChange={(e) => setOpacity(Number(e.target.value))}
                  className="w-20"
                  aria-label="Overlay opacity"
                />
              </label>
              {regions.length > 0 && (
                <label className="inline-flex items-center gap-1.5">
                  <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />
                  {regions.length} region{regions.length === 1 ? "" : "s"}
                </label>
              )}
            </>
          }
        >
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
          {showBoxes && regions.length > 0 && <Boxes regions={regions} width={width} height={height} />}
        </Frame>
      </div>
      <p className="text-sm text-muted mt-5 leading-relaxed">{LAYERS[layer].explain}</p>
      {layer === "ela" && report.signals.ela.reliability === "low" && (
        <p className="text-xs text-edit mt-2">This file is not a JPEG, so Error Level Analysis is less reliable here.</p>
      )}
    </section>
  );
}
