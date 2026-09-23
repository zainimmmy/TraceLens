"use client";

import { useState, type ReactNode } from "react";
import type { MetadataSignal } from "@/lib/types";

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-3 py-2 text-sm border-b border-border last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="break-words">{value}</dd>
    </div>
  );
}

export default function MetadataPanel({ meta }: { meta: MetadataSignal }) {
  const [showRaw, setShowRaw] = useState(false);
  const c2pa = meta.c2pa_manifest;
  const camera = meta.camera ? [meta.camera.make, meta.camera.model].filter(Boolean).join(" ") : null;
  const rawEntries = Object.entries(meta.exif ?? {});

  let c2paText: ReactNode = "None attached";
  if (c2pa) {
    if (c2pa.declares_ai) c2paText = <span className="text-ai font-medium">Declares AI-generated content</span>;
    else if (c2pa.validated) c2paText = <span className="text-real font-medium">Valid content credentials</span>;
    else c2paText = <span className="text-edit font-medium">Present but not validated</span>;
  }

  return (
    <section className="card p-5 sm:p-6" data-testid="metadata-panel">
      <h3 className="font-semibold mb-3">Metadata and provenance</h3>
      <dl>
        <Row label="Camera EXIF" value={meta.exif_present ? camera || "Present (no camera model)" : "Missing"} />
        <Row label="Software" value={meta.software_tag || "Not recorded"} />
        <Row label="Captured" value={meta.dates?.original || "Unknown"} />
        <Row label="Last modified" value={meta.dates?.modified || "Unknown"} />
        <Row label="GPS location" value={meta.gps_present ? "Present (not shown for privacy)" : "None"} />
        <Row label="C2PA credentials" value={c2paText} />
        {c2pa?.claim_generator && <Row label="Signed with" value={c2pa.claim_generator} />}
        {c2pa?.signed_by && <Row label="Signed by" value={c2pa.signed_by} />}
        {c2pa?.actions && c2pa.actions.length > 0 && <Row label="Edit history" value={c2pa.actions.join(", ")} />}
        {meta.ai_generator_hint && (
          <Row label="AI tool trace" value={<span className="text-ai">{`${meta.ai_generator_hint.match} (in ${meta.ai_generator_hint.source})`}</span>} />
        )}
        {meta.png_text_keys && <Row label="PNG text fields" value={meta.png_text_keys.join(", ")} />}
      </dl>
      {rawEntries.length > 0 && (
        <div className="mt-3">
          <button onClick={() => setShowRaw((s) => !s)} className="text-sm text-accent hover:underline">
            {showRaw ? "Hide" : "Show"} all {rawEntries.length} EXIF tags
          </button>
          {showRaw && (
            <pre className="mt-2 text-xs font-mono bg-surface-2 rounded-lg p-3 max-h-64 overflow-auto">
              {rawEntries.map(([k, v]) => `${k}: ${v}`).join("\n")}
            </pre>
          )}
        </div>
      )}
    </section>
  );
}
