"""One-off backfill for XAUUSD covering ~2 years.

Finnhub's free tier rejects a *single* 2-year request, but it cheerfully serves
7-day windows even far in the past. So we walk backwards in 7-day chunks, the
same trick the user's manual script uses (`FinnhubOANDADataFetcher`).

Pipeline
--------
1. **Direct Finnhub chunk-fetch** for primary TFs:
       1m  → last 7 days   (free tier caps 1m at ~3h–7d depending on demand)
       5m  → last 730 days (~2 years)
       15m → last 730 days
   Each chunk goes through the canonical ``upsert_ohlcv`` so reruns are idempotent.

2. **CSV seed** (best-effort): if local CSVs are present, load them too — they
   give us ~1y of pristine bars that the API may not always return.

3. **Resample** 5m → 10m / 30m / 1h / 4h / 1d.

4. **Force-rebuild features** for every higher TF (deletes any stale prebuilt
   parquet first so the warmup-trim path is skipped and the whole frame is
   recomputed).

Run from ``chatbot/quantflow``:
    python -m backend.ingest.backfill_xauusd
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from .feature_writer import append_features
from .finnhub_client import fetch_candles
from .resampler import resample
from .store import (
    OHLCV_DIR,
    read_ohlcv,
    tf_parquet_path,
    upsert_ohlcv,
    write_ohlcv,
)
from ..core.features.smc_cached import prebuilt_paths

logger = logging.getLogger(__name__)

SYMBOL = "XAUUSD"
ASSET_CLASS = "forex"

# How far back to fetch each primary TF directly from Finnhub.
# Free-tier Finnhub serves history when you chunk in 7-day windows — confirmed
# empirically (`forex_candles` with res=1 over 7d windows returns 1500–2800 rows
# even 730 days back). The earlier 7-day cap on 1m was based on a single-window
# probe and was wrong; chunked fetches work for 1m the same way they do for 5m.
PRIMARY_LOOKBACK_DAYS = {
    "1m":  730,
    "5m":  730,
    "15m": 730,
}

# All timeframes we want fully populated on disk. 1m is OHLCV-only; everything
# else also gets a prebuilt feature parquet.
TARGET_OHLCV_TFS = ["1m", "5m", "10m", "15m", "30m", "1h", "4h", "1d"]
TARGET_FEATURE_TFS = ["5m", "10m", "15m", "30m", "1h", "4h", "1d"]

# Chunk window — Finnhub free tier serves 7 days of bars cleanly.
CHUNK_WINDOW = timedelta(days=7)
# Sleep between chunk requests to stay under Finnhub's 60-req/min rate limit.
CHUNK_SLEEP = 1.0

# Path to the existing historical CSVs (one repo level above /chatbot/).
CSV_BASE_DIR = (
    Path(__file__).resolve().parents[4]
    / "marketapi_data_fetcher" / "algo_methods" / "hidden_signals"
    / "strategies" / "enterprise" / "heikin_new"
)
CSV_SOURCES = {
    "5m":  CSV_BASE_DIR / "XAUUSD_5min_20260329_164026.csv",
    "15m": CSV_BASE_DIR / "XAUUSD_15min_20260329_163550.csv",
}


def _read_csv_ohlcv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "datetime" in df.columns:
        df["dt"] = pd.to_datetime(df["datetime"], errors="coerce")
    elif "timestamp" in df.columns:
        df["dt"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")
    else:
        raise ValueError(f"{path}: no datetime/timestamp column")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = df.dropna(subset=["dt"]).sort_values("dt").set_index("dt")
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df[~df.index.duplicated(keep="last")]
    return df


def _seed_from_csv(tfs: Iterable[str]) -> None:
    for tf in tfs:
        path = CSV_SOURCES.get(tf)
        if path is None or not path.is_file():
            logger.info("[seed] no CSV for %s — skipping", tf)
            continue
        logger.info("[seed] loading %s for %s ...", path.name, tf)
        df = _read_csv_ohlcv(path)
        if df.empty:
            continue
        # Upsert (don't write) so anything Finnhub returned that the CSV
        # doesn't have isn't blown away.
        upsert_ohlcv(df, SYMBOL, tf)
        logger.info("[seed] upserted %s rows into %s", len(df), tf_parquet_path(SYMBOL, tf))


def _chunked_fetch(tf: str, total_days: int) -> int:
    """Fetch ``total_days`` of ``tf`` bars in 7-day chunks. Returns total rows added."""
    end = datetime.now(tz=timezone.utc)
    cur_from = end - timedelta(days=total_days)
    rows_added = 0
    chunks_total = 0
    chunks_with_data = 0
    while cur_from < end:
        win_to = min(cur_from + CHUNK_WINDOW, end)
        chunks_total += 1
        try:
            chunk = fetch_candles(
                SYMBOL, tf, int(cur_from.timestamp()), int(win_to.timestamp()),
                asset_class=ASSET_CLASS,
            )
        except Exception as e:
            logger.warning("[chunk %s/%s] %s -> %s: %s", chunks_total, tf, cur_from.date(), win_to.date(), e)
            chunk = pd.DataFrame()
        if not chunk.empty:
            upsert_ohlcv(chunk, SYMBOL, tf)
            rows_added += len(chunk)
            chunks_with_data += 1
        # Progress every 20 chunks so the log doesn't drown
        if chunks_total % 20 == 0:
            logger.info("  ... %s/%s chunks done for %s (data in %s of them, +%s rows so far)",
                        chunks_total, _expected_chunks(total_days), tf, chunks_with_data, rows_added)
        cur_from = win_to
        time.sleep(CHUNK_SLEEP)
    logger.info("[fetch %s] %s/%s chunks returned data, +%s rows total",
                tf, chunks_with_data, chunks_total, rows_added)
    return rows_added


def _expected_chunks(total_days: int) -> int:
    return max(1, (total_days + CHUNK_WINDOW.days - 1) // CHUNK_WINDOW.days)


def _resample_from_5m(target_tfs: Iterable[str]) -> None:
    base = read_ohlcv(SYMBOL, "5m")
    if base.empty:
        logger.error("[resample] no 5m base on disk — cannot derive higher TFs")
        return
    for tf in target_tfs:
        if tf in {"1m", "5m", "15m"}:
            continue
        try:
            agg = resample(base, tf)
        except ValueError:
            logger.warning("[resample] don't know %s — skipping", tf)
            continue
        if agg.empty:
            continue
        write_ohlcv(agg, SYMBOL, tf)
        logger.info("[resample] %s -> %s rows", tf, len(agg))


def _wipe_prebuilts(tfs: Iterable[str]) -> None:
    """Delete existing prebuilt feature parquet/pickle so the next build is full,
    not warmup-trimmed. Safe to call — the chatbot falls back to compute-on-read
    if the prebuilt is missing."""
    for tf in tfs:
        pq, pk = prebuilt_paths(SYMBOL, tf)
        for p in (pq, pk):
            if p.is_file():
                p.unlink()
                logger.info("[wipe] removed %s", p.name)


def _build_features(tfs: Iterable[str]) -> None:
    for tf in tfs:
        bars = read_ohlcv(SYMBOL, tf)
        if bars.empty:
            logger.warning("[features] no bars for %s — skipping", tf)
            continue
        t0 = time.time()
        try:
            append_features(bars, instrument=SYMBOL, timeframe=tf)
            logger.info("[features] %s: built in %.1fs (%s rows)", tf, time.time() - t0, len(bars))
        except Exception:
            logger.exception("[features] %s failed", tf)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s | %(message)s",
        stream=sys.stdout,
    )
    logger.info("=== XAUUSD backfill — %s ===", datetime.now(tz=timezone.utc).isoformat())

    logger.info("Step 1/5: chunked Finnhub fetch (7-day windows, 1s sleep) ...")
    for tf, days in PRIMARY_LOOKBACK_DAYS.items():
        logger.info("  >>> %s: walking back %sd in %sd chunks (~%s requests)",
                    tf, days, CHUNK_WINDOW.days, _expected_chunks(days))
        _chunked_fetch(tf, days)

    logger.info("Step 2/5: seed from existing historical CSVs (idempotent merge) ...")
    _seed_from_csv(["5m", "15m"])

    logger.info("Step 3/5: resample 5m -> %s ...",
                [tf for tf in TARGET_OHLCV_TFS if tf not in {"1m", "5m", "15m"}])
    _resample_from_5m(TARGET_OHLCV_TFS)

    logger.info("Step 4/5: wipe stale prebuilt feature parquets ...")
    _wipe_prebuilts(TARGET_FEATURE_TFS)

    logger.info("Step 5/5: build SMC + TI features for all higher TFs ...")
    _build_features(TARGET_FEATURE_TFS)

    logger.info("=== Disk layout ===")
    for p in sorted(OHLCV_DIR.rglob("*.parquet")):
        try:
            df = pd.read_parquet(p)
            logger.info("  %s | %s rows | %s -> %s",
                        p.relative_to(OHLCV_DIR.parent), len(df),
                        df.index[0] if len(df) else None,
                        df.index[-1] if len(df) else None)
        except Exception as e:
            logger.info("  %s | (read failed: %s)", p, e)

    logger.info("=== done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
