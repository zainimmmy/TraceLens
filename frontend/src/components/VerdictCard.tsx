import type { AnalysisReport } from "@/lib/types";
import { pct, VERDICT_STYLE } from "@/lib/format";

function Meter({ label, value, color, hint }: { label: string; value: number | null; color: string; hint: string }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-muted">{label}</span>
        <span className="font-mono font-medium">{pct(value)}</span>
      </div>
      <div className="h-2 rounded-full bg-surface-2 overflow-hidden relative" title={hint}>
        {/* inconclusive band 40-60% */}
        <div className="absolute inset-y-0 left-[40%] w-[20%] bg-border/70" />
        <div className={`h-full rounded-full relative ${color}`} style={{ width: `${Math.round((value ?? 0) * 100)}%` }} />
      </div>
    </div>
  );
}

export default function VerdictCard({ report }: { report: AnalysisReport }) {
  const s = VERDICT_STYLE[report.verdict];
  const basis: Record<string, string> = {
    metadata_declaration: "Decided by provenance metadata",
    classifier: "Decided by the calibrated classifier",
    fft_baseline: "Decided by the frequency baseline model",
    forensics: "Decided by forensic signals",
  };
  return (
    <section className="card p-5 sm:p-6" data-testid="verdict-card">
      <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${s.bg} ${s.text}`}>
        <span aria-hidden="true">{s.icon}</span>
        Verdict
      </div>
      <h2 className={`mt-3 text-2xl sm:text-3xl font-semibold tracking-tight ${s.text}`} data-testid="verdict-label">
        {report.verdict_label}
      </h2>
      <p className="text-sm text-muted mt-1">
        {report.verdict === "inconclusive" ? "No confident call" : `${pct(report.confidence)} confidence`} ·{" "}
        {basis[report.verdict_basis] ?? "Combined signals"}
      </p>

      <div className="mt-6 space-y-4">
        <Meter
          label="AI-generated probability"
          value={report.ai_probability}
          color="bg-ai"
          hint="Calibrated classifier probability. The shaded band (40-60%) is treated as inconclusive."
        />
        <Meter
          label="Manipulation score"
          value={report.manipulation_score}
          color="bg-edit"
          hint="Combined evidence from Error Level Analysis, noise consistency and metadata edits."
        />
      </div>
      {report.ai_probability === null && (
        <p className="mt-4 text-xs text-muted">The AI classifier is not installed on this server; only forensics and metadata were used.</p>
      )}
    </section>
  );
}
