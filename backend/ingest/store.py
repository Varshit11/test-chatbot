"""Canonical Parquet store for OHLCV bars.

Layout:
    data/ohlcv/{SYMBOL}/{tf}.parquet   # tz-naive UTC DatetimeIndex; cols open/high/low/close/volume

The store is **the source of truth** for backtest + AI-Filter. The legacy CSVs
in ``marketapi_data_fetcher/algo_methods/.../heikin_new/*.csv`` are still used
by the chatbot loader as a fallback, but new data lands here.

Why per-(symbol, timeframe) parquet (instead of a DB):
- Single laptop / Render box. No infra burden.
- Pandas reads are millisecond-fast on <500 MB files.
- Easy to ship to S3 later — the same files work on object storage.
- Production migration target is TimescaleDB (Postgres extension) or DuckDB on
  S3; both can ingest these parquets directly.

Concurrency note:
- Append is read-modify-write under a per-file ``.lock`` sentinel. The ingest
  runner is the *only* writer; the chatbot is read-only. If you ever run two
  writers, switch to DuckDB / Timescale — that's the point at which we outgrow
  this module.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

logger = logging.getLogger(__name__)


_BACKEND_ROOT = Path(__file__).resolve().parents[1]
OHLCV_DIR = _BACKEND_ROOT / "data" / "ohlcv"

CANONICAL_COLS = ("open", "high", "low", "close", "volume")


def base_parquet_path(symbol: str) -> Path:
    """1-minute base file. The fetcher writes here; resamplers read from here."""
    return OHLCV_DIR / symbol.upper() / "1m.parquet"


def tf_parquet_path(symbol: str, timeframe: str) -> Path:
    return OHLCV_DIR / symbol.upper() / f"{timeframe.lower()}.parquet"


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def _file_lock(path: Path, *, timeout: float = 30.0, poll: float = 0.1):
    """Crude per-file mutex via a lock sentinel file. Sufficient for our writer."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    _ensure_dir(lock_path)
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.time() > deadline:
                raise TimeoutError(f"Lock timeout on {lock_path}")
            time.sleep(poll)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DatetimeIndex (tz-naive UTC), required cols, dtype float, deduped, sorted."""
    if df is None or df.empty:
        return pd.DataFrame(columns=list(CANONICAL_COLS))

    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        if "datetime" in out.columns:
            out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")
            out = out.dropna(subset=["datetime"]).set_index("datetime")
        elif "timestamp" in out.columns:
            out["datetime"] = pd.to_datetime(out["timestamp"], unit="s", errors="coerce")
            out = out.dropna(subset=["datetime"]).set_index("datetime")
        else:
            raise ValueError("DataFrame needs DatetimeIndex or 'datetime'/'timestamp' column.")

    if out.index.tz is not None:
        out.index = out.index.tz_convert("UTC").tz_localize(None)

    out.columns = [c.lower() for c in out.columns]
    for col in CANONICAL_COLS:
        if col not in out.columns:
            if col == "volume":
                out[col] = 0.0
            else:
                raise ValueError(f"OHLCV missing column '{col}'")
    out = out[list(CANONICAL_COLS)].astype(float)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def read_ohlcv(
    symbol: str,
    timeframe: str = "1m",
    from_ts: Optional[pd.Timestamp] = None,
    to_ts: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """Read the canonical parquet for ``(symbol, timeframe)``. Empty frame if missing."""
    path = tf_parquet_path(symbol, timeframe)
    if not path.is_file():
        return pd.DataFrame(columns=list(CANONICAL_COLS))
    df = pd.read_parquet(path)
    df = _normalize(df)
    if from_ts is not None:
        df = df.loc[pd.Timestamp(from_ts):]
    if to_ts is not None:
        df = df.loc[: pd.Timestamp(to_ts)]
    return df


def write_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str = "1m") -> Path:
    """Atomic full-file write. Use for backfill / overwrites."""
    out = _normalize(df)
    path = tf_parquet_path(symbol, timeframe)
    _ensure_dir(path)
    with _file_lock(path):
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".parquet", dir=path.parent, delete=False
        ) as tf:
            tmp_path = Path(tf.name)
        out.to_parquet(tmp_path, index=True)
        os.replace(tmp_path, path)
    logger.info("ohlcv wrote %s rows → %s", len(out), path)
    return path


def upsert_ohlcv(df: pd.DataFrame, symbol: str, timeframe: str = "1m") -> Path:
    """Read-modify-write merge: existing rows preserved, new rows appended,
    overlapping timestamps overwritten by the *new* values (last fetch wins,
    so partial-bar corrections from the API land cleanly).
    """
    new = _normalize(df)
    path = tf_parquet_path(symbol, timeframe)
    _ensure_dir(path)
    with _file_lock(path):
        if path.is_file():
            try:
                existing = _normalize(pd.read_parquet(path))
            except Exception as e:
                logger.warning("Corrupt parquet at %s (%s) — overwriting", path, e)
                existing = pd.DataFrame(columns=list(CANONICAL_COLS))
            merged = pd.concat([existing, new])
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        else:
            merged = new
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".parquet", dir=path.parent, delete=False
        ) as tmp:
            tmp_path = Path(tmp.name)
        merged.to_parquet(tmp_path, index=True)
        os.replace(tmp_path, path)
    logger.info("ohlcv upsert %s/%s: +%s new, total %s → %s",
                symbol, timeframe, len(new), len(merged), path.name)
    return path


def latest_ts(symbol: str, timeframe: str = "1m") -> Optional[pd.Timestamp]:
    """Most recent timestamp on disk, or ``None`` if the file is missing/empty."""
    df = read_ohlcv(symbol, timeframe)
    if df.empty:
        return None
    return df.index[-1]


def list_symbols() -> Iterable[str]:
    if not OHLCV_DIR.is_dir():
        return []
    return [p.name for p in OHLCV_DIR.iterdir() if p.is_dir()]
