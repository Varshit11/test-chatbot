"""Simple candlestick pattern detectors. Each returns a boolean Series."""
from __future__ import annotations
import pandas as pd


def is_bullish_engulfing(df: pd.DataFrame) -> pd.Series:
    prev_o = df["open"].shift(1)
    prev_c = df["close"].shift(1)
    bull = (
        (prev_c < prev_o) &
        (df["close"] > df["open"]) &
        (df["close"] > prev_o) &
        (df["open"] < prev_c)
    )
    return bull.fillna(False).rename("bullish_engulfing")


def is_bearish_engulfing(df: pd.DataFrame) -> pd.Series:
    prev_o = df["open"].shift(1)
    prev_c = df["close"].shift(1)
    bear = (
        (prev_c > prev_o) &
        (df["close"] < df["open"]) &
        (df["close"] < prev_o) &
        (df["open"] > prev_c)
    )
    return bear.fillna(False).rename("bearish_engulfing")


def is_pin_bar(df: pd.DataFrame, wick_ratio: float = 2.0) -> pd.Series:
    body = (df["close"] - df["open"]).abs()
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    body_safe = body.replace(0, 1e-9)
    bullish_pin = (lower_wick / body_safe >= wick_ratio) & (upper_wick < body)
    bearish_pin = (upper_wick / body_safe >= wick_ratio) & (lower_wick < body)
    return (bullish_pin | bearish_pin).rename("pin_bar")
