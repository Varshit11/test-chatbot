"""Support / resistance pivot detection."""
from __future__ import annotations
import pandas as pd


def support_resistance(df: pd.DataFrame, left: int = 5, right: int = 5) -> pd.DataFrame:
    """
    Pivot-high / pivot-low detector. Returns a DataFrame with boolean columns
    'pivot_high' and 'pivot_low'.
    """
    high = df["high"]
    low = df["low"]

    pivot_high = high.rolling(left + right + 1, center=True).apply(
        lambda x: float(x[left] == x.max()), raw=True
    ) == 1.0

    pivot_low = low.rolling(left + right + 1, center=True).apply(
        lambda x: float(x[left] == x.min()), raw=True
    ) == 1.0

    return pd.DataFrame(
        {"pivot_high": pivot_high.fillna(False), "pivot_low": pivot_low.fillna(False)},
        index=df.index,
    )
