"""Resample 1-minute bars into the higher timeframes the chatbot serves.

Right boundary is the standard pandas convention (label at the start of the
window). All higher timeframes are derived from the canonical 1m parquet so
they are always consistent with each other.
"""
from __future__ import annotations

import logging
from typing import Sequence

import pandas as pd

logger = logging.getLogger(__name__)


HIGHER_TFS: Sequence[str] = ("5m", "10m", "15m", "30m", "1h", "4h", "1d")


_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


_PANDAS_RULE = {
    "5m": "5min",
    "10m": "10min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}


def resample(df_1m: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Aggregate 1-minute OHLCV to the requested higher timeframe."""
    if df_1m is None or df_1m.empty:
        return df_1m
    rule = _PANDAS_RULE.get(timeframe)
    if rule is None:
        raise ValueError(f"resample doesn't know timeframe {timeframe!r}")
    agg = df_1m.resample(rule, label="left", closed="left").agg(_AGG)
    return agg.dropna(subset=["open", "high", "low", "close"])
