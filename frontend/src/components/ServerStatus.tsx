"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import type { Health } from "@/lib/types";

type State = { kind: "checking" } | { kind: "waking" } | { kind: "ok"; health: Health } | { kind: "down" };

/** Shows whether the API is up, and warns when a sleeping free server is waking up. */
export default function ServerStatus() {
  const [state, setState] = useState<State>({ kind: "checking" });

  useEffect(() => {
    let cancelled = false;
    const slow = setTimeout(() => !cancelled && setState((s) => (s.kind === "checking" ? { kind: "waking" } : s)), 3000);
    getHealth()
      .then((health) => !cancelled && setState({ kind: "ok", health }))
      .catch(() => !cancelled && setState({ kind: "down" }))
      .finally(() => clearTimeout(slow));
    return () => {
      cancelled = true;
      clearTimeout(slow);
    };
  }, []);

  let dot = "bg-unsure";
  let status = "Connecting";
  let detail = "Reaching the analysis server";
  if (state.kind === "waking") {
    dot = "bg-edit animate-pulse";
    status = "Waking";
    detail = "Free server is starting; the first scan can take up to a minute";
  } else if (state.kind === "down") {
    dot = "bg-ai";
    status = "Offline";
    detail = "The analysis server is unreachable right now";
  } else if (state.kind === "ok") {
    const c = state.health.classifier;
    dot = "bg-real";
    status = "Online";
    detail = c.loaded ? `Model ${c.model}` : "Classifier not installed, running forensics and metadata checks only";
  }

  return (
    <p className="inline-flex items-center gap-2.5 font-mono text-[11px] tracking-wide text-muted" data-testid="server-status">
      <span className={`w-1.5 h-1.5 ${dot}`} />
      <span className="uppercase tracking-[0.16em] text-text">{status}</span>
      <span className="text-faint">{"//"}</span>
      <span>{detail}</span>
    </p>
  );
}
