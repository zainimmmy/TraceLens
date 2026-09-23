import type { ReactNode } from "react";

/** "01 // VERDICT" style heading used at the top of every panel. */
export default function SectionLabel({ num, children, right }: { num?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 mb-4">
      <h3 className="label">
        {num && <span className="label-num">{num} {"//"} </span>}
        {children}
      </h3>
      {right}
    </div>
  );
}
