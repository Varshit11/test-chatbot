"""Pre-built strategy templates used by the chatbot.

These templates correspond to the rule-based strategies in
TradeXpert/marketapi_data_fetcher/algo_methods/hidden_signals/strategies/enterprise/*

For Phase 1 MVP, the LLM PARSER picks one of these templates based on the
user's natural-language request and chooses parameter values. For a future
phase the LLM CODE GENERATOR can synthesise new templates from the parsed
JSON spec.
"""
from __future__ import annotations
import pandas as pd

from .base import StrategyBase, Signal
from ..indicators.trend import ema, adx
from ..indicators.momentum import rsi, macd
from ..indicators.volatility import bollinger_bands, atr
from ..patterns.heikin_ashi import calculate_heikin_ashi


class HeikinAshiEMACross(StrategyBase):
    """Heikin Ashi EMA crossover with trend EMA filter (mirrors heikin_strat.txt)."""

    name = "heikin_ashi_ema_cross"
    description = (
        "Long when the fast EMA crosses above the slow EMA on Heikin Ashi closes "
        "AND price is above the trend EMA. Short on the opposite. Exit on opposite "
        "EMA crossover. Optional ATR-based SL/TP."
    )
    default_params = {
        "ema_fast": 9,
        "ema_slow": 21,
        "ema_trend": 55,
        "use_sl_tp": False,
        "atr_period": 14,
        "atr_sl_mult": 1.5,
        "atr_tp_mult": 3.0,
    }
    param_ranges = {
        "ema_fast": [5, 7, 9, 12],
        "ema_slow": [15, 21, 26, 34],
        "ema_trend": [50, 55, 100, 200],
    }

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        ha = calculate_heikin_ashi(df)
        ha["ema_f"] = ha["ha_close"].ewm(span=self.params["ema_fast"], adjust=False).mean()
        ha["ema_s"] = ha["ha_close"].ewm(span=self.params["ema_slow"], adjust=False).mean()
        ha["ema_t"] = ha["ha_close"].ewm(span=self.params["ema_trend"], adjust=False).mean()
        if self.params.get("use_sl_tp"):
            ha["atr_v"] = atr(df, self.params["atr_period"])
        return ha

    def on_bar(self, i, row, df):
        if i < max(self.params["ema_trend"], self.params["ema_slow"]) + 1:
            return None
        prev = df.iloc[i - 1]
        cross_up = row["ema_f"] > row["ema_s"] and prev["ema_f"] <= prev["ema_s"]
        cross_dn = row["ema_f"] < row["ema_s"] and prev["ema_f"] >= prev["ema_s"]
        price_above = row["close"] > row["ema_t"]
        price_below = row["close"] < row["ema_t"]

        sl = tp = None
        if self.params.get("use_sl_tp"):
            atr_v = row.get("atr_v")
            if atr_v and atr_v == atr_v:
                sl_d = atr_v * self.params["atr_sl_mult"]
                tp_d = atr_v * self.params["atr_tp_mult"]
            else:
                sl_d = tp_d = None
        else:
            sl_d = tp_d = None

        side = self.position.side
        if side == "flat":
            if cross_up and price_above:
                if sl_d:
                    sl = row["close"] - sl_d
                    tp = row["close"] + tp_d
                return Signal("buy", "HA EMA cross-up + above trend EMA", sl=sl, tp=tp)
            if cross_dn and price_below:
                if sl_d:
                    sl = row["close"] + sl_d
                    tp = row["close"] - tp_d
                return Signal("sell", "HA EMA cross-down + below trend EMA", sl=sl, tp=tp)
        elif side == "long" and cross_dn:
            return Signal("exit", "HA EMA cross-down")
        elif side == "short" and cross_up:
            return Signal("exit", "HA EMA cross-up")
        return None

    def entry_rules(self):
        return [
            f"LONG: HA-EMA({self.params['ema_fast']}) crosses above HA-EMA({self.params['ema_slow']}) "
            f"AND close > EMA({self.params['ema_trend']})",
            f"SHORT: HA-EMA({self.params['ema_fast']}) crosses below HA-EMA({self.params['ema_slow']}) "
            f"AND close < EMA({self.params['ema_trend']})",
        ]

    def exit_rules(self):
        rules = ["Opposite HA-EMA crossover exits the position."]
        if self.params.get("use_sl_tp"):
            rules.append(
                f"ATR({self.params['atr_period']})-based TP × {self.params['atr_tp_mult']}, "
                f"SL × {self.params['atr_sl_mult']}."
            )
        return rules

    def indicators_used(self):
        out = [
            "heikin_ashi",
            f"ema({self.params['ema_fast']})",
            f"ema({self.params['ema_slow']})",
            f"ema({self.params['ema_trend']})",
        ]
        if self.params.get("use_sl_tp"):
            out.append(f"atr({self.params['atr_period']})")
        return out


class EMACrossover(StrategyBase):
    """Plain EMA crossover on actual close (no Heikin Ashi)."""

    name = "ema_crossover"
    description = (
        "Long when the fast EMA crosses above the slow EMA on close. Short on the "
        "opposite. Optional ADX filter to require trending market. Supports "
        "point-based TP/SL (in price units) or ATR-based TP/SL. If both TP/SL "
        "are unset, exit only on opposite EMA crossover."
    )
    default_params = {
        "ema_fast": 9,
        "ema_slow": 21,
        "use_adx_filter": False,
        "adx_period": 14,
        "adx_threshold": 20,
        # NEW: point-based TP/SL — interpreted in raw price units. For XAUUSD
        # 1 "point" = $1 move on price (e.g. 4400 → 4405 = 5 points). If both
        # tp_points and sl_points are set, they take priority over ATR.
        "tp_points": 0.0,    # 0 = disabled
        "sl_points": 0.0,    # 0 = disabled
        # ATR-based fallback (used only when tp_points/sl_points are 0)
        "use_sl_tp": False,
        "atr_period": 14,
        "atr_sl_mult": 1.5,
        "atr_tp_mult": 2.5,
    }
    param_ranges = {
        "ema_fast": [5, 9, 12, 20],
        "ema_slow": [13, 21, 26, 50],
        "adx_threshold": [15, 20, 25],
    }

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["ema_f"] = ema(df, self.params["ema_fast"])
        out["ema_s"] = ema(df, self.params["ema_slow"])
        if self.params.get("use_adx_filter"):
            ax = adx(df, self.params["adx_period"])
            out["adx_v"] = ax["adx"]
        # Only compute ATR if we'll actually use it (no point-based override).
        if (
            self.params.get("use_sl_tp")
            and not (self.params.get("tp_points") or self.params.get("sl_points"))
        ):
            out["atr_v"] = atr(df, self.params["atr_period"])
        return out

    def on_bar(self, i, row, df):
        if i < self.params["ema_slow"] + 1:
            return None
        prev = df.iloc[i - 1]
        cross_up = row["ema_f"] > row["ema_s"] and prev["ema_f"] <= prev["ema_s"]
        cross_dn = row["ema_f"] < row["ema_s"] and prev["ema_f"] >= prev["ema_s"]

        if self.params.get("use_adx_filter"):
            adx_ok = row.get("adx_v", 0) >= self.params["adx_threshold"]
        else:
            adx_ok = True

        # Resolve TP/SL distances. Point-based takes priority over ATR.
        sl_d = tp_d = None
        tp_pts = float(self.params.get("tp_points") or 0.0)
        sl_pts = float(self.params.get("sl_points") or 0.0)
        if tp_pts > 0:
            tp_d = tp_pts
        if sl_pts > 0:
            sl_d = sl_pts
        if (sl_d is None and tp_d is None) and self.params.get("use_sl_tp"):
            atr_v = row.get("atr_v")
            if atr_v and atr_v == atr_v:
                sl_d = atr_v * self.params["atr_sl_mult"]
                tp_d = atr_v * self.params["atr_tp_mult"]

        side = self.position.side
        if side == "flat":
            if cross_up and adx_ok:
                sl = row["close"] - sl_d if sl_d else None
                tp = row["close"] + tp_d if tp_d else None
                return Signal("buy", "EMA cross-up", sl=sl, tp=tp)
            if cross_dn and adx_ok:
                sl = row["close"] + sl_d if sl_d else None
                tp = row["close"] - tp_d if tp_d else None
                return Signal("sell", "EMA cross-down", sl=sl, tp=tp)
        elif side == "long" and cross_dn:
            return Signal("exit", "EMA cross-down")
        elif side == "short" and cross_up:
            return Signal("exit", "EMA cross-up")
        return None

    def entry_rules(self):
        adx_clause = (
            f" AND ADX({self.params['adx_period']}) ≥ {self.params['adx_threshold']}"
            if self.params.get("use_adx_filter") else ""
        )
        return [
            f"LONG: EMA({self.params['ema_fast']}) crosses above EMA({self.params['ema_slow']}){adx_clause}",
            f"SHORT: EMA({self.params['ema_fast']}) crosses below EMA({self.params['ema_slow']}){adx_clause}",
        ]

    def exit_rules(self):
        rules = [
            "Opposite EMA crossover always exits the open position.",
        ]
        tp_pts = float(self.params.get("tp_points") or 0.0)
        sl_pts = float(self.params.get("sl_points") or 0.0)
        if tp_pts > 0:
            rules.append(f"TAKE-PROFIT at entry ± {tp_pts:g} points (intra-bar via high/low).")
        if sl_pts > 0:
            rules.append(f"STOP-LOSS at entry ∓ {sl_pts:g} points (intra-bar via high/low).")
        if (tp_pts == 0 and sl_pts == 0) and self.params.get("use_sl_tp"):
            rules.append(
                f"TAKE-PROFIT = entry ± ATR({self.params['atr_period']}) × {self.params['atr_tp_mult']}, "
                f"STOP-LOSS = entry ∓ ATR × {self.params['atr_sl_mult']}."
            )
        return rules

    def indicators_used(self):
        out = [
            f"ema({self.params['ema_fast']})",
            f"ema({self.params['ema_slow']})",
        ]
        if self.params.get("use_adx_filter"):
            out.append(f"adx({self.params['adx_period']})")
        if (
            self.params.get("use_sl_tp")
            and not (self.params.get("tp_points") or self.params.get("sl_points"))
        ):
            out.append(f"atr({self.params['atr_period']})")
        return out


class RSIMeanReversion(StrategyBase):
    """RSI mean-reversion: buy oversold, sell overbought."""

    name = "rsi_mean_reversion"
    description = (
        "Long when RSI crosses up from below the lower threshold; short when RSI "
        "crosses down from above the upper threshold. Exit when RSI returns to the "
        "neutral middle band. Optional trend EMA filter."
    )
    default_params = {
        "rsi_period": 14,
        "rsi_lower": 30,
        "rsi_upper": 70,
        "rsi_exit_mid": 50,
        "use_trend_filter": False,
        "ema_trend": 200,
    }
    param_ranges = {
        "rsi_period": [7, 14, 21],
        "rsi_lower": [20, 25, 30],
        "rsi_upper": [70, 75, 80],
    }

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["rsi_v"] = rsi(df, self.params["rsi_period"])
        if self.params.get("use_trend_filter"):
            out["ema_t"] = ema(df, self.params["ema_trend"])
        return out

    def on_bar(self, i, row, df):
        if i < self.params["rsi_period"] + 1:
            return None
        prev = df.iloc[i - 1]
        cross_up = row["rsi_v"] > self.params["rsi_lower"] and prev["rsi_v"] <= self.params["rsi_lower"]
        cross_dn = row["rsi_v"] < self.params["rsi_upper"] and prev["rsi_v"] >= self.params["rsi_upper"]

        if self.params.get("use_trend_filter"):
            up_ok = row["close"] > row["ema_t"]
            dn_ok = row["close"] < row["ema_t"]
        else:
            up_ok = dn_ok = True

        side = self.position.side
        if side == "flat":
            if cross_up and up_ok:
                return Signal("buy", "RSI exited oversold")
            if cross_dn and dn_ok:
                return Signal("sell", "RSI exited overbought")
        elif side == "long" and row["rsi_v"] >= self.params["rsi_exit_mid"]:
            return Signal("exit", "RSI returned to mid")
        elif side == "short" and row["rsi_v"] <= self.params["rsi_exit_mid"]:
            return Signal("exit", "RSI returned to mid")
        return None

    def entry_rules(self):
        trend = (f" AND close > EMA({self.params['ema_trend']})"
                 if self.params.get("use_trend_filter") else "")
        return [
            f"LONG: RSI({self.params['rsi_period']}) crosses up from below {self.params['rsi_lower']}{trend}",
            f"SHORT: RSI({self.params['rsi_period']}) crosses down from above {self.params['rsi_upper']}{trend.replace('>', '<')}",
        ]

    def exit_rules(self):
        return [f"EXIT: RSI returns to neutral ({self.params['rsi_exit_mid']})."]

    def indicators_used(self):
        out = [f"rsi({self.params['rsi_period']})"]
        if self.params.get("use_trend_filter"):
            out.append(f"ema({self.params['ema_trend']})")
        return out


class BollingerBreakout(StrategyBase):
    """Bollinger band squeeze breakout."""

    name = "bollinger_breakout"
    description = (
        "Long on close above the upper Bollinger band, short on close below the "
        "lower band. Exit on cross back through the middle band."
    )
    default_params = {
        "bb_period": 20,
        "bb_std": 2.0,
        "exit_on_middle": True,
    }
    param_ranges = {
        "bb_period": [10, 20, 30],
        "bb_std": [1.5, 2.0, 2.5],
    }

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        bb = bollinger_bands(df, self.params["bb_period"], self.params["bb_std"])
        out["bb_mid"] = bb["middle"]
        out["bb_up"] = bb["upper"]
        out["bb_lo"] = bb["lower"]
        return out

    def on_bar(self, i, row, df):
        if i < self.params["bb_period"] + 1:
            return None
        prev = df.iloc[i - 1]
        side = self.position.side
        if side == "flat":
            if row["close"] > row["bb_up"] and prev["close"] <= prev["bb_up"]:
                return Signal("buy", "Close above upper Bollinger")
            if row["close"] < row["bb_lo"] and prev["close"] >= prev["bb_lo"]:
                return Signal("sell", "Close below lower Bollinger")
        elif side == "long" and self.params["exit_on_middle"] and row["close"] < row["bb_mid"]:
            return Signal("exit", "Close back through Bollinger middle")
        elif side == "short" and self.params["exit_on_middle"] and row["close"] > row["bb_mid"]:
            return Signal("exit", "Close back through Bollinger middle")
        return None

    def entry_rules(self):
        return [
            f"LONG: close crosses above upper Bollinger band ({self.params['bb_period']}, ±{self.params['bb_std']}σ)",
            f"SHORT: close crosses below lower Bollinger band ({self.params['bb_period']}, ±{self.params['bb_std']}σ)",
        ]

    def exit_rules(self):
        if self.params["exit_on_middle"]:
            return ["EXIT: close crosses back through the middle (SMA) band."]
        return ["EXIT: opposite breakout."]

    def indicators_used(self):
        return [f"bollinger_bands({self.params['bb_period']}, {self.params['bb_std']})"]


class MACDTrend(StrategyBase):
    """MACD trend-following: enter on histogram zero-cross, exit on opposite."""

    name = "macd_trend"
    description = (
        "Long when MACD histogram crosses above zero, short when it crosses below. "
        "Optional trend filter using a long EMA."
    )
    default_params = {
        "fast": 12,
        "slow": 26,
        "signal": 9,
        "use_trend_filter": True,
        "ema_trend": 200,
    }
    param_ranges = {
        "fast": [8, 12, 16],
        "slow": [21, 26, 34],
        "signal": [7, 9, 12],
    }

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        m = macd(df, self.params["fast"], self.params["slow"], self.params["signal"])
        out["macd_h"] = m["hist"]
        if self.params.get("use_trend_filter"):
            out["ema_t"] = ema(df, self.params["ema_trend"])
        return out

    def on_bar(self, i, row, df):
        if i < max(self.params["slow"], self.params.get("ema_trend", 0)) + 1:
            return None
        prev = df.iloc[i - 1]
        cross_up = row["macd_h"] > 0 and prev["macd_h"] <= 0
        cross_dn = row["macd_h"] < 0 and prev["macd_h"] >= 0

        if self.params.get("use_trend_filter"):
            up_ok = row["close"] > row["ema_t"]
            dn_ok = row["close"] < row["ema_t"]
        else:
            up_ok = dn_ok = True

        side = self.position.side
        if side == "flat":
            if cross_up and up_ok:
                return Signal("buy", "MACD hist > 0")
            if cross_dn and dn_ok:
                return Signal("sell", "MACD hist < 0")
        elif side == "long" and cross_dn:
            return Signal("exit", "MACD hist crossed down")
        elif side == "short" and cross_up:
            return Signal("exit", "MACD hist crossed up")
        return None

    def entry_rules(self):
        trend = (f" AND close > EMA({self.params['ema_trend']})"
                 if self.params.get("use_trend_filter") else "")
        return [
            f"LONG: MACD histogram ({self.params['fast']}, {self.params['slow']}, {self.params['signal']}) crosses above 0{trend}",
            f"SHORT: MACD histogram crosses below 0{trend.replace('>', '<')}",
        ]

    def exit_rules(self):
        return ["EXIT: opposite MACD histogram zero-cross."]

    def indicators_used(self):
        out = [f"macd({self.params['fast']}, {self.params['slow']}, {self.params['signal']})"]
        if self.params.get("use_trend_filter"):
            out.append(f"ema({self.params['ema_trend']})")
        return out
