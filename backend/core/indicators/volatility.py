"""Volatility indicators."""
from __future__ import annotations
import pandas as pd
from .trend import _true_range, ema as _ema  # type: ignore  (private util re-use)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = _true_range(df)
    return tr.ewm(alpha=1 / period, adjust=False).mean().rename(f"atr_{period}")


def bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0,
                    source: str = "close") -> pd.DataFrame:
    mid = df[source].rolling(period).mean()
    sd = df[source].rolling(period).std()
    upper = mid + std * sd
    lower = mid - std * sd
    width = (upper - lower) / mid
    return pd.DataFrame(
        {"middle": mid, "upper": upper, "lower": lower, "width": width},
        index=df.index,
    )


def keltner_channel(df: pd.DataFrame, period: int = 20, multiplier: float = 2.0) -> pd.DataFrame:
    mid = df["close"].ewm(span=period, adjust=False).mean()
    a = atr(df, period)
    upper = mid + multiplier * a
    lower = mid - multiplier * a
    return pd.DataFrame(
        {"middle": mid, "upper": upper, "lower": lower},
        index=df.index,
    )
