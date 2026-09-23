"use client";

import { useCallback, useEffect, useState } from "react";
import Dropzone from "@/components/Dropzone";
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
    <div className="space-y-6">
      <section className="max-w-3xl">
        <h1 className="text-3xl font-semibold tracking-tight">Batch screening</h1>
        <p className="mt-2 text-muted">
          Check up to {MAX_FILES} images at once, or upload a ZIP or PDF (each image inside is checked). You get a summary table with a verdict per image; open any image on the Analyze
          page for its full heatmaps and report.
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
            hint={`Up to ${MAX_FILES} images, 10 MB each · PDFs up to 20 MB · Ctrl+V adds a copied image`}
          />
          {files.length > 0 && (
            <div className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium">{files.length} file(s) ready</p>
                <button onClick={() => setFiles([])} className="text-sm text-muted hover:text-text" disabled={busy}>
                  Clear
                </button>
              </div>
              <ul className="text-sm text-muted max-h-40 overflow-auto space-y-0.5">
                {files.map((f, i) => (
                  <li key={i} className="truncate">
                    {f.name}
                  </li>
                ))}
              </ul>
              <button
                onClick={run}
                disabled={busy}
                className="mt-4 px-4 py-2 rounded-lg bg-accent text-white dark:text-black text-sm font-medium disabled:opacity-60"
              >
                {busy ? "Analyzing…" : `Analyze ${files.length} file(s)`}
              </button>
            </div>
          )}
        </section>
      )}
      {error && (
        <p role="alert" className="text-sm text-ai">
          {error}
        </p>
      )}

      {report && (
        <section className="space-y-4" data-testid="batch-report">
          <div className="flex flex-wrap items-center gap-2">
            {Object.entries(report.counts_by_verdict).map(([v, n]) => (
              <span key={v} className={`text-sm rounded-full px-3 py-1 ${VERDICT_STYLE[v as keyof typeof VERDICT_STYLE]?.bg ?? "bg-surface-2"}`}>
                {v.replace("_", " ")}: <strong>{n}</strong>
              </span>
            ))}
            <span className="flex-1" />
            <button
              onClick={() => saveBlob(new Blob([toCsv(report)], { type: "text/csv" }), "tracelens-batch.csv")}
              className="px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-surface-2"
            >
              Download CSV
            </button>
            <button
              onClick={() => {
                setReport(null);
                setFiles([]);
              }}
              className="px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-surface-2"
            >
              New batch
            </button>
          </div>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-muted border-b border-border">
                <tr>
                  <th className="p-3 font-medium">File</th>
                  <th className="p-3 font-medium">Verdict</th>
                  <th className="p-3 font-medium">Confidence</th>
                  <th className="p-3 font-medium">AI prob.</th>
                  <th className="p-3 font-medium">Manipulation</th>
                  <th className="p-3 font-medium min-w-[18rem]">Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {report.items.map((i, idx) => {
                  const s = i.verdict ? VERDICT_STYLE[i.verdict] : null;
                  return (
                    <tr key={idx} className="align-top">
                      <td className="p-3 max-w-[14rem] truncate">{i.filename}</td>
                      <td className="p-3">
                        {s ? <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${s.bg} ${s.text}`}>{i.verdict_label}</span> : <span className="text-ai text-xs">Error</span>}
                      </td>
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
          <p className="text-xs text-muted">{report.disclaimer}</p>
        </section>
      )}
    </div>
  );
}
