"use client";

import { useState } from "react";
import { ACCEPT_ATTR, downloadJson, downloadPdf } from "@/lib/api";
import { bytes } from "@/lib/format";
import type { AnalysisReport } from "@/lib/types";
import Dropzone from "./Dropzone";
import EvidenceViewer from "./EvidenceViewer";
import FindingsList from "./FindingsList";
import MetadataPanel from "./MetadataPanel";
import SectionLabel from "./SectionLabel";
import VerdictCard from "./VerdictCard";

interface Props {
  report: AnalysisReport;
  /** Analyse a new file straight from the report page. */
  onNewFiles: (files: File[]) => void;
  /** Back to the empty start screen. */
  onReset: () => void;
  /** Set when this report is one image from a PDF: shows a "Back to the PDF report" link. */
  onBack?: () => void;
  /** Extra context shown above the report, e.g. that the image came from the clipboard. */
  notice?: string | null;
}

/** The "analyse another" bar shown above every report. */
export function NextScanBar({ onFiles }: { onFiles: (files: File[]) => void }) {
  return (
    <Dropzone
      variant="compact"
      accept={ACCEPT_ATTR}
      onFiles={onFiles}
      title="Analyze another image or PDF"
      hint="Drop it here, paste with Ctrl+V, or browse"
    />
  );
}

export default function ReportView({ report, onNewFiles, onReset, onBack, notice }: Props) {
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
      <NextScanBar onFiles={onNewFiles} />

      {onBack && (
        <button onClick={onBack} className="font-mono text-[11px] uppercase tracking-[0.14em] text-accent hover:underline" data-testid="back-to-document">
          ← Back to the PDF report
        </button>
      )}

      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <p className="label text-[10px]">Case file</p>
          <p className="font-display text-xl font-semibold truncate max-w-[36rem] mt-1">{report.filename || "uploaded image"}</p>
          <p className="font-mono text-[11px] text-muted mt-1">
            {report.image_info.format} · {report.image_info.width}×{report.image_info.height} · {bytes(report.image_info.bytes)} ·{" "}
            {(report.timings_ms.total / 1000).toFixed(1)}s · ID {report.id.slice(0, 8)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={pdf} disabled={pdfState === "busy"} className="btn btn-primary">
            {pdfState === "busy" ? "Building PDF…" : "Download PDF report"}
          </button>
          <button onClick={() => downloadJson(report)} className="btn btn-ghost">
            JSON
          </button>
          <button onClick={onReset} className="btn btn-ghost">
            New scan
          </button>
        </div>
      </div>
      {pdfState === "error" && <p className="text-sm text-ai">The PDF could not be generated. Please try again.</p>}
      {notice && (
        <p className="text-sm border-l-2 border-edit bg-edit-soft px-4 py-3" data-testid="notice">
          {notice}
        </p>
      )}

      <div className="grid lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-6 items-start">
        <div className="space-y-6">
          <VerdictCard report={report} />
          <section className="panel p-5 sm:p-6" data-testid="summary">
            <SectionLabel
              num="02"
              right={<span className="label text-[10px] text-faint">{report.summary_source === "gemini" ? "Gemini" : "Auto-generated"}</span>}
            >
              Assessment
            </SectionLabel>
            <p className="leading-relaxed">{report.summary}</p>
          </section>
        </div>
        <EvidenceViewer report={report} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6 items-start">
        <FindingsList findings={report.findings} />
        <MetadataPanel meta={report.signals.metadata} />
      </div>

      <p className="label text-[10px] border-l-2 border-accent pl-3 normal-case tracking-[0.08em]" data-testid="disclaimer">
        {report.disclaimer}
      </p>
    </div>
  );
}
