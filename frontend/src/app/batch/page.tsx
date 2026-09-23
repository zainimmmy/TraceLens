"use client";

import { useCallback, useEffect, useState } from "react";
import Dropzone from "@/components/Dropzone";
import SectionLabel from "@/components/SectionLabel";
import { analyzeBatch, filesFromClipboard, saveBlob } from "@/lib/api";
import { pct, VERDICT_STYLE } from "@/lib/format";
import type { BatchReport } from "@/lib/types";

const MAX_FILES = 20;

function toCsv(report: BatchReport): string {
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const rows = [["filename", "verdict", "confidence", "ai_probability", "manipulation_score", "summary", "error"]];
  for (const i of report.items) {
    rows.push([i.filename, i.verdict ?? "", i.confidence ?? "", i.ai_probability ?? "", i.manipulation_score ?? "", i.summary ?? "", i.error ?? ""].map(String));
  }
  return rows.map((r) => r.map(esc).join(",")).join("\n");
}

export default function BatchPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [report, setReport] = useState<BatchReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const add = useCallback((incoming: File[]) => {
    setError(null);
    const ok = incoming.filter((f) => /\.(jpe?g|png|webp|zip|pdf)$/i.test(f.name));
    if (ok.length < incoming.length) setError("Some files were skipped: only JPG, PNG, WEBP, PDF and ZIP are accepted.");
    setFiles((prev) => [...prev, ...ok].slice(0, MAX_FILES));
  }, []);

  // Ctrl+V adds copied images or screenshots to the batch.
  const collecting = !busy && !report;
  useEffect(() => {
    if (!collecting) return;
    const onPaste = (e: ClipboardEvent) => {
      const pasted = filesFromClipboard(e);
      if (pasted.length) {
        e.preventDefault();
        add(pasted);
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [collecting, add]);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setReport(await analyzeBatch(files));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-8">
      <section className="max-w-3xl">
        <p className="label">
          <span className="label-num">■</span> Bulk screening
        </p>
        <h1 className="font-display text-4xl font-semibold tracking-tight mt-4">Batch screening</h1>
        <p className="mt-4 text-muted leading-relaxed">
          Check up to {MAX_FILES} images at once, or upload a ZIP or PDF (each image inside is checked). You get one verdict per image; open any
          image on the Analyze page for its full heatmaps and report.
        </p>
      </section>

      {!report && (
        <section className="max-w-3xl space-y-4">
          <Dropzone
            multiple
            accept="image/jpeg,image/png,image/webp,.zip,application/zip,.pdf,application/pdf"
            onFiles={add}
            disabled={busy}
            title="Drop images, a ZIP or a PDF here, or paste"
            hint={`Up to ${MAX_FILES} images · 10 MB each  //  PDFs up to 20 MB  //  Ctrl+V adds a copied image`}
          />
          {files.length > 0 && (
            <div className="panel p-5">
              <SectionLabel
                num="Q"
                right={
                  <button onClick={() => setFiles([])} className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted hover:text-accent" disabled={busy}>
                    Clear
                  </button>
                }
              >
                {`${files.length} file(s) queued`}
              </SectionLabel>
              <ul className="font-mono text-[12px] text-muted max-h-40 overflow-auto divide-y divide-border border-y border-border">
                {files.map((f, i) => (
                  <li key={i} className="truncate py-1.5">
                    {f.name}
                  </li>
                ))}
              </ul>
              <button onClick={run} disabled={busy} className="btn btn-primary mt-5">
                {busy ? "Analyzing…" : `Analyze ${files.length} file(s)`}
              </button>
            </div>
          )}
        </section>
      )}
      {error && (
        <p role="alert" className="text-sm text-ai border-l-2 border-ai bg-ai-soft px-4 py-3">
          {error}
        </p>
      )}

      {report && (
        <section className="space-y-4" data-testid="batch-report">
          <div className="flex flex-wrap items-center gap-2">
            {Object.entries(report.counts_by_verdict).map(([v, n]) => {
              const vs = VERDICT_STYLE[v as keyof typeof VERDICT_STYLE];
              return (
                <span key={v} className={`tag ${vs?.text ?? "text-ai"}`}>
                  {vs?.code ?? v} × {n}
                </span>
              );
            })}
            <span className="flex-1" />
            <button onClick={() => saveBlob(new Blob([toCsv(report)], { type: "text/csv" }), "tracelens-batch.csv")} className="btn btn-ghost">
              Download CSV
            </button>
            <button
              onClick={() => {
                setReport(null);
                setFiles([]);
              }}
              className="btn btn-ghost"
            >
              New batch
            </button>
          </div>
          <div className="panel overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left border-b border-border">
                <tr className="label text-[10px]">
                  <th className="p-3 font-normal">File</th>
                  <th className="p-3 font-normal">Verdict</th>
                  <th className="p-3 font-normal">Confidence</th>
                  <th className="p-3 font-normal">AI prob.</th>
                  <th className="p-3 font-normal">Manipulation</th>
                  <th className="p-3 font-normal min-w-[18rem]">Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {report.items.map((i, idx) => {
                  const s = i.verdict ? VERDICT_STYLE[i.verdict] : null;
                  return (
                    <tr key={idx} className="align-top hover:bg-surface-2 transition-colors">
                      <td className="p-3 font-mono text-[12px] max-w-[14rem] truncate">{i.filename}</td>
                      <td className="p-3">{s ? <span className={`tag ${s.text}`}>{i.verdict_label}</span> : <span className="tag text-ai">Error</span>}</td>
                      <td className="p-3 font-mono">{i.verdict === "inconclusive" ? "—" : pct(i.confidence)}</td>
                      <td className="p-3 font-mono">{pct(i.ai_probability)}</td>
                      <td className="p-3 font-mono">{pct(i.manipulation_score)}</td>
                      <td className="p-3 text-muted">{i.error ?? i.summary}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="label text-[10px] normal-case tracking-[0.08em]">{report.disclaimer}</p>
        </section>
      )}
    </div>
  );
}
