"""Chart pattern utilities."""
from .heikin_ashi import calculate_heikin_ashi
from .candlesticks import is_bullish_engulfing, is_bearish_engulfing, is_pin_bar
from .levels import support_resistance

PATTERN_REGISTRY = {
    "heikin_ashi": {
        "fn": calculate_heikin_ashi,
        "description": "Convert OHLC to Heikin Ashi candles (smoother trend representation).",
        "params": {},
    },
    "bullish_engulfing": {
        "fn": is_bullish_engulfing,
        "description": "Two-candle bullish reversal pattern.",
        "params": {},
    },
    "bearish_engulfing": {
        "fn": is_bearish_engulfing,
        "description": "Two-candle bearish reversal pattern.",
        "params": {},
    },
    "pin_bar": {
        "fn": is_pin_bar,
        "description": "Pin bar / hammer / shooting star (long-wick rejection).",
        "params": {"wick_ratio": {"type": "float", "default": 2.0, "min": 1.0, "max": 5.0}},
    },
    "support_resistance": {
        "fn": support_resistance,
        "description": "Pivot-based support / resistance levels.",
        "params": {"left": {"type": "int", "default": 5}, "right": {"type": "int", "default": 5}},
    },
}
