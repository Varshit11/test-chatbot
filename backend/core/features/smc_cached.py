"""SMC/ICT bar features with a **offline-first** workflow.

1. **Prebuilt store** (fast, default for AI filter): ``data/prebuilt_features/{SYMBOL}_{tf}_smc.parquet``
   (``.pkl`` fallback). Built once per symbol/timeframe by running:

       python materialize_prebuilt_features.py

   ``python materialize_prebuilt_features.py`` from ``chatbot/quantflow/backend``. At request time we only
   ``read_parquet`` + ``.loc[df.index]`` — **no** SMC engine.

2. **Session pickle** ``data/feature_cache/smc_features_current.pkl`` — last in-memory snapshot
   when the bar index exactly matched (Renko / odd slices).

3. **Compute** — only if prebuilt + pickle miss (slow).

Product roadmap: generate prebuilt files from a scheduled job every N minutes instead of this script.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from ...data.instruments import canonical_timeframe
from .smc_ict_native import EnhancedSMCFeatures
from .technical_indicators_v2 import EnhancedTechnicalIndicatorsGeneric

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = _BACKEND_ROOT / "data" / "feature_cache"
PREBUILT_DIR = _BACKEND_ROOT / "data" / "prebuilt_features"
FEATURES_PICKLE = CACHE_DIR / "smc_features_current.pkl"


def prebuilt_stem(instrument: str, timeframe: str) -> str:
    inst = (instrument or "NA").strip().upper()
    raw = (timeframe or "").strip()
    if not raw or raw.upper() == "NA":
        tf = "NA"
    else:
        tf = canonical_timeframe(raw)
    return f"{inst}_{tf}_smc"


def prebuilt_paths(instrument: str, timeframe: str) -> tuple[Path, Path]:
    PREBUILT_DIR.mkdir(parents=True, exist_ok=True)
    stem = prebuilt_stem(instrument, timeframe)
    return PREBUILT_DIR / f"{stem}.parquet", PREBUILT_DIR / f"{stem}.pkl"


def try_load_prebuilt_features(
    df: pd.DataFrame,
    instrument: str,
    timeframe: str,
) -> Optional[pd.DataFrame]:
    """Load offline SMC features for this symbol/TF and align to ``df`` index (no SMC engine)."""
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return None
    pq, pk = prebuilt_paths(instrument, timeframe)
    full: Optional[pd.DataFrame] = None
    try:
        if pq.is_file():
            full = pd.read_parquet(pq)
        elif pk.is_file():
            full = pd.read_pickle(pk)
    except Exception as e:
        logger.warning("Prebuilt SMC read failed (%s): %s", pq.name if pq.is_file() else pk.name, e)
        return None
    if full is None or full.empty:
        return None
    if not isinstance(full.index, pd.DatetimeIndex):
        full.index = pd.to_datetime(full.index)
    full = full.sort_index()
    missing = df.index.difference(full.index)
    if len(missing) > 0:
        logger.info(
            "Prebuilt SMC missing %s of %s bars for %s %s — need refresh or full compute",
            len(missing),
            len(df),
            instrument,
            timeframe,
        )
        return None
    try:
        out = full.loc[df.index].copy()
        logger.info(
            "SMC features: loaded prebuilt %s (%s rows)",
            prebuilt_stem(instrument, timeframe),
            len(out),
        )
        return out
    except Exception as e:
        logger.warning("Prebuilt SMC align failed: %s", e)
        return None


def build_smc_feature_frame(
    ohlcv: pd.DataFrame,
    *,
    choch_period: int = 50,
    idm_period: int = 3,
    swing_length: int = 8,
    timeframe: str = "",
) -> pd.DataFrame:
    """Run SMC + technical_indicators_v2 engines on OHLCV and merge to a single feature frame.

    SMC engine assumes positional integer indexing; technical_indicators_v2 needs the
    original DatetimeIndex (session and multi-timeframe features resample on it). Run them
    against the appropriate index, then concatenate non-OHLCV columns.
    """
    if ohlcv.empty:
        return ohlcv

    # 1) SMC features — engine writes via `df.loc[i, col]` with integer i, so reset index.
    smc_in = ohlcv.reset_index(drop=True).copy()
    smc_engine = EnhancedSMCFeatures(
        df=smc_in,
        choch_period=choch_period,
        idm_period=idm_period,
        swing_length=swing_length,
    )
    smc_out = smc_engine.process_all_features()
    smc_out.index = ohlcv.index

    # 2) Technical indicators v2 — needs DatetimeIndex for session/MTF features.
    ti_engine = EnhancedTechnicalIndicatorsGeneric(primary_timeframe=timeframe or "5m")
    ti_out = ti_engine.calculate_all_indicators(ohlcv.copy())

    # 3) Merge: keep SMC frame as the base (has OHLCV), append TI columns that aren't already present.
    base_cols = {"open", "high", "low", "close", "volume"}
    extra_cols = [c for c in ti_out.columns if c not in base_cols and c not in smc_out.columns]
    if extra_cols:
        merged = pd.concat([smc_out, ti_out[extra_cols]], axis=1)
    else:
        merged = smc_out
    merged.index = ohlcv.index
    return merged


def save_prebuilt_features(
    feat_df: pd.DataFrame,
    instrument: str,
    timeframe: str,
) -> Path:
    """Write ``{SYMBOL}_{tf}_smc.parquet`` (+ ``.pkl`` backup if parquet fails)."""
    PREBUILT_DIR.mkdir(parents=True, exist_ok=True)
    pq, pk = prebuilt_paths(instrument, timeframe)
    try:
        feat_df.to_parquet(pq, index=True)
        logger.info("Prebuilt SMC saved: %s", pq)
        return pq
    except Exception as e:
        logger.warning("to_parquet failed (%s); using pickle — pip install pyarrow for Parquet", e)
        feat_df.to_pickle(pk)
        logger.info("Prebuilt SMC saved: %s", pk)
        return pk


def materialize_prebuilt_for_catalog() -> tuple[list[str], list[str]]:
    """Build + save prebuilt features for every (symbol, tf) in ``INSTRUMENTS``.

    Returns ``(succeeded_keys, failed_keys)``. Each successful pair is written
    immediately so a later crash still leaves partial Parquet on disk.
    """
    import gc
    import traceback

    from ...data.instruments import INSTRUMENTS
    from ...data.loader import load_bars_only

    done: list[str] = []
    failed: list[str] = []
    for sym, meta in INSTRUMENTS.items():
        for tf in meta.get("data_files", {}):
            key = f"{sym}/{tf}"
            try:
                logger.info("Materializing prebuilt SMC: %s …", key)
                bars = load_bars_only(sym, tf)
                feat = build_smc_feature_frame(bars, timeframe=tf)
                save_prebuilt_features(feat, sym, tf)
                done.append(key)
                del feat, bars
                gc.collect()
            except Exception as e:
                tb = traceback.format_exc()
                logger.error("Materialize failed for %s: %s\n%s", key, e, tb)
                failed.append(f"{key}: {e}")
    return done, failed


def _try_load_saved_session(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return None
    if not FEATURES_PICKLE.is_file():
        return None
    try:
        cached = pd.read_pickle(FEATURES_PICKLE)
        if len(cached) == len(df) and cached.index.equals(df.index):
            logger.info("SMC features: loaded session cache %s", FEATURES_PICKLE.name)
            return cached
    except Exception as e:
        logger.warning("SMC session cache read failed (%s)", e)
    return None


def _save_session_features(feat_df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        feat_df.to_pickle(FEATURES_PICKLE)
        logger.info("SMC features: wrote session cache %s", FEATURES_PICKLE)
    except Exception as e:
        logger.warning("SMC session cache save failed: %s", e)


def compute_smc_features_cached(
    df: pd.DataFrame,
    *,
    instrument: str = "",
    timeframe: str = "",
    use_cache: bool = True,
    choch_period: int = 50,
    idm_period: int = 3,
    swing_length: int = 8,
) -> pd.DataFrame:
    """Prebuilt Parquet → session pickle → compute (slow)."""
    if df.empty:
        return df
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("compute_smc_features_cached expects a DatetimeIndex on df")

    inst = (instrument or "NA").strip().upper()
    raw_tf = (timeframe or "").strip()
    if not raw_tf or raw_tf.upper() == "NA":
        tf = "NA"
    else:
        tf = canonical_timeframe(raw_tf)

    if use_cache:
        hit = try_load_prebuilt_features(df, inst, tf)
        if hit is not None:
            return hit
        hit = _try_load_saved_session(df)
        if hit is not None:
            return hit

    logger.warning(
        "SMC features: no prebuilt for %s %s — running full SMC (use materialize_prebuilt_features.py)",
        inst,
        tf,
    )
    out = build_smc_feature_frame(
        df,
        choch_period=choch_period,
        idm_period=idm_period,
        swing_length=swing_length,
        timeframe=tf,
    )
    if use_cache:
        _save_session_features(out)
    return out


def materialize_smc_features(
    df: pd.DataFrame,
    *,
    instrument: str = "",
    timeframe: str = "",
    choch_period: int = 50,
    idm_period: int = 3,
    swing_length: int = 8,
) -> pd.DataFrame:
    """After backtest: prefer prebuilt slice, else compute + session cache."""
    return compute_smc_features_cached(
        df,
        instrument=instrument,
        timeframe=timeframe,
        use_cache=True,
        choch_period=choch_period,
        idm_period=idm_period,
        swing_length=swing_length,
    )


def smc_feature_categories(feature_cols: list) -> dict:
    """UI grouping — mirrors notebook feature families without inventing new signals."""
    cats: dict = {"SMC / ICT structure": [], "SMC lags & activity": [], "TA helpers": []}
    for c in feature_cols:
        if any(x in c for x in ("any_", "_last_")) or c.startswith("smc_activity"):
            cats["SMC lags & activity"].append(c)
        elif c.startswith("sma_") or c.startswith("above_sma") or c == "trend_strength":
            cats["TA helpers"].append(c)
        else:
            cats["SMC / ICT structure"].append(c)
    return {k: v for k, v in cats.items() if v}
