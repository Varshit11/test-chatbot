/**
 * Derive 1–2 plain-English “flagship” lines from rule_based_insights payloads.
 */

export type SpotlightCard = {
  id: string;
  headline: string;
  body: string;
  deltaLabel: string;
  tone: "emerald" | "cyan" | "violet";
  category: "time" | "indicator";
};

const SESSION_COPY: Record<string, { label: string; plain: string }> = {
  US: {
    label: "U.S. session",
    plain: "U.S. trading hours (includes New York, 16:00–22:00 UTC)",
  },
  London: { label: "London session", plain: "London hours (08:00–13:00 UTC)" },
  Overlap: {
    label: "London–NY overlap",
    plain: "the London–New York overlap (13:00–16:00 UTC)",
  },
  Asian: { label: "Asian session", plain: "Asian hours (23:00–08:00 UTC)" },
};

function minSampleSize(baseTrades: number): number {
  return Math.max(8, Math.min(40, Math.floor(0.04 * baseTrades + 10)));
}

type Cand = SpotlightCard & { score: number };

function pushSessionSpotlights(
  sessions: any[],
  hoursUtc: Record<string, string>,
  baseWr: number,
  baseN: number,
  minN: number,
  out: Cand[]
): void {
  for (const row of sessions) {
    const n = Number(row.trades) || 0;
    if (n < minN) continue;
    const imp = Number(row.improvement_vs_base);
    if (imp == null || imp < 0.75) continue;
    const wr = Number(row.win_rate);
    const key = String(row.bucket || "");
    const copy = SESSION_COPY[key] || {
      label: key || "this session",
      plain: key || "this session window",
    };
    const utc = hoursUtc[key] || "";
    out.push({
      id: `session-${key}`,
      category: "time",
      headline: `Stick to ${copy.label}`,
      body: `If you only traded during ${copy.plain}${
        utc ? ` (${utc})` : ""
      }, win rate would be about **${wr.toFixed(1)}%** instead of **${baseWr.toFixed(1)}%** overall — still **${n}** qualifying trades.`,
      deltaLabel: `+${imp.toFixed(1)} pts vs baseline`,
      tone: "emerald",
      score: imp * Math.log1p(n),
    });
  }
}

function pushHourSpotlight(
  byHour: any[],
  baseWr: number,
  minN: number,
  out: Cand[]
): void {
  let best: { hour: number; trades: number; win_rate: number; imp: number } | null = null;
  for (const row of byHour || []) {
    const n = Number(row.trades) || 0;
    if (n < minN) continue;
    const imp = Number(row.improvement_vs_base);
    if (imp == null || imp < 0.75) continue;
    const wr = Number(row.win_rate);
    if (!best || imp > best.imp) best = { hour: row.hour, trades: n, win_rate: wr, imp };
  }
  if (!best) return;
  out.push({
    id: `hour-${best.hour}`,
    category: "time",
    headline: `Best hour block (UTC)`,
    body: `Entries clustered around **${String(best.hour).padStart(2, "0")}:00 UTC** saw **${best.win_rate.toFixed(1)}%** wins on **${best.trades}** trades — about **+${best.imp.toFixed(1)}** percentage points vs baseline.`,
    deltaLabel: `+${best.imp.toFixed(1)} pts`,
    tone: "cyan",
    score: best.imp * Math.log1p(best.trades) * 0.92,
  });
}

function pushMacdAdxRsi(tech: any, baseWr: number, minN: number, out: Cand[]): void {
  const macdRows = tech?.macd?.tests || [];
  for (const row of macdRows) {
    const n = Number(row.trades) || 0;
    if (n < minN) continue;
    const imp = Number(row.improvement_vs_base_pct);
    if (imp == null || imp < 0.75) continue;
    const wr = Number(row.win_rate_pct);
    const shortName = shortMacdLabel(String(row.name || ""));
    out.push({
      id: `macd-${shortName}`,
      category: "indicator",
      headline: "Add a simple MACD filter",
      body: `Requiring **${shortName}** bumps win rate to about **${wr.toFixed(1)}%** (**${n}** trades) — roughly **+${imp.toFixed(1)}** points vs your baseline **${baseWr.toFixed(1)}%**.`,
      deltaLabel: `+${imp.toFixed(1)} pts`,
      tone: "violet",
      score: imp * Math.log1p(n),
    });
  }

  const adxRows = tech?.adx?.adx_gt_thresholds || [];
  for (const row of adxRows) {
    const n = Number(row.trades) || 0;
    if (n < minN) continue;
    const imp = Number(row.improvement_vs_base_pct);
    if (imp == null || imp < 0.75) continue;
    const wr = Number(row.win_rate_pct);
    const thr = row.adx_gt;
    out.push({
      id: `adx-${thr}`,
      category: "indicator",
      headline: "Trade stronger trends (ADX)",
      body: `When **ADX > ${thr}** at entry, win rate is **${wr.toFixed(1)}%** over **${n}** trades — about **+${imp.toFixed(1)}** points vs baseline.`,
      deltaLabel: `+${imp.toFixed(1)} pts`,
      tone: "violet",
      score: imp * Math.log1p(n) * 1.05,
    });
  }

  const rsiGrid = tech?.rsi_extremes?.grid || [];
  for (const row of rsiGrid) {
    const n = Number(row.trades) || 0;
    if (n < minN) continue;
    const imp = Number(row.improvement_vs_base_pct);
    if (imp == null || imp < 0.75) continue;
    const wr = Number(row.combined_win_rate_pct ?? row.win_rate_pct);
    const lbl = String(row.label || "RSI extreme");
    out.push({
      id: `rsi-${row.rsi_short_ge ?? lbl}`,
      category: "indicator",
      headline: "Exploit RSI extremes",
      body: `Using **${lbl}** as a filter lifts win rate to **${wr.toFixed(1)}%** (**${n}** trades) — **+${imp.toFixed(1)}** points vs baseline.`,
      deltaLabel: `+${imp.toFixed(1)} pts`,
      tone: "violet",
      score: imp * Math.log1p(n),
    });
  }
}

function shortMacdLabel(full: string): string {
  if (full.includes("vs zero")) return "MACD on the right side of zero (longs > 0, shorts < 0)";
  if (full.includes("histogram")) return "MACD histogram agreeing with direction";
  if (full.includes("aligned") || full.includes("direction"))
    return "MACD line aligned with signal in your direction";
  return full.length > 80 ? `${full.slice(0, 77)}…` : full;
}

/** Pick up to two cards: prefer one time + one indicator when possible. */
export function pickRuleBasedSpotlights(data: any): SpotlightCard[] {
  if (!data || (data.schema !== "rule_based_v1" && data.schema !== "rule_based_v2")) {
    return [];
  }

  const base = data.base || {};
  const baseN = Number(base.n_trades) || 0;
  if (baseN < 15) return [];

  const minN = minSampleSize(baseN);
  const tech = data.technical_context;
  const tradeBaselinePct = Number(base.win_rate) || 0;
  const techBase =
    tech?.baseline_win_rate_pct != null ? Number(tech.baseline_win_rate_pct) : tradeBaselinePct;

  const cands: Cand[] = [];
  pushSessionSpotlights(
    data.by_session || [],
    data.session_hours_utc || {},
    tradeBaselinePct,
    baseN,
    minN,
    cands
  );
  pushHourSpotlight(data.by_hour || [], tradeBaselinePct, minN, cands);
  if (tech?.available === true) {
    pushMacdAdxRsi(tech, techBase, minN, cands);
  }

  cands.sort((a, b) => b.score - a.score);
  if (cands.length === 0) return [];

  const picked: SpotlightCard[] = [];
  const first = cands[0];
  picked.push(stripScore(first));

  const wantOtherCat = first.category === "time" ? "indicator" : "time";
  const second =
    cands.find((c) => c.id !== first.id && c.category === wantOtherCat) ||
    cands.find((c) => c.id !== first.id);
  if (second) picked.push(stripScore(second));

  return picked.slice(0, 2);
}

function stripScore(c: Cand): SpotlightCard {
  const { score: _s, ...rest } = c;
  return rest;
}
