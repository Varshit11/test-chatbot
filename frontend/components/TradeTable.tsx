"use client";

import { useState } from "react";
import clsx from "clsx";
import { fmtNum, fmtDate } from "@/lib/format";
import type { Trade } from "@/lib/types";

export function TradeTable({
  trades,
  truncated,
  fullCount,
  highlightDropped,
}: {
  trades: Trade[];
  truncated?: boolean;
  fullCount?: number;
  highlightDropped?: number[];
}) {
  const [open, setOpen] = useState(false);
  const visible = open ? trades : trades.slice(-12);
  if (!trades || trades.length === 0) {
    return <div className="text-xs text-ink-dim">No trades</div>;
  }
  return (
    <div className="overflow-hidden rounded-md border border-line bg-bg-elev">
      <div className="flex items-center justify-between border-b border-line px-3 py-1.5 text-xs text-ink-muted">
        <span>
          {trades.length} trades shown
          {truncated && ` (last 500 of ${fullCount})`}
        </span>
        <button
          onClick={() => setOpen((o) => !o)}
          className="rounded px-2 py-0.5 text-[11px] text-ink-dim hover:bg-bg-panel hover:text-ink"
        >
          {open ? "Show last 12" : "Show all"}
        </button>
      </div>
      <div className="max-h-72 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-bg-elev text-[10px] uppercase tracking-wide text-ink-dim">
            <tr>
              <th className="px-3 py-1.5 text-left">#</th>
              <th className="px-3 py-1.5 text-left">Side</th>
              <th className="px-3 py-1.5 text-left">Entry</th>
              <th className="px-3 py-1.5 text-left">Exit</th>
              <th className="px-3 py-1.5 text-right">Entry Px</th>
              <th className="px-3 py-1.5 text-right">Exit Px</th>
              <th className="px-3 py-1.5 text-right">PnL</th>
              <th className="px-3 py-1.5 text-left">Reason</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((t, idx) => {
              const realIdx = open ? idx : trades.length - visible.length + idx;
              const dropped = highlightDropped?.includes(realIdx);
              return (
                <tr
                  key={idx}
                  className={clsx(
                    "border-t border-line/60",
                    dropped && "bg-red-950/40 opacity-60"
                  )}
                >
                  <td className="px-3 py-1 text-ink-dim">{realIdx + 1}</td>
                  <td
                    className={clsx(
                      "px-3 py-1 font-medium",
                      t.side === "long" ? "text-good" : "text-bad"
                    )}
                  >
                    {t.side.toUpperCase()}
                  </td>
                  <td className="px-3 py-1 text-ink-muted">{fmtDate(t.entry_time)}</td>
                  <td className="px-3 py-1 text-ink-muted">{fmtDate(t.exit_time)}</td>
                  <td className="px-3 py-1 text-right tabular-nums">{fmtNum(t.entry_price, 4)}</td>
                  <td className="px-3 py-1 text-right tabular-nums">{fmtNum(t.exit_price ?? null, 4)}</td>
                  <td
                    className={clsx(
                      "px-3 py-1 text-right tabular-nums",
                      t.pnl > 0 ? "text-good" : t.pnl < 0 ? "text-bad" : ""
                    )}
                  >
                    {t.pnl > 0 ? "+" : ""}
                    {fmtNum(t.pnl, 2)}
                  </td>
                  <td className="px-3 py-1 text-[11px] text-ink-dim">{t.exit_reason}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
