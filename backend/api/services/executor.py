"""Executor: glue between parsed-spec and the core engine.

Every function returns plain JSON-friendly dicts so the orchestrator can stash
them in `Conversation.context` and ship them straight to the frontend.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import logging
import math
import numpy as np
import pandas as pd

from ...core.strategy import get_strategy_class
from ...core.strategy.dynamic_loader import load_strategy_class_from_source
from ...core.backtest import run_backtest, session_breakdown, compute_metrics
from ...core.optimizer import run_optimization
from ...core.ai_filter import apply_ml_filter, apply_filter
from ...core.ai_filter.ml_filter import _rebuild_equity_curve
from ...data import apply_chart, load_bars_only, load_ohlcv
from ...core.insights import compute_rule_based_insights
from ...core.features.smc_cached import materialize_smc_features
from ..config import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_POSITION_SIZE,
)

logger = logging.getLogger(__name__)

_UNIT_DAYS = {
    "day": 1, "days": 1,
    "week": 7, "weeks": 7, "wk": 7, "wks": 7,
    "month": 30, "months": 30, "mo": 30, "mos": 30,
    "year": 365, "years": 365, "yr": 365, "yrs": 365,
}


def _strategy_class_from_parsed(parsed: Dict[str, Any]):
    """Return the strategy class for either a registry template or generated Python."""
    if (
        parsed.get("implementation_mode") == "generated_class"
        and parsed.get("generated_python")
    ):
        return load_strategy_class_from_source(parsed["generated_python"])
    return get_strategy_class(parsed["template"])


def _instantiate_strategy(parsed: Dict[str, Any]):
    """Build a strategy instance from a parsed spec (registry or codegen)."""
    params = parsed.get("parameters") or {}
    return _strategy_class_from_parsed(parsed)(**params)


def _chart_from_parsed(parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    c = parsed.get("chart")
    if isinstance(c, dict) and str(c.get("type", "")).lower() == "renko":
        out: Dict[str, Any] = {"type": "renko", "mode": c.get("mode") or "wicks"}
        bs = c.get("brick_size")
        if bs is not None:
            try:
                bf = float(bs)
                if bf > 0:
                    out["brick_size"] = bf
            except (TypeError, ValueError):
                pass
        return out
    if str(parsed.get("chart_type", "") or "").lower() == "renko":
        out = {"type": "renko", "mode": parsed.get("renko_mode") or "wicks"}
        bs = parsed.get("renko_brick_size")
        if bs is not None:
            try:
                bf = float(bs)
                if bf > 0:
                    out["brick_size"] = bf
            except (TypeError, ValueError):
                pass
        return out
    return None


def _load_for_parsed(parsed: Dict[str, Any], limit: Optional[int] = None) -> pd.DataFrame:
    """Load OHLCV honouring ``parsed['date_range']`` and the optional Renko chart.

    ``date_range`` shape:
        {"type": "relative", "value": <int>, "unit": "day|week|month|year"}
        {"type": "absolute", "from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}
        {"type": "all"}                                # whole catalog (no cap)

    ``limit`` is *only* used by the AI Filter for last-N-bars fallback queries
    where date_range was never set. Backtests must rely on ``date_range`` —
    the legacy ``QUANTFLOW_DATA_LIMIT`` cap no longer applies to backtest loads.
    """
    chart = _chart_from_parsed(parsed)
    instrument = parsed["instrument"]
    timeframe = parsed["timeframe"]
    dr = parsed.get("date_range") or {"type": "all"}
    dr_type = (dr.get("type") or "all").lower()

    if dr_type == "relative" and dr.get("value") and dr.get("unit"):
        days = int(dr["value"]) * _UNIT_DAYS.get(dr["unit"].rstrip("s") + "s", 30)
        all_df = load_bars_only(instrument, timeframe)
        if all_df.empty:
            return all_df
        end = all_df.index[-1]
        start = end - timedelta(days=days)
        sub = all_df.loc[start:end]
        return apply_chart(sub, chart)

    if dr_type == "absolute" and (dr.get("from") or dr.get("to")):
        return load_ohlcv(
            instrument, timeframe,
            from_date=dr.get("from"), to_date=dr.get("to"),
            limit=limit, chart=chart,
        )

    return load_ohlcv(instrument, timeframe, limit=limit, chart=chart)


def _slim_equity(curve: List[Dict[str, Any]], max_points: int = 600) -> List[Dict[str, Any]]:
    """Down-sample equity curve so the JSON payload to the frontend stays small."""
    n = len(curve)
    if n <= max_points:
        return curve
    step = max(1, n // max_points)
    return curve[::step] + ([curve[-1]] if (n - 1) % step != 0 else [])


def execute_backtest(parsed: Dict[str, Any]) -> Dict[str, Any]:
    instrument = parsed["instrument"]
    timeframe = parsed["timeframe"]
    params = parsed.get("parameters") or {}

    df = _load_for_parsed(parsed)

    StratCls = _strategy_class_from_parsed(parsed)
    strat = StratCls(**params)

    # Capture the rules + code BEFORE running so the user can see exactly what
    # is about to execute. (Side effect: forces param validation early.)
    explain = strat.explain()
    if parsed.get("generated_python"):
        explain["full_strategy_source"] = parsed["generated_python"]
        explain["implementation_mode"] = "generated_class"
    else:
        explain["implementation_mode"] = "registry_template"

    res = run_backtest(
        strat, df, instrument=instrument, timeframe=timeframe,
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        position_size=DEFAULT_POSITION_SIZE,
    )
    out = res.to_dict()
    full_trades = out["trades"]
    out["equity_curve"] = _slim_equity(out["equity_curve"])
    out["drawdown_curve"] = _slim_equity(out["drawdown_curve"])
    out["bars_used"] = len(df)
    out["from"] = str(df.index[0]) if len(df) else None
    out["to"] = str(df.index[-1]) if len(df) else None
    out["date_range"] = parsed.get("date_range")
    out["explain"] = explain
    out["session_stats"] = session_breakdown(full_trades)
    out["rule_based_insights"] = compute_rule_based_insights(full_trades, ohlcv=df)
    ch = _chart_from_parsed(parsed)
    if ch:
        out["chart"] = {
            "type": ch["type"],
            "mode": ch.get("mode"),
            "brick_size": ch.get("brick_size"),
            "bars_after_transform": len(df),
        }
    # Keep **all** trades in context so AI filter never replays a 1k+ trade backtest.
    # `trades_truncated` is only a UI hint (chat meta may preview fewer rows).
    out["trades"] = full_trades
    out["full_trade_count"] = len(full_trades)
    out["trades_truncated"] = len(full_trades) > 500
    # Materialize SMC feature frame to disk so AI filter only loads (read_pickle), not recomputes.
    if len(df):
        try:
            materialize_smc_features(df, instrument=instrument, timeframe=timeframe)
        except Exception:
            logger.warning("SMC feature materialization after backtest failed", exc_info=True)
    return out


def execute_strategy_finder(parsed: Dict[str, Any], objective: str = "sharpe_ratio",
                            top_k: Optional[int] = None,
                            param_ranges_override: Optional[Dict[str, list]] = None) -> Dict[str, Any]:
    template = parsed.get("template") or "custom_generated"
    instrument = parsed["instrument"]
    timeframe = parsed["timeframe"]

    # Works for both built-in templates AND AI-generated strategy classes; the
    # optimizer only needs a class with default_params and a callable backtest.
    StratCls = _strategy_class_from_parsed(parsed)
    fixed = dict(parsed["parameters"])
    # Source of truth for "what params does this strategy actually accept" is
    # default_params on the class (anything in default_params is a valid knob).
    # The hard-coded param_ranges class attribute is just a fallback grid; we
    # do NOT use it to filter the override or auto-fill missing params, or
    # we'd silently drop Claude-proposed sweeps and add back ones nobody asked for.
    accepted_params = set((StratCls.default_params or {}).keys())
    fallback_ranges = {k: list(v) for k, v in (StratCls.param_ranges or {}).items()}

    if param_ranges_override:
        ranges: Dict[str, list] = {}
        for k, vals in param_ranges_override.items():
            if not vals:
                continue
            if accepted_params and k not in accepted_params:
                logger.warning(
                    "execute_strategy_finder: dropping unknown param '%s' for template '%s'",
                    k, template,
                )
                continue
            ranges[k] = list(vals)
        if not ranges:
            ranges = fallback_ranges
    else:
        ranges = fallback_ranges
    for k in ranges.keys():
        fixed.pop(k, None)

    # ─── Speed budget ────────────────────────────────────────────────────────
    # Bar-by-bar backtest × N combos × walk-forward splits is the bottleneck.
    # We cap to 3000 bars + 2 walk-forward splits for the grid search so the
    # full table comes back in ≈30s (vs. 90s+ before).
    sf_limit = 3000
    df = _load_for_parsed(parsed, limit=sf_limit)

    # Always return ALL combos — the UI ranks/sorts them locally.
    n_combos = 1
    for v in ranges.values():
        n_combos *= max(1, len(v))
    if top_k is None:
        top_k = max(n_combos, 50)

    opt = run_optimization(
        StratCls,
        df,
        param_ranges=ranges,
        fixed_params=fixed,
        objective=objective,
        top_k=top_k,
        backtester_kwargs={
            "initial_capital": DEFAULT_INITIAL_CAPITAL,
            "position_size": DEFAULT_POSITION_SIZE,
        },
        instrument=instrument,
        timeframe=timeframe,
        walk_forward_splits=2,
    )
    out = opt.to_dict()
    out["best_equity_curve"] = _slim_equity(out.get("best_equity_curve") or [])
    out["param_ranges"] = {k: list(v) for k, v in ranges.items()}
    out["fixed_params"] = fixed
    out["bars_used"] = len(df)
    out["from"] = str(df.index[0]) if len(df) else None
    out["to"] = str(df.index[-1]) if len(df) else None
    # Slim ranked list: drop infinite/NaN-valued entries that would break JSON
    cleaned = []
    for row in out.get("ranked", []):
        m = row.get("metrics") or {}
        if not isinstance(m, dict):
            continue
        # Drop any entry that errored
        if "error" in m:
            continue
        for k, v in list(m.items()):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                m[k] = 0.0
        cleaned.append(row)
    out["ranked"] = cleaned
    return out


def execute_ai_filter(parsed: Dict[str, Any], backtest_result: Dict[str, Any],
                      threshold: float = 0.55,
                      model_path: Optional[str] = None,
                      scaler_path: Optional[str] = None) -> Dict[str, Any]:
    """Run the ML AI Filter end-to-end:

       (1) load SMC/ICT features per bar (cached Parquet of your notebook code),
       (2) align trade entries to feature rows (no look-ahead),
       (3) target win_trade from points (or pnl) like the notebook,
       (4) time-based LightGBM split,
       (5) score all trades; **optimal threshold** = argmax sum(points) on **test**
           rows (same grid as notebook: 0.02–0.99 step 0.005),
       (6) apply that threshold to **all** trades for the filtered equity curve.
    """
    df = _load_for_parsed(parsed)

    ctx_trades = list(backtest_result.get("trades") or [])
    ctx_metrics = backtest_result.get("metrics")
    ctx_equity = backtest_result.get("equity_curve")
    ctx_full_n = int(backtest_result.get("full_trade_count") or len(ctx_trades))
    initial_capital = DEFAULT_INITIAL_CAPITAL

    if (
        ctx_trades
        and isinstance(ctx_metrics, dict)
        and ctx_equity
        and ctx_full_n > 0
        and len(ctx_trades) == ctx_full_n
    ):
        trades = ctx_trades
        before_metrics = ctx_metrics
        base_equity = ctx_equity
        full_trade_count = len(trades)
    else:
        # UI may only store the last 500 trades — replay once for the full list for training.
        strat = _instantiate_strategy(parsed)
        full_res = run_backtest(
            strat,
            df,
            instrument=parsed["instrument"],
            timeframe=parsed["timeframe"],
            initial_capital=initial_capital,
            position_size=DEFAULT_POSITION_SIZE,
        ).to_dict()
        trades = full_res["trades"]
        full_trade_count = len(trades)
        before_metrics = full_res["metrics"]
        base_equity = full_res["equity_curve"]
        if len(df):
            try:
                materialize_smc_features(
                    df,
                    instrument=parsed["instrument"],
                    timeframe=parsed["timeframe"],
                )
            except Exception:
                logger.warning(
                    "SMC feature materialization after replay backtest failed", exc_info=True
                )

    fresh_bt = {
        "trades": trades,
        "metrics": before_metrics,
        "equity_curve": base_equity,
    }

    result = apply_ml_filter(
        df,
        fresh_bt,
        initial_capital=initial_capital,
        threshold=threshold,
        instrument=parsed.get("instrument") or "",
        timeframe=parsed.get("timeframe") or "",
        use_feature_cache=True,
        use_notebook_optimal_threshold=True,
    )

    scores_list = list(result.scores) if result.scores else []

    # Threshold sweep using the trained model's predict_proba scores.
    def metrics_at(thr: float) -> Dict[str, Any]:
        kept_idx, dropped_idx, kept_trades = [], [], []
        for i, t in enumerate(trades):
            s = scores_list[i] if i < len(scores_list) else 0.5
            if s >= thr:
                kept_trades.append(t)
                kept_idx.append(i)
            else:
                dropped_idx.append(i)
        eq = _rebuild_equity_curve(kept_trades, base_equity, initial_capital)
        m = compute_metrics(kept_trades, eq, initial_capital)
        return {
            "threshold": round(float(thr), 2),
            "kept": len(kept_idx),
            "dropped": len(dropped_idx),
            "kept_pct": round(len(kept_idx) / max(1, len(trades)) * 100, 1),
            "total_return_pct": m.get("total_return_pct", 0.0),
            "sharpe_ratio": m.get("sharpe_ratio", 0.0),
            "win_rate_pct": m.get("win_rate_pct", 0.0),
            "max_drawdown_pct": m.get("max_drawdown_pct", 0.0),
            "profit_factor": m.get("profit_factor", 0.0),
            "expectancy": m.get("expectancy", 0.0),
            "avg_trade": m.get("avg_trade", 0.0),
            "total_points": m.get("total_points", 0.0),
            "avg_points": m.get("avg_points", 0.0),
        }

    sweep_thresholds = list(np.round(np.arange(0.02, 0.99, 0.02), 3))
    threshold_sweep = [metrics_at(t) for t in sweep_thresholds]

    # Always pick the threshold that maximises total points across the full
    # trade book, requiring ≥10% of trades kept so we don't latch onto a single
    # lucky outlier. Falls back to the notebook-optimal threshold only if the
    # sweep is empty for some reason.
    requested_threshold = float(threshold)
    chosen_threshold = float(result.threshold)
    used_fallback_threshold = False

    if len(trades) > 0 and threshold_sweep:
        min_keep = max(1, int(0.10 * len(trades)))
        candidates = [r for r in threshold_sweep if r["kept"] >= min_keep]
        if candidates:
            best = max(candidates, key=lambda r: (r["total_points"], r["sharpe_ratio"]))
            chosen_threshold = float(best["threshold"])
            used_fallback_threshold = True
            new_kept_idx, new_dropped_idx, new_kept = [], [], []
            for i, t in enumerate(trades):
                s = scores_list[i] if i < len(scores_list) else 0.5
                if s >= chosen_threshold:
                    new_kept.append(t)
                    new_kept_idx.append(i)
                else:
                    new_dropped_idx.append(i)
            new_eq = _rebuild_equity_curve(new_kept, base_equity, initial_capital)
            new_after_metrics = compute_metrics(new_kept, new_eq, initial_capital)
            result.kept_indices = new_kept_idx
            result.dropped_indices = new_dropped_idx
            result.after_metrics = new_after_metrics
            result.after_equity_curve = new_eq

    # Per-trade scoring table for the UI
    per_trade = []
    for i, t in enumerate(trades):
        s = scores_list[i] if i < len(scores_list) else 0.5
        per_trade.append({
            "index": i,
            "entry_time": t.get("entry_time"),
            "exit_time": t.get("exit_time"),
            "side": t.get("side"),
            "pnl": t.get("pnl"),
            "points": t.get("points"),
            "score": round(float(s), 3),
            "kept_at_default": s >= chosen_threshold,
        })

    importances_full = result.feature_importances or {}
    # Top-25 by importance for the UI
    top_importances = dict(
        sorted(importances_full.items(), key=lambda kv: kv[1], reverse=True)[:25]
    )

    train_summary = result.train_summary
    return {
        "mode": result.mode,
        "threshold": chosen_threshold,
        "requested_threshold": threshold,
        "auto_picked_threshold": used_fallback_threshold,
        "notebook_optimal_threshold": round(float(result.suggested_threshold), 4),
        "scores": scores_list,
        "feature_columns": train_summary.feature_cols,
        "feature_importances": importances_full,
        "top_feature_importances": top_importances,
        "feature_categories": result.feature_categories or {},
        "per_trade": per_trade,
        "kept_indices": result.kept_indices,
        "dropped_indices": result.dropped_indices,
        "before_metrics": before_metrics,
        "after_metrics": result.after_metrics,
        "after_equity_curve": _slim_equity(result.after_equity_curve),
        "threshold_sweep": threshold_sweep,
        "total_trades": len(trades),
        "full_trade_count": full_trade_count,
        "model_meta": {
            "used_lightgbm": train_summary.used_lightgbm,
            "n_trades_with_features": train_summary.n_trades_with_features,
            "n_features": train_summary.n_features,
            "train_size": train_summary.train_size,
            "test_size": train_summary.test_size,
            "train_win_rate": round(train_summary.train_win_rate, 4),
            "test_win_rate": round(train_summary.test_win_rate, 4),
            "train_auc": round(train_summary.train_auc, 4),
            "test_auc": round(train_summary.test_auc, 4),
            "test_accuracy_at_default": round(train_summary.test_accuracy_at_default, 4),
            "iterations": train_summary.iterations,
            "fallback_reason": train_summary.fallback_reason,
            "test_rows_start": train_summary.test_rows_start,
            "notebook_test_points_at_optimal": round(train_summary.notebook_test_points_at_optimal, 4),
            "suggested_threshold": round(float(result.suggested_threshold), 4),
            "feature_source": getattr(result, "feature_source", "smc_ict_native"),
        },
    }


