"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceDot } from "recharts";
import { fmtNum, fmtPct } from "@/lib/format";

export type SweepRow = {
  threshold: number;
  kept: number;
  dropped: number;
  kept_pct: number;
  total_return_pct: number;
  sharpe_ratio: number;
  win_rate_pct: number;
  max_drawdown_pct: number;
  profit_factor: number;
  expectancy: number;
  avg_trade: number;
};

export function ThresholdSweepPanel({
  sweep,
  selectedThreshold,
  onSelect,
}: {
  sweep: SweepRow[];
  selectedThreshold: number;
  onSelect?: (t: number) => void;
}) {
  if (!sweep || sweep.length === 0) return null;

  const chartData = sweep.map((s) => ({
    threshold: s.threshold,
    return: s.total_return_pct,
    sharpe: s.sharpe_ratio,
    keptPct: s.kept_pct,
    winRate: s.win_rate_pct,
  }));

  // Highlight the row with the best return for visual cue
  const bestReturnRow = sweep.reduce((acc, r) => (r.total_return_pct > acc.total_return_pct ? r : acc), sweep[0]);
  const bestSharpeRow = sweep.reduce((acc, r) => (r.sharpe_ratio > acc.sharpe_ratio ? r : acc), sweep[0]);

  return (
    <div className="rounded-md border border-line bg-bg-panel p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-wide text-ink-dim">
          Threshold sweep — how aggressive should the filter be?
        </div>
        <div className="flex items-center gap-2 text-[10px] text-ink-dim">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-400" /> best return
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-blue-400" /> best Sharpe
          </span>
        </div>
      </div>

      {/* Mini chart */}
      <div className="h-[160px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 6, right: 12, bottom: 6, left: -10 }}>
            <CartesianGrid strokeDasharray="2 2" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="threshold"
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              tickFormatter={(v) => v.toFixed(2)}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              tickFormatter={(v) => `${v.toFixed(0)}%`}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 10, fill: "#9ca3af" }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(20,20,28,0.95)",
                border: "1px solid #2a2a3a",
                borderRadius: 6,
                fontSize: 11,
              }}
              labelFormatter={(v) => `Threshold ${Number(v).toFixed(2)}`}
              formatter={(v: any, n: any) => {
                if (n === "Return %" || n === "Kept %" || n === "Win %") return [`${Number(v).toFixed(2)}%`, n];
                return [Number(v).toFixed(2), n];
              }}
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="return"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ r: 3 }}
              name="Return %"
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="winRate"
              stroke="#a78bfa"
              strokeWidth={1.5}
              dot={{ r: 2 }}
              name="Win %"
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="keptPct"
              stroke="#fbbf24"
              strokeWidth={1.5}
              dot={{ r: 2 }}
              name="Kept %"
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="sharpe"
              stroke="#60a5fa"
              strokeWidth={2}
              dot={{ r: 3 }}
              name="Sharpe"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Sweep table */}
      <div className="mt-2 overflow-hidden rounded-md border border-line">
        <table className="w-full text-xs">
          <thead className="text-[10px] uppercase tracking-wide text-ink-dim">
            <tr className="border-b border-line">
              <th className="px-3 py-1.5 text-left">Threshold</th>
              <th className="px-3 py-1.5 text-right">Kept</th>
              <th className="px-3 py-1.5 text-right">Return</th>
              <th className="px-3 py-1.5 text-right">Sharpe</th>
              <th className="px-3 py-1.5 text-right">Win-rate</th>
              <th className="px-3 py-1.5 text-right">Max DD</th>
              <th className="px-3 py-1.5 text-right">PF</th>
              <th className="px-3 py-1.5 text-right">Avg/trade</th>
            </tr>
          </thead>
          <tbody>
            {sweep.map((r, i) => {
              const isCurrent = Math.abs(r.threshold - selectedThreshold) < 0.001;
              const isBestRet = r === bestReturnRow;
              const isBestSharpe = r === bestSharpeRow;
              return (
                <tr
                  key={i}
                  onClick={() => onSelect?.(r.threshold)}
                  className={clsx(
                    "cursor-pointer border-t border-line/60 transition-colors",
                    isCurrent ? "bg-purple-900/30" : "hover:bg-bg-elev/40"
                  )}
                >
                  <td className="px-3 py-1 font-mono text-ink">
                    <span className="inline-flex items-center gap-1.5">
                      {fmtNum(r.threshold, 2)}
                      {isBestRet && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />}
                      {isBestSharpe && <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />}
                    </span>
                  </td>
                  <td className="px-3 py-1 text-right font-mono tabular-nums text-ink-muted">
                    {r.kept}/{r.kept + r.dropped} <span className="text-ink-dim">({fmtNum(r.kept_pct, 0)}%)</span>
                  </td>
                  <td
                    className={clsx(
                      "px-3 py-1 text-right font-mono tabular-nums",
                      r.total_return_pct >= 0 ? "text-good" : "text-bad"
                    )}
                  >
                    {fmtPct(r.total_return_pct)}
                  </td>
                  <td className="px-3 py-1 text-right font-mono tabular-nums">
                    {fmtNum(r.sharpe_ratio, 2)}
                  </td>
                  <td className="px-3 py-1 text-right font-mono tabular-nums">
                    {fmtPct(r.win_rate_pct)}
                  </td>
                  <td className="px-3 py-1 text-right font-mono tabular-nums text-bad">
                    {fmtPct(r.max_drawdown_pct)}
                  </td>
                  <td className="px-3 py-1 text-right font-mono tabular-nums text-ink-muted">
                    {fmtNum(r.profit_factor, 2)}
                  </td>
                  <td
                    className={clsx(
                      "px-3 py-1 text-right font-mono tabular-nums",
                      (r.avg_trade || 0) >= 0 ? "text-good" : "text-bad"
                    )}
                  >
                    {fmtNum(r.avg_trade, 2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type PerTrade = {
  index: number;
  entry_time?: string;
  exit_time?: string;
  side?: string;
  pnl?: number;
  score: number;
  kept_at_default: boolean;
};

export function PerTradeScoreTable({
  perTrade,
  threshold,
}: {
  perTrade: PerTrade[];
  threshold: number;
}) {
  const [filter, setFilter] = useState<"all" | "kept" | "dropped">("all");
  const [maxRows, setMaxRows] = useState(20);

  const sorted = useMemo(() => {
    return [...perTrade].sort((a, b) => b.score - a.score);
  }, [perTrade]);

  const filtered = useMemo(() => {
    if (filter === "all") return sorted;
    if (filter === "kept") return sorted.filter((t) => t.score >= threshold);
    return sorted.filter((t) => t.score < threshold);
  }, [sorted, filter, threshold]);

  const visible = filtered.slice(0, maxRows);

  return (
    <div className="rounded-md border border-line bg-bg-panel p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-wide text-ink-dim">
          Trade-level scores ({perTrade.length} total)
        </div>
        <div className="flex gap-1 text-[10px]">
          {(["all", "kept", "dropped"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                "rounded px-2 py-0.5 capitalize",
                filter === f
                  ? "bg-accent/20 text-accent"
                  : "text-ink-dim hover:text-ink-muted"
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-auto rounded-md border border-line max-h-[280px]">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-bg-panel text-[10px] uppercase tracking-wide text-ink-dim">
            <tr className="border-b border-line">
              <th className="px-3 py-1.5 text-left">#</th>
              <th className="px-3 py-1.5 text-left">Score</th>
              <th className="px-3 py-1.5 text-left">Entry</th>
              <th className="px-3 py-1.5 text-left">Side</th>
              <th className="px-3 py-1.5 text-right">PnL</th>
              <th className="px-3 py-1.5 text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((t, i) => {
              const kept = t.score >= threshold;
              return (
                <tr key={t.index} className="border-t border-line/60">
                  <td className="px-3 py-1 text-ink-dim">{t.index + 1}</td>
                  <td className="px-3 py-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono tabular-nums text-ink">
                        {fmtNum(t.score, 3)}
                      </span>
                      <div className="relative h-1 w-16 rounded-full bg-bg-elev">
                        <div
                          className={clsx(
                            "absolute inset-y-0 left-0 rounded-full",
                            kept ? "bg-purple-400" : "bg-rose-400/60"
                          )}
                          style={{ width: `${t.score * 100}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-1 font-mono text-[10px] text-ink-muted">
                    {String(t.entry_time || "—").slice(0, 16).replace("T", " ")}
                  </td>
                  <td
                    className={clsx(
                      "px-3 py-1 font-mono text-[10px]",
                      t.side === "long" ? "text-emerald-300" : "text-rose-300"
                    )}
                  >
                    {t.side}
                  </td>
                  <td
                    className={clsx(
                      "px-3 py-1 text-right font-mono tabular-nums",
                      (t.pnl ?? 0) >= 0 ? "text-good" : "text-bad"
                    )}
                  >
                    {(t.pnl ?? 0) >= 0 ? "+" : ""}
                    {fmtNum(t.pnl, 2)}
                  </td>
                  <td className="px-3 py-1 text-center">
                    {kept ? (
                      <span className="rounded bg-emerald-900/40 px-1.5 py-0.5 text-[10px] text-emerald-200">
                        Kept
                      </span>
                    ) : (
                      <span className="rounded bg-rose-900/40 px-1.5 py-0.5 text-[10px] text-rose-200">
                        Dropped
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
            {visible.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-ink-dim">
                  No trades match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {filtered.length > maxRows && (
        <button
          onClick={() => setMaxRows((m) => m + 30)}
          className="mt-2 text-[10px] text-ink-dim hover:text-ink"
        >
          Show {Math.min(30, filtered.length - maxRows)} more (of {filtered.length})
        </button>
      )}
    </div>
  );
}
