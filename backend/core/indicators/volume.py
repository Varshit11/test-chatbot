"""Volume indicators."""
from __future__ import annotations
import numpy as np
import pandas as pd


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume-weighted average price (cumulative within session/day)."""
    if "volume" not in df.columns:
        raise ValueError("VWAP requires a 'volume' column.")
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical * df["volume"]
    cum_pv = pv.groupby(df.index.date).cumsum() if hasattr(df.index, "date") else pv.cumsum()
    cum_v = df["volume"].groupby(df.index.date).cumsum() if hasattr(df.index, "date") else df["volume"].cumsum()
    out = cum_pv / cum_v.replace(0, np.nan)
    return out.rename("vwap")


def obv(df: pd.DataFrame) -> pd.Series:
    if "volume" not in df.columns:
        raise ValueError("OBV requires a 'volume' column.")
    direction = np.sign(df["close"].diff().fillna(0))
    return (direction * df["volume"]).cumsum().rename("obv")
