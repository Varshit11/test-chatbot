"""AI Filter — trade-quality classifier aligned with the Renko notebook.

Notebook reference (threshold on **test** set, maximise **sum(points)** / points_gained):

  Optimization_Strategies/notebook/Renko/
  Intra Strategy Improvement with only Technical and Multi Timeframe features.ipynb

  - `thresholds = np.arange(0.02, 0.99, 0.005)`
  - For each threshold: keep trades where `predict_proba >= threshold`
  - `total_profit = test_pnl[recommended_indices].sum()`
  - `best_threshold_idx = np.argmax(total_profit_scores)`

Feature source — **your** SMC/ICT implementation (no parallel mini feature stack):

  Optimization_Strategies/Technical Indicators/smc_ict_features_without_future_bars.py
  vendored as `core.features.smc_ict_native`; features are saved once to
  `data/feature_cache/smc_features_current.pkl` and reloaded when bar index matches.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from ..backtest.metrics import compute_metrics
from ..features.smc_cached import compute_smc_features_cached, smc_feature_categories

logger = logging.getLogger(__name__)

_EXCLUDE_FROM_X = {
    "open", "high", "low", "close", "volume", "datetime", "timestamp",
    "Unnamed: 0", "Unnamed: 0.1",
    "win_trade", "points_gained", "pnl", "pnl_pct", "pnl_percentage",
    "side", "side_long", "position", "entry_time", "exit_time",
    "exit_price", "entry_price", "exit_reason", "bars_held", "points",
}


def _select_feature_cols(feat_df: pd.DataFrame) -> List[str]:
    cols = []
    for c in feat_df.columns:
        if c in _EXCLUDE_FROM_X:
            continue
        s = feat_df[c]
        if pd.api.types.is_numeric_dtype(s):
            cols.append(c)
    return cols


def _trade_win_label(t: Dict[str, Any]) -> int:
    """Match notebook: win_trade from points_gained / points when present."""
    if t.get("points") is not None:
        return 1 if float(t["points"]) > 0 else 0
    return 1 if float(t.get("pnl", 0.0)) > 0 else 0


def _trade_points(t: Dict[str, Any]) -> float:
    if t.get("points") is not None:
        return float(t["points"])
    return float(t.get("pnl", 0.0))


def _time_split_index(n: int, test_frac: float = 0.2) -> int:
    if n < 10:
        return max(0, n // 2)
    split = max(int(round(n * (1 - test_frac))), int(n * 0.6))
    split = min(split, n - 5)
    return int(split)


NOTEBOOK_THRESHOLD_GRID = np.arange(0.02, 0.99, 0.005)


def _max_points_threshold_on_test(
    scores_per_trade: np.ndarray,
    pts_per_trade: np.ndarray,
    idxs: List[int],
    test_rows_start: int,
) -> Tuple[float, float]:
    """Notebook: argmax threshold using **only** trades whose feature rows fall in the test split."""
    if not idxs or test_rows_start >= len(idxs):
        return 0.55, float("-inf")
    test_trade_idx = set(idxs[k] for k in range(test_rows_start, len(idxs)))
    if not test_trade_idx:
        return 0.55, float("-inf")

    n_tr = len(scores_per_trade)
    best_thr, best_profit = 0.55, float("-inf")
    for thr in NOTEBOOK_THRESHOLD_GRID:
        tot = 0.0
        for ti in test_trade_idx:
            if 0 <= ti < n_tr and scores_per_trade[ti] >= float(thr):
                tot += float(pts_per_trade[ti]) if ti < len(pts_per_trade) else 0.0
        if tot > best_profit:
            best_profit = tot
            best_thr = float(thr)
    return best_thr, best_profit


def _heuristic_scores_smc(X: pd.DataFrame) -> np.ndarray:
    """When LightGBM cannot train — lightweight_prior from SMC columns only."""
    if X.empty:
        return np.zeros(0)
    n = len(X)
    out = np.full(n, 0.5, dtype=float)
    for i in range(n):
        r = X.iloc[i]
        s = 0.5
        ts = float(r.get("trend_strength", 0) or 0)
        s += float(np.clip(ts / 12.0, -0.2, 0.2))
        act5 = float(r.get("smc_activity_score_5", 0) or 0)
        act10 = float(r.get("smc_activity_score_10", 0) or 0)
        s += float(np.clip((act5 + act10) * 0.015, 0, 0.12))
        bos = float(r.get("is_bos_bullish", 0) or 0) + float(r.get("is_bos_bearish", 0) or 0)
        s += 0.05 * min(bos, 1.0)
        out[i] = max(0.0, min(1.0, s))
    return out


@dataclass
class FilterTrainSummary:
    used_lightgbm: bool = False
    n_trades_total: int = 0
    n_trades_with_features: int = 0
    n_features: int = 0
    feature_cols: List[str] = field(default_factory=list)
    train_size: int = 0
    test_size: int = 0
    train_win_rate: float = 0.0
    test_win_rate: float = 0.0
    train_auc: float = 0.0
    test_auc: float = 0.0
    test_accuracy_at_default: float = 0.0
    iterations: int = 0
    fallback_reason: str = ""
    test_rows_start: int = 0
    notebook_test_points_at_optimal: float = 0.0


@dataclass
class FilterModelResult:
    threshold: float
    scores: List[float] = field(default_factory=list)
    kept_indices: List[int] = field(default_factory=list)
    dropped_indices: List[int] = field(default_factory=list)
    before_metrics: Dict[str, Any] = field(default_factory=dict)
    after_metrics: Dict[str, Any] = field(default_factory=dict)
    after_trades: List[Dict[str, Any]] = field(default_factory=list)
    after_equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    feature_importances: Dict[str, float] = field(default_factory=dict)
    feature_categories: Dict[str, List[str]] = field(default_factory=dict)
    train_summary: FilterTrainSummary = field(default_factory=FilterTrainSummary)
    mode: str = "lightgbm"
    suggested_threshold: float = 0.55
    feature_source: str = "smc_ict_native"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _build_trade_feature_matrix(
    feat_df: pd.DataFrame,
    trades: List[Dict[str, Any]],
    feature_cols: List[str],
) -> Tuple[pd.DataFrame, pd.Series, List[int]]:
    if not trades:
        return pd.DataFrame(columns=feature_cols), pd.Series(dtype=int), []

    if not isinstance(feat_df.index, pd.DatetimeIndex):
        raise ValueError("feat_df must have a DatetimeIndex.")
    feat_df = feat_df.sort_index()
    rows: List[pd.Series] = []
    ys: List[int] = []
    idxs: List[int] = []
    for i, t in enumerate(trades):
        try:
            ts = pd.to_datetime(t.get("entry_time"))
            pos = feat_df.index.searchsorted(ts, side="right") - 1
            if pos < 1 or pos >= len(feat_df):
                continue
            row = feat_df.iloc[pos]
            rows.append(row[feature_cols])
            ys.append(_trade_win_label(t))
            idxs.append(i)
        except Exception:
            continue
    if not rows:
        return pd.DataFrame(columns=feature_cols), pd.Series(dtype=int), []
    X = pd.DataFrame(rows, columns=feature_cols).reset_index(drop=True)
    y = pd.Series(ys, name="win_trade")
    return X, y, idxs


def _train_lightgbm(
    X: pd.DataFrame,
    y: pd.Series,
    test_frac: float = 0.2,
) -> Tuple[Any, FilterTrainSummary, np.ndarray, int]:
    try:
        import lightgbm as lgb
        from sklearn.metrics import roc_auc_score, accuracy_score
    except ImportError as e:
        raise RuntimeError(f"lightgbm/sklearn unavailable: {e}")

    n = len(X)
    summary = FilterTrainSummary(
        used_lightgbm=True,
        n_trades_total=n,
        n_trades_with_features=n,
        n_features=X.shape[1],
        feature_cols=list(X.columns),
        train_size=0,
        test_size=0,
    )

    if n < 30 or y.nunique() < 2:
        raise RuntimeError(
            f"Not enough data for ML: {n} trades, {y.nunique()} classes. "
            f"Need ≥30 trades with both win and loss outcomes."
        )

    split = _time_split_index(n, test_frac)
    summary.test_rows_start = split

    X_train = X.iloc[:split]
    X_test = X.iloc[split:]
    y_train = y.iloc[:split]
    y_test = y.iloc[split:]

    summary.train_size = len(X_train)
    summary.test_size = len(X_test)
    summary.train_win_rate = float(y_train.mean()) if len(y_train) else 0.0
    summary.test_win_rate = float(y_test.mean()) if len(y_test) else 0.0

    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
    params = {
        "objective": "binary",
        "metric": ["binary_logloss", "auc"],
        "learning_rate": 0.03,
        "num_leaves": 15,
        "max_depth": 6,
        "min_child_samples": max(20, len(X_train) // 50),
        "feature_fraction": 0.7,
        "bagging_fraction": 0.7,
        "bagging_freq": 5,
        "lambda_l1": 0.1,
        "lambda_l2": 0.1,
        "verbose": -1,
        "force_col_wise": True,
    }
    callbacks = [lgb.early_stopping(40, verbose=False), lgb.log_evaluation(0)]
    model = lgb.train(
        params,
        train_data,
        num_boost_round=250,
        valid_sets=[train_data, valid_data],
        valid_names=["train", "test"],
        callbacks=callbacks,
    )
    summary.iterations = int(getattr(model, "best_iteration", 0) or 0)

    train_pred = model.predict(X_train, num_iteration=model.best_iteration)
    test_pred = model.predict(X_test, num_iteration=model.best_iteration)
    try:
        if y_train.nunique() > 1:
            summary.train_auc = float(roc_auc_score(y_train, train_pred))
        if y_test.nunique() > 1:
            summary.test_auc = float(roc_auc_score(y_test, test_pred))
    except Exception:
        pass
    try:
        summary.test_accuracy_at_default = float(
            accuracy_score(y_test, (test_pred >= 0.5).astype(int))
        )
    except Exception:
        pass

    full_scores = model.predict(X, num_iteration=model.best_iteration)
    return model, summary, np.asarray(full_scores, dtype=float), split


def _rebuild_equity_curve(trades, original_curve, initial_capital):
    """Walk an equity curve adding each trade's pnl at its exit time.

    Vectorised: scalar ``pd.to_datetime`` per element is ~50µs on Windows,
    so the naive O(curve × thresholds) loop in the executor's threshold sweep
    spent minutes on long backtests. This version converts timestamps once.
    """
    if not original_curve:
        return []
    if not trades:
        return [{"t": pt["t"], "equity": round(float(initial_capital), 2)} for pt in original_curve]

    n = len(original_curve)
    ts_curve = pd.to_datetime([pt["t"] for pt in original_curve]).values
    trade_times_raw = [t.get("exit_time") or t.get("entry_time") for t in trades]
    trade_times = pd.to_datetime(trade_times_raw).values
    trade_pnls = np.array([float(t.get("pnl", 0.0)) for t in trades], dtype=float)

    # Order by exit time for the cumulative walk.
    order = np.argsort(trade_times, kind="stable")
    trade_times = trade_times[order]
    trade_pnls = trade_pnls[order]

    # For each trade find the curve bar it closes at (largest curve_t <= trade_t).
    # Trades that exit before bar 0 land at index 0 and are folded into that bar.
    pos = np.searchsorted(ts_curve, trade_times, side="right") - 1
    pos = np.clip(pos, 0, n - 1)

    pnl_per_bar = np.zeros(n, dtype=float)
    np.add.at(pnl_per_bar, pos, trade_pnls)
    eq_per_bar = float(initial_capital) + np.cumsum(pnl_per_bar)

    curve = [{"t": pt["t"], "equity": round(float(e), 2)} for pt, e in zip(original_curve, eq_per_bar)]
    # Force the last bar to the exact terminal equity (matches old contract: any trades
    # later than the last curve bar still get applied to the final equity).
    if curve:
        curve[-1]["equity"] = round(float(initial_capital) + float(trade_pnls.sum()), 2)
    return curve


def apply_ml_filter(
    df: pd.DataFrame,
    backtest_result: Dict[str, Any],
    *,
    initial_capital: float,
    threshold: float = 0.55,
    instrument: str = "",
    timeframe: str = "",
    use_feature_cache: bool = True,
    use_notebook_optimal_threshold: bool = True,
) -> FilterModelResult:
    """Run ML pipeline on SMC/ICT features. When `use_notebook_optimal_threshold`,
    the applied cutoff is the notebook rule (max **sum(points)** on time-based **test**
    trades); `threshold` is still echoed for UI / audit when override is added later.
    """
    trades = backtest_result.get("trades", []) or []
    before_metrics = backtest_result.get("metrics", {}) or {}
    base_equity = backtest_result.get("equity_curve", []) or []
    pts_per_trade = np.array([_trade_points(t) for t in trades], dtype=float)

    if not trades:
        return FilterModelResult(
            threshold=threshold,
            mode="empty",
            train_summary=FilterTrainSummary(fallback_reason="No trades to score."),
            before_metrics=before_metrics,
            after_metrics=before_metrics,
            after_equity_curve=base_equity,
            suggested_threshold=threshold,
        )

    inst = (instrument or "NA").strip().upper()
    tf = (timeframe or "NA").strip().lower()
    feat_df = compute_smc_features_cached(
        df, instrument=inst, timeframe=tf, use_cache=use_feature_cache
    )
    if feat_df.empty:
        return FilterModelResult(
            threshold=threshold,
            mode="empty",
            train_summary=FilterTrainSummary(fallback_reason="No feature data available."),
            before_metrics=before_metrics,
            after_metrics=before_metrics,
            after_equity_curve=base_equity,
            suggested_threshold=threshold,
        )

    feature_cols = _select_feature_cols(feat_df)
    X_all, y_all, idxs = _build_trade_feature_matrix(feat_df, trades, feature_cols)
    split_row = _time_split_index(len(X_all)) if len(X_all) else 0

    summary = FilterTrainSummary(
        n_trades_total=len(trades),
        n_trades_with_features=len(idxs),
        n_features=len(feature_cols),
        feature_cols=feature_cols,
        test_rows_start=split_row,
    )

    scores_per_trade = np.full(len(trades), 0.5, dtype=float)
    importances: Dict[str, float] = {}
    mode = "empty"

    if X_all.empty:
        summary.fallback_reason = "Could not align trade timestamps to feature rows."
    else:
        try:
            model, train_summary, scores, split_row = _train_lightgbm(X_all, y_all)
            train_summary.n_trades_total = len(trades)
            train_summary.n_trades_with_features = len(idxs)
            summary = train_summary
            scores_per_trade[idxs] = scores
            try:
                gain = model.feature_importance(importance_type="gain")
                total = float(np.sum(gain)) or 1.0
                importances = {n: float(v) / total for n, v in zip(feature_cols, gain)}
            except Exception:
                pass
            mode = "lightgbm"
        except Exception as e:
            logger.warning("LightGBM training failed, SMC heuristic: %s", e)
            scores_h = _heuristic_scores_smc(X_all)
            scores_per_trade[idxs] = scores_h
            summary.fallback_reason = str(e)
            summary.used_lightgbm = False
            summary.test_rows_start = split_row
            importances = {c: 1.0 / max(1, len(feature_cols)) for c in feature_cols[:20]}
            mode = "heuristic"

    suggested_thr, test_pts = _max_points_threshold_on_test(
        scores_per_trade, pts_per_trade, idxs, split_row
    )
    summary.notebook_test_points_at_optimal = float(test_pts) if np.isfinite(test_pts) else 0.0

    effective_thr = float(suggested_thr) if use_notebook_optimal_threshold else float(threshold)

    kept_idx, dropped_idx, kept_trades = [], [], []
    for i, t in enumerate(trades):
        s = float(scores_per_trade[i])
        if s >= effective_thr:
            kept_trades.append(t)
            kept_idx.append(i)
        else:
            dropped_idx.append(i)

    after_eq = _rebuild_equity_curve(kept_trades, base_equity, initial_capital)
    after_metrics = compute_metrics(kept_trades, after_eq, initial_capital)

    categories = smc_feature_categories(feature_cols)

    return FilterModelResult(
        threshold=effective_thr,
        suggested_threshold=float(suggested_thr),
        scores=[float(s) for s in scores_per_trade.tolist()],
        kept_indices=kept_idx,
        dropped_indices=dropped_idx,
        before_metrics=before_metrics,
        after_metrics=after_metrics,
        after_trades=kept_trades,
        after_equity_curve=after_eq,
        feature_importances=importances,
        feature_categories=categories,
        train_summary=summary,
        mode=mode,
        feature_source="smc_ict_native",
    )
