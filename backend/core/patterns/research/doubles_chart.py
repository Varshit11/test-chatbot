"""
Double tops / bottoms — aligned with
`marketapi_data_fetcher/algo_methods/patterns/doubles.py` and
`pivot_points.py`, using **integer row positions** in the lookback window
(so behaviour is correct for any DatetimeIndex). tqdm/plotly omitted.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _find_pivot_point_num(
    lows: np.ndarray,
    highs: np.ndarray,
    current_row: int,
    left_count: int,
    right_count: int,
) -> int:
    if current_row - left_count < 0 or current_row + right_count >= len(lows):
        return 0
    pivot_low = 1
    pivot_high = 1
    lv, hv = lows[current_row], highs[current_row]
    for idx in range(current_row - left_count, current_row + right_count + 1):
        if lv > lows[idx]:
            pivot_low = 0
        if hv < highs[idx]:
            pivot_high = 0
    if pivot_low and pivot_high:
        return 3
    if pivot_low:
        return 1
    if pivot_high:
        return 2
    return 0


def find_all_pivot_points(
    ohlc: pd.DataFrame,
    left_count: int = 3,
    right_count: int = 3,
) -> pd.DataFrame:
    """Add `pivot` (0 none, 1 low, 2 high, 3 both) and `pivot_pos` columns."""
    out = ohlc.copy()
    needed = ("low", "high")
    for c in needed:
        if c not in out.columns:
            raise ValueError(f"doubles/pivots: column '{c}' required (lowercase OHLC).")
    lows = out["low"].to_numpy(dtype=float)
    highs = out["high"].to_numpy(dtype=float)
    n = len(out)
    piv = np.zeros(n, dtype=np.int8)
    ppos = np.full(n, np.nan, dtype=float)
    for i in range(n):
        p = _find_pivot_point_num(lows, highs, i, left_count, right_count)
        piv[i] = p
        if p == 1:
            ppos[i] = lows[i] - 1e-3
        elif p == 2:
            ppos[i] = highs[i] + 1e-3
    out["pivot"] = piv
    out["pivot_pos"] = ppos
    return out


def find_doubles_pattern(
    ohlc: pd.DataFrame,
    lookback: int = 50,
    double: str = "tops",
    tops_max_ratio: float = 1.01,
    bottoms_min_ratio: float = 0.98,
    count: int = 5,
) -> pd.DataFrame:
    """
    Mark rows where a double-top or double-bottom structure is detected on the
    **last bar of the lookback** slice (same idea as the research script).
    Adds columns: double_type, chart_type, double_idx, double_point.
    """
    out = find_all_pivot_points(ohlc, left_count=count, right_count=count)
    n = len(out)
    plow = out["pivot"].to_numpy(dtype=np.int8)
    ppos = out["pivot_pos"].to_numpy(dtype=float)

    double_type = np.array([""] * n, dtype=object)
    chart_type = np.array([""] * n, dtype=object)
    double_idx: list = [np.array([], dtype=np.int64) for _ in range(n)]
    double_point: list = [np.array([], dtype=float) for _ in range(n)]

    for candle_idx in range(lookback, n):
        sub_lo = candle_idx - lookback
        sub_p = plow[sub_lo : candle_idx + 1]
        rel = np.where(sub_p != 0)[0]
        if len(rel) != 5:
            continue

        pivot_indx = (rel + sub_lo).astype(np.int64)
        pivots = ppos[pivot_indx]
        if np.any(np.isnan(pivots)):
            continue
        pivots = pivots.astype(float).tolist()

        if double in ("tops", "both"):
            if (
                (pivots[0] < pivots[1])
                and (pivots[0] < pivots[3])
                and (pivots[2] < pivots[1])
                and (pivots[2] < pivots[3])
                and (pivots[4] < pivots[1])
                and (pivots[4] < pivots[3])
                and (pivots[1] > pivots[3])
                and (pivots[1] / pivots[3] <= tops_max_ratio)
                and (pivots[1] / pivots[0] >= 1.012)
                and (pivots[3] / pivots[2] >= 1.012)
            ):
                double_idx[candle_idx] = pivot_indx
                double_point[candle_idx] = np.array(pivots, dtype=float)
                double_type[candle_idx] = "tops"
                chart_type[candle_idx] = "double"

        if double in ("bottoms", "both"):
            if (
                (pivots[0] > pivots[1])
                and (pivots[0] > pivots[3])
                and (pivots[2] > pivots[1])
                and (pivots[2] > pivots[3])
                and (pivots[4] > pivots[1])
                and (pivots[4] > pivots[3])
                and (pivots[1] < pivots[3])
                and (pivots[1] / pivots[3] >= bottoms_min_ratio)
            ):
                double_idx[candle_idx] = pivot_indx
                double_point[candle_idx] = np.array(pivots, dtype=float)
                double_type[candle_idx] = "bottoms"
                chart_type[candle_idx] = "double"

    out["double_type"] = double_type
    out["chart_type"] = chart_type
    out["double_idx"] = double_idx
    out["double_point"] = double_point
    return out
