"""
Post-backtest rule-style insights.

Time buckets match `rule_based_analysis_intra/session_time_analysis.py` (UTC).

Technical / momentum buckets mirror `rule_based_analysis_intra/` scripts (RSI,
MACD, ADX, stochastic, EMA alignment, MA distance, trend vs EMA200, UTC 13–16,
monthly) — computed on the **same OHLCV** as the backtest in `technical_rule_insights`.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from .technical_rule_insights import compute_technical_rule_insights


def _session_utc(hour: int) -> str:
    if 23 <= hour or hour < 8:
        return "Asian"
    if 8 <= hour < 13:
        return "London"
    if 13 <= hour < 16:
        return "Overlap"
    if 16 <= hour < 22:
        return "US"
    return "Asian"


SESSION_HOURS_UTC = {
    "Asian": "23:00–08:00",
    "London": "08:00–13:00",
    "Overlap": "13:00–16:00",
    "US": "16:00–22:00",
}

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def compute_rule_based_insights(
    trades: List[Dict[str, Any]],
    min_n: int = 5,
    ohlcv: Optional[Any] = None,
) -> Dict[str, Any]:
    """Return JSON-serialisable time buckets + optional technical-context rules (RSI/MACD/ADX/…)."""
    if not trades:
        out = {
            "schema": "rule_based_v2",
            "base": {"n_trades": 0, "win_rate": 0.0},
            "by_session": [],
            "by_weekday": [],
            "by_hour": [],
            "rules": [],
            "notes": ["No trades to analyse."],
            "technical_context": None,
        }
        return out

    rows = []
    for t in trades:
        try:
            dt_raw = t.get("entry_time")
            if dt_raw is None:
                continue
            if isinstance(dt_raw, str):
                dt = datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
            elif isinstance(dt_raw, datetime):
                dt = dt_raw
            else:
                continue
            pnl = float(t.get("pnl", 0.0) or 0.0)
            pts = t.get("points")
            if pts is None:
                pts = pnl
            pts = float(pts or 0.0)
            win = 1 if pnl > 0 else 0
            rows.append(
                {
                    "hour": dt.hour,
                    "dow": dt.weekday(),
                    "session": _session_utc(dt.hour),
                    "win": win,
                    "pnl": pnl,
                    "points_gained": pts,
                }
            )
        except Exception:
            continue

    if not rows:
        return {
            "schema": "rule_based_v2",
            "base": {"n_trades": 0, "win_rate": 0.0},
            "by_session": [],
            "by_weekday": [],
            "by_hour": [],
            "rules": [],
            "notes": ["Could not parse entry times for insights."],
            "technical_context": None,
        }

    base_n = len(rows)
    base_wr = sum(r["win"] for r in rows) / base_n

    def _rollup(key_fn, buckets: List[str]) -> List[Dict[str, Any]]:
        out = []
        for b in buckets:
            sub = [r for r in rows if key_fn(r) == b]
            n = len(sub)
            if n == 0:
                out.append(
                    {
                        "bucket": b,
                        "trades": 0,
                        "win_rate": 0.0,
                        "improvement_vs_base": 0.0,
                        "avg_points": 0.0,
                        "retention_pct": 0.0,
                    }
                )
                continue
            wr = sum(r["win"] for r in sub) / n
            out.append(
                {
                    "bucket": b,
                    "trades": n,
                    "win_rate": round(wr * 100, 2),
                    "improvement_vs_base": round((wr - base_wr) * 100, 2),
                    "avg_points": round(float(np.mean([r["points_gained"] for r in sub])), 4),
                    "retention_pct": round(100.0 * n / base_n, 2),
                }
            )
        return out

    session_order = ["Asian", "London", "Overlap", "US"]
    by_session = _rollup(lambda r: r["session"], session_order)
    by_weekday = _rollup(lambda r: DAYS[r["dow"]], DAYS)

    by_hour = []
    for h in range(24):
        sub = [r for r in rows if r["hour"] == h]
        n = len(sub)
        if n == 0:
            by_hour.append(
                {
                    "hour": h,
                    "trades": 0,
                    "win_rate": 0.0,
                    "improvement_vs_base": 0.0,
                    "avg_points": 0.0,
                }
            )
            continue
        wr = sum(r["win"] for r in sub) / n
        by_hour.append(
            {
                "hour": h,
                "trades": n,
                "win_rate": round(wr * 100, 2),
                "improvement_vs_base": round((wr - base_wr) * 100, 2),
                "avg_points": round(float(np.mean([r["points_gained"] for r in sub])), 4),
            }
        )

    rules: List[str] = []
    notes: List[str] = []
    elig = [s for s in by_session if s["trades"] >= min_n]
    if elig:
        best = max(elig, key=lambda x: (x["win_rate"], x["trades"]))
        worst = min(elig, key=lambda x: (x["win_rate"], -x["trades"]))
        if best["bucket"] != worst["bucket"]:
            rules.append(
                f"Strongest session (UTC, n≥{min_n}): **{best['bucket']}** "
                f"({SESSION_HOURS_UTC.get(best['bucket'], '')}) "
                f"win-rate {best['win_rate']:.1f}% vs baseline {base_wr*100:.1f}%."
            )
            rules.append(
                f"Weakest session: **{worst['bucket']}** "
                f"win-rate {worst['win_rate']:.1f}% "
                f"(Δ {worst['improvement_vs_base']:+.1f} pts vs baseline)."
            )
        wd_elig = [d for d in by_weekday if d["trades"] >= min_n]
        if wd_elig:
            best_d = max(wd_elig, key=lambda x: x["win_rate"])
            rules.append(
                f"Best weekday (n≥{min_n}): **{best_d['bucket']}** "
                f"({best_d['win_rate']:.1f}% win-rate, {best_d['trades']} trades)."
            )
    else:
        notes.append(
            f"Not enough trades per session for strong conclusions "
            f"(need ≥{min_n} trades in a bucket)."
        )

    technical_context = None
    if ohlcv is not None:
        try:
            technical_context = compute_technical_rule_insights(trades, ohlcv)
        except Exception:
            technical_context = {"available": False, "reason": "technical insights failed"}

    return {
        "schema": "rule_based_v2",
        "timezone_note": "Sessions use entry_time interpreted as UTC (notebook convention).",
        "session_hours_utc": SESSION_HOURS_UTC,
        "base": {"n_trades": base_n, "win_rate": round(base_wr * 100, 2)},
        "by_session": by_session,
        "by_weekday": by_weekday,
        "by_hour": by_hour,
        "rules": rules,
        "notes": notes,
        "technical_context": technical_context,
    }
