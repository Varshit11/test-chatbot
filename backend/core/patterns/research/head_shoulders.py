"""
Head & shoulders (regular + inverted) — logic aligned with
`marketapi_data_fetcher/algo_methods/patterns/head_and_shoulders.py`.
Plotting / mplfinance / matplotlib removed for QuantFlow sandbox use.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


def rw_top(data: np.ndarray, curr_index: int, order: int) -> bool:
    if curr_index < order * 2 + 1:
        return False

    top = True
    k = curr_index - order
    v = data[k]
    for i in range(1, order + 1):
        if data[k + i] > v or data[k - i] > v:
            top = False
            break

    return top


def rw_bottom(data: np.ndarray, curr_index: int, order: int) -> bool:
    if curr_index < order * 2 + 1:
        return False

    bottom = True
    k = curr_index - order
    v = data[k]
    for i in range(1, order + 1):
        if data[k + i] < v or data[k - i] < v:
            bottom = False
            break

    return bottom


@dataclass
class HSPattern:
    inverted: bool
    l_shoulder: int = -1
    r_shoulder: int = -1
    l_armpit: int = -1
    r_armpit: int = -1
    head: int = -1
    l_shoulder_p: float = -1
    r_shoulder_p: float = -1
    l_armpit_p: float = -1
    r_armpit_p: float = -1
    head_p: float = -1
    start_i: int = -1
    break_i: int = -1
    break_p: float = -1
    neck_start: float = -1
    neck_end: float = -1
    neck_slope: float = -1
    head_width: float = -1
    head_height: float = -1
    pattern_r2: float = -1


def compute_pattern_r2(data: np.ndarray, pat: HSPattern) -> float:
    line0_slope = (pat.l_shoulder_p - pat.neck_start) / (pat.l_shoulder - pat.start_i)
    line0 = pat.neck_start + np.arange(pat.l_shoulder - pat.start_i) * line0_slope

    line1_slope = (pat.l_armpit_p - pat.l_shoulder_p) / (pat.l_armpit - pat.l_shoulder)
    line1 = pat.l_shoulder_p + np.arange(pat.l_armpit - pat.l_shoulder) * line1_slope

    line2_slope = (pat.head_p - pat.l_armpit_p) / (pat.head - pat.l_armpit)
    line2 = pat.l_armpit_p + np.arange(pat.head - pat.l_armpit) * line2_slope

    line3_slope = (pat.r_armpit_p - pat.head_p) / (pat.r_armpit - pat.head)
    line3 = pat.head_p + np.arange(pat.r_armpit - pat.head) * line3_slope

    line4_slope = (pat.r_shoulder_p - pat.r_armpit_p) / (pat.r_shoulder - pat.r_armpit)
    line4 = pat.r_armpit_p + np.arange(pat.r_shoulder - pat.r_armpit) * line4_slope

    line5_slope = (pat.break_p - pat.r_shoulder_p) / (pat.break_i - pat.r_shoulder)
    line5 = pat.r_shoulder_p + np.arange(pat.break_i - pat.r_shoulder) * line5_slope

    raw_data = data[pat.start_i : pat.break_i]
    hs_model = np.concatenate([line0, line1, line2, line3, line4, line5])
    mean = np.mean(raw_data)

    ss_res = np.sum((raw_data - hs_model) ** 2.0)
    ss_tot = np.sum((raw_data - mean) ** 2.0)

    r2 = 1.0 - ss_res / ss_tot
    return float(r2)


def check_hs_pattern(
    extrema_indices: List[int], data: np.ndarray, i: int, early_find: bool = False
) -> HSPattern | None:
    l_shoulder = extrema_indices[0]
    l_armpit = extrema_indices[1]
    head = extrema_indices[2]
    r_armpit = extrema_indices[3]

    if i - r_armpit < 2:
        return None

    r_shoulder = r_armpit + int(data[r_armpit + 1 : i].argmax()) + 1

    if data[head] <= max(data[l_shoulder], data[r_shoulder]):
        return None

    r_midpoint = 0.5 * (data[r_shoulder] + data[r_armpit])
    l_midpoint = 0.5 * (data[l_shoulder] + data[l_armpit])
    if data[l_shoulder] < r_midpoint or data[r_shoulder] < l_midpoint:
        return None

    r_to_h_time = r_shoulder - head
    l_to_h_time = head - l_shoulder
    if r_to_h_time > 2.5 * l_to_h_time or l_to_h_time > 2.5 * r_to_h_time:
        return None

    neck_run = r_armpit - l_armpit
    neck_rise = data[r_armpit] - data[l_armpit]
    neck_slope = neck_rise / neck_run

    neck_val = data[l_armpit] + (i - l_armpit) * neck_slope

    if early_find:
        if data[i] > r_midpoint:
            return None
    else:
        if data[i] > neck_val:
            return None

    head_width = r_armpit - l_armpit
    pat_start = -1
    neck_start = -1.0
    for j in range(1, head_width):
        neck = data[l_armpit] + (l_shoulder - l_armpit - j) * neck_slope

        if l_shoulder - j < 0:
            return None

        if data[l_shoulder - j] < neck:
            pat_start = l_shoulder - j
            neck_start = neck
            break

    if pat_start == -1:
        return None

    pat = HSPattern(inverted=False)

    pat.l_shoulder = l_shoulder
    pat.r_shoulder = r_shoulder
    pat.l_armpit = l_armpit
    pat.r_armpit = r_armpit
    pat.head = head

    pat.l_shoulder_p = data[l_shoulder]
    pat.r_shoulder_p = data[r_shoulder]
    pat.l_armpit_p = data[l_armpit]
    pat.r_armpit_p = data[r_armpit]
    pat.head_p = data[head]

    pat.start_i = pat_start
    pat.break_i = i
    pat.break_p = data[i]

    pat.neck_start = neck_start
    pat.neck_end = neck_val

    pat.neck_slope = neck_slope
    pat.head_width = float(head_width)
    pat.head_height = data[head] - (data[l_armpit] + (head - l_armpit) * neck_slope)
    pat.pattern_r2 = compute_pattern_r2(data, pat)

    return pat


def check_ihs_pattern(
    extrema_indices: List[int], data: np.ndarray, i: int, early_find: bool = False
) -> HSPattern | None:
    l_shoulder = extrema_indices[0]
    l_armpit = extrema_indices[1]
    head = extrema_indices[2]
    r_armpit = extrema_indices[3]

    if i - r_armpit < 2:
        return None

    r_shoulder = r_armpit + int(data[r_armpit + 1 : i].argmin()) + 1

    if data[head] >= min(data[l_shoulder], data[r_shoulder]):
        return None

    r_midpoint = 0.5 * (data[r_shoulder] + data[r_armpit])
    l_midpoint = 0.5 * (data[l_shoulder] + data[l_armpit])
    if data[l_shoulder] > r_midpoint or data[r_shoulder] > l_midpoint:
        return None

    r_to_h_time = r_shoulder - head
    l_to_h_time = head - l_shoulder
    if r_to_h_time > 2.5 * l_to_h_time or l_to_h_time > 2.5 * r_to_h_time:
        return None

    neck_run = r_armpit - l_armpit
    neck_rise = data[r_armpit] - data[l_armpit]
    neck_slope = neck_rise / neck_run

    neck_val = data[l_armpit] + (i - l_armpit) * neck_slope

    if early_find:
        if data[i] < r_midpoint:
            return None
    else:
        if data[i] < neck_val:
            return None

    head_width = r_armpit - l_armpit
    pat_start = -1
    neck_start = -1.0
    for j in range(1, head_width):
        neck = data[l_armpit] + (l_shoulder - l_armpit - j) * neck_slope

        if l_shoulder - j < 0:
            return None

        if data[l_shoulder - j] > neck:
            pat_start = l_shoulder - j
            neck_start = neck
            break

    if pat_start == -1:
        return None

    pat = HSPattern(inverted=True)

    pat.l_shoulder = l_shoulder
    pat.r_shoulder = r_shoulder
    pat.l_armpit = l_armpit
    pat.r_armpit = r_armpit
    pat.head = head

    pat.l_shoulder_p = data[l_shoulder]
    pat.r_shoulder_p = data[r_shoulder]
    pat.l_armpit_p = data[l_armpit]
    pat.r_armpit_p = data[r_armpit]
    pat.head_p = data[head]

    pat.start_i = pat_start
    pat.break_i = i
    pat.break_p = data[i]

    pat.neck_start = neck_start
    pat.neck_end = neck_val

    pat.neck_slope = neck_slope
    pat.head_width = float(head_width)
    pat.head_height = (data[l_armpit] + (head - l_armpit) * neck_slope) - data[head]
    pat.pattern_r2 = compute_pattern_r2(data, pat)

    return pat


def find_hs_patterns(
    data: np.ndarray, order: int, early_find: bool = False
) -> Tuple[list, list]:
    assert order >= 1

    last_is_top = False
    recent_extrema = deque(maxlen=5)
    recent_types = deque(maxlen=5)

    hs_lock = False
    ihs_lock = False

    ihs_patterns: list = []
    hs_patterns: list = []
    for i in range(len(data)):

        if rw_top(data, i, order):
            recent_extrema.append(i - order)
            recent_types.append(1)
            ihs_lock = False
            last_is_top = True

        if rw_bottom(data, i, order):
            recent_extrema.append(i - order)
            recent_types.append(-1)
            hs_lock = False
            last_is_top = False

        if len(recent_extrema) < 5:
            continue

        hs_alternating = True
        ihs_alternating = True

        if last_is_top:
            for j in range(2, 5):
                if recent_types[j] == recent_types[j - 1]:
                    ihs_alternating = False

            for j in range(1, 4):
                if recent_types[j] == recent_types[j - 1]:
                    hs_alternating = False

            ihs_extrema = list(recent_extrema)[1:5]
            hs_extrema = list(recent_extrema)[0:4]
        else:

            for j in range(2, 5):
                if recent_types[j] == recent_types[j - 1]:
                    hs_alternating = False

            for j in range(1, 4):
                if recent_types[j] == recent_types[j - 1]:
                    ihs_alternating = False

            ihs_extrema = list(recent_extrema)[0:4]
            hs_extrema = list(recent_extrema)[1:5]

        if ihs_lock or not ihs_alternating:
            ihs_pat = None
        else:
            ihs_pat = check_ihs_pattern(ihs_extrema, data, i, early_find)

        if hs_lock or not hs_alternating:
            hs_pat = None
        else:
            hs_pat = check_hs_pattern(hs_extrema, data, i, early_find)

        if hs_pat is not None:
            hs_lock = True
            hs_patterns.append(hs_pat)

        if ihs_pat is not None:
            ihs_lock = True
            ihs_patterns.append(ihs_pat)

    return hs_patterns, ihs_patterns


def hs_pattern_return(data: np.ndarray, pat: HSPattern, log_prices: bool = True) -> float:
    entry_price = pat.break_p
    entry_i = pat.break_i
    stop_price = pat.r_shoulder_p

    if pat.inverted:
        tp_price = pat.neck_end + pat.head_height
    else:
        tp_price = pat.neck_end - pat.head_height

    exit_price = -1.0
    for j in range(int(pat.head_width)):
        if entry_i + j >= len(data):
            return float("nan")
        exit_price = data[entry_i + j]
        if pat.inverted and (exit_price > tp_price or exit_price < stop_price):
            break

        if not pat.inverted and (exit_price < tp_price or exit_price > stop_price):
            break

    if pat.inverted:
        if log_prices:
            return float(exit_price - entry_price)
        return float((exit_price - entry_price) / entry_price)
    if log_prices:
        return float(entry_price - exit_price)
    return float(-1 * (exit_price - entry_price) / entry_price)
