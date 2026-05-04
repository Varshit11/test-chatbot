"""OHLCV loader.

Source-of-truth precedence:
    1. **Canonical Parquet store** at ``data/ohlcv/{SYMBOL}/{tf}.parquet`` —
       written by ``backend.ingest.runner``. This is what production reads.
    2. **Legacy CSV** registered in ``instruments.py`` — kept as a fallback so
       the chatbot still works on a fresh checkout that hasn't run an ingest yet.

The parquet path is checked first; when it's present and non-empty, the CSV is
ignored entirely. This is the only place in the codebase that knows about both
sources.
"""
from __future__ import annotations
import logging
import os
from typing import Optional, List, Dict, Any
import pandas as pd

from .instruments import INSTRUMENTS, canonical_timeframe, get_instrument, list_instruments
from ..ingest.store import tf_parquet_path, read_ohlcv as read_parquet_ohlcv

logger = logging.getLogger(__name__)


def _load_from_parquet(symbol: str, timeframe: str) -> pd.DataFrame:
    pq = tf_parquet_path(symbol.upper(), timeframe.lower())
    if not pq.is_file():
        return pd.DataFrame()
    try:
        df = read_parquet_ohlcv(symbol.upper(), timeframe.lower())
        return df
    except Exception as e:
        logger.warning("Parquet read failed for %s %s (%s) — falling back to CSV", symbol, timeframe, e)
        return pd.DataFrame()


def _load_from_csv(symbol: str, timeframe: str) -> pd.DataFrame:
    inst = get_instrument(symbol)
    data_files = inst.get("data_files") or {}
    tf_key = canonical_timeframe(timeframe)
    if tf_key not in data_files and timeframe in data_files:
        tf_key = timeframe
    if tf_key not in data_files:
        raise ValueError(
            f"No data for {symbol} {timeframe}. "
            f"Run `python -m backend.ingest.runner --backfill 30 --symbol {symbol}` "
            f"or register a CSV in instruments.py. "
            f"Available CSV TFs: {list(data_files.keys())}"
        )

    path = data_files[tf_key]
    if not os.path.exists(path):
        raise FileNotFoundError(f"Data file not found: {path}")

    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "datetime" not in df.columns:
        if "timestamp" in df.columns:
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")
        else:
            raise ValueError(f"CSV {path} missing datetime/timestamp column.")
    else:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    df = df.set_index("datetime")

    needed = ["open", "high", "low", "close"]
    for col in needed:
        if col not in df.columns:
            raise ValueError(f"CSV {path} missing column '{col}'.")
    if "volume" not in df.columns:
        df["volume"] = 0
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def load_bars_only(
    symbol: str,
    timeframe: str = "5m",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Load OHLCV. Prefers the canonical parquet store; falls back to CSV.

    Index: tz-naive UTC ``DatetimeIndex``; columns: open, high, low, close, volume.

    ``limit`` truncates from the *tail* and is mainly here for the AI Filter's
    "last N bars" query — backtests should pass ``date_range`` instead.
    """
    df = _load_from_parquet(symbol, timeframe)
    if df.empty:
        df = _load_from_csv(symbol, timeframe)

    if from_date:
        df = df.loc[pd.to_datetime(from_date):]
    if to_date:
        df = df.loc[: pd.to_datetime(to_date)]
    if limit is not None and limit > 0:
        df = df.tail(int(limit))
    return df


def apply_chart(df: pd.DataFrame, chart: Optional[Dict[str, Any]]) -> pd.DataFrame:
    """Optional post-process: Renko bricks from time bars (same engine as enterprise Renko code)."""
    if df is None or len(df) == 0 or not chart:
        return df
    ctype = (chart.get("type") or "").lower().strip()
    if ctype != "renko":
        return df
    from ..core.chart.renko_bricks import ohlcv_to_renko_df

    mode = chart.get("mode") or "wicks"
    brick = chart.get("brick_size")
    try:
        brick_f = float(brick) if brick is not None else None
    except (TypeError, ValueError):
        brick_f = None
    if brick_f is not None and brick_f <= 0:
        brick_f = None
    return ohlcv_to_renko_df(df, brick_size=brick_f, mode=str(mode))


def load_ohlcv(
    symbol: str,
    timeframe: str = "5m",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: Optional[int] = None,
    chart: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Load OHLCV (parquet → CSV fallback) with optional Renko transform."""
    df = load_bars_only(symbol, timeframe, from_date=from_date, to_date=to_date, limit=limit)
    return apply_chart(df, chart)


def list_available_instruments() -> List[Dict[str, Any]]:
    return list_instruments()
