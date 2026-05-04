"""Session and hour-of-day breakdowns of a trade list.

We classify each trade's *entry time* into one of four FX sessions (UTC):
  - Asia    (00:00 – 07:00)
  - London  (07:00 – 12:00)
  - Overlap (12:00 – 16:00)   # London/NY overlap, usually highest liquidity
  - NY      (16:00 – 22:00)
  - OffHrs  (22:00 – 24:00)

Plus a per-hour and per-weekday rollup. All buckets return the same metric
shape so the UI can render them uniformly.
"""
from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime
import numpy as np


SESSIONS = [
    ("Asia",     0,  7),
    ("London",   7,  12),
    ("Overlap", 12,  16),
    ("NewYork", 16,  22),
    ("OffHrs",  22,  24),
]

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _classify_session(hour: int) -> str:
    for name, start, end in SESSIONS:
        if start <= hour < end:
            return name
    return "OffHrs"


def _bucket_metrics(pnls: List[float]) -> Dict[str, Any]:
    n = len(pnls)
    if n == 0:
        return {
            "n_trades": 0, "win_rate_pct": 0.0, "total_pnl": 0.0,
            "avg_trade": 0.0, "best_trade": 0.0, "worst_trade": 0.0,
            "profit_factor": 0.0, "expectancy": 0.0,
        }
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gp = float(sum(wins))
    gl = float(abs(sum(losses)))
    pf = (gp / gl) if gl > 0 else (999.0 if gp > 0 else 0.0)
    return {
        "n_trades": n,
        "win_rate_pct": round(len(wins) / n * 100, 2),
        "total_pnl": round(float(sum(pnls)), 2),
        "avg_trade": round(float(np.mean(pnls)), 2),
        "best_trade": round(float(max(pnls)), 2),
        "worst_trade": round(float(min(pnls)), 2),
        "profit_factor": round(pf, 2),
        "expectancy": round(float(np.mean(pnls)), 2),
    }


def session_breakdown(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Group trades by FX session, hour and weekday and return metrics for each
    bucket. Hour and weekday are based on the trade *entry_time*."""
    if not trades:
        return {"by_session": [], "by_hour": [], "by_weekday": []}

    sess_buckets: Dict[str, List[float]] = {n: [] for n, _, _ in SESSIONS}
    hour_buckets: Dict[int, List[float]] = {h: [] for h in range(24)}
    wd_buckets: Dict[str, List[float]] = {d: [] for d in WEEKDAYS}

    for t in trades:
        try:
            dt = t.get("entry_time")
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            elif not isinstance(dt, datetime):
                continue
            hour = dt.hour
            wd = WEEKDAYS[dt.weekday()] if 0 <= dt.weekday() < 7 else "Mon"
            session = _classify_session(hour)
            pnl = float(t.get("pnl", 0.0))
            sess_buckets[session].append(pnl)
            hour_buckets[hour].append(pnl)
            wd_buckets[wd].append(pnl)
        except Exception:
            continue

    by_session = [
        {"session": name, **_bucket_metrics(sess_buckets[name])}
        for name, _, _ in SESSIONS
    ]
    by_hour = [
        {"hour": h, **_bucket_metrics(hour_buckets[h])}
        for h in range(24)
    ]
    by_weekday = [
        {"weekday": d, **_bucket_metrics(wd_buckets[d])}
        for d in WEEKDAYS
    ]
    return {"by_session": by_session, "by_hour": by_hour, "by_weekday": by_weekday}
