"use client";

import { useMemo, useState } from "react";
import { Play, Sliders, RotateCcw, Sparkles } from "lucide-react";
import clsx from "clsx";

interface Props {
  meta: {
    template?: string;
    instrument?: string;
    timeframe?: string;
    param_ranges: Record<string, (number | string | boolean)[]>;
    rationales?: Record<string, string>;
    focus?: string;
    ai_source?: "claude" | "template_defaults" | string;
    fixed_params?: Record<string, any>;
    n_combos?: number;
    objective?: string;
    actions?: { id: string; label: string; icon?: string }[];
  };
  onAction: (id: string, payload?: Record<string, any>) => void;
  busy?: string | null;
}

const OBJECTIVES = [
  { id: "sharpe_ratio", label: "Sharpe ratio" },
  { id: "total_return_pct", label: "Total return" },
  { id: "profit_factor", label: "Profit factor" },
  { id: "calmar_ratio", label: "Calmar ratio" },
];

function valuesToText(values: (number | string | boolean)[]): string {
  return values.map((v) => String(v)).join(", ");
}

function parseValues(input: string): (number | string)[] {
  return input
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      const n = Number(s);
      return Number.isFinite(n) && s.match(/^-?\d+(\.\d+)?$/) ? n : s;
    });
}

export function StrategyFinderPreview({ meta, onAction, busy }: Props) {
  const initialDraft = useMemo(() => {
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(meta.param_ranges || {})) {
      out[k] = valuesToText(v);
    }
    return out;
  }, [meta.param_ranges]);

  const [draft, setDraft] = useState<Record<string, string>>(initialDraft);
  const [objective, setObjective] = useState<string>(meta.objective || "sharpe_ratio");

  const parsedRanges = useMemo(() => {
    const out: Record<string, (number | string)[]> = {};
    for (const [k, text] of Object.entries(draft)) {
      const vals = parseValues(text);
      if (vals.length) out[k] = vals;
    }
    return out;
  }, [draft]);

  const liveCombos = useMemo(() => {
    let n = 1;
    for (const v of Object.values(parsedRanges)) {
      n *= Math.max(1, v.length);
    }
    return n;
  }, [parsedRanges]);

  const isBusy = busy === "confirm_run_finder";
  const tooMany = liveCombos > 500;
  const noRanges = Object.keys(parsedRanges).length === 0;

  const reset = () => setDraft(initialDraft);
  const aiPicked = meta.ai_source === "claude";

  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#101015] p-4">
      <div className="mb-3 flex items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="rounded bg-violet-900/40 px-1.5 py-0.5 font-medium text-violet-200">
            Strategy Finder
          </span>
          <span className="text-white/55">
            {meta.template} · {meta.instrument} · {meta.timeframe}
          </span>
        </div>
        <button
          type="button"
          onClick={reset}
          className="inline-flex items-center gap-1 text-[11px] text-white/40 transition-colors hover:text-white"
          title="Reset to AI-suggested ranges"
        >
          <RotateCcw size={11} /> Reset
        </button>
      </div>

      {meta.focus && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-violet-500/25 bg-gradient-to-br from-violet-950/40 via-[#16161e] to-fuchsia-950/15 p-3">
          <Sparkles size={14} className="mt-0.5 shrink-0 text-violet-300" strokeWidth={1.75} />
          <div>
            <div className="mb-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-violet-200/85">
              {aiPicked ? "AI-picked focus" : "Default sweep"}
            </div>
            <div className="text-[13px] leading-snug text-white/85">{meta.focus}</div>
          </div>
        </div>
      )}

      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-violet-700/30 bg-gradient-to-br from-violet-950/30 via-[#16161e] to-fuchsia-950/15 p-3">
        <div className="text-[11px] uppercase tracking-wide text-violet-200/85">
          Will test
        </div>
        <div className="font-mono text-2xl font-semibold tabular-nums text-white">
          {liveCombos.toLocaleString()}{" "}
          <span className="text-[11px] font-normal text-white/50">combos</span>
        </div>
      </div>

      <div className="mb-3 grid gap-2 sm:grid-cols-2">
        {Object.entries(draft).map(([key, text]) => {
          const rationale = meta.rationales?.[key];
          return (
            <div
              key={key}
              className="rounded-lg border border-white/[0.06] bg-black/30 px-3 py-2"
            >
              <div className="mb-1 flex items-center justify-between">
                <code className="text-[11px] font-medium text-violet-200">{key}</code>
                <span className="text-[10px] text-white/40">
                  {parsedRanges[key]?.length ?? 0} values
                </span>
              </div>
              <input
                type="text"
                value={text}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, [key]: e.target.value }))
                }
                placeholder="comma-separated, e.g. 5, 9, 13, 21"
                className="w-full rounded bg-transparent text-[13px] text-white outline-none placeholder:text-white/25 focus:bg-white/[0.03]"
              />
              {rationale && (
                <div className="mt-1 text-[11px] leading-snug text-white/45">
                  {rationale}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {meta.fixed_params && Object.keys(meta.fixed_params).length > 0 && (
        <div className="mb-3 rounded-lg border border-white/[0.06] bg-black/30 p-3 text-[11px]">
          <div className="mb-1.5 flex items-center gap-1.5 uppercase tracking-wide text-white/40">
            <Sliders size={11} /> Fixed during search
          </div>
          <div className="flex flex-wrap gap-1.5 font-mono">
            {Object.entries(meta.fixed_params).map(([k, v]) => (
              <span
                key={k}
                className="rounded bg-white/[0.05] px-2 py-0.5 text-white/65"
              >
                {k}={String(v)}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mb-3 flex items-center gap-2 text-[11px]">
        <span className="text-white/55">Rank by</span>
        <select
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          className="rounded border border-white/[0.08] bg-black/40 px-2 py-1 text-[12px] text-white outline-none focus:border-violet-500/40"
        >
          {OBJECTIVES.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {tooMany && (
        <div className="mb-3 rounded-md border border-amber-700/40 bg-amber-900/15 p-2 text-[12px] text-amber-200">
          {liveCombos.toLocaleString()} combinations is a lot — this will take a
          while. Consider trimming a range or two.
        </div>
      )}
      {noRanges && (
        <div className="mb-3 rounded-md border border-rose-700/40 bg-rose-900/15 p-2 text-[12px] text-rose-200">
          You've cleared every range — add at least one value per parameter.
        </div>
      )}

      <button
        type="button"
        disabled={!!busy || noRanges}
        onClick={() =>
          onAction("confirm_run_finder", {
            ranges: parsedRanges,
            objective,
          })
        }
        className={clsx(
          "tx-send-btn inline-flex items-center gap-2 rounded-lg px-4 py-2 text-[13px] font-medium text-white disabled:cursor-not-allowed",
          isBusy && "opacity-70"
        )}
      >
        <Play size={14} />
        {isBusy ? "Running…" : "Run Optimization"}
      </button>
    </div>
  );
}
