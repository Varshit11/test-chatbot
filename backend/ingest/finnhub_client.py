"""Thin Finnhub wrapper for OHLCV fetches.

Uses the same endpoints already proven in
``marketapi_data_fetcher/data_fetchers.py::FinnhubForexFetcher`` — but exposes a
single ``fetch_candles(symbol, resolution, from_ts, to_ts)`` that the ingest
pipeline can call repeatedly without duplicated bookkeeping.

Authentication: ``QUANTFLOW_FINNHUB_KEY`` env var (preferred) → fallback to
``marketapi_data_fetcher/config/config.yaml`` (``finnhub.api_key``).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


_RESOLUTION_MAP: Dict[str, str] = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "4h": "240",
    "1d": "D",
    "1w": "W",
}


def resolution_for(timeframe: str) -> str:
    """Map a TradeXpert canonical timeframe to a Finnhub resolution string."""
    tf = (timeframe or "").lower()
    if tf in _RESOLUTION_MAP:
        return _RESOLUTION_MAP[tf]
    raise ValueError(f"Unsupported timeframe for Finnhub: {timeframe!r}")


def _read_yaml_key(path: str, dotted_key: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return None
    cur = data
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return str(cur) if cur is not None else None


def _resolve_api_key() -> str:
    env_key = os.environ.get("QUANTFLOW_FINNHUB_KEY") or os.environ.get("FINNHUB_API_KEY")
    if env_key:
        return env_key
    cfg_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "..",
            "marketapi_data_fetcher", "config", "config.yaml",
        )
    )
    yaml_key = _read_yaml_key(cfg_path, "finnhub.api_key")
    if yaml_key:
        return yaml_key
    raise RuntimeError(
        "Finnhub API key not found. Set QUANTFLOW_FINNHUB_KEY env var or add "
        "finnhub.api_key to marketapi_data_fetcher/config/config.yaml."
    )


_OANDA_OVERRIDES = {
    # OANDA's Finnhub feed uses underscore-separated tickers for the metals /
    # exotic-pair instruments. ``XAUUSD`` returns ``no_data``; ``XAU_USD`` works.
    "XAUUSD": "XAU_USD",
    "XAGUSD": "XAG_USD",
    "XPTUSD": "XPT_USD",
    "XPDUSD": "XPD_USD",
}


def _finnhub_symbol(symbol: str, asset_class: str) -> str:
    s = (symbol or "").upper()
    ac = (asset_class or "").lower()
    if ":" in s:
        return s
    if ac == "crypto":
        return f"BINANCE:{s}"
    if ac == "forex":
        s = _OANDA_OVERRIDES.get(s, s)
        return f"OANDA:{s}"
    return s


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    import finnhub  # type: ignore
    _client = finnhub.Client(api_key=_resolve_api_key())
    return _client


def fetch_candles(
    symbol: str,
    timeframe: str,
    from_ts: int,
    to_ts: int,
    *,
    asset_class: str = "forex",
) -> pd.DataFrame:
    """Fetch OHLCV from Finnhub and return a DataFrame indexed by UTC datetime.

    The dataframe columns are exactly ``[open, high, low, close, volume]``;
    the index is a tz-naive UTC ``DatetimeIndex`` (matches the rest of the codebase).
    """
    client = _get_client()
    fin_sym = _finnhub_symbol(symbol, asset_class)
    resolution = resolution_for(timeframe)

    try:
        if asset_class.lower() == "crypto":
            candles = client.crypto_candles(
                symbol=fin_sym, resolution=resolution, _from=int(from_ts), to=int(to_ts)
            )
        else:
            candles = client.forex_candles(
                symbol=fin_sym, resolution=resolution, _from=int(from_ts), to=int(to_ts)
            )
    except Exception as e:
        logger.exception("Finnhub fetch failed: %s/%s %s→%s", symbol, timeframe, from_ts, to_ts)
        raise RuntimeError(f"Finnhub fetch failed: {e}") from e

    if not isinstance(candles, dict) or candles.get("s") != "ok":
        logger.warning("Finnhub no_data for %s %s window %s→%s: %s",
                       symbol, timeframe, from_ts, to_ts, candles)
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame({
        "datetime": pd.to_datetime(candles["t"], unit="s", utc=True).tz_convert(None),
        "open": candles["o"],
        "high": candles["h"],
        "low": candles["l"],
        "close": candles["c"],
        "volume": candles["v"],
    })
    df = df.dropna(subset=["datetime"]).sort_values("datetime").drop_duplicates("datetime")
    df = df.set_index("datetime")
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df


def now_utc_ts() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())
