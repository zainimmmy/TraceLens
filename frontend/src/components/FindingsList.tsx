import type { Finding } from "@/lib/types";
import { POINTS_TO_LABEL, POINTS_TO_STYLE } from "@/lib/format";

const SIGNAL_LABEL: Record<string, string> = {
  classifier: "Classifier",
  ela: "ELA",
  noise: "Noise",
  metadata: "Metadata",
  pdf: "PDF",
};
const ORDER = { high: 0, medium: 1, low: 2, info: 3 };

export default function FindingsList({ findings }: { findings: Finding[] }) {
  const sorted = [...findings].sort((a, b) => ORDER[a.strength] - ORDER[b.strength]);
  return (
    <section className="card p-5 sm:p-6" data-testid="findings">
      <h3 className="font-semibold mb-4">Every signal, broken out</h3>
      <ul className="divide-y divide-border">
        {sorted.map((f, i) => (
          <li key={i} className="py-3 first:pt-0 last:pb-0 flex gap-3">
            <span className="shrink-0 w-20 text-xs font-medium text-muted pt-0.5">{SIGNAL_LABEL[f.signal] ?? f.signal}</span>
            <p className="text-sm flex-1 leading-relaxed">{f.text}</p>
            <span className="shrink-0 flex flex-col items-end gap-1">
              <span className={`text-[11px] font-medium rounded-full px-2 py-0.5 ${POINTS_TO_STYLE[f.points_to] ?? POINTS_TO_STYLE.neutral}`}>
                {POINTS_TO_LABEL[f.points_to] ?? f.points_to}
              </span>
              <span className="text-[11px] text-muted">{f.strength}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
