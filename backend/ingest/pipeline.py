"""End-to-end ingest cycle.

For each tracked instrument:
    1. Determine the gap between the last 1m bar on disk and now.
    2. Fetch the gap from Finnhub (single request, capped at the API window).
    3. Upsert 1m parquet.
    4. Resample 1m → 5m / 15m / 30m / 1h / 4h, upsert each.
    5. For every active timeframe, append features to the prebuilt parquet.

The cycle is **idempotent** — calling ``run_cycle()`` repeatedly never duplicates
or corrupts data. That's the contract the cron / loop runner relies on.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from .finnhub_client import fetch_candles, now_utc_ts
from .resampler import resample
from .store import latest_ts, read_ohlcv, upsert_ohlcv, write_ohlcv
from .feature_writer import append_features

logger = logging.getLogger(__name__)


# Default catalog for the ingest pipeline. Format:
#   {SYMBOL: {
#       "asset_class": "forex"|"crypto"|"equity",
#       "primary":     [...],   # fetched directly from Finnhub each cycle
#       "derived":     [...],   # resampled from 1m on disk
#       "feature_tfs": [...],   # which TFs (primary + derived) get prebuilt features
#   }}
# Primary always includes 1m so we have a base for resampling. derived ⊆ resamplable_tfs.
DEFAULT_CATALOG: Dict[str, Dict[str, List[str]]] = {
    "XAUUSD": {
        "asset_class": "forex",
        "primary": ["1m", "5m", "15m"],
        "derived": ["10m", "30m", "1h", "4h", "1d"],
        # Skip 1m features — they're computationally expensive and never used by backtests.
        "feature_tfs": ["5m", "10m", "15m", "30m", "1h", "4h", "1d"],
    },
}


def _all_timeframes(meta: Dict[str, Any]) -> List[str]:
    out = list(meta.get("primary") or [])
    for tf in meta.get("derived") or []:
        if tf not in out:
            out.append(tf)
    # Legacy "timeframes" key still supported.
    for tf in meta.get("timeframes") or []:
        if tf not in out:
            out.append(tf)
    return out


# Finnhub free tier returns at most a few thousand 1m bars per request. We
# fetch in 5-day windows when backfilling.
_BACKFILL_WINDOW = timedelta(days=5)


def _fetch_window(
    symbol: str,
    asset_class: str,
    from_ts: int,
    to_ts: int,
) -> pd.DataFrame:
    return fetch_candles(symbol, "1m", from_ts, to_ts, asset_class=asset_class)


def _refresh_one_minute(
    symbol: str,
    asset_class: str,
    *,
    lookback_minutes: int = 90,
) -> pd.DataFrame:
    """Top up the 1m parquet with the gap between disk-state and now.

    Returns the merged 1m frame (all rows on disk after upsert).
    """
    last = latest_ts(symbol, "1m")
    now_ts = now_utc_ts()
    if last is None:
        # First run for this symbol — caller should have explicitly backfilled,
        # but be defensive: pull the recent 90 minutes so the loop can start.
        from_ts = now_ts - lookback_minutes * 60
    else:
        # Re-fetch the last few bars so partial-bar corrections land cleanly.
        from_ts = int(last.timestamp()) - 5 * 60
    if from_ts >= now_ts:
        return read_ohlcv(symbol, "1m")

    new = _fetch_window(symbol, asset_class, from_ts, now_ts)
    if not new.empty:
        upsert_ohlcv(new, symbol, "1m")
    return read_ohlcv(symbol, "1m")


def _refresh_higher_tfs(
    symbol: str,
    timeframes: Iterable[str],
    df_1m: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """Resample 1m → each higher TF and upsert. Returns the newly written frames."""
    out: Dict[str, pd.DataFrame] = {}
    for tf in timeframes:
        agg = resample(df_1m, tf)
        if agg is None or agg.empty:
            continue
        upsert_ohlcv(agg, symbol, tf)
        out[tf] = read_ohlcv(symbol, tf)
    return out


def run_cycle(
    catalog: Optional[Dict[str, Dict[str, List[str]]]] = None,
    *,
    skip_features: bool = False,
) -> Dict[str, Dict[str, int]]:
    """One full ingest cycle. Returns ``{symbol: {tf: n_rows_after}}`` for telemetry.

    Live-cycle behaviour: only the gap between the last 1m bar on disk and now
    is fetched. Higher TFs (primary or derived) are resampled from the merged
    1m frame — at sub-minute scale, Finnhub's own 5m grid and a resampled 5m
    grid are functionally identical, and resampling cuts API calls 5×.
    """
    cat = catalog or DEFAULT_CATALOG
    summary: Dict[str, Dict[str, int]] = {}
    for symbol, meta in cat.items():
        ac = meta.get("asset_class", "forex")
        higher_tfs = [tf for tf in _all_timeframes(meta) if tf != "1m"]
        feature_tfs = meta.get("feature_tfs") or [tf for tf in higher_tfs]
        try:
            t0 = time.time()
            df_1m = _refresh_one_minute(symbol, ac)
            tf_frames = _refresh_higher_tfs(symbol, higher_tfs, df_1m)
            counts = {"1m": len(df_1m), **{k: len(v) for k, v in tf_frames.items()}}

            if not skip_features:
                for tf in feature_tfs:
                    frame = tf_frames.get(tf)
                    if frame is None or frame.empty:
                        continue
                    try:
                        append_features(frame, instrument=symbol, timeframe=tf)
                    except Exception as e:
                        logger.exception("feature append failed: %s/%s — %s", symbol, tf, e)

            summary[symbol] = counts
            logger.info("ingest cycle %s done in %.2fs: %s", symbol, time.time() - t0, counts)
        except Exception as e:
            logger.exception("ingest cycle failed for %s: %s", symbol, e)
            summary[symbol] = {"error": -1}
    return summary


def run_loop(
    every_seconds: int = 60,
    *,
    catalog: Optional[Dict[str, Dict[str, List[str]]]] = None,
    max_cycles: Optional[int] = None,
) -> None:
    """Run ``run_cycle`` repeatedly. Sleeps to maintain the requested cadence."""
    cycles = 0
    while True:
        start = time.time()
        run_cycle(catalog)
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            return
        elapsed = time.time() - start
        sleep_for = max(0.5, every_seconds - elapsed)
        time.sleep(sleep_for)


def _fetch_tf_in_chunks(
    symbol: str,
    asset_class: str,
    timeframe: str,
    days: int,
    *,
    window: timedelta = _BACKFILL_WINDOW,
) -> pd.DataFrame:
    """Fetch ``days`` of ``timeframe`` bars from Finnhub directly, in chunks.

    Used for primary timeframes that we want straight from the API rather than
    resampled from 1m (Finnhub guarantees its own 5m / 15m grids; resampled
    versions would expose any tiny gap in the 1m feed)."""
    end = datetime.now(tz=timezone.utc)
    cur_from = end - timedelta(days=days)
    chunks: List[pd.DataFrame] = []
    while cur_from < end:
        win_to = min(cur_from + window, end)
        try:
            chunk = fetch_candles(
                symbol, timeframe, int(cur_from.timestamp()), int(win_to.timestamp()),
                asset_class=asset_class,
            )
        except Exception as e:
            logger.warning("Fetch chunk %s/%s %s→%s failed: %s",
                           symbol, timeframe, cur_from, win_to, e)
            chunk = pd.DataFrame()
        if chunk is not None and not chunk.empty:
            chunks.append(chunk)
        cur_from = win_to
    if not chunks:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    full = pd.concat(chunks).sort_index()
    return full[~full.index.duplicated(keep="last")]


def backfill(
    symbol: str,
    *,
    asset_class: str = "forex",
    days: int = 30,
    primary: Optional[List[str]] = None,
    derived: Optional[List[str]] = None,
    feature_tfs: Optional[List[str]] = None,
    higher_timeframes: Optional[List[str]] = None,  # backward compat
    rebuild_features: bool = True,
) -> Dict[str, int]:
    """Backfill ``days`` of history for one symbol.

    Workflow:
        1. For each TF in ``primary``: fetch directly from Finnhub, write parquet.
        2. For each TF in ``derived``: resample from the 1m parquet, write parquet.
        3. For each TF in ``feature_tfs``: rebuild SMC + TI features.

    Catalog defaults are used when args are omitted.
    """
    catalog_meta = DEFAULT_CATALOG.get(symbol.upper(), {})
    if primary is None:
        primary = list(catalog_meta.get("primary") or ["1m"])
    if "1m" not in primary:
        # We always need 1m on disk so derived TFs can resample from it.
        primary = ["1m", *primary]
    if derived is None:
        derived = list(catalog_meta.get("derived") or [])
    if higher_timeframes:
        # Treat legacy `higher_timeframes` as derived TFs.
        for tf in higher_timeframes:
            if tf not in derived and tf not in primary:
                derived.append(tf)
    if feature_tfs is None:
        feature_tfs = list(catalog_meta.get("feature_tfs") or [tf for tf in primary + derived if tf != "1m"])

    counts: Dict[str, int] = {}

    # 1) Primary timeframes — fetch directly.
    for tf in primary:
        logger.info("backfill: fetching primary %s %s for %sd", symbol, tf, days)
        df = _fetch_tf_in_chunks(symbol, asset_class, tf, days)
        if not df.empty:
            write_ohlcv(df, symbol, tf)
        counts[tf] = len(df)

    # 2) Derived timeframes — resample from 1m on disk.
    one_min = read_ohlcv(symbol, "1m")
    for tf in derived:
        agg = resample(one_min, tf)
        if agg.empty:
            counts[tf] = 0
            continue
        write_ohlcv(agg, symbol, tf)
        counts[tf] = len(agg)

    # 3) Feature build for the listed TFs.
    if rebuild_features:
        for tf in feature_tfs:
            bars = read_ohlcv(symbol, tf)
            if bars.empty:
                logger.warning("feature build skipped for %s/%s (empty bars)", symbol, tf)
                continue
            try:
                logger.info("backfill: building features for %s %s (%s rows)", symbol, tf, len(bars))
                append_features(bars, instrument=symbol, timeframe=tf)
            except Exception as e:
                logger.exception("feature backfill failed for %s/%s: %s", symbol, tf, e)

    logger.info("backfill done %s (%sd): %s", symbol, days, counts)
    return counts
