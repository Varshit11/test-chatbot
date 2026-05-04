"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

/** Generic, client-facing copy only — no implementation details. */
const STEPS = [
  "Running the patented AI filter…",
  "This step takes a bit longer — thanks for waiting…",
  "Almost there — finishing up the AI filter pass…",
];

export function AIFilterBusyBanner() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setStep((s) => (s + 1) % STEPS.length);
    }, 2800);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="qf-ai-filter-busy relative mx-auto mt-2 max-w-xl overflow-hidden rounded-xl border border-violet-500/35 bg-gradient-to-br from-violet-950/50 via-bg-panel to-fuchsia-950/30 px-4 py-4 shadow-[0_0_32px_-8px_rgba(139,92,246,0.45)]">
      <div className="qf-ai-filter-busy-shimmer pointer-events-none absolute inset-0 opacity-40" />
      <div className="relative flex gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-violet-500/20 text-violet-200">
          <Sparkles size={22} strokeWidth={1.75} className="qf-ai-filter-icon" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-violet-200/95">
              Patented AI filter
            </span>
            <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] font-medium text-violet-100/95">
              In progress
            </span>
          </div>
          <p className="mt-1 text-sm font-medium leading-snug text-ink">
            Sit tight — we&apos;re applying the AI filter to your results.
          </p>
          <div className="qf-ai-filter-step mt-2 min-h-[2.5rem] text-[11px] leading-relaxed text-ink-muted">
            <span key={step} className="inline-block">
              {STEPS[step]}
              <span className="qf-ai-filter-dots" aria-hidden="true">
                ...
              </span>
            </span>
          </div>
          <div className="qf-ai-filter-progress mt-3 h-1 w-full overflow-hidden rounded-full bg-violet-950/80">
            <div className="qf-ai-filter-progress-bar h-full rounded-full bg-gradient-to-r from-violet-400 via-fuchsia-400 to-violet-300" />
          </div>
        </div>
      </div>
    </div>
  );
}
