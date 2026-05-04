"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Flame, Lightbulb } from "lucide-react";
import { pickRuleBasedSpotlights, type SpotlightCard } from "@/lib/ruleBasedSpotlights";

const SCHEMA_OK = new Set(["rule_based_v1", "rule_based_v2"]);

const tableWrap =
  "overflow-x-auto rounded-xl border border-line/80 bg-bg-elev/35 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]";
const thClass =
  "border-b border-line px-3 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-ink-dim/90";
const tdClass = "border-b border-line/45 px-3 py-2 text-[11px] text-ink-muted";

function toneFrame(tone: SpotlightCard["tone"]) {
  switch (tone) {
    case "emerald":
      return "border-emerald-500/35 bg-gradient-to-br from-emerald-950/40 via-bg-panel/90 to-emerald-950/15 shadow-[0_0_28px_-12px_rgba(52,211,153,0.35)]";
    case "cyan":
      return "border-cyan-500/35 bg-gradient-to-br from-cyan-950/35 via-bg-panel/90 to-slate-950/20 shadow-[0_0_28px_-12px_rgba(34,211,238,0.3)]";
    default:
      return "border-violet-500/35 bg-gradient-to-br from-violet-950/45 via-bg-panel/90 to-fuchsia-950/20 shadow-[0_0_28px_-12px_rgba(167,139,250,0.35)]";
  }
}

function badgeTone(tone: SpotlightCard["tone"]) {
  switch (tone) {
    case "emerald":
      return "bg-emerald-500/20 text-emerald-100 ring-emerald-400/30";
    case "cyan":
      return "bg-cyan-500/20 text-cyan-100 ring-cyan-400/30";
    default:
      return "bg-violet-500/20 text-violet-100 ring-violet-400/30";
  }
}

function InsightSpotlights({ cards }: { cards: SpotlightCard[] }) {
  if (!cards.length) return null;
  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200/90">
        <Flame size={13} className="text-amber-300" />
        Standout takeaways
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {cards.map((c) => (
          <div
            key={c.id}
            className={clsx(
              "rounded-xl border p-3.5 ring-1 ring-inset ring-white/[0.04]",
              toneFrame(c.tone)
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold leading-snug text-ink">
                <Lightbulb size={14} className="shrink-0 text-amber-200/80" />
                {c.headline}
              </div>
              <span
                className={clsx(
                  "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1",
                  badgeTone(c.tone)
                )}
              >
                {c.deltaLabel}
              </span>
            </div>
            <div className="markdown-body mt-2 text-[11px] leading-relaxed text-ink-muted [&_strong]:text-ink">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{c.body}</ReactMarkdown>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function RuleBasedInsightsPanel({ data }: { data: any }) {
  const [hoursOpen, setHoursOpen] = useState(false);
  const [techOpen, setTechOpen] = useState(true);
  const spotlights = useMemo(() => pickRuleBasedSpotlights(data), [data]);

  if (!data || !SCHEMA_OK.has(data.schema)) {
    return (
      <p className="text-xs text-ink-dim">No rule-based insights available for this run.</p>
    );
  }

  const tech = data.technical_context;
  const base = data.base || {};
  const sessions = data.by_session || [];
  const dow = data.by_weekday || [];
  const rules = data.rules || [];
  const notes = data.notes || [];
  const hoursUtc = data.session_hours_utc || {};
  const byHour = data.by_hour || [];

  return (
    <div className="space-y-5 text-xs">
      {data.timezone_note && (
        <p className="text-[11px] text-amber-200/90">{data.timezone_note}</p>
      )}

      {spotlights.length > 0 && <InsightSpotlights cards={spotlights} />}

      <div className="rounded-xl border border-line/90 bg-gradient-to-r from-bg-panel/80 to-bg-elev/50 px-3 py-2.5">
        <span className="text-ink-dim">Baseline: </span>
        <span className="font-mono text-sm text-ink">
          {base.n_trades ?? 0} trades · {base.win_rate ?? 0}% win-rate
        </span>
      </div>

      {rules.length > 0 && (
        <div className="rounded-xl border border-amber-900/45 bg-amber-950/25 p-3">
          <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200/85">
            Rule-style flags
          </div>
          <ul className="markdown-body ml-4 list-disc space-y-1 text-[11px] text-ink-muted">
            {rules.map((r: string, i: number) => (
              <li key={i}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{r}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-dim">
          Sessions (UTC)
        </div>
        <div className={tableWrap}>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="bg-bg-panel/95">
                <th className={thClass}>Session</th>
                <th className={thClass}>Hours</th>
                <th className={clsx(thClass, "text-right")}>Trades</th>
                <th className={clsx(thClass, "text-right")}>Win %</th>
                <th className={clsx(thClass, "text-right")}>Δ vs base</th>
                <th className={clsx(thClass, "text-right")}>Avg pts</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((row: any, idx: number) => (
                <tr
                  key={row.bucket}
                  className={clsx(
                    "transition-colors hover:bg-white/[0.04]",
                    idx % 2 === 1 && "bg-black/[0.12]"
                  )}
                >
                  <td className={clsx(tdClass, "font-medium text-ink")}>{row.bucket}</td>
                  <td className={clsx(tdClass, "text-ink-dim/90")}>
                    {hoursUtc[row.bucket] || "—"}
                  </td>
                  <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                    {row.trades}
                  </td>
                  <td
                    className={clsx(
                      tdClass,
                      "text-right font-mono tabular-nums",
                      row.win_rate >= base.win_rate ? "font-medium text-emerald-300" : ""
                    )}
                  >
                    {row.win_rate?.toFixed?.(1) ?? row.win_rate}%
                  </td>
                  <td className={clsx(tdClass, "text-right font-mono tabular-nums text-ink-dim")}>
                    {row.improvement_vs_base != null
                      ? `${row.improvement_vs_base >= 0 ? "+" : ""}${row.improvement_vs_base}`
                      : "—"}
                  </td>
                  <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                    {row.avg_points ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-dim">
          Weekday
        </div>
        <div className={tableWrap}>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="bg-bg-panel/95">
                <th className={thClass}>Day</th>
                <th className={clsx(thClass, "text-right")}>Trades</th>
                <th className={clsx(thClass, "text-right")}>Win %</th>
                <th className={clsx(thClass, "text-right")}>Δ vs base</th>
              </tr>
            </thead>
            <tbody>
              {dow.map((row: any, idx: number) => (
                <tr
                  key={row.bucket}
                  className={clsx(
                    "hover:bg-white/[0.04]",
                    idx % 2 === 1 && "bg-black/[0.12]"
                  )}
                >
                  <td className={clsx(tdClass, "text-ink")}>{row.bucket}</td>
                  <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                    {row.trades}
                  </td>
                  <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                    {row.win_rate?.toFixed?.(1) ?? row.win_rate}%
                  </td>
                  <td className={clsx(tdClass, "text-right font-mono tabular-nums text-ink-dim")}>
                    {row.improvement_vs_base != null
                      ? `${row.improvement_vs_base >= 0 ? "+" : ""}${row.improvement_vs_base}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setHoursOpen((o) => !o)}
          className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-ink-dim hover:text-ink-muted"
        >
          <span className="font-mono text-[9px]">{hoursOpen ? "▼" : "▶"}</span>
          Hourly buckets (UTC)
        </button>
        {hoursOpen && byHour.length > 0 && (
          <div className={clsx(tableWrap, "max-h-52 overflow-y-auto")}>
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 z-[1] bg-bg-panel shadow-sm">
                <tr>
                  <th className={thClass}>Hour</th>
                  <th className={clsx(thClass, "text-right")}>Trades</th>
                  <th className={clsx(thClass, "text-right")}>Win %</th>
                  <th className={clsx(thClass, "text-right")}>Δ vs base</th>
                </tr>
              </thead>
              <tbody>
                {byHour.map((row: any, idx: number) => (
                  <tr
                    key={row.hour}
                    className={clsx(
                      "border-b border-line/30 hover:bg-white/[0.03]",
                      row.trades === 0 && "opacity-35",
                      idx % 2 === 1 && row.trades > 0 && "bg-black/[0.08]"
                    )}
                  >
                    <td className={clsx(tdClass, "font-mono text-ink-muted")}>
                      {String(row.hour).padStart(2, "0")}:00
                    </td>
                    <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                      {row.trades}
                    </td>
                    <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                      {row.win_rate?.toFixed?.(1) ?? row.win_rate}%
                    </td>
                    <td className={clsx(tdClass, "text-right font-mono tabular-nums text-ink-dim")}>
                      {row.improvement_vs_base != null
                        ? `${row.improvement_vs_base >= 0 ? "+" : ""}${row.improvement_vs_base}`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {tech && tech.available === true && (
        <div className="rounded-xl border border-cyan-800/50 bg-cyan-950/20 p-3 ring-1 ring-cyan-500/10">
          <button
            type="button"
            onClick={() => setTechOpen((o) => !o)}
            className="mb-2 flex w-full items-center gap-2 text-left text-[10px] font-semibold uppercase tracking-wide text-cyan-200/95 hover:text-cyan-50"
          >
            <span className="font-mono text-[9px]">{techOpen ? "▼" : "▶"}</span>
            Momentum &amp; trend checks (RSI, MACD, ADX, stoch, EMA — notebook-style)
          </button>
          {techOpen && (
            <div className="space-y-4 text-[11px] text-ink-muted">
              <p className="text-[11px] leading-relaxed text-ink-dim">
                Aligned <span className="font-mono text-ink">{tech.aligned_trades}</span> trades to
                OHLCV bars (indicators at entry). Baseline win-rate{" "}
                <span className="font-mono text-ink">{tech.baseline_win_rate_pct}%</span>.
              </p>
              {tech.technical_rules?.length > 0 && (
                <ul className="markdown-body ml-4 list-disc space-y-1 rounded-lg border border-cyan-900/30 bg-cyan-950/10 p-2.5">
                  {tech.technical_rules.map((r: string, i: number) => (
                    <li key={i}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{r}</ReactMarkdown>
                    </li>
                  ))}
                </ul>
              )}

              {tech.trend_vs_counter_ema200 && (
                <div className="rounded-lg border border-line/70 bg-bg-panel/50 p-2.5">
                  <div className="mb-1 text-[10px] font-semibold text-cyan-100/85">
                    Trend vs counter (EMA200)
                  </div>
                  <div className="grid grid-cols-2 gap-3 font-mono text-[10px] leading-relaxed">
                    <div>
                      <span className="text-ink-dim">With trend</span>
                      <br />
                      <span className="text-ink">
                        {tech.trend_vs_counter_ema200.with_trend?.trades} trades ·{" "}
                        {tech.trend_vs_counter_ema200.with_trend?.win_rate_pct}%
                      </span>
                    </div>
                    <div>
                      <span className="text-ink-dim">Counter</span>
                      <br />
                      <span className="text-ink">
                        {tech.trend_vs_counter_ema200.counter_trend?.trades} trades ·{" "}
                        {tech.trend_vs_counter_ema200.counter_trend?.win_rate_pct}%
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {tech.macd?.tests?.length > 0 && (
                <div>
                  <div className="mb-1.5 text-[10px] font-semibold text-ink-dim">MACD rules</div>
                  <div className={tableWrap}>
                    <table className="w-full border-collapse text-left">
                      <thead>
                        <tr className="bg-bg-panel/95">
                          <th className={thClass}>MACD rule</th>
                          <th className={clsx(thClass, "text-right")}>N</th>
                          <th className={clsx(thClass, "text-right")}>Win %</th>
                          <th className={clsx(thClass, "text-right")}>Δ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tech.macd.tests.map((row: any, i: number) => (
                          <tr
                            key={i}
                            className={clsx(
                              "hover:bg-white/[0.04]",
                              i % 2 === 1 && "bg-black/[0.12]"
                            )}
                          >
                            <td className={clsx(tdClass, "max-w-[14rem] text-ink-muted")}>
                              {row.name}
                            </td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.trades}
                            </td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.win_rate_pct}%
                            </td>
                            <td
                              className={clsx(
                                tdClass,
                                "text-right font-mono tabular-nums",
                                Number(row.improvement_vs_base_pct) > 0 && "text-emerald-300/95"
                              )}
                            >
                              {row.improvement_vs_base_pct > 0 ? "+" : ""}
                              {row.improvement_vs_base_pct}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {tech.rsi_extremes?.grid?.length > 0 && (
                <div>
                  <div className="mb-1.5 text-[10px] font-semibold text-ink-dim">
                    RSI extreme grid
                  </div>
                  <div className={tableWrap}>
                    <table className="w-full border-collapse text-left">
                      <thead>
                        <tr className="bg-bg-panel/95">
                          <th className={thClass}>Label</th>
                          <th className={clsx(thClass, "text-right")}>N</th>
                          <th className={clsx(thClass, "text-right")}>Win %</th>
                          <th className={clsx(thClass, "text-right")}>Δ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tech.rsi_extremes.grid.slice(0, 8).map((row: any, i: number) => (
                          <tr
                            key={i}
                            className={clsx(
                              "hover:bg-white/[0.04]",
                              i % 2 === 1 && "bg-black/[0.12]"
                            )}
                          >
                            <td className={clsx(tdClass, "text-ink-muted")}>{row.label}</td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.trades}
                            </td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.combined_win_rate_pct ?? row.win_rate_pct}%
                            </td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {Number(row.improvement_vs_base_pct) > 0 ? "+" : ""}
                              {row.improvement_vs_base_pct}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {tech.rsi_extremes.grid.every((r: any) => (r.trades ?? 0) === 0) && (
                    <p className="mt-1.5 text-[10px] italic text-ink-dim">
                      No trades landed in these RSI extreme buckets for this run — the grid stays for
                      when they do.
                    </p>
                  )}
                </div>
              )}

              {tech.adx?.adx_gt_thresholds?.length > 0 && (
                <div>
                  <div className="mb-1.5 text-[10px] font-semibold text-ink-dim">ADX &gt; threshold</div>
                  <div className={tableWrap}>
                    <table className="w-full border-collapse text-left">
                      <thead>
                        <tr className="bg-bg-panel/95">
                          <th className={thClass}>Rule</th>
                          <th className={clsx(thClass, "text-right")}>N</th>
                          <th className={clsx(thClass, "text-right")}>Win %</th>
                          <th className={clsx(thClass, "text-right")}>Δ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tech.adx.adx_gt_thresholds.map((row: any, i: number) => (
                          <tr
                            key={i}
                            className={clsx(
                              "hover:bg-white/[0.04]",
                              i % 2 === 1 && "bg-black/[0.12]"
                            )}
                          >
                            <td className={tdClass}>ADX &gt; {row.adx_gt}</td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.trades}
                            </td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.win_rate_pct}%
                            </td>
                            <td
                              className={clsx(
                                tdClass,
                                "text-right font-mono tabular-nums",
                                Number(row.improvement_vs_base_pct) > 0 && "text-emerald-300/95"
                              )}
                            >
                              {row.improvement_vs_base_pct > 0 ? "+" : ""}
                              {row.improvement_vs_base_pct}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {tech.ema_alignment?.tests?.length > 0 && (
                <div>
                  <div className="mb-1.5 text-[10px] font-semibold text-ink-dim">EMA alignment</div>
                  <div className={tableWrap}>
                    <table className="w-full border-collapse text-left">
                      <thead>
                        <tr className="bg-bg-panel/95">
                          <th className={thClass}>Rule</th>
                          <th className={clsx(thClass, "text-right")}>N</th>
                          <th className={clsx(thClass, "text-right")}>Win %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tech.ema_alignment.tests.map((row: any, i: number) => (
                          <tr
                            key={i}
                            className={clsx(
                              "hover:bg-white/[0.04]",
                              i % 2 === 1 && "bg-black/[0.12]"
                            )}
                          >
                            <td className={clsx(tdClass, "text-ink-muted")}>{row.name}</td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.trades}
                            </td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.win_rate_pct}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {tech.by_month?.length > 0 && (
                <div>
                  <div className="mb-1.5 text-[10px] font-semibold text-ink-dim">By month</div>
                  <div className={tableWrap}>
                    <table className="w-full border-collapse text-left">
                      <thead>
                        <tr className="bg-bg-panel/95">
                          <th className={thClass}>Month</th>
                          <th className={clsx(thClass, "text-right")}>Trades</th>
                          <th className={clsx(thClass, "text-right")}>Win %</th>
                          <th className={clsx(thClass, "text-right")}>Pts</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tech.by_month.map((row: any, i: number) => (
                          <tr
                            key={row.month}
                            className={clsx(
                              "hover:bg-white/[0.04]",
                              i % 2 === 1 && "bg-black/[0.12]"
                            )}
                          >
                            <td className={clsx(tdClass, "font-mono text-ink")}>{row.month}</td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.trades}
                            </td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.win_rate_pct}%
                            </td>
                            <td className={clsx(tdClass, "text-right font-mono tabular-nums")}>
                              {row.total_points} pts
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tech && tech.available === false && tech.reason && (
        <p className="text-[11px] text-ink-dim">Technical rule layer skipped: {tech.reason}</p>
      )}

      {notes.length > 0 && (
        <ul className="ml-4 list-disc text-[11px] text-ink-dim">
          {notes.map((n: string, i: number) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
