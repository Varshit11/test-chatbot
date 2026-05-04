"use client";

import clsx from "clsx";
import { fmtNum, fmtPct, colorForPct } from "@/lib/format";
import type { MetricsBundle } from "@/lib/types";

const TILES: Array<{
  key: keyof MetricsBundle;
  label: string;
  fmt?: "pct" | "num" | "money" | "ratio" | "points";
  hint?: string;
  emphasize?: boolean;
  colorByValue?: boolean;
}> = [
  { key: "total_return_pct", label: "Total Return", fmt: "pct", emphasize: true, colorByValue: true },
  { key: "total_points", label: "Total Points", fmt: "points", emphasize: true, colorByValue: true },
  { key: "sharpe_ratio", label: "Sharpe", fmt: "ratio", emphasize: true, colorByValue: true },
  { key: "max_drawdown_pct", label: "Max DD", fmt: "pct", emphasize: true, colorByValue: true },
  { key: "profit_factor", label: "Profit Factor", fmt: "ratio" },
  { key: "win_rate_pct", label: "Win Rate", fmt: "pct" },
  { key: "n_trades", label: "Trades" },
  { key: "avg_trade", label: "Avg PnL", fmt: "money", colorByValue: true },
  { key: "avg_points", label: "Avg Points", fmt: "points", colorByValue: true },
  { key: "best_points", label: "Best (pts)", fmt: "points" },
  { key: "worst_points", label: "Worst (pts)", fmt: "points" },
  { key: "expectancy", label: "Expectancy", fmt: "money", colorByValue: true },
  { key: "cagr_pct", label: "CAGR", fmt: "pct", colorByValue: true },
  { key: "sortino_ratio", label: "Sortino", fmt: "ratio" },
];

export function MetricsGrid({
  metrics,
  compact = false,
}: {
  metrics: MetricsBundle;
  compact?: boolean;
}) {
  return (
    <div
      className={clsx(
        "grid gap-2",
        compact ? "grid-cols-3 sm:grid-cols-4" : "grid-cols-3 sm:grid-cols-4 md:grid-cols-6"
      )}
    >
      {TILES.map((t) => {
        const v = metrics[t.key] as number;
        let display = "—";
        if (v !== undefined && v !== null && !Number.isNaN(v)) {
          if (t.fmt === "pct") display = fmtPct(v);
          else if (t.fmt === "ratio") display = fmtNum(v, 2);
          else if (t.fmt === "money") display = (v >= 0 ? "" : "") + fmtNum(v, 2);
          else if (t.fmt === "points") display = (v > 0 ? "+" : "") + fmtNum(v, 1) + " pt";
          else if (t.fmt === "num") display = fmtNum(v, 2);
          else display = fmtNum(v, 0);
        }
        const color = t.colorByValue ? colorForPct(v) : "text-ink";
        return (
          <div
            key={t.key}
            className={clsx(
              "rounded-md border border-line bg-bg-elev px-3 py-2",
              t.emphasize && "ring-1 ring-line"
            )}
          >
            <div className="text-[10px] uppercase tracking-wide text-ink-dim">{t.label}</div>
            <div className={clsx("font-mono text-base font-medium tabular-nums", color)}>
              {display}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function CompareMetricRow({
  label,
  before,
  after,
  fmt = "num",
}: {
  label: string;
  before?: number;
  after?: number;
  fmt?: "pct" | "num";
}) {
  const f = (v?: number) =>
    v === undefined || v === null
      ? "—"
      : fmt === "pct"
      ? fmtPct(v)
      : fmtNum(v, 2);
  const delta =
    before !== undefined && after !== undefined ? after - before : undefined;
  const deltaColor =
    delta === undefined
      ? "text-ink-dim"
      : delta > 0
      ? "text-good"
      : delta < 0
      ? "text-bad"
      : "text-ink-dim";

  return (
    <div className="grid grid-cols-4 gap-2 border-b border-line py-1.5 text-sm last:border-b-0">
      <div className="text-ink-muted">{label}</div>
      <div className="font-mono tabular-nums text-ink">{f(before)}</div>
      <div className="font-mono tabular-nums text-ink">{f(after)}</div>
      <div className={clsx("font-mono tabular-nums", deltaColor)}>
        {delta !== undefined
          ? (delta > 0 ? "+" : "") +
            (fmt === "pct" ? fmtNum(delta, 2) + "%" : fmtNum(delta, 2))
          : "—"}
      </div>
    </div>
  );
}
