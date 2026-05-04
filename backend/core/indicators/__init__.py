"""Indicator library.

Every indicator follows the contract:
    fn(df: pd.DataFrame, **params) -> pd.Series | pd.DataFrame
where df has columns: open, high, low, close, volume (DatetimeIndex).
"""
from .trend import ema, sma, wma, supertrend, adx
from .momentum import rsi, macd, stochastic, roc
from .volatility import atr, bollinger_bands, keltner_channel
from .volume import vwap, obv

INDICATOR_REGISTRY = {
    # Trend
    "ema": {
        "fn": ema, "category": "trend",
        "description": "Exponential Moving Average",
        "params": {"period": {"type": "int", "default": 20, "min": 2, "max": 500}},
        "returns": "series",
    },
    "sma": {
        "fn": sma, "category": "trend",
        "description": "Simple Moving Average",
        "params": {"period": {"type": "int", "default": 20, "min": 2, "max": 500}},
        "returns": "series",
    },
    "wma": {
        "fn": wma, "category": "trend",
        "description": "Weighted Moving Average",
        "params": {"period": {"type": "int", "default": 20, "min": 2, "max": 500}},
        "returns": "series",
    },
    "supertrend": {
        "fn": supertrend, "category": "trend",
        "description": "SuperTrend (ATR-based trend follower)",
        "params": {
            "period": {"type": "int", "default": 10, "min": 2, "max": 100},
            "multiplier": {"type": "float", "default": 3.0, "min": 0.5, "max": 10.0},
        },
        "returns": "frame",
    },
    "adx": {
        "fn": adx, "category": "trend",
        "description": "Average Directional Index (trend strength)",
        "params": {"period": {"type": "int", "default": 14, "min": 2, "max": 100}},
        "returns": "frame",
    },
    # Momentum
    "rsi": {
        "fn": rsi, "category": "momentum",
        "description": "Relative Strength Index",
        "params": {"period": {"type": "int", "default": 14, "min": 2, "max": 100}},
        "returns": "series",
    },
    "macd": {
        "fn": macd, "category": "momentum",
        "description": "Moving Average Convergence Divergence",
        "params": {
            "fast": {"type": "int", "default": 12, "min": 2, "max": 100},
            "slow": {"type": "int", "default": 26, "min": 2, "max": 200},
            "signal": {"type": "int", "default": 9, "min": 2, "max": 100},
        },
        "returns": "frame",
    },
    "stochastic": {
        "fn": stochastic, "category": "momentum",
        "description": "Stochastic Oscillator",
        "params": {
            "k_period": {"type": "int", "default": 14, "min": 2, "max": 100},
            "d_period": {"type": "int", "default": 3, "min": 1, "max": 50},
        },
        "returns": "frame",
    },
    "roc": {
        "fn": roc, "category": "momentum",
        "description": "Rate of Change",
        "params": {"period": {"type": "int", "default": 12, "min": 1, "max": 100}},
        "returns": "series",
    },
    # Volatility
    "atr": {
        "fn": atr, "category": "volatility",
        "description": "Average True Range",
        "params": {"period": {"type": "int", "default": 14, "min": 2, "max": 100}},
        "returns": "series",
    },
    "bollinger_bands": {
        "fn": bollinger_bands, "category": "volatility",
        "description": "Bollinger Bands",
        "params": {
            "period": {"type": "int", "default": 20, "min": 2, "max": 200},
            "std": {"type": "float", "default": 2.0, "min": 0.5, "max": 5.0},
        },
        "returns": "frame",
    },
    "keltner_channel": {
        "fn": keltner_channel, "category": "volatility",
        "description": "Keltner Channel",
        "params": {
            "period": {"type": "int", "default": 20, "min": 2, "max": 200},
            "multiplier": {"type": "float", "default": 2.0, "min": 0.5, "max": 5.0},
        },
        "returns": "frame",
    },
    # Volume
    "vwap": {
        "fn": vwap, "category": "volume",
        "description": "Volume Weighted Average Price",
        "params": {},
        "returns": "series",
    },
    "obv": {
        "fn": obv, "category": "volume",
        "description": "On-Balance Volume",
        "params": {},
        "returns": "series",
    },
}


def list_indicators():
    """Return human-readable indicator catalog (without callables)."""
    return [
        {
            "name": name,
            "category": meta["category"],
            "description": meta["description"],
            "params": meta["params"],
            "returns": meta["returns"],
        }
        for name, meta in INDICATOR_REGISTRY.items()
    ]


def compute(name: str, df, **params):
    """Compute an indicator by name."""
    if name not in INDICATOR_REGISTRY:
        raise KeyError(f"Unknown indicator: {name}")
    return INDICATOR_REGISTRY[name]["fn"](df, **params)
