"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import type { Health } from "@/lib/types";

type State = { kind: "checking" } | { kind: "waking" } | { kind: "ok"; health: Health } | { kind: "down" };

/** Shows whether the API is up, and warns when the free Space is waking from sleep. */
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
  let text = "Connecting to the analysis server…";
  if (state.kind === "waking") {
    dot = "bg-edit animate-pulse";
    text = "Waking up the free server. The first analysis can take up to a minute.";
  } else if (state.kind === "down") {
    dot = "bg-ai";
    text = "The analysis server is unreachable right now.";
  } else if (state.kind === "ok") {
    const c = state.health.classifier;
    dot = "bg-real";
    text = c.loaded
      ? `Online · model ${c.model}`
      : "Online · classifier not installed, running forensics and metadata checks only";
  }

  return (
    <p className="inline-flex items-center gap-2 text-xs text-muted" data-testid="server-status">
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      {text}
    </p>
  );
}
