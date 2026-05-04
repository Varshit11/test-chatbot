"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import {
  BarChart2,
  ChevronDown,
  Info,
  Lightbulb,
  Search,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { RuleBasedInsightsPanel } from "./RuleBasedInsightsPanel";
import { MetricsGrid, CompareMetricRow } from "./MetricsGrid";
import { EquityChart, DrawdownChart } from "./EquityChart";
import { TradeTable } from "./TradeTable";
import { ActionButtons } from "./ActionButtons";
import { SessionStatsPanel } from "./SessionStatsPanel";
import {
  StrategyFinderTable,
  StrategyFinderScatter,
} from "./StrategyFinderTable";
import {
  ThresholdSweepPanel,
  PerTradeScoreTable,
  type SweepRow,
} from "./AIFilterPanels";
import { StrategyLogicPanel } from "./StrategyLogicPanel";
import { fmtNum, fmtPct } from "@/lib/format";

export function BacktestCard({
  meta,
  onAction,
  busy,
}: {
  meta: any;
  onAction: (id: string, payload?: any) => void;
  busy?: string | null;
}) {
  const [showTrades, setShowTrades] = useState(false);
  const [showInsights, setShowInsights] = useState(false);
  const chart = meta.chart;
  return (
    <div className="rounded-lg border border-line bg-bg-elev p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-ink-dim">
        <span className="rounded bg-blue-900/40 px-1.5 py-0.5 text-blue-200">Backtest</span>
        <span>{meta.instrument} · {meta.timeframe}</span>
        {chart?.type === "renko" && (
          <span className="rounded bg-violet-900/50 px-1.5 py-0.5 font-mono text-[10px] text-violet-200">
            Renko ({chart.mode || "wicks"}
            {chart.brick_size != null ? ` · brick ${chart.brick_size}` : " · auto brick"})
          </span>
        )}
        {meta.from && meta.to && (
          <span className="text-ink-dim">
            · <span className="font-mono">{String(meta.from).slice(0, 10)}</span> →{" "}
            <span className="font-mono">{String(meta.to).slice(0, 10)}</span>
            {meta.bars_used && <> ({meta.bars_used.toLocaleString()} bars)</>}
          </span>
        )}
      </div>

      <MetricsGrid metrics={meta.metrics} />

      <div className="mt-3">
        <StrategyLogicPanel explain={meta.explain} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="rounded-md border border-line bg-bg-panel p-3 lg:col-span-2">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-ink-dim">Equity curve</div>
          <EquityChart data={meta.equity_curve || []} initial={meta.metrics.initial_capital} />
        </div>
        <div className="rounded-md border border-line bg-bg-panel p-3">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-ink-dim">Drawdown</div>
          <DrawdownChart data={meta.drawdown_curve || []} />
        </div>
      </div>

      {meta.session_stats && (
        <div className="mt-4">
          <SessionStatsPanel stats={meta.session_stats} />
        </div>
      )}

      {meta.rule_based_insights && (
        <div className="mt-4">
          <button
            type="button"
            onClick={() => setShowInsights((s) => !s)}
            className="inline-flex items-center gap-1.5 rounded-md border border-line bg-bg-panel px-2.5 py-1 text-[11px] text-ink-muted hover:text-ink"
          >
            <BarChart2 size={12} className="text-violet-300" />
            {showInsights ? "Hide rule-based insights" : "See insights (sessions & buckets)"}
          </button>
          {showInsights && (
            <div className="mt-3 rounded-md border border-violet-900/40 bg-bg-panel/40 p-3">
              <RuleBasedInsightsPanel data={meta.rule_based_insights} />
            </div>
          )}
        </div>
      )}

      <button
        onClick={() => setShowTrades((s) => !s)}
        className="mt-3 inline-flex items-center gap-1 rounded-md border border-line bg-bg-panel px-2.5 py-1 text-[11px] text-ink-muted hover:text-ink"
      >
        <ChevronDown
          size={12}
          className={clsx("transition-transform", showTrades && "rotate-180")}
        />
        {showTrades ? "Hide trades" : `Show trades (${meta.full_trade_count ?? meta.trades.length})`}
      </button>

      {showTrades && (
        <div className="mt-3">
          <TradeTable
            trades={meta.trades}
            truncated={meta.trades_truncated}
            fullCount={meta.full_trade_count}
          />
        </div>
      )}

      <ActionButtons actions={meta.actions} onAction={onAction} busy={busy} />
    </div>
  );
}

export function StrategyFinderCard({
  meta,
  onAction,
  busy,
}: {
  meta: any;
  onAction: (id: string, payload?: any) => void;
  busy?: string | null;
}) {
  return (
    <div className="rounded-lg border border-line bg-bg-elev p-4">
      <div className="mb-3 flex items-center justify-between gap-2 text-xs text-ink-dim">
        <div className="flex items-center gap-2">
          <span className="rounded bg-emerald-900/40 px-1.5 py-0.5 text-emerald-200">
            Strategy Finder
          </span>
          <span>
            {meta.n_combos} combinations tested
            {meta.bars_used && (
              <span className="ml-1 text-ink-dim/70">on {meta.bars_used.toLocaleString()} bars</span>
            )}
          </span>
        </div>
      </div>

      <SFImprovementSummary
        before={meta.original_metrics}
        after={meta.best_metrics}
        bestBeatsOriginal={meta.best_beats_original}
        objective={meta.objective}
      />

      {meta.best_beats_original !== false && (
        <SFBestCombination
          bestParams={meta.best_params || {}}
          originalParams={meta.original_params || {}}
        />
      )}

      {/* Best equity curve, full width — params + metrics live in the panels above. */}
      <div className="rounded-md border border-line bg-bg-panel p-3">
        <div className="mb-1 flex items-center justify-between text-[10px] uppercase tracking-wide text-ink-dim">
          <span>Best equity curve</span>
          <span className="text-emerald-300">
            {fmtPct(meta.best_metrics?.total_return_pct)} · Sharpe {fmtNum(meta.best_metrics?.sharpe_ratio)}
          </span>
        </div>
        <EquityChart
          data={meta.best_equity_curve || []}
          initial={meta.best_metrics?.initial_capital || 100000}
        />
      </div>

      {/* Scatter overview */}
      <div className="mt-3">
        <StrategyFinderScatter ranked={meta.ranked || []} />
      </div>

      {/* Sortable interactive table */}
      <div className="mt-3">
        <StrategyFinderTable
          ranked={meta.ranked || []}
          paramRanges={meta.param_ranges}
          bestParams={meta.best_params}
        />
      </div>

      {meta.walk_forward && (
        <div className="mt-3 rounded-md border border-line bg-bg-panel p-3">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-ink-dim">
            Walk-forward validation ({meta.walk_forward.splits} splits) — does the best combo hold up out-of-period?
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {(meta.walk_forward.results || []).map((r: any, i: number) => (
              <div key={i} className="rounded border border-line/60 bg-bg-elev p-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-ink-dim">Split {r.split}</span>
                  <span className="text-[9px] font-mono text-ink-dim/70">
                    {String(r.from || "").slice(0, 10)}
                  </span>
                </div>
                {r.error ? (
                  <div className="text-bad">{r.error}</div>
                ) : (
                  <div className="mt-1 space-y-0.5">
                    <div className="flex justify-between">
                      <span className="text-ink-muted">Return</span>
                      <span
                        className={clsx(
                          "font-mono",
                          (r.metrics?.total_return_pct || 0) >= 0 ? "text-good" : "text-bad"
                        )}
                      >
                        {fmtPct(r.metrics?.total_return_pct)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-muted">Sharpe</span>
                      <span className="font-mono text-ink">
                        {fmtNum(r.metrics?.sharpe_ratio)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-ink-muted">Win-rate</span>
                      <span className="font-mono text-ink">
                        {fmtPct(r.metrics?.win_rate_pct)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <ActionButtons actions={meta.actions} onAction={onAction} busy={busy} />
    </div>
  );
}

export function AIFilterCard({
  meta,
  onAction,
  busy,
}: {
  meta: any;
  onAction: (id: string, payload?: any) => void;
  busy?: string | null;
}) {
  const sweep: SweepRow[] = meta.threshold_sweep || [];

  // Local interactive threshold — defaults to whatever the backend used.
  const [threshold, setThreshold] = useState<number>(Number(meta.threshold) || 0.55);
  // Find the row in the sweep closest to the chosen threshold so we can show
  // the metrics card update live without another backend roundtrip.
  const liveRow = useMemo(() => {
    if (!sweep.length) return null;
    return sweep.reduce((best, r) =>
      Math.abs(r.threshold - threshold) < Math.abs(best.threshold - threshold) ? r : best,
      sweep[0]
    );
  }, [sweep, threshold]);

  const totalTrades = meta.total_trades ?? meta.scores?.length ?? 0;
  const keptCount = meta.kept_indices?.length ?? 0;

  return (
    <div className="rounded-lg border border-line bg-bg-elev p-4">
      <div className="mb-3 flex items-center justify-between gap-2 text-xs text-ink-dim">
        <div className="flex items-center gap-2">
          <span className="rounded bg-purple-900/40 px-1.5 py-0.5 text-purple-200">AI Filter</span>
          <span>kept {keptCount} of {totalTrades} trades</span>
        </div>
      </div>

      {/* Headline improvement at the best threshold */}
      <ImprovementSummary
        before={meta.before_metrics}
        after={meta.after_metrics}
        kept={keptCount}
        total={totalTrades}
      />

      {/* Before / After at the best threshold */}
      <div className="rounded-md border border-line bg-bg-panel p-3">
        <div className="grid grid-cols-4 gap-2 border-b border-line pb-1.5 text-[10px] uppercase tracking-wide text-ink-dim">
          <div>Metric</div>
          <div>Before</div>
          <div>After</div>
          <div>Δ</div>
        </div>
        <CompareMetricRow
          label="Total Return"
          before={meta.before_metrics?.total_return_pct}
          after={meta.after_metrics?.total_return_pct}
          fmt="pct"
        />
        <CompareMetricRow
          label="Sharpe"
          before={meta.before_metrics?.sharpe_ratio}
          after={meta.after_metrics?.sharpe_ratio}
        />
        <CompareMetricRow
          label="Max DD"
          before={meta.before_metrics?.max_drawdown_pct}
          after={meta.after_metrics?.max_drawdown_pct}
          fmt="pct"
        />
        <CompareMetricRow
          label="Profit Factor"
          before={meta.before_metrics?.profit_factor}
          after={meta.after_metrics?.profit_factor}
        />
        <CompareMetricRow
          label="Win Rate"
          before={meta.before_metrics?.win_rate_pct}
          after={meta.after_metrics?.win_rate_pct}
          fmt="pct"
        />
        <CompareMetricRow
          label="Trades"
          before={meta.before_metrics?.n_trades}
          after={meta.after_metrics?.n_trades}
        />
      </div>

      {/* Threshold sweep */}
      {sweep.length > 0 && (
        <div className="mt-3">
          <ThresholdSweepPanel
            sweep={sweep}
            selectedThreshold={threshold}
            onSelect={(t) => setThreshold(t)}
          />
        </div>
      )}

      {/* Interactive sensitivity slider: dial filter strictness, see metrics live */}
      {liveRow && (
        <div className="mt-3 rounded-md border border-line bg-bg-panel p-3">
          <div className="mb-1.5 flex items-center justify-between">
            <div className="text-[10px] uppercase tracking-wide text-ink-dim">
              AI Filter sensitivity — drag to preview a different strictness
            </div>
            <div className="text-[10px] text-ink-dim">
              {fmtNum(liveRow.kept_pct, 0)}% kept
            </div>
          </div>
          <input
            type="range"
            min={0.30}
            max={0.70}
            step={0.05}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="w-full accent-purple-500"
          />
          <div className="mt-1 flex justify-between text-[9px] uppercase tracking-wide text-ink-dim">
            <span>Lenient</span>
            <span>Strict</span>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat
              label="Kept"
              value={`${liveRow.kept}/${liveRow.kept + liveRow.dropped}`}
              sub={`${fmtNum(liveRow.kept_pct, 0)}%`}
            />
            <Stat
              label="Return"
              value={fmtPct(liveRow.total_return_pct)}
              tone={liveRow.total_return_pct >= 0 ? "good" : "bad"}
            />
            <Stat
              label="Sharpe"
              value={fmtNum(liveRow.sharpe_ratio, 2)}
              tone={liveRow.sharpe_ratio >= 0 ? "good" : "bad"}
            />
            <Stat
              label="Win-rate"
              value={fmtPct(liveRow.win_rate_pct)}
            />
          </div>
        </div>
      )}

      {/* Equity after filter */}
      <div className="mt-3">
        <div className="rounded-md border border-line bg-bg-panel p-3">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-ink-dim">
            Equity curve after AI Filter
          </div>
          <EquityChart data={meta.after_equity_curve || []} initial={100000} />
        </div>
      </div>

      {/* Per-trade scores */}
      {meta.per_trade && meta.per_trade.length > 0 && (
        <div className="mt-3">
          <PerTradeScoreTable perTrade={meta.per_trade} threshold={threshold} />
        </div>
      )}

      <ActionButtons actions={meta.actions} onAction={onAction} busy={busy} />
    </div>
  );
}

function ImprovementSummary({
  before,
  after,
  kept,
  total,
}: {
  before?: any;
  after?: any;
  kept: number;
  total: number;
}) {
  if (!before || !after) return null;

  const b = {
    ret: Number(before.total_return_pct ?? 0),
    sharpe: Number(before.sharpe_ratio ?? 0),
    win: Number(before.win_rate_pct ?? 0),
    dd: Number(before.max_drawdown_pct ?? 0),
    pf: Number(before.profit_factor ?? 0),
  };
  const a = {
    ret: Number(after.total_return_pct ?? 0),
    sharpe: Number(after.sharpe_ratio ?? 0),
    win: Number(after.win_rate_pct ?? 0),
    dd: Number(after.max_drawdown_pct ?? 0),
    pf: Number(after.profit_factor ?? 0),
  };
  const dRet = a.ret - b.ret;
  const dSharpe = a.sharpe - b.sharpe;
  const dWin = a.win - b.win;
  const dDD = a.dd - b.dd; // drawdown: lower is better (negative delta = improvement)
  const dPF = a.pf - b.pf;
  const dropped = Math.max(0, total - kept);
  const droppedPct = total > 0 ? (dropped / total) * 100 : 0;

  const fmtSigned = (v: number, digits = 2) =>
    `${v >= 0 ? "+" : ""}${v.toFixed(digits)}`;

  return (
    <div className="mb-3 rounded-md border border-purple-700/40 bg-gradient-to-br from-purple-950/30 via-bg-panel to-fuchsia-950/15 p-3">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <div className="text-[10px] uppercase tracking-wide text-purple-200/80">
          AI Filter improvement
        </div>
        <div className="text-[11px] text-ink-dim">
          Filtered out {dropped} of {total} trades ({droppedPct.toFixed(0)}%)
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <Delta label="Return" before={`${b.ret.toFixed(2)}%`} after={`${a.ret.toFixed(2)}%`} delta={`${fmtSigned(dRet)}%`} good={dRet > 0} />
        <Delta label="Sharpe" before={b.sharpe.toFixed(2)} after={a.sharpe.toFixed(2)} delta={fmtSigned(dSharpe)} good={dSharpe > 0} />
        <Delta label="Win-rate" before={`${b.win.toFixed(1)}%`} after={`${a.win.toFixed(1)}%`} delta={`${fmtSigned(dWin, 1)}%`} good={dWin > 0} />
        <Delta label="Max DD" before={`${b.dd.toFixed(2)}%`} after={`${a.dd.toFixed(2)}%`} delta={`${fmtSigned(dDD)}%`} good={dDD < 0} />
        <Delta label="Profit factor" before={b.pf.toFixed(2)} after={a.pf.toFixed(2)} delta={fmtSigned(dPF)} good={dPF > 0} />
      </div>
    </div>
  );
}

function Delta({
  label,
  before,
  after,
  delta,
  good,
}: {
  label: string;
  before: string;
  after: string;
  delta: string;
  good: boolean;
}) {
  return (
    <div className="rounded border border-line/60 bg-bg-elev px-2.5 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-ink-dim">{label}</div>
      <div className="mt-0.5 flex items-baseline gap-1.5 font-mono text-[12px] tabular-nums">
        <span className="text-ink-muted">{before}</span>
        <span className="text-ink-dim">→</span>
        <span className="text-ink">{after}</span>
      </div>
      <div className={clsx("mt-0.5 font-mono text-[11px] tabular-nums", good ? "text-good" : "text-bad")}>
        {delta}
      </div>
    </div>
  );
}

function SFImprovementSummary({
  before,
  after,
  bestBeatsOriginal,
  objective,
}: {
  before?: any;
  after?: any;
  bestBeatsOriginal?: boolean;
  objective?: string;
}) {
  if (!before || !after) return null;
  const b = {
    ret: Number(before.total_return_pct ?? 0),
    sharpe: Number(before.sharpe_ratio ?? 0),
    win: Number(before.win_rate_pct ?? 0),
    dd: Number(before.max_drawdown_pct ?? 0),
    pf: Number(before.profit_factor ?? 0),
  };

  // No combination beat the original on the chosen objective — show a single
  // honest banner with the original metrics and skip the misleading green
  // "Improvement vs original" delta panel.
  if (bestBeatsOriginal === false) {
    const objLabel = (objective || "sharpe ratio").replace(/_/g, " ");
    return (
      <div className="mb-3 rounded-md border border-amber-700/35 bg-gradient-to-br from-amber-950/25 via-bg-panel to-amber-900/10 p-3">
        <div className="mb-2 text-[10px] uppercase tracking-wide text-amber-200/85">
          Original strategy is the best
        </div>
        <div className="mb-3 text-xs text-ink-muted">
          None of the tested combinations beat your original parameters on{" "}
          <span className="text-ink">{objLabel}</span>. The original metrics below stand:
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <PlainStat label="Return" value={`${b.ret.toFixed(2)}%`} tone={b.ret >= 0 ? "good" : "bad"} />
          <PlainStat label="Sharpe" value={b.sharpe.toFixed(2)} tone={b.sharpe >= 0 ? "good" : "bad"} />
          <PlainStat label="Win-rate" value={`${b.win.toFixed(1)}%`} />
          <PlainStat label="Max DD" value={`${b.dd.toFixed(2)}%`} tone="bad" />
          <PlainStat label="Profit factor" value={b.pf.toFixed(2)} tone={b.pf >= 1 ? "good" : "bad"} />
        </div>
      </div>
    );
  }

  const a = {
    ret: Number(after.total_return_pct ?? 0),
    sharpe: Number(after.sharpe_ratio ?? 0),
    win: Number(after.win_rate_pct ?? 0),
    dd: Number(after.max_drawdown_pct ?? 0),
    pf: Number(after.profit_factor ?? 0),
  };
  const dRet = a.ret - b.ret;
  const dSharpe = a.sharpe - b.sharpe;
  const dWin = a.win - b.win;
  const dDD = a.dd - b.dd;
  const dPF = a.pf - b.pf;
  const fmtSigned = (v: number, digits = 2) =>
    `${v >= 0 ? "+" : ""}${v.toFixed(digits)}`;

  return (
    <div className="mb-3 rounded-md border border-emerald-700/35 bg-gradient-to-br from-emerald-950/25 via-bg-panel to-emerald-900/10 p-3">
      <div className="mb-2 text-[10px] uppercase tracking-wide text-emerald-200/85">
        Improvement vs original strategy
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <Delta label="Return" before={`${b.ret.toFixed(2)}%`} after={`${a.ret.toFixed(2)}%`} delta={`${fmtSigned(dRet)}%`} good={dRet > 0} />
        <Delta label="Sharpe" before={b.sharpe.toFixed(2)} after={a.sharpe.toFixed(2)} delta={fmtSigned(dSharpe)} good={dSharpe > 0} />
        <Delta label="Win-rate" before={`${b.win.toFixed(1)}%`} after={`${a.win.toFixed(1)}%`} delta={`${fmtSigned(dWin, 1)}%`} good={dWin > 0} />
        <Delta label="Max DD" before={`${b.dd.toFixed(2)}%`} after={`${a.dd.toFixed(2)}%`} delta={`${fmtSigned(dDD)}%`} good={dDD < 0} />
        <Delta label="Profit factor" before={b.pf.toFixed(2)} after={a.pf.toFixed(2)} delta={fmtSigned(dPF)} good={dPF > 0} />
      </div>
    </div>
  );
}

function PlainStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "bad";
}) {
  return (
    <div className="rounded border border-line/60 bg-bg-elev px-2.5 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-ink-dim">{label}</div>
      <div
        className={clsx(
          "mt-0.5 font-mono text-[12px] tabular-nums",
          tone === "good" && "text-good",
          tone === "bad" && "text-bad",
          !tone && "text-ink"
        )}
      >
        {value}
      </div>
    </div>
  );
}

function SFBestCombination({
  bestParams,
  originalParams,
}: {
  bestParams: Record<string, any>;
  originalParams: Record<string, any>;
}) {
  if (!bestParams || Object.keys(bestParams).length === 0) return null;
  return (
    <div className="mb-3 rounded-md border border-line bg-bg-panel p-3">
      <div className="mb-2 text-[10px] uppercase tracking-wide text-ink-dim">
        Best combination
      </div>
      <div className="grid gap-1.5 sm:grid-cols-2 md:grid-cols-3">
        {Object.entries(bestParams).map(([k, v]) => {
          const orig = originalParams[k];
          const changed = String(orig) !== String(v);
          return (
            <div
              key={k}
              className={clsx(
                "flex items-baseline justify-between gap-2 rounded border px-2.5 py-1.5 font-mono text-[12px]",
                changed
                  ? "border-emerald-700/40 bg-emerald-950/20"
                  : "border-line/60 bg-bg-elev"
              )}
            >
              <span className="truncate text-ink-dim">{k}</span>
              <span className="flex items-baseline gap-1.5 tabular-nums">
                {changed && orig !== undefined && (
                  <>
                    <span className="text-ink-dim/60 line-through">{String(orig)}</span>
                    <span className="text-ink-dim">→</span>
                  </>
                )}
                <span className={changed ? "font-semibold text-emerald-300" : "text-ink"}>
                  {String(v)}
                </span>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "bad" }) {
  return (
    <div className="rounded border border-line/60 bg-bg-elev px-2.5 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-ink-dim">{label}</div>
      <div
        className={clsx(
          "font-mono text-sm tabular-nums",
          tone === "good" && "text-good",
          tone === "bad" && "text-bad",
          !tone && "text-ink"
        )}
      >
        {value}
      </div>
      {sub && <div className="text-[10px] text-ink-dim">{sub}</div>}
    </div>
  );
}

export function ImprovementsCard({
  meta,
  onAction,
  busy,
}: {
  meta: any;
  onAction: (id: string, payload?: any) => void;
  busy?: string | null;
}) {
  return (
    <div className="rounded-lg border border-line bg-bg-elev p-4">
      <div className="mb-3 flex items-center gap-2 text-xs text-ink-dim">
        <Lightbulb size={13} className="text-warn" />
        <span className="rounded bg-amber-900/40 px-1.5 py-0.5 text-amber-200">Improvements</span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-md border border-line bg-bg-panel p-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-good">
            <ThumbsUp size={11} /> Pros
          </div>
          <ul className="space-y-1 text-sm text-ink-muted">
            {(meta.pros || []).map((p: string, i: number) => (
              <li key={i} className="flex gap-1.5">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-good" />
                <span>{p}</span>
              </li>
            ))}
            {(meta.pros || []).length === 0 && <li className="text-ink-dim">—</li>}
          </ul>
        </div>
        <div className="rounded-md border border-line bg-bg-panel p-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-bad">
            <ThumbsDown size={11} /> Cons
          </div>
          <ul className="space-y-1 text-sm text-ink-muted">
            {(meta.cons || []).map((p: string, i: number) => (
              <li key={i} className="flex gap-1.5">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-bad" />
                <span>{p}</span>
              </li>
            ))}
            {(meta.cons || []).length === 0 && <li className="text-ink-dim">—</li>}
          </ul>
        </div>
      </div>

      {meta.basic_filter_suggestions?.length > 0 && (
        <div className="mt-3 rounded-md border border-line bg-bg-panel p-3">
          <div className="mb-2 text-[10px] uppercase tracking-wide text-ink-dim">Basic filters to try</div>
          <div className="space-y-2">
            {meta.basic_filter_suggestions.map((b: any, i: number) => (
              <div
                key={i}
                className="flex items-center justify-between gap-2 rounded border border-line/60 bg-bg-elev px-3 py-2"
              >
                <div>
                  <div className="text-sm text-ink">{b.name}</div>
                  <div className="text-[11px] text-ink-dim">{b.rationale}</div>
                </div>
                <button
                  disabled={!!busy}
                  onClick={() =>
                    onAction("edit_params", { parameters: { [b.param]: b.value } })
                  }
                  className="shrink-0 rounded-md border border-line bg-bg-panel px-2.5 py-1 text-[11px] text-ink-muted hover:text-ink disabled:opacity-50"
                >
                  Apply &amp; re-run
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {(!meta.sf_done || !meta.ai_filter_done) && (
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {!meta.sf_done && (
            <div className="rounded-md border border-line bg-bg-panel p-3">
              <div className="mb-1.5 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-emerald-300">
                <Search size={11} /> Strategy Finder
              </div>
              <div className="text-xs text-ink-muted">
                {meta.param_tuning_suggestion?.should_run
                  ? "Recommended — explore the suggested ranges to find a higher-Sharpe combo."
                  : "Optional — current params already look reasonable."}
              </div>
              <button
                disabled={!!busy}
                onClick={() => onAction("run_finder")}
                className="mt-2 rounded-md bg-emerald-700/40 px-3 py-1 text-xs text-emerald-100 hover:bg-emerald-700/60 disabled:opacity-50"
              >
                Run Strategy Finder
              </button>
            </div>
          )}
          {!meta.ai_filter_done && (
            <div className="rounded-md border border-line bg-bg-panel p-3">
              <div className="mb-1.5 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-purple-300">
                <Sparkles size={11} /> AI Filter
              </div>
              <div className="text-xs text-ink-muted">
                {meta.ai_filter_suggestion?.rationale ||
                  "Score each entry on context features and drop low-quality trades."}
              </div>
              <button
                disabled={!!busy}
                onClick={() => onAction("run_filter")}
                className="mt-2 rounded-md bg-purple-700/40 px-3 py-1 text-xs text-purple-100 hover:bg-purple-700/60 disabled:opacity-50"
              >
                Apply AI Filter
              </button>
            </div>
          )}
        </div>
      )}

      {meta.ranked_next_steps?.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-ink-dim">
            Next steps (in order)
          </div>
          <ol className="ml-4 list-decimal space-y-1 text-sm text-ink-muted marker:text-ink-dim">
            {meta.ranked_next_steps.map((s: string, i: number) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
