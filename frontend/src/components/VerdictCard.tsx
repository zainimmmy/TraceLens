import type { AnalysisReport } from "@/lib/types";
import { pct, VERDICT_STYLE } from "@/lib/format";
import SectionLabel from "./SectionLabel";

/** Segmented gauge with the 40-60% inconclusive band marked underneath. */
function Meter({ label, value, color, hint }: { label: string; value: number | null; color: string; hint: string }) {
  const filled = value === null ? 0 : Math.round(value * 24);
  return (
    <div title={hint}>
      <div className="flex justify-between items-baseline mb-2">
        <span className="label">{label}</span>
        <span className="font-mono text-sm">{pct(value)}</span>
      </div>
      <div className="grid grid-cols-[repeat(24,minmax(0,1fr))] gap-[3px] h-2.5">
        {Array.from({ length: 24 }, (_, i) => (
          <span key={i} className={i < filled ? color : "bg-surface-2"} />
        ))}
      </div>
      <div className="relative h-3 mt-1">
        <span className="absolute left-[40%] w-[20%] top-0 h-1 border-x border-b border-border-strong" />
      </div>
    </div>
  );
}

export default function VerdictCard({ report }: { report: AnalysisReport }) {
  const s = VERDICT_STYLE[report.verdict];
  const basis: Record<string, string> = {
    metadata_declaration: "Provenance metadata",
    classifier: "Calibrated classifier",
    fft_baseline: "Frequency baseline model",
    forensics: "Forensic signals",
  };
  return (
    <section className="panel p-5 sm:p-6" data-testid="verdict-card">
      <SectionLabel num="01" right={<span className={`tag ${s.text}`}>{s.code}</span>}>
        Verdict
      </SectionLabel>
      <h2 className={`font-display text-[28px] sm:text-[32px] leading-[1.1] font-semibold uppercase tracking-wide ${s.text}`} data-testid="verdict-label">
        {report.verdict_label}
      </h2>
      <dl className="mt-4 grid grid-cols-2 gap-4 border-y border-border py-3">
        <div>
          <dt className="label text-[10px]">Confidence</dt>
          <dd className="font-mono text-lg mt-0.5">{report.verdict === "inconclusive" ? "—" : pct(report.confidence)}</dd>
        </div>
        <div>
          <dt className="label text-[10px]">Decided by</dt>
          <dd className="text-sm mt-1.5">{basis[report.verdict_basis] ?? "Combined signals"}</dd>
        </div>
      </dl>

      <div className="mt-5 space-y-3">
        <Meter
          label="AI-generated probability"
          value={report.ai_probability}
          color="bg-ai"
          hint="Calibrated classifier probability. The bracket marks the 40-60% inconclusive band."
        />
        <Meter
          label="Manipulation score"
          value={report.manipulation_score}
          color="bg-edit"
          hint="Combined evidence from Error Level Analysis, noise consistency and metadata edits."
        />
      </div>
      {report.ai_probability === null && (
        <p className="mt-3 text-xs text-muted">No AI classifier is installed on this server, so only forensics and metadata were used.</p>
      )}
    </section>
  );
}
