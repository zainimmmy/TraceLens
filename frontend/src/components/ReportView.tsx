"use client";

import { useState } from "react";
import { downloadJson, downloadPdf } from "@/lib/api";
import { bytes } from "@/lib/format";
import type { AnalysisReport } from "@/lib/types";
import EvidenceViewer from "./EvidenceViewer";
import FindingsList from "./FindingsList";
import MetadataPanel from "./MetadataPanel";
import VerdictCard from "./VerdictCard";

interface Props {
  report: AnalysisReport;
  onReset: () => void;
  /** Set when this report is one image from a PDF: shows a "Back to document" button. */
  onBack?: () => void;
  /** Extra context shown above the report, e.g. that the image came from the clipboard. */
  notice?: string | null;
}

export default function ReportView({ report, onReset, onBack, notice }: Props) {
  const [pdfState, setPdfState] = useState<"idle" | "busy" | "error">("idle");

  const pdf = async () => {
    setPdfState("busy");
    try {
      await downloadPdf(report);
      setPdfState("idle");
    } catch {
      setPdfState("error");
    }
  };

  return (
    <div className="space-y-6" data-testid="report">
      {onBack && (
        <button onClick={onBack} className="text-sm text-accent hover:underline" data-testid="back-to-document">
          ← Back to the PDF report
        </button>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-muted">Report for</p>
          <p className="font-medium truncate max-w-[28rem]">{report.filename || "uploaded image"}</p>
          <p className="text-xs text-muted">
            {report.image_info.format} · {report.image_info.width}×{report.image_info.height} · {bytes(report.image_info.bytes)} · analysed in{" "}
            {(report.timings_ms.total / 1000).toFixed(1)} s
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={pdf}
            disabled={pdfState === "busy"}
            className="px-4 py-2 rounded-lg bg-accent text-white dark:text-black text-sm font-medium hover:opacity-90 disabled:opacity-60"
          >
            {pdfState === "busy" ? "Building PDF…" : "Download PDF report"}
          </button>
          <button onClick={() => downloadJson(report)} className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-surface-2">
            JSON
          </button>
          <button onClick={onReset} className="px-4 py-2 rounded-lg border border-border text-sm hover:bg-surface-2">
            Analyze another
          </button>
        </div>
      </div>
      {pdfState === "error" && <p className="text-sm text-ai">The PDF could not be generated. Please try again.</p>}
      {notice && (
        <p className="text-sm border border-border bg-surface-2 rounded-lg px-4 py-3" data-testid="notice">
          {notice}
        </p>
      )}

      <div className="grid lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-6 items-start">
        <div className="space-y-6">
          <VerdictCard report={report} />
          <section className="card p-5 sm:p-6" data-testid="summary">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold">In plain English</h3>
              <span className="text-[11px] text-muted">{report.summary_source === "gemini" ? "Written by Gemini from the signals" : "Generated from the signals"}</span>
            </div>
            <p className="text-sm leading-relaxed">{report.summary}</p>
          </section>
        </div>
        <EvidenceViewer report={report} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6 items-start">
        <FindingsList findings={report.findings} />
        <MetadataPanel meta={report.signals.metadata} />
      </div>

      <p className="text-xs text-muted border-l-2 border-edit pl-3" data-testid="disclaimer">
        {report.disclaimer}
      </p>
    </div>
  );
}
