"""Heikin Ashi candle calculation.

Mirrors the formula used in the existing strategies under
marketapi_data_fetcher/algo_methods/.../heikin_new/.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Heikin Ashi columns (ha_open, ha_high, ha_low, ha_close).

    HA Close = (O + H + L + C) / 4
    HA Open[0] = (O[0] + C[0]) / 2
    HA Open[i] = (HA Open[i-1] + HA Close[i-1]) / 2
    HA High = max(High, HA Open, HA Close)
    HA Low  = min(Low,  HA Open, HA Close)
    """
    out = df.copy()
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)

    ha_close = (o + h + l + c) / 4.0
    n = len(df)
    ha_open = np.empty(n)
    if n > 0:
        ha_open[0] = (o[0] + c[0]) / 2.0
        for i in range(1, n):
            ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0

    ha_high = np.maximum(np.maximum(h, ha_open), ha_close)
    ha_low = np.minimum(np.minimum(l, ha_open), ha_close)

    out["ha_open"] = ha_open
    out["ha_high"] = ha_high
    out["ha_low"] = ha_low
    out["ha_close"] = ha_close
    return out
