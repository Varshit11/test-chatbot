"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import { fmtNum, fmtPct } from "@/lib/format";

type SessionRow = {
  session?: string;
  hour?: number;
  weekday?: string;
  n_trades: number;
  win_rate_pct: number;
  total_pnl: number;
  avg_trade: number;
  best_trade: number;
  worst_trade: number;
  profit_factor: number;
};

type SessionStats = {
  by_session?: SessionRow[];
  by_hour?: SessionRow[];
  by_weekday?: SessionRow[];
};

type Tab = "session" | "hour" | "weekday";

const SESSION_COLORS: Record<string, string> = {
  Asia: "#60a5fa",
  London: "#34d399",
  Overlap: "#fbbf24",
  NewYork: "#f472b6",
  OffHrs: "#94a3b8",
};

function PnlBars({ rows, labelKey }: { rows: SessionRow[]; labelKey: keyof SessionRow }) {
  const filtered = rows.filter((r) => (r.n_trades || 0) > 0);
  const max = Math.max(1, ...filtered.map((r) => Math.abs(r.total_pnl || 0)));
  return (
    <div className="space-y-1">
      {filtered.map((r, i) => {
        const pnl = r.total_pnl || 0;
        const pct = (Math.abs(pnl) / max) * 100;
        return (
          <div key={i} className="grid grid-cols-[80px_1fr_70px] items-center gap-2 text-[11px]">
            <span className="font-mono text-ink-muted">{String(r[labelKey])}</span>
            <div className="relative h-3 rounded-sm bg-bg-elev">
              <div
                className={clsx(
                  "absolute top-0 h-3 rounded-sm",
                  pnl >= 0 ? "bg-emerald-500/70" : "bg-rose-500/70"
                )}
                style={{
                  width: `${pct}%`,
                  left: pnl >= 0 ? "0%" : `${100 - pct}%`,
                }}
              />
            </div>
            <span
              className={clsx(
                "text-right font-mono tabular-nums",
                pnl >= 0 ? "text-good" : "text-bad"
              )}
            >
              {pnl >= 0 ? "+" : ""}
              {fmtNum(pnl, 0)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function StatTable({ rows, labelKey, labelHeader }: {
  rows: SessionRow[];
  labelKey: keyof SessionRow;
  labelHeader: string;
}) {
  return (
    <div className="overflow-hidden rounded-md border border-line bg-bg-panel">
      <table className="w-full text-xs">
        <thead className="text-[10px] uppercase tracking-wide text-ink-dim">
          <tr className="border-b border-line">
            <th className="px-3 py-1.5 text-left">{labelHeader}</th>
            <th className="px-3 py-1.5 text-right">Trades</th>
            <th className="px-3 py-1.5 text-right">Win-rate</th>
            <th className="px-3 py-1.5 text-right">Total PnL</th>
            <th className="px-3 py-1.5 text-right">Avg trade</th>
            <th className="px-3 py-1.5 text-right">PF</th>
            <th className="px-3 py-1.5 text-right">Best</th>
            <th className="px-3 py-1.5 text-right">Worst</th>
          </tr>
        </thead>
        <tbody>
          {rows
            .filter((r) => (r.n_trades || 0) > 0)
            .map((r, i) => (
              <tr key={i} className="border-t border-line/60">
                <td className="px-3 py-1 font-mono text-ink">{String(r[labelKey])}</td>
                <td className="px-3 py-1 text-right font-mono tabular-nums text-ink-muted">
                  {r.n_trades}
                </td>
                <td className="px-3 py-1 text-right font-mono tabular-nums">{fmtPct(r.win_rate_pct)}</td>
                <td
                  className={clsx(
                    "px-3 py-1 text-right font-mono tabular-nums",
                    (r.total_pnl || 0) >= 0 ? "text-good" : "text-bad"
                  )}
                >
                  {(r.total_pnl || 0) >= 0 ? "+" : ""}
                  {fmtNum(r.total_pnl, 2)}
                </td>
                <td
                  className={clsx(
                    "px-3 py-1 text-right font-mono tabular-nums",
                    (r.avg_trade || 0) >= 0 ? "text-good" : "text-bad"
                  )}
                >
                  {fmtNum(r.avg_trade, 2)}
                </td>
                <td className="px-3 py-1 text-right font-mono tabular-nums text-ink-muted">
                  {fmtNum(r.profit_factor, 2)}
                </td>
                <td className="px-3 py-1 text-right font-mono tabular-nums text-good">
                  {fmtNum(r.best_trade, 2)}
                </td>
                <td className="px-3 py-1 text-right font-mono tabular-nums text-bad">
                  {fmtNum(r.worst_trade, 2)}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

function SessionPills({ rows }: { rows: SessionRow[] }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
      {rows.map((r, i) => {
        const pnl = r.total_pnl || 0;
        const color = SESSION_COLORS[r.session || ""] || "#94a3b8";
        return (
          <div
            key={i}
            className="rounded-md border border-line bg-bg-panel p-2.5 text-xs"
          >
            <div className="flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: color }}
              />
              <span className="text-ink">{r.session}</span>
            </div>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-[10px] text-ink-dim">{r.n_trades} trades</span>
              <span
                className={clsx(
                  "font-mono tabular-nums text-[11px]",
                  pnl >= 0 ? "text-good" : "text-bad"
                )}
              >
                {pnl >= 0 ? "+" : ""}
                {fmtNum(pnl, 0)}
              </span>
            </div>
            <div className="mt-0.5 text-[10px] text-ink-muted">
              WR {fmtNum(r.win_rate_pct, 1)}%
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function SessionStatsPanel({ stats }: { stats: SessionStats }) {
  const [tab, setTab] = useState<Tab>("session");
  const hasData =
    (stats?.by_session || []).some((r) => (r.n_trades || 0) > 0) ||
    (stats?.by_hour || []).some((r) => (r.n_trades || 0) > 0);
  if (!hasData) return null;

  return (
    <div className="rounded-md border border-line bg-bg-panel p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-wide text-ink-dim">
          Performance by time-of-day
        </div>
        <div className="flex gap-1 text-[10px]">
          {(["session", "hour", "weekday"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={clsx(
                "rounded px-2 py-0.5 capitalize",
                tab === t
                  ? "bg-accent/20 text-accent"
                  : "text-ink-dim hover:text-ink-muted"
              )}
            >
              {t === "weekday" ? "Day-of-week" : t}
            </button>
          ))}
        </div>
      </div>

      {tab === "session" && (
        <div className="space-y-3">
          <SessionPills rows={stats.by_session || []} />
          <StatTable
            rows={stats.by_session || []}
            labelKey="session"
            labelHeader="Session"
          />
        </div>
      )}

      {tab === "hour" && (
        <div className="space-y-3">
          <PnlBars rows={stats.by_hour || []} labelKey="hour" />
          <StatTable
            rows={stats.by_hour || []}
            labelKey="hour"
            labelHeader="Hour (UTC)"
          />
        </div>
      )}

      {tab === "weekday" && (
        <div className="space-y-3">
          <PnlBars rows={stats.by_weekday || []} labelKey="weekday" />
          <StatTable
            rows={stats.by_weekday || []}
            labelKey="weekday"
            labelHeader="Weekday"
          />
        </div>
      )}
    </div>
  );
}
