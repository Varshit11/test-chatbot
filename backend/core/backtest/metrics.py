"""Backtest performance metrics."""
from __future__ import annotations
from typing import Any, Dict, List
import math
import numpy as np


def compute_metrics(
    trades: List[Dict[str, Any]],
    equity_curve: List[Dict[str, Any]],
    initial_capital: float,
) -> Dict[str, Any]:
    n_trades = len(trades)

    if not equity_curve:
        return _empty_metrics()

    eq = np.array([p["equity"] for p in equity_curve], dtype=float)
    final_equity = float(eq[-1])
    total_return_pct = (final_equity / initial_capital - 1) * 100 if initial_capital else 0.0

    # Drawdown stats
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    max_dd_pct = float(dd.min() * 100) if len(dd) else 0.0

    # Returns (per-bar) for Sharpe / Sortino
    returns = np.diff(eq) / eq[:-1]
    returns = returns[~np.isnan(returns) & ~np.isinf(returns)]
    if len(returns) > 1 and returns.std() > 0:
        sharpe = float(np.sqrt(252) * returns.mean() / returns.std())
        downside = returns[returns < 0]
        if len(downside) and downside.std() > 0:
            sortino = float(np.sqrt(252) * returns.mean() / downside.std())
        else:
            sortino = 0.0
    else:
        sharpe = 0.0
        sortino = 0.0

    if n_trades == 0:
        win_rate = 0.0
        avg_win = 0.0
        avg_loss = 0.0
        profit_factor = 0.0
        expectancy = 0.0
        avg_trade = 0.0
        best_trade = 0.0
        worst_trade = 0.0
        long_trades = 0
        short_trades = 0
        gross_profit = 0.0
        gross_loss = 0.0
        total_points = 0.0
        avg_points = 0.0
        avg_points_win = 0.0
        avg_points_loss = 0.0
        best_points = 0.0
        worst_points = 0.0
    else:
        pnls = [t["pnl"] for t in trades]
        # `points` is the directional price-distance per trade (pre-size). We
        # fall back to `pnl / size` if a trade was logged before the points
        # field was added.
        pts = []
        for t in trades:
            if "points" in t and t["points"] is not None:
                pts.append(float(t["points"]))
            else:
                # legacy fallback — pnl as currency, treat as points for size=1
                pts.append(float(t.get("pnl", 0.0)))
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        gross_profit = float(sum(wins))
        gross_loss = float(abs(sum(losses)))
        win_rate = len(wins) / n_trades * 100
        avg_win = float(np.mean(wins)) if wins else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (math.inf if gross_profit > 0 else 0.0)
        if not math.isfinite(profit_factor):
            profit_factor = 999.0
        expectancy = float(np.mean(pnls)) if pnls else 0.0
        avg_trade = expectancy
        best_trade = float(max(pnls))
        worst_trade = float(min(pnls))
        long_trades = sum(1 for t in trades if t["side"] == "long")
        short_trades = sum(1 for t in trades if t["side"] == "short")
        # Points-based aggregates
        win_pts = [p for p in pts if p > 0]
        loss_pts = [p for p in pts if p < 0]
        total_points = float(sum(pts))
        avg_points = float(np.mean(pts)) if pts else 0.0
        avg_points_win = float(np.mean(win_pts)) if win_pts else 0.0
        avg_points_loss = float(np.mean(loss_pts)) if loss_pts else 0.0
        best_points = float(max(pts)) if pts else 0.0
        worst_points = float(min(pts)) if pts else 0.0

    cagr = _cagr(eq, equity_curve)

    return {
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "cagr_pct": round(cagr, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "n_trades": n_trades,
        "long_trades": long_trades,
        "short_trades": short_trades,
        "win_rate_pct": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "avg_trade": round(avg_trade, 2),
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        # Points-based — directional price-distance gained, pre-size & pre-commission.
        # For 1 unit / 1 contract this is identical to pnl in price units.
        "total_points": round(total_points, 2),
        "avg_points": round(avg_points, 2),
        "avg_points_win": round(avg_points_win, 2),
        "avg_points_loss": round(avg_points_loss, 2),
        "best_points": round(best_points, 2),
        "worst_points": round(worst_points, 2),
    }


def _cagr(eq: np.ndarray, curve: List[Dict[str, Any]]) -> float:
    if len(curve) < 2 or eq[0] == 0:
        return 0.0
    try:
        from datetime import datetime
        t0 = datetime.fromisoformat(curve[0]["t"])
        t1 = datetime.fromisoformat(curve[-1]["t"])
        years = max((t1 - t0).total_seconds() / (365.25 * 24 * 3600), 1e-6)
        if years <= 0 or eq[0] <= 0:
            return 0.0
        return float(((eq[-1] / eq[0]) ** (1.0 / years) - 1.0) * 100)
    except Exception:
        return 0.0


def _empty_metrics() -> Dict[str, Any]:
    return {
        "initial_capital": 0,
        "final_equity": 0,
        "total_return_pct": 0,
        "cagr_pct": 0,
        "max_drawdown_pct": 0,
        "sharpe_ratio": 0,
        "sortino_ratio": 0,
        "n_trades": 0,
        "long_trades": 0,
        "short_trades": 0,
        "win_rate_pct": 0,
        "avg_win": 0,
        "avg_loss": 0,
        "avg_trade": 0,
        "best_trade": 0,
        "worst_trade": 0,
        "profit_factor": 0,
        "expectancy": 0,
        "gross_profit": 0,
        "gross_loss": 0,
        "total_points": 0,
        "avg_points": 0,
        "avg_points_win": 0,
        "avg_points_loss": 0,
        "best_points": 0,
        "worst_points": 0,
    }
