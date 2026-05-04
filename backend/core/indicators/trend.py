"""Trend indicators."""
from __future__ import annotations
import numpy as np
import pandas as pd


def ema(df: pd.DataFrame, period: int = 20, source: str = "close") -> pd.Series:
    return df[source].ewm(span=period, adjust=False).mean().rename(f"ema_{period}")


def sma(df: pd.DataFrame, period: int = 20, source: str = "close") -> pd.Series:
    return df[source].rolling(period).mean().rename(f"sma_{period}")


def wma(df: pd.DataFrame, period: int = 20, source: str = "close") -> pd.Series:
    weights = np.arange(1, period + 1)
    out = df[source].rolling(period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )
    return out.rename(f"wma_{period}")


def _true_range(df: pd.DataFrame) -> pd.Series:
    h_l = df["high"] - df["low"]
    h_pc = (df["high"] - df["close"].shift()).abs()
    l_pc = (df["low"] - df["close"].shift()).abs()
    return pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    Returns a DataFrame with columns: supertrend, direction (1=up, -1=down).
    """
    hl2 = (df["high"] + df["low"]) / 2.0
    tr = _true_range(df)
    atr_val = tr.ewm(alpha=1 / period, adjust=False).mean()

    upper = hl2 + multiplier * atr_val
    lower = hl2 - multiplier * atr_val

    n = len(df)
    final_upper = upper.copy().to_numpy()
    final_lower = lower.copy().to_numpy()
    close = df["close"].to_numpy()

    for i in range(1, n):
        if upper.iloc[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            pass
        else:
            final_upper[i] = final_upper[i - 1]

        if lower.iloc[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            pass
        else:
            final_lower[i] = final_lower[i - 1]

    direction = np.ones(n, dtype=int)
    st = np.full(n, np.nan)
    for i in range(1, n):
        if close[i] > final_upper[i - 1]:
            direction[i] = 1
        elif close[i] < final_lower[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]
        st[i] = final_lower[i] if direction[i] == 1 else final_upper[i]

    return pd.DataFrame(
        {"supertrend": st, "direction": direction},
        index=df.index,
    )


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Returns DataFrame with columns: adx, plus_di, minus_di.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    up = high.diff()
    dn = -low.diff()
    plus_dm = ((up > dn) & (up > 0)).astype(float) * up
    minus_dm = ((dn > up) & (dn > 0)).astype(float) * dn

    tr = _true_range(df)
    atr_ = tr.ewm(alpha=1 / period, adjust=False).mean()

    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_.replace(0, np.nan))

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1 / period, adjust=False).mean()

    return pd.DataFrame(
        {"adx": adx_val, "plus_di": plus_di, "minus_di": minus_di},
        index=df.index,
    )
