"""Live ingest pipeline.

Pulls 1-minute OHLCV from Finnhub, persists to a canonical Parquet store,
resamples to higher timeframes (5m/15m/1h/4h), and appends features so the
AI Filter never has to recompute on demand.

Entry points:
    python -m backend.ingest.runner --once             # single fetch+resample+features cycle
    python -m backend.ingest.runner --loop --every 60  # run every 60 seconds
    python -m backend.ingest.runner --once --backfill 90d  # historical backfill (last 90 days)
"""
from .pipeline import run_cycle, run_loop, backfill
from .store import (
    OHLCV_DIR,
    base_parquet_path,
    tf_parquet_path,
    read_ohlcv,
    write_ohlcv,
    upsert_ohlcv,
)

__all__ = [
    "run_cycle",
    "run_loop",
    "backfill",
    "OHLCV_DIR",
    "base_parquet_path",
    "tf_parquet_path",
    "read_ohlcv",
    "write_ohlcv",
    "upsert_ohlcv",
]
