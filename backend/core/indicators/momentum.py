"""Momentum indicators."""
from __future__ import annotations
import numpy as np
import pandas as pd


def rsi(df: pd.DataFrame, period: int = 14, source: str = "close") -> pd.Series:
    delta = df[source].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.rename(f"rsi_{period}")


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9,
         source: str = "close") -> pd.DataFrame:
    ema_fast = df[source].ewm(span=fast, adjust=False).mean()
    ema_slow = df[source].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist},
        index=df.index,
    )


def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return pd.DataFrame({"k": k, "d": d}, index=df.index)


def roc(df: pd.DataFrame, period: int = 12, source: str = "close") -> pd.Series:
    out = (df[source] / df[source].shift(period) - 1) * 100
    return out.rename(f"roc_{period}")
