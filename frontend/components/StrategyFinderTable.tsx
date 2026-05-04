"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
  Cell,
} from "recharts";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { fmtNum, fmtPct } from "@/lib/format";

type Combo = {
  params: Record<string, any>;
  metrics: Record<string, any>;
  score: number;
};

type ColKey =
  | "score"
  | "total_return_pct"
  | "sharpe_ratio"
  | "max_drawdown_pct"
  | "win_rate_pct"
  | "profit_factor"
  | "n_trades";

const COLUMNS: { key: ColKey; label: string; fmt: "num" | "pct"; tone?: "good-bad" | "bad-only" }[] = [
  { key: "score", label: "Score", fmt: "num" },
  { key: "total_return_pct", label: "Return", fmt: "pct", tone: "good-bad" },
  { key: "sharpe_ratio", label: "Sharpe", fmt: "num", tone: "good-bad" },
  { key: "max_drawdown_pct", label: "Max DD", fmt: "pct", tone: "bad-only" },
  { key: "win_rate_pct", label: "Win-rate", fmt: "pct" },
  { key: "profit_factor", label: "PF", fmt: "num" },
  { key: "n_trades", label: "Trades", fmt: "num" },
];

function getMetric(c: Combo, k: ColKey): number {
  if (k === "score") return Number(c.score) || 0;
  return Number(c.metrics?.[k]) || 0;
}

export function StrategyFinderTable({
  ranked,
  paramRanges,
  bestParams,
}: {
  ranked: Combo[];
  paramRanges?: Record<string, any[]>;
  bestParams?: Record<string, any>;
}) {
  const [sortKey, setSortKey] = useState<ColKey>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [pageSize, setPageSize] = useState<number>(15);

  const paramKeys = useMemo(() => {
    if (paramRanges && Object.keys(paramRanges).length) return Object.keys(paramRanges);
    if (ranked[0]) return Object.keys(ranked[0].params);
    return [];
  }, [paramRanges, ranked]);

  const sorted = useMemo(() => {
    const arr = [...ranked].sort((a, b) => {
      const va = getMetric(a, sortKey);
      const vb = getMetric(b, sortKey);
      return sortDir === "asc" ? va - vb : vb - va;
    });
    return arr;
  }, [ranked, sortKey, sortDir]);

  const visible = sorted.slice(0, pageSize);

  const toggleSort = (k: ColKey) => {
    if (sortKey === k) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(k);
      // Negative metrics (DD) default to ascending; everything else descending.
      setSortDir(k === "max_drawdown_pct" ? "asc" : "desc");
    }
  };

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-wide text-ink-dim">
          All combinations ({ranked.length})
          <span className="ml-1 text-ink-dim/70">— click any column header to sort</span>
        </div>
        {ranked.length > pageSize && (
          <button
            onClick={() => setPageSize((s) => (s >= ranked.length ? 15 : ranked.length))}
            className="text-[10px] text-ink-dim hover:text-ink"
          >
            {pageSize >= ranked.length ? "Show fewer" : `Show all ${ranked.length}`}
          </button>
        )}
      </div>

      <div className="overflow-auto rounded-md border border-line bg-bg-panel max-h-[420px]">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-bg-panel text-[10px] uppercase tracking-wide text-ink-dim">
            <tr className="border-b border-line">
              <th className="px-3 py-1.5 text-left">#</th>
              {paramKeys.map((k) => (
                <th key={k} className="px-3 py-1.5 text-left font-normal">
                  {k}
                </th>
              ))}
              {COLUMNS.map((c) => {
                const active = sortKey === c.key;
                return (
                  <th
                    key={c.key}
                    onClick={() => toggleSort(c.key)}
                    className={clsx(
                      "cursor-pointer select-none px-3 py-1.5 text-right hover:text-ink",
                      active && "text-accent"
                    )}
                  >
                    <span className="inline-flex items-center gap-1">
                      {c.label}
                      {active ? (
                        sortDir === "asc" ? (
                          <ArrowUp size={9} />
                        ) : (
                          <ArrowDown size={9} />
                        )
                      ) : (
                        <ArrowUpDown size={9} className="opacity-30" />
                      )}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visible.map((r, i) => {
              const isBest =
                bestParams &&
                Object.keys(bestParams).every(
                  (k) => String(r.params?.[k]) === String(bestParams?.[k])
                );
              return (
                <tr
                  key={i}
                  className={clsx(
                    "border-t border-line/60",
                    isBest && "bg-emerald-900/15"
                  )}
                >
                  <td className="px-3 py-1 text-ink-dim">
                    {isBest ? (
                      <span className="inline-flex items-center gap-1 rounded bg-emerald-900/40 px-1.5 py-0.5 text-[9px] uppercase text-emerald-200">
                        Best
                      </span>
                    ) : (
                      sorted.indexOf(r) + 1
                    )}
                  </td>
                  {paramKeys.map((k) => (
                    <td key={k} className="px-3 py-1 font-mono text-[10px] text-ink-muted">
                      {String(r.params?.[k] ?? "—")}
                    </td>
                  ))}
                  {COLUMNS.map((c) => {
                    const v = getMetric(r, c.key);
                    const cls =
                      c.tone === "good-bad"
                        ? v >= 0
                          ? "text-good"
                          : "text-bad"
                        : c.tone === "bad-only"
                          ? "text-bad"
                          : "text-ink";
                    return (
                      <td
                        key={c.key}
                        className={clsx(
                          "px-3 py-1 text-right font-mono tabular-nums",
                          cls
                        )}
                      >
                        {c.fmt === "pct" ? fmtPct(v) : fmtNum(v, 2)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
            {ranked.length === 0 && (
              <tr>
                <td
                  colSpan={paramKeys.length + COLUMNS.length + 1}
                  className="px-3 py-4 text-center text-ink-dim"
                >
                  No combinations to show.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function StrategyFinderScatter({ ranked }: { ranked: Combo[] }) {
  const data = ranked.map((r, i) => ({
    rank: i + 1,
    return: r.metrics?.total_return_pct ?? 0,
    dd: Math.abs(r.metrics?.max_drawdown_pct ?? 0),
    sharpe: r.metrics?.sharpe_ratio ?? 0,
    trades: r.metrics?.n_trades ?? 0,
    score: r.score ?? 0,
  }));
  if (!data.length) return null;
  return (
    <div className="rounded-md border border-line bg-bg-panel p-3">
      <div className="mb-1 text-[10px] uppercase tracking-wide text-ink-dim">
        Return vs Drawdown · bubble size = trades · color = Sharpe
      </div>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 8, bottom: 24, left: 8 }}>
            <CartesianGrid strokeDasharray="2 2" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              type="number"
              dataKey="dd"
              name="Drawdown"
              tickFormatter={(v) => `${v.toFixed(1)}%`}
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              label={{ value: "Max Drawdown %", position: "insideBottom", offset: -10, fontSize: 10, fill: "#9ca3af" }}
            />
            <YAxis
              type="number"
              dataKey="return"
              name="Return"
              tickFormatter={(v) => `${v.toFixed(1)}%`}
              tick={{ fontSize: 10, fill: "#9ca3af" }}
            />
            <ZAxis type="number" dataKey="trades" range={[40, 240]} />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(20,20,28,0.95)",
                border: "1px solid #2a2a3a",
                borderRadius: 6,
                fontSize: 11,
              }}
              cursor={{ strokeDasharray: "3 3" }}
              formatter={(v: any, n: any) => {
                if (n === "Drawdown" || n === "Return") return [`${Number(v).toFixed(2)}%`, n];
                return [v, n];
              }}
            />
            <Scatter data={data} fill="#60a5fa">
              {data.map((d, i) => (
                <Cell
                  key={i}
                  fill={
                    d.sharpe >= 1
                      ? "#10b981"
                      : d.sharpe >= 0.3
                        ? "#84cc16"
                        : d.sharpe >= 0
                          ? "#fbbf24"
                          : "#f87171"
                  }
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
