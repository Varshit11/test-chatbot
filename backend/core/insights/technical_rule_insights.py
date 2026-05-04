"""
Momentum / trend / RSI-style rule buckets aligned with
`Optimization_Strategies/notebook/Renko/rule_based_analysis_intra/` scripts
(rsi_extreme, macd_momentum, adx_trend_strength, ema_alignment,
 stochastic_extreme, price_distance_ma, trend_vs_counter_trend).

Indicators are computed on the **same OHLCV** used for the backtest; each trade is
aligned to the **last bar at or before entry_time** via ``merge_asof``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..indicators.momentum import macd, rsi, stochastic
from ..indicators.trend import adx, ema, sma


def _parse_entry_time(dt_raw: Any) -> Optional[datetime]:
    if dt_raw is None:
        return None
    if isinstance(dt_raw, str):
        return datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
    if isinstance(dt_raw, datetime):
        return dt_raw
    if isinstance(dt_raw, pd.Timestamp):
        return dt_raw.to_pydatetime()
    return None


def _trade_side_long(t: Dict[str, Any]) -> Optional[bool]:
    s = (t.get("side") or "").lower()
    if s in ("long", "buy", "l"):
        return True
    if s in ("short", "sell", "s"):
        return False
    return None


def _build_feature_frame(ohlcv: pd.DataFrame) -> pd.DataFrame:
    df = ohlcv.copy()
    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
    if "datetime" not in df.columns and len(df.columns) > 0:
        c0 = df.columns[0]
        df = df.rename(columns={c0: "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"]).set_index("datetime").sort_index()
    for c in ("open", "high", "low", "close"):
        if c not in df.columns:
            raise ValueError(f"technical insights need column '{c}'")
    out = pd.DataFrame(index=df.index)
    out["close"] = df["close"].astype(float)
    out["rsi_14"] = rsi(df, 14)
    m = macd(df, 12, 26, 9)
    out["macd"] = m["macd"]
    out["macd_signal"] = m["signal"]
    out["macd_hist"] = m["hist"]
    ad = adx(df, 14)
    out["adx"] = ad["adx"]
    out["plus_di"] = ad["plus_di"]
    out["minus_di"] = ad["minus_di"]
    st = stochastic(df, 14, 3)
    out["stoch_k"] = st["k"]
    out["stoch_d"] = st["d"]
    for period in (8, 13, 21, 50, 200):
        out[f"ema_{period}"] = ema(df, period)
    for period in (21, 50):
        out[f"sma_{period}"] = sma(df, period)
    out["dist_ema_21"] = (df["close"] - out["ema_21"]) / df["close"].replace(0, np.nan)
    out["dist_ema_50"] = (df["close"] - out["ema_50"]) / df["close"].replace(0, np.nan)
    out["htf_bullish_ema200"] = (df["close"] > out["ema_200"]).astype(int)
    feat = out.reset_index()
    tc = feat.columns[0]
    feat = feat.rename(columns={tc: "bar_time"}).sort_values("bar_time")
    return feat


def _trades_dataframe(trades: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
    rows = []
    for t in trades:
        et = _parse_entry_time(t.get("entry_time"))
        if et is None:
            continue
        lng = _trade_side_long(t)
        if lng is None:
            continue
        pnl = float(t.get("pnl", 0.0) or 0.0)
        pts = t.get("points")
        if pts is None:
            pts = pnl
        pts = float(pts or 0.0)
        win = 1 if pnl > 0 else 0
        pos = "long" if lng else "short"
        rows.append(
            {
                "entry_time": pd.Timestamp(et),
                "position": pos,
                "win": win,
                "points_gained": pts,
            }
        )
    if not rows:
        return None
    return pd.DataFrame(rows).sort_values("entry_time")


def _merge_trades_features(
    trades_df: pd.DataFrame, feat_long: pd.DataFrame
) -> pd.DataFrame:
    left = trades_df.sort_values("entry_time").copy()
    right = feat_long.sort_values("bar_time").copy()
    merged = pd.merge_asof(
        left,
        right,
        left_on="entry_time",
        right_on="bar_time",
        direction="backward",
    )
    return merged.dropna(subset=["rsi_14", "macd", "adx"], how="any")


def _bucket_row(
    n: int,
    wins: float,
    base_wr: float,
    base_n: int,
) -> Dict[str, Any]:
    wr = wins / n if n else 0.0
    return {
        "trades": n,
        "win_rate_pct": round(wr * 100, 2),
        "improvement_vs_base_pct": round((wr - base_wr) * 100, 2),
        "retention_pct": round(100.0 * n / base_n, 2) if base_n else 0.0,
    }


def _rsi_extreme_grid(merged: pd.DataFrame, base_wr: float, base_n: int) -> List[Dict[str, Any]]:
    rsi_col = "rsi_14"
    out = []
    for threshold in (70, 75, 80, 85, 90, 95):
        oversold = 100 - threshold
        long_m = (merged["position"] == "long") & (merged[rsi_col] < oversold)
        short_m = (merged["position"] == "short") & (merged[rsi_col] > threshold)
        sub = merged[long_m | short_m]
        n = len(sub)
        wr = float(sub["win"].mean()) if n else 0.0
        row = {
            "rsi_short_ge": threshold,
            "rsi_long_lt": oversold,
            "label": f"short RSI≥{threshold} or long RSI<{oversold}",
            **_bucket_row(n, float(sub["win"].sum()) if n else 0, base_wr, base_n),
        }
        if n:
            row["combined_win_rate_pct"] = round(wr * 100, 2)
        out.append(row)
    return out


def _macd_tests(merged: pd.DataFrame, base_wr: float, base_n: int) -> List[Dict[str, Any]]:
    tests = []
    mdf = merged

    long_bull = mdf[(mdf["position"] == "long") & (mdf["macd"] > mdf["macd_signal"])]
    short_bear = mdf[(mdf["position"] == "short") & (mdf["macd"] < mdf["macd_signal"])]
    aligned = pd.concat([long_bull, short_bear])
    tests.append(
        {
            "name": "MACD direction aligned (long: line>signal, short: line<signal)",
            **_bucket_row(len(aligned), float(aligned["win"].sum()), base_wr, base_n),
        }
    )

    long_az = mdf[(mdf["position"] == "long") & (mdf["macd"] > 0)]
    short_bz = mdf[(mdf["position"] == "short") & (mdf["macd"] < 0)]
    zero_band = pd.concat([long_az, short_bz])
    tests.append(
        {
            "name": "MACD vs zero (long>0, short<0)",
            **_bucket_row(
                len(zero_band),
                float(zero_band["win"].sum()),
                base_wr,
                base_n,
            ),
        }
    )

    long_h = mdf[(mdf["position"] == "long") & (mdf["macd_hist"] > 0)]
    short_h = mdf[(mdf["position"] == "short") & (mdf["macd_hist"] < 0)]
    hist_band = pd.concat([long_h, short_h])
    tests.append(
        {
            "name": "MACD histogram (long>0, short<0)",
            **_bucket_row(
                len(hist_band),
                float(hist_band["win"].sum()),
                base_wr,
                base_n,
            ),
        }
    )
    return tests


def _adx_grid(merged: pd.DataFrame, base_wr: float, base_n: int) -> Dict[str, Any]:
    adx_col = "adx"
    by_threshold = []
    for threshold in (15, 20, 25, 30, 35, 40, 45, 50):
        sub = merged[merged[adx_col] > threshold]
        n = len(sub)
        by_threshold.append(
            {
                "adx_gt": threshold,
                **_bucket_row(n, float(sub["win"].sum()) if n else 0, base_wr, base_n),
            }
        )
    avoid_weak = []
    for threshold in (15, 20, 25):
        sub = merged[merged[adx_col] >= threshold]
        n = len(sub)
        avoid_weak.append(
            # notebook phrasing: avoid ADX < T → keep ADX >= T
            {"adx_gte": threshold, **_bucket_row(n, float(sub["win"].sum()) if n else 0, base_wr, base_n)}
        )

    plus, minus = "plus_di", "minus_di"
    long_bias = merged[
        (merged["position"] == "long")
        & (merged[plus] > merged[minus])
        & (merged[adx_col] > 25)
    ]
    short_bias = merged[
        (merged["position"] == "short")
        & (merged[plus] < merged[minus])
        & (merged[adx_col] > 25)
    ]
    directional = pd.concat([long_bias, short_bias])
    directional_block = {
        "long_plus_di_gt_minus_di_adx_gt_25": _bucket_row(
            len(long_bias), float(long_bias["win"].sum()), base_wr, base_n
        ),
        "short_plus_di_lt_minus_di_adx_gt_25": _bucket_row(
            len(short_bias), float(short_bias["win"].sum()), base_wr, base_n
        ),
        "combined_directional_aligned": _bucket_row(
            len(directional), float(directional["win"].sum()), base_wr, base_n
        ),
    }
    return {
        "adx_gt_thresholds": by_threshold,
        "adx_avoid_weak_buckets": avoid_weak,
        "directional_adx25": directional_block,
    }


def _stoch_grid(merged: pd.DataFrame, base_wr: float, base_n: int) -> List[Dict[str, Any]]:
    k, d = "stoch_k", "stoch_d"
    results = []
    for threshold in (10, 15, 20, 25, 30):
        overb = 100 - threshold
        long_m = (merged["position"] == "long") & (merged[k] < threshold) & (merged[d] < threshold)
        short_m = (merged["position"] == "short") & (merged[k] > overb) & (merged[d] > overb)
        sub = merged[long_m | short_m]
        n = len(sub)
        results.append(
            {
                "threshold_oversold_lt": threshold,
                "threshold_overbought_gt": overb,
                "label": f"long K&D<{threshold} or short K&D>{overb}",
                **_bucket_row(n, float(sub["win"].sum()) if n else 0, base_wr, base_n),
            }
        )
    return results


def _ema_alignment(merged: pd.DataFrame, base_wr: float, base_n: int) -> List[Dict[str, Any]]:
    m = merged
    tests = []
    e8, e13, e21, e50, e200 = "ema_8", "ema_13", "ema_21", "ema_50", "ema_200"

    bull = (m[e8] > m[e21]) & (m[e21] > m[e50])
    bear = (m[e8] < m[e21]) & (m[e21] < m[e50])
    t1 = m[(m["position"] == "long") & bull]
    t2 = m[(m["position"] == "short") & bear]
    t_all = pd.concat([t1, t2])
    tests.append(
        {
            "name": "EMA 8>21>50 (long) / 8<21<50 (short)",
            **_bucket_row(len(t_all), float(t_all["win"].sum()), base_wr, base_n),
        }
    )

    fbull = (m[e8] > m[e13]) & (m[e13] > m[e21])
    fbear = (m[e8] < m[e13]) & (m[e13] < m[e21])
    t1 = m[(m["position"] == "long") & fbull]
    t2 = m[(m["position"] == "short") & fbear]
    t_all = pd.concat([t1, t2])
    tests.append(
        {
            "name": "Fast stack 8>13>21 / 8<13<21",
            **_bucket_row(len(t_all), float(t_all["win"].sum()), base_wr, base_n),
        }
    )

    lbull = (m[e21] > m[e50]) & (m[e50] > m[e200])
    lbear = (m[e21] < m[e50]) & (m[e50] < m[e200])
    t1 = m[(m["position"] == "long") & lbull]
    t2 = m[(m["position"] == "short") & lbear]
    t_all = pd.concat([t1, t2])
    tests.append(
        {
            "name": "Slow stack 21>50>200 / inverse",
            **_bucket_row(len(t_all), float(t_all["win"].sum()), base_wr, base_n),
        }
    )

    t1 = m[(m["position"] == "long") & (m["close"] > m[e21])]
    t2 = m[(m["position"] == "short") & (m["close"] < m[e21])]
    t_all = pd.concat([t1, t2])
    tests.append(
        {
            "name": "Price vs EMA21 (long above / short below)",
            **_bucket_row(len(t_all), float(t_all["win"].sum()), base_wr, base_n),
        }
    )

    ctr_long = (m["position"] == "long") & bear
    ctr_short = (m["position"] == "short") & bull
    ct = pd.concat([m[ctr_long], m[ctr_short]])
    tests.append(
        {
            "name": "Counter-trend vs 8-21-50 stack",
            **_bucket_row(len(ct), float(ct["win"].sum()), base_wr, base_n),
        }
    )
    return tests


def _price_ma_distance(merged: pd.DataFrame, base_wr: float, base_n: int) -> List[Dict[str, Any]]:
    out = []
    for col, label in (("dist_ema_21", "EMA21 distance"), ("dist_ema_50", "EMA50 distance")):
        if col not in merged.columns:
            continue
        s = merged[col].dropna()
        if len(s) < 20:
            continue
        abs_med = float(merged[col].abs().median())
        near = merged[merged[col].abs() <= abs_med]
        far = merged[merged[col].abs() > abs_med]
        out.append(
            {
                "column": col,
                "label": f"{label} |close-ma|/close ≤ median",
                **_bucket_row(len(near), float(near["win"].sum()), base_wr, base_n),
            }
        )
        out.append(
            {
                "column": col,
                "label": f"{label} |close-ma|/close > median",
                **_bucket_row(len(far), float(far["win"].sum()), base_wr, base_n),
            }
        )
    return out


def _trend_vs_counter(merged: pd.DataFrame, base_wr: float, base_n: int) -> Dict[str, Any]:
    bull = merged["htf_bullish_ema200"] == 1
    with_trend = ((merged["position"] == "long") & bull) | ((merged["position"] == "short") & ~bull)
    against = ((merged["position"] == "long") & ~bull) | ((merged["position"] == "short") & bull)
    w = merged[with_trend]
    a = merged[against]
    return {
        "definition": "With trend = long when close>EMA200 else short; against = opposite",
        "with_trend": _bucket_row(len(w), float(w["win"].sum()), base_wr, base_n),
        "counter_trend": _bucket_row(len(a), float(a["win"].sum()), base_wr, base_n),
    }


def _session_filter_13_16_utc(merged: pd.DataFrame, base_wr: float, base_n: int) -> Dict[str, Any]:
    """Rough analogue to overlap / 1–4pm style session filters (UTC 13:00–16:59)."""
    h = merged["entry_time"].dt.hour
    sub = merged[(h >= 13) & (h <= 16)]
    return {
        "utc_hours_inclusive": "13–16",
        **_bucket_row(len(sub), float(sub["win"].sum()), base_wr, base_n),
    }


def _monthly_rollup(merged: pd.DataFrame) -> List[Dict[str, Any]]:
    merged = merged.copy()
    merged["ym"] = merged["entry_time"].dt.to_period("M").astype(str)
    rows = []
    for ym, grp in merged.groupby("ym"):
        n = len(grp)
        if n == 0:
            continue
        wr = grp["win"].mean()
        rows.append(
            {
                "month": ym,
                "trades": n,
                "win_rate_pct": round(float(wr) * 100, 2),
                "total_points": round(float(grp["points_gained"].sum()), 4),
            }
        )
    return sorted(rows, key=lambda x: x["month"])


def compute_technical_rule_insights(
    trades: List[Dict[str, Any]],
    ohlcv: pd.DataFrame,
    min_trades_for_highlight: int = 30,
) -> Optional[Dict[str, Any]]:
    """
    Run notebook-style technical bucketing when OHLCV is available.
    Returns None if alignment yields too few rows.
    """
    if ohlcv is None or len(ohlcv) < 60 or not trades:
        return None

    trades_df = _trades_dataframe(trades)
    if trades_df is None or trades_df.empty:
        return None

    try:
        feat = _build_feature_frame(ohlcv)
    except Exception:
        return None

    merged = _merge_trades_features(trades_df, feat)
    if merged.empty or len(merged) < 10:
        return {
            "available": False,
            "reason": "Too few trades after aligning to indicator bars (need warmup / valid OHLCV).",
        }

    base_n = len(merged)
    base_wr = float(merged["win"].mean())

    rsi_grid = _rsi_extreme_grid(merged, base_wr, base_n)
    best_rsi = None
    cand = [r for r in rsi_grid if r["trades"] >= min_trades_for_highlight]
    if cand:
        best_rsi = max(
            cand,
            key=lambda x: x.get("combined_win_rate_pct", x["win_rate_pct"]),
        )

    adx_block = _adx_grid(merged, base_wr, base_n)
    cand_adx = [r for r in adx_block["adx_gt_thresholds"] if r["trades"] >= min_trades_for_highlight]
    best_adx = max(cand_adx, key=lambda x: x["win_rate_pct"]) if cand_adx else None

    technical_rules: List[str] = []
    if best_rsi:
        technical_rules.append(
            f"RSI extreme combo (notebook grid): best sampled bucket **{best_rsi['label']}** "
            f"→ win-rate **{best_rsi.get('combined_win_rate_pct', best_rsi['win_rate_pct'])}%** "
            f"({best_rsi['trades']} trades)."
        )
    if best_adx:
        technical_rules.append(
            f"ADX > **{best_adx['adx_gt']}** → win-rate **{best_adx['win_rate_pct']}%** "
            f"({best_adx['trades']} trades vs base {base_wr*100:.1f}%)."
        )

    tv = _trend_vs_counter(merged, base_wr, base_n)
    if tv["with_trend"]["trades"] >= min_trades_for_highlight:
        technical_rules.append(
            f"EMA200 trend alignment: with-trend win-rate **{tv['with_trend']['win_rate_pct']}%** "
            f"vs counter-trend **{tv['counter_trend']['win_rate_pct']}%**."
        )

    return {
        "available": True,
        "reference": "Optimization_Strategies/notebook/Renko/rule_based_analysis_intra/",
        "aligned_trades": base_n,
        "baseline_win_rate_pct": round(base_wr * 100, 2),
        "rsi_extremes": {"grid": rsi_grid, "best_by_volume": best_rsi},
        "macd": {"tests": _macd_tests(merged, base_wr, base_n)},
        "adx": adx_block,
        "stochastic_extremes": {"grid": _stoch_grid(merged, base_wr, base_n)},
        "ema_alignment": {"tests": _ema_alignment(merged, base_wr, base_n)},
        "price_distance_ma": {"buckets": _price_ma_distance(merged, base_wr, base_n)},
        "trend_vs_counter_ema200": tv,
        "utc_session_13_16": _session_filter_13_16_utc(merged, base_wr, base_n),
        "by_month": _monthly_rollup(merged),
        "technical_rules": technical_rules,
    }
