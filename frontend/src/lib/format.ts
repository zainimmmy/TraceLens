import type { Verdict } from "./types";

export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : `${Math.round(v * 100)}%`);

export const bytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;

export const VERDICT_STYLE: Record<Verdict, { text: string; bg: string; bar: string; code: string }> = {
  ai_generated: { text: "text-ai", bg: "bg-ai-soft", bar: "bg-ai", code: "AI-GEN" },
  manipulated: { text: "text-edit", bg: "bg-edit-soft", bar: "bg-edit", code: "EDITED" },
  real: { text: "text-real", bg: "bg-real-soft", bar: "bg-real", code: "AUTHENTIC" },
  inconclusive: { text: "text-unsure", bg: "bg-unsure-soft", bar: "bg-unsure", code: "UNRESOLVED" },
};

export const POINTS_TO_STYLE: Record<string, string> = {
  ai_generated: "text-ai",
  manipulated: "text-edit",
  real: "text-real",
  neutral: "text-unsure",
};

export const POINTS_TO_LABEL: Record<string, string> = {
  ai_generated: "AI",
  manipulated: "Edited",
  real: "Authentic",
  neutral: "Neutral",
};
