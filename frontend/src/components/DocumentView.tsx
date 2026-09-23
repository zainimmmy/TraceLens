"use client";

import { pct, POINTS_TO_LABEL, POINTS_TO_STYLE, VERDICT_STYLE } from "@/lib/format";
import type { PdfReport } from "@/lib/types";

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
    <div className="grid grid-cols-[8rem_1fr] gap-3 py-2 text-sm border-b border-border last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="break-words">{value || "Not recorded"}</dd>
    </div>
  );
}

export default function DocumentView({ doc, onOpen, onReset }: { doc: PdfReport; onOpen: (index: number) => void; onReset: () => void }) {
  const s = VERDICT_STYLE[doc.overall_verdict];
  const d = doc.document;
  const x = doc.extraction;
  const rendered = x.mode === "rendered_pages";

  return (
    <div className="space-y-6" data-testid="document-report">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-muted">PDF report for</p>
          <p className="font-medium truncate max-w-[28rem]">{doc.filename || "document.pdf"}</p>
          <p className="text-xs text-muted">
            {d.pages} page{d.pages === 1 ? "" : "s"} · {x.images_analyzed} {rendered ? "rendered page" : "embedded image"}
            {x.images_analyzed === 1 ? "" : "s"} analysed
          </p>
        </div>
        <button onClick={onReset} className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-surface-2">
          Analyze another
        </button>
      </div>

      <div className="grid lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-6 items-start">
        <div className="space-y-6">
          <section className="card p-5 sm:p-6">
            <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${s.bg} ${s.text}`}>
              <span aria-hidden="true">{s.icon}</span>
              Document verdict
            </div>
            <h2 className={`mt-3 text-2xl font-semibold tracking-tight ${s.text}`} data-testid="document-verdict">
              {(doc.overall_basis === "document" ? DOCUMENT_LABEL : IMAGE_LABEL)[doc.overall_verdict]}
            </h2>
            <p className="text-sm leading-relaxed mt-3">{doc.summary}</p>
            <div className="flex flex-wrap gap-2 mt-4">
              {Object.entries(doc.counts_by_verdict).map(([v, n]) => {
                const vs = VERDICT_STYLE[v as keyof typeof VERDICT_STYLE];
                return (
                  <span key={v} className={`text-xs rounded-full px-2.5 py-1 ${vs?.bg ?? "bg-surface-2"} ${vs?.text ?? ""}`}>
                    {v.replace("_", " ")}: <strong>{n}</strong>
                  </span>
                );
              })}
            </div>
          </section>

          <section className="card p-5 sm:p-6" data-testid="document-integrity">
            <h3 className="font-semibold mb-3">Document integrity</h3>
            {doc.document_flags.length > 0 ? (
              <ul className="space-y-2 mb-4">
                {doc.document_flags.map((f) => (
                  <li key={f.code} className="flex gap-3 text-sm">
                    <span className={`shrink-0 h-fit text-[11px] font-medium rounded-full px-2 py-0.5 ${POINTS_TO_STYLE[f.points_to] ?? POINTS_TO_STYLE.neutral}`}>
                      {POINTS_TO_LABEL[f.points_to] ?? f.points_to}
                    </span>
                    <span className="leading-relaxed">{f.message}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted mb-4">No signs of the PDF itself being edited after it was created.</p>
            )}
            <dl>
              <Row label="Created with" value={d.creator} />
              <Row label="Producer" value={d.producer} />
              <Row label="Created" value={d.created} />
              <Row label="Modified" value={d.modified} />
              <Row label="Saved revisions" value={d.revisions} />
            </dl>
          </section>
        </div>

        <section className="card p-5 sm:p-6">
          <h3 className="font-semibold">{rendered ? "Rendered pages" : "Images found in the PDF"}</h3>
          <p className="text-sm text-muted mt-1 mb-4">
            {rendered
              ? "This PDF has no embedded photos, so its pages were rendered and analysed. Rendered pages carry little forensic evidence."
              : "Each image is analysed from its original bytes inside the PDF, so compression history and camera metadata are preserved. Select one for its full report."}
          </p>
          {doc.items.length === 0 && <p className="text-sm text-muted">No images could be analysed.</p>}
          <ul className="grid sm:grid-cols-2 gap-3" data-testid="document-items">
            {doc.items.map((item, i) => {
              const r = item.report;
              const vs = r ? VERDICT_STYLE[r.verdict] : null;
              return (
                <li key={i}>
                  <button
                    onClick={() => r && onOpen(i)}
                    disabled={!r}
                    className="w-full text-left rounded-lg border border-border hover:border-accent transition-colors overflow-hidden disabled:cursor-not-allowed"
                  >
                    <div className="checker aspect-[4/3] overflow-hidden">
                      {r?.images.original && (
                        // eslint-disable-next-line @next/next/no-img-element -- data URL from the API
                        <img src={r.images.original} alt={item.name} className="w-full h-full object-contain" />
                      )}
                    </div>
                    <div className="p-3">
                      <p className="text-sm font-medium">{item.name}</p>
                      {r && vs ? (
                        <p className="text-xs mt-1 flex items-center gap-2">
                          <span className={`rounded-full px-2 py-0.5 font-medium ${vs.bg} ${vs.text}`}>{r.verdict_label}</span>
                          {r.verdict !== "inconclusive" && <span className="text-muted">{pct(r.confidence)}</span>}
                        </p>
                      ) : (
                        <p className="text-xs text-ai mt-1">{item.error}</p>
                      )}
                      <p className="text-[11px] text-muted mt-1">
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

      <p className="text-xs text-muted border-l-2 border-edit pl-3">{doc.disclaimer}</p>
    </div>
  );
}
