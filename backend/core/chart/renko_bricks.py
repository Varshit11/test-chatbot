"""
Renko brick construction — aligned with
`marketapi_data_fetcher/.../advance_renko_strategy_vFinal.py` (Renko class +
`renko_df` modes). No plotting dependencies (matplotlib/mplfinance stripped).
"""
from __future__ import annotations
from typing import Optional, List

import numpy as np
import pandas as pd

_MODE_dict = [
    "normal",
    "wicks",
    "nongap",
    "reverse-wicks",
    "reverse-nongap",
    "fake-r-wicks",
    "fake-r-nongap",
]


class Renko:
    def __init__(
        self,
        df: pd.DataFrame,
        brick_size: float,
        add_columns: Optional[List[str]] = None,
        show_progress: bool = False,
    ):
        if brick_size is None or brick_size <= 0:
            raise ValueError("brick_size cannot be 'None' or '<= 0'")
        if "datetime" not in df.columns:
            df = df.copy()
            df["datetime"] = df.index
        if "close" not in df.columns:
            raise ValueError("Column 'close' doesn't exist!")
        if add_columns is not None:
            if not set(add_columns).issubset(df.columns):
                raise ValueError(f"One or more of {add_columns} columns don't exist!")

        self._brick_size = brick_size
        self._custom_columns = add_columns
        self._df_len = len(df["close"])
        self._show_progress = show_progress

        first_close = df["close"].iat[0]
        initial_price = (first_close // brick_size) * brick_size
        self._rsd = {
            "origin_index": [0],
            "date": [df["datetime"].iat[0]],
            "price": [initial_price],
            "direction": [0],
            "wick": [initial_price],
            "volume": [1],
        }
        if add_columns is not None:
            for name in add_columns:
                self._rsd.update({name: [df[name].iat[0]]})

        self._wick_min_i = initial_price
        self._wick_max_i = initial_price
        self._volume_i = 1

        for i in range(1, self._df_len):
            self._add_prices(i, df)

    def _add_prices(self, i, df):
        df_close = df["close"].iat[i]
        self._wick_min_i = df_close if df_close < self._wick_min_i else self._wick_min_i
        self._wick_max_i = df_close if df_close > self._wick_max_i else self._wick_max_i
        self._volume_i += 1

        last_price = self._rsd["price"][-1]
        current_n_bricks = (df_close - last_price) / self._brick_size
        current_direction = np.sign(current_n_bricks)
        if current_direction == 0:
            return
        last_direction = self._rsd["direction"][-1]
        is_same_direction = (current_direction > 0 and last_direction >= 0) or (
            current_direction < 0 and last_direction <= 0
        )

        total_same_bricks = current_n_bricks if is_same_direction else 0
        if not is_same_direction and abs(current_n_bricks) >= 2:
            self._add_brink_loop(df, i, 2, current_direction, current_n_bricks)
            total_same_bricks = current_n_bricks - 2 * current_direction

        for _ in range(abs(int(total_same_bricks))):
            self._add_brink_loop(df, i, 1, current_direction, current_n_bricks)

        if self._show_progress:
            print(f"\r {round(float((i + 1) / self._df_len * 100), 2)}%", end="")

    def _add_brink_loop(self, df, i, renko_multiply, current_direction, current_n_bricks):
        last_price = self._rsd["price"][-1]
        renko_price = last_price + (current_direction * renko_multiply * self._brick_size)
        wick = self._wick_min_i if current_n_bricks > 0 else self._wick_max_i

        to_add = [i, df["datetime"].iat[i], renko_price, current_direction, wick, self._volume_i]
        for name, add in zip(list(self._rsd.keys()), to_add):
            self._rsd[name].append(add)
        if self._custom_columns is not None:
            for name in self._custom_columns:
                self._rsd[name].append(df[name].iat[i])

        self._volume_i = 1
        self._wick_min_i = renko_price if current_n_bricks > 0 else self._wick_min_i
        self._wick_max_i = renko_price if current_n_bricks < 0 else self._wick_max_i

    def renko_df(self, mode: str = "wicks") -> pd.DataFrame:
        if mode not in _MODE_dict:
            raise ValueError(f"Only {_MODE_dict} options are valid.")

        dates = self._rsd["date"]
        prices = self._rsd["price"]
        directions = self._rsd["direction"]
        wicks = self._rsd["wick"]
        volumes = self._rsd["volume"]
        indexes = list(range(len(prices)))
        brick_size = self._brick_size

        df_dict = {
            "datetime": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }
        if self._custom_columns is not None:
            for name in self._custom_columns:
                df_dict.update({name: []})

        reverse_rule = mode in ["normal", "wicks", "reverse-wicks", "fake-r-wicks"]
        fake_reverse_rule = mode in ["fake-r-nongap", "fake-r-wicks"]
        same_direction_rule = mode in ["wicks", "nongap"]

        prev_direction = 0
        prev_close = 0
        prev_close_up = 0
        prev_close_down = 0
        for price, direction, date, wick, volume, index in zip(
            prices, directions, dates, wicks, volumes, indexes
        ):
            if direction != 0:
                df_dict["datetime"].append(date)
                df_dict["close"].append(price)
                df_dict["volume"].append(volume)

            if direction == 1.0:
                df_dict["high"].append(price)
                if self._custom_columns is not None:
                    for name in self._custom_columns:
                        df_dict[name].append(self._rsd[name][index])
                if prev_direction == 1:
                    df_dict["open"].append(wick if mode == "nongap" else prev_close_up)
                    df_dict["low"].append(wick if same_direction_rule else prev_close_up)
                else:
                    if reverse_rule:
                        df_dict["open"].append(prev_close + brick_size)
                    elif mode == "fake-r-nongap":
                        df_dict["open"].append(prev_close_down)
                    else:
                        df_dict["open"].append(wick)

                    if mode == "normal":
                        df_dict["low"].append(prev_close + brick_size)
                    elif fake_reverse_rule:
                        df_dict["low"].append(prev_close_down)
                    else:
                        df_dict["low"].append(wick)
                prev_close_up = price
            elif direction == -1.0:
                df_dict["low"].append(price)
                if self._custom_columns is not None:
                    for name in self._custom_columns:
                        df_dict[name].append(self._rsd[name][index])
                if prev_direction == -1:
                    df_dict["open"].append(wick if mode == "nongap" else prev_close_down)
                    df_dict["high"].append(wick if same_direction_rule else prev_close_down)
                else:
                    if reverse_rule:
                        df_dict["open"].append(prev_close - brick_size)
                    elif mode == "fake-r-nongap":
                        df_dict["open"].append(prev_close_up)
                    else:
                        df_dict["open"].append(wick)

                    if mode == "normal":
                        df_dict["high"].append(prev_close - brick_size)
                    elif fake_reverse_rule:
                        df_dict["high"].append(prev_close_up)
                    else:
                        df_dict["high"].append(wick)
                prev_close_down = price
            else:
                df_dict["datetime"].append(np.nan)
                df_dict["low"].append(np.nan)
                df_dict["close"].append(np.nan)
                df_dict["high"].append(np.nan)
                df_dict["open"].append(np.nan)
                df_dict["volume"].append(np.nan)
                if self._custom_columns is not None:
                    for name in self._custom_columns:
                        df_dict[name].append(np.nan)

            prev_direction = direction
            prev_close = price

        df_out = pd.DataFrame(df_dict)
        df_out.drop(df_out.head(2).index, inplace=True)
        df_out.index = pd.DatetimeIndex(df_out["datetime"])
        df_out.drop(columns=["datetime"], inplace=True)
        return df_out


def ohlcv_to_renko_df(
    df: pd.DataFrame,
    brick_size: Optional[float] = None,
    mode: str = "wicks",
) -> pd.DataFrame:
    """Build Renko OHLCV from a time-based OHLCV frame (DatetimeIndex or datetime column)."""
    if df is None or len(df) == 0:
        return df
    mode = (mode or "wicks").strip()
    work = df.copy()
    work = work.reset_index()
    first_col = work.columns[0]
    if first_col != "datetime":
        work = work.rename(columns={first_col: "datetime"})
    needed = ["open", "high", "low", "close", "volume"]
    for c in needed:
        if c not in work.columns:
            raise ValueError(f"Renko input missing column '{c}'")
    sub = work[["datetime"] + needed].copy()
    for c in needed:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna(subset=["datetime", "close"])

    bs = brick_size
    if bs is None or (isinstance(bs, (int, float)) and float(bs) <= 0):
        med_close = float(sub["close"].median())
        hl_rng = float((sub["high"] - sub["low"]).median())
        bs = max(med_close * 0.001, hl_rng * 0.25, 1e-9)

    r = Renko(sub, float(bs), show_progress=False)
    out = r.renko_df(mode)
    return out.astype(
        {c: float for c in ("open", "high", "low", "close", "volume") if c in out.columns},
        errors="ignore",
    )


def renko_modes() -> list:
    return list(_MODE_dict)
