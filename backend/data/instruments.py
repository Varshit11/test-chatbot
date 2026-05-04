"""Instrument metadata.

For MVP we ship a static catalog backed by CSV files already present in the
existing TradeXpert codebase. Add more instruments here or later swap for a
DB-backed lookup.
"""
from __future__ import annotations
import os
import re
from typing import Dict, Any, List


def canonical_timeframe(timeframe: str) -> str:
    """Map common aliases (``5min``, ``15 minutes``) to catalog keys like ``5m``."""
    s = re.sub(r"\s+", "", (timeframe or "").strip().lower())
    return {
        "5min": "5m",
        "5minute": "5m",
        "5minutes": "5m",
        "10min": "10m",
        "10minute": "10m",
        "10minutes": "10m",
        "15min": "15m",
        "15minute": "15m",
        "15minutes": "15m",
        "30min": "30m",
        "60min": "1h",
        "60minutes": "1h",
        "1hour": "1h",
    }.get(s, s)

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
)

# Path to existing CSV data inside the larger TradeXpert codebase
HEIKIN_DATA_DIR = os.path.join(
    REPO_ROOT,
    "TradeXpert",
    "marketapi_data_fetcher",
    "algo_methods",
    "hidden_signals",
    "strategies",
    "enterprise",
    "heikin_new",
)

INSTRUMENTS: Dict[str, Dict[str, Any]] = {
    "XAUUSD": {
        "symbol": "XAUUSD",
        "name": "Gold / US Dollar",
        "exchange": "FX",
        "asset_class": "forex",
        "tick_size": 0.01,
        "lot_size": 1,
        "data_files": {
            "5m": os.path.join(HEIKIN_DATA_DIR, "XAUUSD_5min_20260329_164026.csv"),
            "15m": os.path.join(HEIKIN_DATA_DIR, "XAUUSD_15min_20260329_163550.csv"),
        },
    },
}


def get_instrument(symbol: str) -> Dict[str, Any]:
    sym = symbol.upper()
    if sym not in INSTRUMENTS:
        raise KeyError(f"Unknown instrument: {symbol}")
    return INSTRUMENTS[sym]


def list_instruments() -> List[Dict[str, Any]]:
    out = []
    for sym, meta in INSTRUMENTS.items():
        out.append({
            "symbol": sym,
            "name": meta["name"],
            "exchange": meta["exchange"],
            "asset_class": meta["asset_class"],
            "timeframes": list(meta["data_files"].keys()),
        })
    return out
