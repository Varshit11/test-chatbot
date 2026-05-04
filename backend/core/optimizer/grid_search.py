"""Parameter optimisation via grid search + optional walk-forward validation."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from itertools import product
from typing import Any, Dict, List, Optional, Sequence, Type
import pandas as pd

from ..strategy.base import StrategyBase
from ..backtest.engine import Backtester, BacktestResult


OBJECTIVE_FNS = {
    "sharpe_ratio":   lambda m: m.get("sharpe_ratio", 0.0),
    "total_return":   lambda m: m.get("total_return_pct", 0.0),
    "profit_factor":  lambda m: m.get("profit_factor", 0.0),
    "expectancy":     lambda m: m.get("expectancy", 0.0),
    "cagr":           lambda m: m.get("cagr_pct", 0.0),
    "win_rate":       lambda m: m.get("win_rate_pct", 0.0),
    # composite: total return penalised by drawdown
    "calmar":         lambda m: (
        m.get("total_return_pct", 0.0) / abs(m.get("max_drawdown_pct", -1e-9)) if m.get("max_drawdown_pct", 0) else 0.0
    ),
}


@dataclass
class OptimizerResult:
    objective: str
    ranked: List[Dict[str, Any]] = field(default_factory=list)   # top-N param combos with metrics
    best_params: Dict[str, Any] = field(default_factory=dict)
    best_metrics: Dict[str, Any] = field(default_factory=dict)
    best_equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    n_combos: int = 0
    walk_forward: Optional[Dict[str, Any]] = None

    def to_dict(self):
        return asdict(self)


class StrategyFinder:
    def __init__(
        self,
        backtester_kwargs: Optional[Dict[str, Any]] = None,
        objective: str = "sharpe_ratio",
        top_k: int = 10,
    ):
        self.bt_kwargs = backtester_kwargs or {}
        self.objective = objective
        self.top_k = top_k

    def search(
        self,
        strategy_cls: Type[StrategyBase],
        df: pd.DataFrame,
        param_ranges: Dict[str, Sequence],
        fixed_params: Optional[Dict[str, Any]] = None,
        instrument: str = "",
        timeframe: str = "",
        walk_forward_splits: int = 0,
    ) -> OptimizerResult:
        fixed_params = fixed_params or {}
        keys = list(param_ranges.keys())
        if not keys:
            raise ValueError("Provide at least one parameter to optimise.")

        combos = list(product(*[param_ranges[k] for k in keys]))
        scored: List[Dict[str, Any]] = []
        obj_fn = OBJECTIVE_FNS.get(self.objective, OBJECTIVE_FNS["sharpe_ratio"])

        for combo in combos:
            params = {**fixed_params, **dict(zip(keys, combo))}
            try:
                strat = strategy_cls(**params)
                result = Backtester(**self.bt_kwargs).run(strat, df, instrument, timeframe)
                score = obj_fn(result.metrics)
                scored.append({
                    "params": params,
                    "metrics": result.metrics,
                    "score": float(score) if score == score else 0.0,
                    "_equity_curve": result.equity_curve,
                })
            except Exception as e:
                scored.append({
                    "params": params,
                    "metrics": {"error": str(e)},
                    "score": -1e9,
                    "_equity_curve": [],
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[: self.top_k]

        wf = None
        if walk_forward_splits and walk_forward_splits >= 2 and scored and scored[0]["score"] > -1e9:
            wf = self._walk_forward(
                strategy_cls,
                df,
                scored[0]["params"],
                instrument,
                timeframe,
                walk_forward_splits,
            )

        # strip equity curves from non-best entries to keep payload small
        best_eq = top[0]["_equity_curve"] if top else []
        ranked = []
        for r in top:
            ranked.append({
                "params": r["params"],
                "metrics": r["metrics"],
                "score": r["score"],
            })

        return OptimizerResult(
            objective=self.objective,
            ranked=ranked,
            best_params=top[0]["params"] if top else {},
            best_metrics=top[0]["metrics"] if top else {},
            best_equity_curve=best_eq,
            n_combos=len(combos),
            walk_forward=wf,
        )

    def _walk_forward(self, strategy_cls, df, params, instrument, timeframe, splits):
        n = len(df)
        if n < splits * 50:
            return None
        chunk = n // splits
        results = []
        for k in range(splits):
            seg = df.iloc[k * chunk:(k + 1) * chunk]
            if len(seg) < 50:
                continue
            try:
                strat = strategy_cls(**params)
                res = Backtester(**self.bt_kwargs).run(strat, seg, instrument, timeframe)
                results.append({
                    "split": k + 1,
                    "from": str(seg.index[0]),
                    "to": str(seg.index[-1]),
                    "metrics": res.metrics,
                })
            except Exception as e:
                results.append({"split": k + 1, "error": str(e)})
        return {"splits": splits, "results": results}


def run_optimization(strategy_cls, df, param_ranges, **kw) -> OptimizerResult:
    finder = StrategyFinder(
        backtester_kwargs=kw.pop("backtester_kwargs", None),
        objective=kw.pop("objective", "sharpe_ratio"),
        top_k=kw.pop("top_k", 10),
    )
    return finder.search(strategy_cls, df, param_ranges, **kw)
