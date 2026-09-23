import type { Finding } from "@/lib/types";
import { POINTS_TO_LABEL, POINTS_TO_STYLE } from "@/lib/format";
import SectionLabel from "./SectionLabel";

const SIGNAL_LABEL: Record<string, string> = {
  classifier: "CLS",
  ela: "ELA",
  noise: "NOISE",
  metadata: "META",
  pdf: "PDF",
};
const ORDER = { high: 0, medium: 1, low: 2, info: 3 };

export default function FindingsList({ findings }: { findings: Finding[] }) {
  const sorted = [...findings].sort((a, b) => ORDER[a.strength] - ORDER[b.strength]);
  return (
    <section className="panel p-5 sm:p-6" data-testid="findings">
      <SectionLabel num="04" right={<span className="label text-[10px]">{findings.length} signals</span>}>
        Signal log
      </SectionLabel>
      <ul className="divide-y divide-border border-y border-border">
        {sorted.map((f, i) => (
          <li key={i} className="py-3 grid grid-cols-[3.5rem_1fr_auto] gap-3 items-start">
            <span className="font-mono text-[11px] text-faint pt-0.5">{SIGNAL_LABEL[f.signal] ?? f.signal}</span>
            <p className="text-sm leading-relaxed">{f.text}</p>
            <span className="flex flex-col items-end gap-1">
              <span className={`tag ${POINTS_TO_STYLE[f.points_to] ?? POINTS_TO_STYLE.neutral}`}>{POINTS_TO_LABEL[f.points_to] ?? f.points_to}</span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-faint">{f.strength}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
