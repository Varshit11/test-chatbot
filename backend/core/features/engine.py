"""Feature engineering for the AI Filter.

Inspired by the user's existing notebooks:
  - Optimization_Strategies/Technical Indicators/smc_ict_features_without_future_bars.py
  - Optimization_Strategies/notebook/Renko/Intra Strategy Improvement with only
    Technical and Multi Timeframe features.ipynb

Goals:
  * Produce a SINGLE DataFrame indexed identically to the input OHLCV with a
    rich set of contextual features at every bar (technicals + lag/roll +
    light SMC). NO LOOK-AHEAD: every feature at row i uses only rows ≤ i.
  * Stay fast enough to run inline in the chatbot (~tens of ms per 1000 bars).

These features are then aligned with the strategy's *trade entries* in
ai_filter.filter to build (X, y) for LightGBM training.
"""
from __future__ import annotations
from typing import Dict, List
import numpy as np
import pandas as pd

from ..indicators.trend import ema, sma, adx, supertrend
from ..indicators.momentum import rsi, macd, stochastic
from ..indicators.volatility import atr, bollinger_bands
from ..patterns.heikin_ashi import calculate_heikin_ashi


# Categories of features so the UI can group them sensibly.
FEATURE_CATEGORIES = {
    "Trend":       ["ema_8", "ema_21", "ema_50", "ema_200", "sma_20", "sma_50",
                    "ema_8_21_diff_pct", "ema_21_50_diff_pct", "ema_50_200_diff_pct",
                    "above_ema_50", "above_ema_200", "ma_bullish_alignment",
                    "ma_bearish_alignment", "supertrend_dir"],
    "Momentum":    ["rsi_14", "rsi_7", "rsi_21",
                    "macd_line", "macd_signal", "macd_hist", "macd_hist_pos",
                    "stoch_k", "stoch_d",
                    "ret_1", "ret_3", "ret_5", "ret_10", "ret_20",
                    "price_velocity_2", "price_change_4"],
    "Volatility":  ["atr_14", "atr_pct", "bb_upper", "bb_lower", "bb_pos",
                    "bb_width_pct", "true_range", "range_pct"],
    "Volume":      ["volume", "volume_sma_20", "volume_ratio_20",
                    "volume_momentum_4", "is_high_volume"],
    "Candle":      ["body_pct", "upper_wick_pct", "lower_wick_pct",
                    "is_bullish_candle", "is_bearish_candle", "is_doji"],
    "ADX/Trend":   ["adx_14", "plus_di", "minus_di",
                    "di_diff", "trend_strength"],
    "Heikin Ashi": ["ha_bull", "ha_bear", "ha_streak"],
    "Time":        ["hour", "weekday", "session_asia", "session_london",
                    "session_overlap", "session_ny"],
    "SMC (light)": ["is_pivot_high", "is_pivot_low", "is_hh", "is_hl",
                    "is_lh", "is_ll", "is_fvg_bull", "is_fvg_bear",
                    "is_sweep_bull", "is_sweep_bear", "market_structure",
                    "smc_activity_5", "smc_activity_10"],
}

ALL_FEATURE_NAMES: List[str] = sum(FEATURE_CATEGORIES.values(), [])


def _safe(s: pd.Series) -> pd.Series:
    return s.replace([np.inf, -np.inf], np.nan)


def _detect_pivot_points(df: pd.DataFrame, swing: int = 5) -> pd.DataFrame:
    """Pivot-high / pivot-low with `swing` confirmation bars on each side. Signal
    is published at the confirmation bar (i.e. swing bars after the pivot) so
    there's no look-ahead."""
    h = df["high"].values
    l = df["low"].values
    n = len(df)
    is_ph = np.zeros(n, dtype=np.int8)
    is_pl = np.zeros(n, dtype=np.int8)
    for i in range(swing, n - swing):
        win_h = h[i - swing:i + swing + 1]
        win_l = l[i - swing:i + swing + 1]
        if h[i] == win_h.max() and (win_h == h[i]).sum() == 1:
            is_ph[min(i + swing, n - 1)] = 1
        if l[i] == win_l.min() and (win_l == l[i]).sum() == 1:
            is_pl[min(i + swing, n - 1)] = 1
    df["is_pivot_high"] = is_ph
    df["is_pivot_low"] = is_pl
    return df


def _light_smc(df: pd.DataFrame) -> pd.DataFrame:
    """Lightweight version of EnhancedSMCFeatures — only the features that are
    cheap and stable enough for inline use. ~10 SMC columns."""
    df = _detect_pivot_points(df, swing=5)
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    n = len(df)

    # Higher-high / higher-low / lower-high / lower-low flagged at each pivot.
    is_hh = np.zeros(n, dtype=np.int8)
    is_hl = np.zeros(n, dtype=np.int8)
    is_lh = np.zeros(n, dtype=np.int8)
    is_ll = np.zeros(n, dtype=np.int8)
    last_ph = None
    last_pl = None
    for i in range(n):
        if df["is_pivot_high"].iat[i]:
            if last_ph is not None:
                if h[i] > h[last_ph]:
                    is_hh[i] = 1
                else:
                    is_lh[i] = 1
            last_ph = i
        if df["is_pivot_low"].iat[i]:
            if last_pl is not None:
                if l[i] > l[last_pl]:
                    is_hl[i] = 1
                else:
                    is_ll[i] = 1
            last_pl = i
    df["is_hh"] = is_hh
    df["is_hl"] = is_hl
    df["is_lh"] = is_lh
    df["is_ll"] = is_ll

    # Fair Value Gaps — bullish / bearish. Compares bar i-2 to bar i (3-bar gap).
    fvg_bull = np.zeros(n, dtype=np.int8)
    fvg_bear = np.zeros(n, dtype=np.int8)
    for i in range(2, n):
        if h[i - 2] < l[i]:
            fvg_bull[i] = 1
        if l[i - 2] > h[i]:
            fvg_bear[i] = 1
    df["is_fvg_bull"] = fvg_bull
    df["is_fvg_bear"] = fvg_bear

    # Liquidity sweeps using recent pivots (last 30 bars).
    sweep_bull = np.zeros(n, dtype=np.int8)
    sweep_bear = np.zeros(n, dtype=np.int8)
    for i in range(30, n):
        recent_ph = np.where(df["is_pivot_high"].iloc[i - 30:i].values == 1)[0]
        recent_pl = np.where(df["is_pivot_low"].iloc[i - 30:i].values == 1)[0]
        if len(recent_ph):
            ph_idx = i - 30 + recent_ph[-1]
            if h[i] > h[ph_idx] and c[i] < h[ph_idx]:
                sweep_bear[i] = 1
        if len(recent_pl):
            pl_idx = i - 30 + recent_pl[-1]
            if l[i] < l[pl_idx] and c[i] > l[pl_idx]:
                sweep_bull[i] = 1
    df["is_sweep_bull"] = sweep_bull
    df["is_sweep_bear"] = sweep_bear

    # Simple market structure: 1 if any HH or HL in the last 20 bars dominates,
    # else 0. This avoids the heavier CHoCH/BOS logic.
    bull_score = (df["is_hh"].rolling(20, min_periods=1).sum() +
                  df["is_hl"].rolling(20, min_periods=1).sum())
    bear_score = (df["is_lh"].rolling(20, min_periods=1).sum() +
                  df["is_ll"].rolling(20, min_periods=1).sum())
    df["market_structure"] = (bull_score > bear_score).astype(np.int8)

    df["smc_activity_5"] = (
        df["is_pivot_high"].rolling(5).sum().fillna(0) +
        df["is_pivot_low"].rolling(5).sum().fillna(0) +
        df["is_fvg_bull"].rolling(5).sum().fillna(0) +
        df["is_fvg_bear"].rolling(5).sum().fillna(0)
    ).astype(np.int8)
    df["smc_activity_10"] = (
        df["is_pivot_high"].rolling(10).sum().fillna(0) +
        df["is_pivot_low"].rolling(10).sum().fillna(0) +
        df["is_fvg_bull"].rolling(10).sum().fillna(0) +
        df["is_fvg_bear"].rolling(10).sum().fillna(0)
    ).astype(np.int8)
    return df


def compute_features(df: pd.DataFrame, *, include_smc: bool = True) -> pd.DataFrame:
    """Compute the full feature set on `df`. Returns a NEW DataFrame indexed
    identically to `df`. Always uses past-only data."""
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        if "datetime" in out.columns:
            out["datetime"] = pd.to_datetime(out["datetime"])
            out = out.set_index("datetime")
    out = out.sort_index()

    c = out["close"]
    h = out["high"]
    l = out["low"]

    # Trend
    e8 = ema(out, 8); e21 = ema(out, 21); e50 = ema(out, 50); e200 = ema(out, 200)
    out["ema_8"] = e8
    out["ema_21"] = e21
    out["ema_50"] = e50
    out["ema_200"] = e200
    out["sma_20"] = sma(out, 20)
    out["sma_50"] = sma(out, 50)
    out["ema_8_21_diff_pct"] = _safe((e8 - e21) / c)
    out["ema_21_50_diff_pct"] = _safe((e21 - e50) / c)
    out["ema_50_200_diff_pct"] = _safe((e50 - e200) / c)
    out["above_ema_50"] = (c > e50).astype(np.int8)
    out["above_ema_200"] = (c > e200).astype(np.int8)
    out["ma_bullish_alignment"] = (
        (e8 > e21) & (e21 > e50) & (e50 > e200)
    ).astype(np.int8)
    out["ma_bearish_alignment"] = (
        (e8 < e21) & (e21 < e50) & (e50 < e200)
    ).astype(np.int8)
    try:
        st = supertrend(out, 10, 3.0)
        out["supertrend_dir"] = st.get("direction", pd.Series(0, index=out.index)).fillna(0).astype(np.int8)
    except Exception:
        out["supertrend_dir"] = 0

    # Momentum
    out["rsi_14"] = rsi(out, 14)
    out["rsi_7"] = rsi(out, 7)
    out["rsi_21"] = rsi(out, 21)
    md = macd(out, 12, 26, 9)
    out["macd_line"] = md["macd"]
    out["macd_signal"] = md["signal"]
    out["macd_hist"] = md["hist"]
    out["macd_hist_pos"] = (md["hist"] > 0).astype(np.int8)
    try:
        st_osc = stochastic(out, 14, 3)
        out["stoch_k"] = st_osc["k"]
        out["stoch_d"] = st_osc["d"]
    except Exception:
        out["stoch_k"] = 50.0
        out["stoch_d"] = 50.0
    for n in (1, 3, 5, 10, 20):
        out[f"ret_{n}"] = c.pct_change(n)
    out["price_velocity_2"] = c.pct_change(2)
    out["price_change_4"] = c.pct_change(4)

    # Volatility
    a14 = atr(out, 14)
    out["atr_14"] = a14
    out["atr_pct"] = _safe(a14 / c)
    bb = bollinger_bands(out, 20, 2.0)
    out["bb_upper"] = bb["upper"]
    out["bb_lower"] = bb["lower"]
    width = (bb["upper"] - bb["lower"]).replace(0, np.nan)
    out["bb_pos"] = _safe((c - bb["lower"]) / width)
    out["bb_width_pct"] = _safe(width / c)
    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    out["true_range"] = tr
    out["range_pct"] = _safe((h - l) / c)

    # Volume
    if "volume" not in out.columns:
        out["volume"] = 0.0
    out["volume_sma_20"] = out["volume"].rolling(20, min_periods=1).mean()
    out["volume_ratio_20"] = _safe(out["volume"] / out["volume_sma_20"].replace(0, np.nan))
    out["volume_momentum_4"] = out["volume"].pct_change(4)
    out["is_high_volume"] = (out["volume"] > out["volume_sma_20"] * 1.5).astype(np.int8)

    # Candle anatomy
    rng = (h - l).replace(0, np.nan)
    body = (c - out["open"]).abs()
    upper = h - out[["open", "close"]].max(axis=1)
    lower = out[["open", "close"]].min(axis=1) - l
    out["body_pct"] = _safe(body / rng)
    out["upper_wick_pct"] = _safe(upper / rng)
    out["lower_wick_pct"] = _safe(lower / rng)
    out["is_bullish_candle"] = (c > out["open"]).astype(np.int8)
    out["is_bearish_candle"] = (c < out["open"]).astype(np.int8)
    out["is_doji"] = (body / rng < 0.1).fillna(False).astype(np.int8)

    # ADX / DI
    try:
        ax = adx(out, 14)
        out["adx_14"] = ax["adx"]
        out["plus_di"] = ax["plus_di"]
        out["minus_di"] = ax["minus_di"]
        out["di_diff"] = ax["plus_di"] - ax["minus_di"]
    except Exception:
        out["adx_14"] = 0
        out["plus_di"] = 0
        out["minus_di"] = 0
        out["di_diff"] = 0
    out["trend_strength"] = (out["adx_14"] / 50.0).clip(0, 2)

    # Heikin Ashi cues
    try:
        ha = calculate_heikin_ashi(out)
        ha_bull = (ha["ha_close"] > ha["ha_open"]).astype(np.int8)
        out["ha_bull"] = ha_bull
        out["ha_bear"] = (ha["ha_close"] < ha["ha_open"]).astype(np.int8)
        # streak: number of consecutive bull/bear HA candles up to & including this bar
        streak = (ha_bull.diff().ne(0)).cumsum()
        out["ha_streak"] = ha_bull.groupby(streak).cumcount() + 1
    except Exception:
        out["ha_bull"] = 0
        out["ha_bear"] = 0
        out["ha_streak"] = 0

    # Time / session — assume index is UTC.
    out["hour"] = out.index.hour
    out["weekday"] = out.index.weekday
    out["session_asia"] = ((out.index.hour >= 0) & (out.index.hour < 7)).astype(np.int8)
    out["session_london"] = ((out.index.hour >= 7) & (out.index.hour < 12)).astype(np.int8)
    out["session_overlap"] = ((out.index.hour >= 12) & (out.index.hour < 16)).astype(np.int8)
    out["session_ny"] = ((out.index.hour >= 16) & (out.index.hour < 22)).astype(np.int8)

    # SMC (light) — adds 11 columns
    if include_smc:
        out = _light_smc(out)
    else:
        for col in FEATURE_CATEGORIES["SMC (light)"]:
            out[col] = 0

    # Final sanity pass
    feats = [c for c in ALL_FEATURE_NAMES if c in out.columns]
    out[feats] = (
        out[feats]
        .replace([np.inf, -np.inf], np.nan)
        .ffill()
        .fillna(0.0)
    )
    return out


def feature_categories() -> Dict[str, List[str]]:
    return {k: list(v) for k, v in FEATURE_CATEGORIES.items()}
