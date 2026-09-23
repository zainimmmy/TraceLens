import type { Verdict } from "./types";

export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : `${Math.round(v * 100)}%`);

export const bytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;

export const VERDICT_STYLE: Record<Verdict, { text: string; bg: string; bar: string; icon: string }> = {
  ai_generated: { text: "text-ai", bg: "bg-ai-soft", bar: "bg-ai", icon: "✦" },
  manipulated: { text: "text-edit", bg: "bg-edit-soft", bar: "bg-edit", icon: "◩" },
  real: { text: "text-real", bg: "bg-real-soft", bar: "bg-real", icon: "✓" },
  inconclusive: { text: "text-unsure", bg: "bg-unsure-soft", bar: "bg-unsure", icon: "?" },
};

export const POINTS_TO_STYLE: Record<string, string> = {
  ai_generated: "text-ai bg-ai-soft",
  manipulated: "text-edit bg-edit-soft",
  real: "text-real bg-real-soft",
  neutral: "text-unsure bg-unsure-soft",
};

export const POINTS_TO_LABEL: Record<string, string> = {
  ai_generated: "AI",
  manipulated: "Edited",
  real: "Authentic",
  neutral: "Neutral",
};
