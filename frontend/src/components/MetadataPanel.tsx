"use client";

import { useState, type ReactNode } from "react";
import type { MetadataSignal } from "@/lib/types";
import SectionLabel from "./SectionLabel";

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-[8.5rem_1fr] gap-3 py-2.5 text-sm border-b border-border last:border-0">
      <dt className="label text-[10px] pt-0.5">{label}</dt>
      <dd className="break-words">{value}</dd>
    </div>
  );
}

export default function MetadataPanel({ meta }: { meta: MetadataSignal }) {
  const [showRaw, setShowRaw] = useState(false);
  const c2pa = meta.c2pa_manifest;
  const camera = meta.camera ? [meta.camera.make, meta.camera.model].filter(Boolean).join(" ") : null;
  const rawEntries = Object.entries(meta.exif ?? {});
  const none = <span className="text-faint">Not recorded</span>;

  let c2paText: ReactNode = <span className="text-faint">None attached</span>;
  if (c2pa) {
    if (c2pa.declares_ai) c2paText = <span className="text-ai">Declares AI-generated content</span>;
    else if (c2pa.validated) c2paText = <span className="text-real">Valid content credentials</span>;
    else c2paText = <span className="text-edit">Present but not validated</span>;
  }

  return (
    <section className="panel p-5 sm:p-6" data-testid="metadata-panel">
      <SectionLabel num="05">Metadata and provenance</SectionLabel>
      <dl className="border-y border-border">
        <Row label="Camera EXIF" value={meta.exif_present ? camera || "Present (no camera model)" : <span className="text-faint">Missing</span>} />
        <Row label="Software" value={meta.software_tag || none} />
        <Row label="Captured" value={meta.dates?.original ? <span className="font-mono text-[13px]">{meta.dates.original}</span> : none} />
        <Row label="Last modified" value={meta.dates?.modified ? <span className="font-mono text-[13px]">{meta.dates.modified}</span> : none} />
        <Row label="GPS location" value={meta.gps_present ? "Present (hidden for privacy)" : <span className="text-faint">None</span>} />
        <Row label="C2PA credentials" value={c2paText} />
        {c2pa?.claim_generator && <Row label="Signed with" value={c2pa.claim_generator} />}
        {c2pa?.signed_by && <Row label="Signed by" value={c2pa.signed_by} />}
        {c2pa?.actions && c2pa.actions.length > 0 && <Row label="Edit history" value={c2pa.actions.join(", ")} />}
        {meta.ai_generator_hint && (
          <Row label="AI tool trace" value={<span className="text-ai">{`${meta.ai_generator_hint.match} (in ${meta.ai_generator_hint.source})`}</span>} />
        )}
        {meta.png_text_keys && <Row label="PNG text fields" value={<span className="font-mono text-[13px]">{meta.png_text_keys.join(", ")}</span>} />}
      </dl>
      {rawEntries.length > 0 && (
        <div className="mt-3">
          <button onClick={() => setShowRaw((s) => !s)} className="font-mono text-[11px] uppercase tracking-[0.14em] text-accent hover:underline">
            {showRaw ? "Hide" : "Show"} all {rawEntries.length} EXIF tags
          </button>
          {showRaw && (
            <pre className="mt-2 text-xs font-mono bg-bg border border-border p-3 max-h-64 overflow-auto text-muted">
              {rawEntries.map(([k, v]) => `${k.padEnd(24)} ${v}`).join("\n")}
            </pre>
          )}
        </div>
      )}
    </section>
  );
}
