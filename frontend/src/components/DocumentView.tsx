"use client";

import { pct, POINTS_TO_LABEL, POINTS_TO_STYLE, VERDICT_STYLE } from "@/lib/format";
import type { PdfReport } from "@/lib/types";
import { NextScanBar } from "./ReportView";
import SectionLabel from "./SectionLabel";

const IMAGE_LABEL = {
  ai_generated: "Contains a likely AI-generated image",
  manipulated: "Contains a likely edited image",
  real: "Images look authentic",
  inconclusive: "Inconclusive",
};
const DOCUMENT_LABEL = {
  ai_generated: "The PDF declares an AI tool",
  manipulated: "The PDF shows signs of editing",
  real: IMAGE_LABEL.real,
  inconclusive: IMAGE_LABEL.inconclusive,
};

function Row({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-3 py-2.5 text-sm border-b border-border last:border-0">
      <dt className="label text-[10px] pt-0.5">{label}</dt>
      <dd className="break-words">{value || <span className="text-faint">Not recorded</span>}</dd>
    </div>
  );
}

interface Props {
  doc: PdfReport;
  onOpen: (index: number) => void;
  onReset: () => void;
  onNewFiles: (files: File[]) => void;
}

export default function DocumentView({ doc, onOpen, onReset, onNewFiles }: Props) {
  const s = VERDICT_STYLE[doc.overall_verdict];
  const d = doc.document;
  const x = doc.extraction;
  const rendered = x.mode === "rendered_pages";

  return (
    <div className="space-y-6" data-testid="document-report">
      <NextScanBar onFiles={onNewFiles} />

      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <p className="label text-[10px]">Case file · PDF document</p>
          <p className="font-display text-xl font-semibold truncate max-w-[36rem] mt-1">{doc.filename || "document.pdf"}</p>
          <p className="font-mono text-[11px] text-muted mt-1">
            {d.pages} page{d.pages === 1 ? "" : "s"} · {x.images_analyzed} {rendered ? "rendered page" : "embedded image"}
            {x.images_analyzed === 1 ? "" : "s"} analysed
          </p>
        </div>
        <button onClick={onReset} className="btn btn-ghost">
          New scan
        </button>
      </div>

      <div className="grid lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-6 items-start">
        <div className="space-y-6">
          <section className="panel p-5 sm:p-6">
            <SectionLabel num="01" right={<span className={`tag ${s.text}`}>{s.code}</span>}>
              Document verdict
            </SectionLabel>
            <h2 className={`font-display text-[26px] leading-[1.15] font-semibold uppercase tracking-wide ${s.text}`} data-testid="document-verdict">
              {(doc.overall_basis === "document" ? DOCUMENT_LABEL : IMAGE_LABEL)[doc.overall_verdict]}
            </h2>
            <p className="leading-relaxed mt-4">{doc.summary}</p>
            <div className="flex flex-wrap gap-2 mt-4">
              {Object.entries(doc.counts_by_verdict).map(([v, n]) => {
                const vs = VERDICT_STYLE[v as keyof typeof VERDICT_STYLE];
                return (
                  <span key={v} className={`tag ${vs?.text ?? "text-muted"}`}>
                    {vs?.code ?? v} × {n}
                  </span>
                );
              })}
            </div>
          </section>

          <section className="panel p-5 sm:p-6" data-testid="document-integrity">
            <SectionLabel num="02">Document integrity</SectionLabel>
            {doc.document_flags.length > 0 ? (
              <ul className="space-y-3 mb-5">
                {doc.document_flags.map((f) => (
                  <li key={f.code} className="grid grid-cols-[auto_1fr] gap-3 text-sm items-start">
                    <span className={`tag ${POINTS_TO_STYLE[f.points_to] ?? POINTS_TO_STYLE.neutral}`}>{POINTS_TO_LABEL[f.points_to] ?? f.points_to}</span>
                    <span className="leading-relaxed">{f.message}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted mb-5">No signs of the PDF itself being edited after it was created.</p>
            )}
            <dl className="border-y border-border">
              <Row label="Created with" value={d.creator} />
              <Row label="Producer" value={d.producer} />
              <Row label="Created" value={d.created} />
              <Row label="Modified" value={d.modified} />
              <Row label="Saved revisions" value={d.revisions} />
            </dl>
          </section>
        </div>

        <section className="panel p-5 sm:p-6">
          <SectionLabel num="03">{rendered ? "Rendered pages" : "Images found in the PDF"}</SectionLabel>
          <p className="text-sm text-muted -mt-1 mb-5 leading-relaxed">
            {rendered
              ? "This PDF has no embedded photos, so its pages were rendered and analysed. Rendered pages carry little forensic evidence."
              : "Each image is analysed from its original bytes inside the PDF, so compression history and camera metadata are preserved. Select one for its full report."}
          </p>
          {doc.items.length === 0 && <p className="text-sm text-muted">No images could be analysed.</p>}
          <ul className="grid sm:grid-cols-2 gap-4" data-testid="document-items">
            {doc.items.map((item, i) => {
              const r = item.report;
              const vs = r ? VERDICT_STYLE[r.verdict] : null;
              return (
                <li key={i}>
                  <button
                    onClick={() => r && onOpen(i)}
                    disabled={!r}
                    className="group w-full text-left border border-border hover:border-accent transition-colors disabled:cursor-not-allowed"
                  >
                    <div className="checker aspect-[4/3] overflow-hidden border-b border-border">
                      {r?.images.original && (
                        // eslint-disable-next-line @next/next/no-img-element -- data URL from the API
                        <img src={r.images.original} alt={item.name} className="w-full h-full object-contain" />
                      )}
                    </div>
                    <div className="p-3">
                      <p className="font-mono text-[12px] group-hover:text-accent transition-colors">{item.name}</p>
                      {r && vs ? (
                        <p className="mt-2 flex items-center gap-2">
                          <span className={`tag ${vs.text}`}>{r.verdict_label}</span>
                          {r.verdict !== "inconclusive" && <span className="font-mono text-[11px] text-muted">{pct(r.confidence)}</span>}
                        </p>
                      ) : (
                        <p className="text-xs text-ai mt-2">{item.error}</p>
                      )}
                      <p className="label text-[9px] mt-2 text-faint">
                        {item.embedded_format === "JPEG" ? "Original JPEG from the PDF" : item.embedded_format === "PNG" ? "Decoded image" : "Rendered page"}
                      </p>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
          {(x.truncated || x.skipped_small > 0 || x.skipped_duplicate > 0) && (
            <p className="text-xs text-muted mt-4">
              {x.truncated && "Only the first images were analysed to keep the free server responsive. "}
              {x.skipped_small > 0 && `${x.skipped_small} small image(s) such as logos and icons were skipped. `}
              {x.skipped_duplicate > 0 && `${x.skipped_duplicate} repeated image(s) were skipped.`}
            </p>
          )}
        </section>
      </div>

      <p className="label text-[10px] border-l-2 border-accent pl-3 normal-case tracking-[0.08em]">{doc.disclaimer}</p>
    </div>
  );
}
