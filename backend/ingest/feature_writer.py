"""Append-mode feature writer.

After resampling fresh 1m bars into a higher timeframe, recompute the SMC + TI
feature frame for the **tail** of the bar series (so we don't redo work for
historical rows) and merge with the existing prebuilt parquet that the AI
filter reads.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from ..core.features.smc_cached import (
    build_smc_feature_frame,
    prebuilt_paths,
    save_prebuilt_features,
)

logger = logging.getLogger(__name__)


# Number of bars to recompute on every cycle. SMC structure features look
# back over a few hundred bars (CHoCH window, swing length, etc.), so we
# rebuild the last ~600 bars on each cycle to be safe — that's ~50 hours
# on 5m bars.
WARMUP_BARS = 600


def append_features(
    bars: pd.DataFrame,
    *,
    instrument: str,
    timeframe: str,
    warmup: int = WARMUP_BARS,
) -> Optional[Path]:
    """Recompute features for the tail of ``bars`` and merge into the prebuilt parquet.

    Returns the parquet path that was written, or ``None`` if there was nothing
    to do (empty input).
    """
    if bars is None or bars.empty:
        return None

    pq, pk = prebuilt_paths(instrument, timeframe)
    existing: pd.DataFrame = pd.DataFrame()
    if pq.is_file():
        try:
            existing = pd.read_parquet(pq)
            if not isinstance(existing.index, pd.DatetimeIndex):
                existing.index = pd.to_datetime(existing.index)
            existing = existing.sort_index()
        except Exception as e:
            logger.warning("Existing prebuilt unreadable (%s) — full rebuild", e)
            existing = pd.DataFrame()
    elif pk.is_file():
        try:
            existing = pd.read_pickle(pk)
            existing = existing.sort_index()
        except Exception as e:
            logger.warning("Existing pickle unreadable (%s) — full rebuild", e)
            existing = pd.DataFrame()

    # First ever build, or empty: do the whole frame.
    if existing.empty:
        feat = build_smc_feature_frame(bars, timeframe=timeframe)
        return save_prebuilt_features(feat, instrument, timeframe)

    last_known = existing.index[-1]
    if bars.index[-1] <= last_known:
        return pq if pq.is_file() else pk  # nothing newer arrived

    # Safety check: if the gap between new tail and existing tail is wider than
    # `warmup`, the warmup-only recompute would silently leave bars without
    # features. Detect that case and fall back to a full rebuild — slower, but
    # correct.
    new_bar_count = int((bars.index > last_known).sum())
    if new_bar_count >= warmup:
        logger.warning(
            "feature_writer: %s/%s gap = %s bars (>= warmup=%s) — full rebuild",
            instrument, timeframe, new_bar_count, warmup,
        )
        feat = build_smc_feature_frame(bars, timeframe=timeframe)
        return save_prebuilt_features(feat, instrument, timeframe)

    # Incremental: rebuild the trailing window and merge.
    tail_start_idx = max(0, len(bars) - warmup)
    tail = bars.iloc[tail_start_idx:]
    new_feat = build_smc_feature_frame(tail, timeframe=timeframe)
    new_feat = new_feat[new_feat.index > last_known - pd.Timedelta(minutes=1)]
    merged = pd.concat([existing, new_feat])
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    return save_prebuilt_features(merged, instrument, timeframe)
