"""AI Filter implementation.

Two modes:
  1. **Heuristic mode** (default, no model required) — scores each trade based
     on context features (RSI extremity, ADX strength, BB position, volatility
     regime). Useful as a fallback when no trained model is loaded.
  2. **Model mode** — loads a pickled LightGBM classifier (and optional
     scaler) and uses `predict_proba` to score each trade entry.

The filter takes the original BacktestResult and returns a FilterResult that
contains only the kept trades + recomputed metrics + a "before vs after"
comparison.
"""
from __future__ import annotations
import os
import pickle
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from ..indicators.trend import ema, adx
from ..indicators.momentum import rsi
from ..indicators.volatility import atr, bollinger_bands
from ..backtest.metrics import compute_metrics


FEATURE_COLUMNS = [
    "rsi_14",
    "adx_14",
    "atr_pct",
    "bb_pos",
    "ret_5",
    "ret_20",
    "ema_diff_pct",
    "vol_ratio",
    "side_long",
]


def build_features(df: pd.DataFrame, trades: List[Dict[str, Any]]) -> pd.DataFrame:
    """Compute a feature row for each trade entry."""
    if not trades:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime")
    df = df.sort_index()

    df["rsi_14"] = rsi(df, 14)
    ax = adx(df, 14)
    df["adx_14"] = ax["adx"]
    df["atr_pct"] = atr(df, 14) / df["close"]
    bb = bollinger_bands(df, 20, 2.0)
    df["bb_pos"] = (df["close"] - bb["lower"]) / (bb["upper"] - bb["lower"])
    df["ret_5"] = df["close"].pct_change(5)
    df["ret_20"] = df["close"].pct_change(20)
    e_fast = ema(df, 9)
    e_slow = ema(df, 50)
    df["ema_diff_pct"] = (e_fast - e_slow) / df["close"]
    if "volume" in df.columns:
        v_avg = df["volume"].rolling(20).mean()
        df["vol_ratio"] = df["volume"] / v_avg.replace(0, np.nan)
    else:
        df["vol_ratio"] = 1.0

    rows = []
    for t in trades:
        ts = pd.to_datetime(t.get("entry_time"))
        try:
            idx = df.index.get_indexer([ts], method="ffill")[0]
            if idx < 0 or idx >= len(df):
                continue
            r = df.iloc[idx]
        except Exception:
            continue
        rows.append({
            "rsi_14":        float(r.get("rsi_14", np.nan)),
            "adx_14":        float(r.get("adx_14", np.nan)),
            "atr_pct":       float(r.get("atr_pct", np.nan)),
            "bb_pos":        float(r.get("bb_pos", np.nan)),
            "ret_5":         float(r.get("ret_5", np.nan)),
            "ret_20":        float(r.get("ret_20", np.nan)),
            "ema_diff_pct":  float(r.get("ema_diff_pct", np.nan)),
            "vol_ratio":     float(r.get("vol_ratio", 1.0)),
            "side_long":     1.0 if t["side"] == "long" else 0.0,
        })
    feats = pd.DataFrame(rows)
    return feats.fillna(feats.median(numeric_only=True)).fillna(0.0)


# ---------------------------------------------------------------------------


@dataclass
class FilterResult:
    threshold: float
    scores: List[float] = field(default_factory=list)
    kept_indices: List[int] = field(default_factory=list)
    dropped_indices: List[int] = field(default_factory=list)
    before_metrics: Dict[str, Any] = field(default_factory=dict)
    after_metrics: Dict[str, Any] = field(default_factory=dict)
    after_trades: List[Dict[str, Any]] = field(default_factory=list)
    after_equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    feature_importances: Dict[str, float] = field(default_factory=dict)
    mode: str = "heuristic"

    def to_dict(self):
        return asdict(self)


class AIFilter:
    """ML-based trade signal filter."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        scaler_path: Optional[str] = None,
        threshold: float = 0.55,
    ):
        self.threshold = threshold
        self.model = None
        self.scaler = None
        self.mode = "heuristic"
        self.feature_names: List[str] = list(FEATURE_COLUMNS)

        if model_path and os.path.exists(model_path):
            try:
                with open(model_path, "rb") as f:
                    self.model = pickle.load(f)
                self.mode = "model"
                if scaler_path and os.path.exists(scaler_path):
                    with open(scaler_path, "rb") as f:
                        self.scaler = pickle.load(f)
            except Exception as e:
                self.model = None
                self.mode = "heuristic"
                # silently fall back; orchestrator surfaces this in metadata

    def score(self, features: pd.DataFrame) -> np.ndarray:
        if features.empty:
            return np.array([])

        if self.mode == "model" and self.model is not None:
            X = features.values
            if self.scaler is not None:
                try:
                    X = self.scaler.transform(X)
                except Exception:
                    pass
            try:
                proba = self.model.predict_proba(X)[:, 1]
                return proba
            except Exception:
                pass  # fall back to heuristic

        # Heuristic score: combine context features into a 0-1 quality score.
        # Penalises:
        #   - RSI very extreme on entry (likely chasing)
        #   - low ADX (no trend)
        #   - very high atr_pct relative to median (volatility shock)
        # Rewards:
        #   - moderate momentum (|ema_diff_pct| > median)
        #   - bb_pos around 0.3-0.7 for trend continuation
        out = []
        for _, r in features.iterrows():
            score = 0.5
            # Trend strength
            adx_v = r.get("adx_14", 20)
            if adx_v >= 25:
                score += 0.10
            elif adx_v < 15:
                score -= 0.10
            # Momentum alignment
            ema_diff = r.get("ema_diff_pct", 0.0)
            side_long = r.get("side_long", 0.0)
            if (side_long == 1 and ema_diff > 0) or (side_long == 0 and ema_diff < 0):
                score += 0.10
            else:
                score -= 0.10
            # RSI extremity
            rsi_v = r.get("rsi_14", 50)
            if 40 <= rsi_v <= 60:
                score += 0.05
            elif rsi_v >= 80 or rsi_v <= 20:
                score -= 0.10
            # BB position
            bb = r.get("bb_pos", 0.5)
            if 0.3 <= bb <= 0.7:
                score += 0.05
            elif bb >= 1.0 or bb <= 0.0:
                score -= 0.05
            # Volatility
            atr_v = r.get("atr_pct", 0.01)
            if atr_v > 0.03:
                score -= 0.05
            score = max(0.0, min(1.0, score))
            out.append(score)
        return np.array(out)

    def feature_importance(self) -> Dict[str, float]:
        if self.mode == "model" and self.model is not None:
            try:
                imp = getattr(self.model, "feature_importances_", None)
                if imp is not None and len(imp) == len(self.feature_names):
                    total = float(imp.sum()) or 1.0
                    return {n: float(v) / total for n, v in zip(self.feature_names, imp)}
            except Exception:
                pass
        # default heuristic weights
        return {
            "adx_14": 0.20, "ema_diff_pct": 0.20, "rsi_14": 0.15,
            "bb_pos": 0.10, "atr_pct": 0.10, "ret_20": 0.10,
            "ret_5": 0.05, "vol_ratio": 0.05, "side_long": 0.05,
        }

    def apply(
        self,
        df: pd.DataFrame,
        backtest_result_dict: Dict[str, Any],
        initial_capital: float,
    ) -> FilterResult:
        trades = backtest_result_dict.get("trades", [])
        before_metrics = backtest_result_dict.get("metrics", {})

        if not trades:
            return FilterResult(
                threshold=self.threshold,
                before_metrics=before_metrics,
                after_metrics=before_metrics,
                after_trades=[],
                after_equity_curve=backtest_result_dict.get("equity_curve", []),
                feature_importances=self.feature_importance(),
                mode=self.mode,
            )

        feats = build_features(df, trades)
        scores = self.score(feats) if not feats.empty else np.array([])

        kept_idx, dropped_idx = [], []
        kept_trades = []
        for i, t in enumerate(trades):
            s = float(scores[i]) if i < len(scores) else 0.5
            if s >= self.threshold:
                kept_trades.append(t)
                kept_idx.append(i)
            else:
                dropped_idx.append(i)

        # rebuild equity curve from kept trades only
        after_eq = _rebuild_equity_curve(
            kept_trades, backtest_result_dict.get("equity_curve", []), initial_capital
        )
        after_metrics = compute_metrics(kept_trades, after_eq, initial_capital)

        return FilterResult(
            threshold=self.threshold,
            scores=[float(s) for s in scores.tolist()],
            kept_indices=kept_idx,
            dropped_indices=dropped_idx,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            after_trades=kept_trades,
            after_equity_curve=after_eq,
            feature_importances=self.feature_importance(),
            mode=self.mode,
        )


def _rebuild_equity_curve(trades, original_curve, initial_capital):
    """Reconstruct an equity curve given only the kept trades.

    We map each trade onto the original curve's timestamps using its exit_time;
    between trades, equity stays flat at the prior level. This is a faithful
    approximation that matches the metrics module's expectations.
    """
    if not original_curve:
        return []
    curve = []
    eq = initial_capital
    sorted_trades = sorted(
        trades, key=lambda t: pd.to_datetime(t.get("exit_time") or t.get("entry_time"))
    )
    ti = 0
    for pt in original_curve:
        t = pd.to_datetime(pt["t"])
        # add any trade that closed at or before this timestamp
        while ti < len(sorted_trades):
            tt = pd.to_datetime(sorted_trades[ti].get("exit_time") or sorted_trades[ti].get("entry_time"))
            if tt <= t:
                eq += float(sorted_trades[ti].get("pnl", 0.0))
                ti += 1
            else:
                break
        curve.append({"t": pt["t"], "equity": round(eq, 2)})
    # any remaining trades go to the last bar
    while ti < len(sorted_trades):
        eq += float(sorted_trades[ti].get("pnl", 0.0))
        ti += 1
    if curve:
        curve[-1]["equity"] = round(eq, 2)
    return curve


def apply_filter(
    df: pd.DataFrame,
    backtest_result_dict: Dict[str, Any],
    initial_capital: float,
    model_path: Optional[str] = None,
    scaler_path: Optional[str] = None,
    threshold: float = 0.55,
) -> FilterResult:
    f = AIFilter(model_path=model_path, scaler_path=scaler_path, threshold=threshold)
    return f.apply(df, backtest_result_dict, initial_capital)
