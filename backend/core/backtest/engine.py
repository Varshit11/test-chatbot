"""Bar-by-bar backtester.

Order model:
  * Signals received on bar `i` are EXECUTED at the close of that bar
    (configurable via `signal_on_close=False` to execute on next-bar open).
  * Stop-loss / take-profit are evaluated INTRABAR using the bar's high/low
    (after the signal-execution check).
  * One position at a time (long or short). New entry while in a position
    forces an exit first (sequential exit + entry on the same bar).
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from ..strategy.base import StrategyBase, Position, Signal
from .metrics import compute_metrics

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0           # currency PnL (after size + commission + slippage)
    pnl_pct: float = 0.0       # return % vs entry price
    points: float = 0.0        # raw price-distance moved in our favour (no size)
    bars_held: int = 0
    exit_reason: str = ""

    def to_dict(self):
        d = asdict(self)
        # serialise timestamps for JSON
        if self.entry_time is not None:
            d["entry_time"] = pd.Timestamp(self.entry_time).isoformat()
        if self.exit_time is not None:
            d["exit_time"] = pd.Timestamp(self.exit_time).isoformat()
        return d


@dataclass
class BacktestResult:
    metrics: Dict[str, Any] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    drawdown_curve: List[Dict[str, Any]] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    instrument: str = ""
    timeframe: str = ""

    def to_dict(self):
        return {
            "metrics": self.metrics,
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": self.equity_curve,
            "drawdown_curve": self.drawdown_curve,
            "params": self.params,
            "instrument": self.instrument,
            "timeframe": self.timeframe,
        }


class Backtester:
    """Execute a StrategyBase instance against an OHLCV DataFrame."""

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        position_size: float = 1.0,           # units per trade (point-based PnL)
        commission_per_trade: float = 0.0,    # absolute per round-trip
        slippage_per_unit: float = 0.0,       # absolute per unit per side
        signal_on_close: bool = True,
    ):
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.commission = commission_per_trade
        self.slippage = slippage_per_unit
        self.signal_on_close = signal_on_close

    def run(
        self,
        strategy: StrategyBase,
        df: pd.DataFrame,
        instrument: str = "",
        timeframe: str = "",
    ) -> BacktestResult:
        if df.empty:
            return BacktestResult(metrics={}, trades=[], equity_curve=[], drawdown_curve=[])

        if not isinstance(df.index, pd.DatetimeIndex):
            if "datetime" in df.columns:
                df = df.copy()
                df["datetime"] = pd.to_datetime(df["datetime"])
                df = df.set_index("datetime")
            else:
                raise ValueError("DataFrame must have DatetimeIndex or 'datetime' column.")

        df = df.sort_index()
        df_prep = strategy.prepare(df)
        # ensure the prepared df has the same index/length
        if len(df_prep) != len(df):
            raise RuntimeError("strategy.prepare() must return a df of the same length as input.")

        # The strategy's `on_bar(i, row, df)` receives `i` as an integer bar
        # position. Generated strategies often write `df.loc[i, "col"]` —
        # which crashes if `df` still has the original DatetimeIndex
        # (KeyError: int not in DatetimeIndex). Reset the index to integers
        # so both `df.iloc[i]` (templates) and `df.loc[i, ...]` (LLM-gen)
        # work. The original timestamps are kept on the side for the engine
        # to stamp trades / equity curve points.
        ts_index = df_prep.index
        df_strat = df_prep.reset_index(drop=True)

        # state
        strategy.position = Position(side="flat")
        trades: List[Trade] = []
        equity = self.initial_capital
        equity_curve: List[Dict[str, Any]] = []
        peak = equity
        dd_curve: List[Dict[str, Any]] = []

        # Track the first error from on_bar for diagnostics. We still don't let
        # one bad bar abort the whole backtest, but we log at least once so a
        # silent "0 trades" no longer hides a code-gen bug.
        first_strategy_error: Optional[str] = None
        strategy_error_count = 0

        for i in range(len(df_strat)):
            row = df_strat.iloc[i]
            ts = ts_index[i]
            bar_high = float(row["high"])
            bar_low = float(row["low"])
            bar_close = float(row["close"])

            # 1. Manage open position: SL / TP intra-bar
            if strategy.position.side != "flat":
                hit, exit_price, exit_reason = self._check_sl_tp(strategy.position, bar_high, bar_low)
                if hit:
                    trade = self._close_position(strategy, exit_price, ts, exit_reason)
                    if trade:
                        equity += trade.pnl
                        trades.append(trade)

            # 2. Get signal for this bar
            try:
                sig: Optional[Signal] = strategy.on_bar(i, row, df_strat)
            except Exception as e:
                sig = None
                strategy_error_count += 1
                if first_strategy_error is None:
                    first_strategy_error = f"{type(e).__name__}: {e} (bar i={i})"
                    logger.warning("strategy.on_bar raised at bar %d: %s: %s", i, type(e).__name__, e)

            if sig is not None:
                exec_price = bar_close if self.signal_on_close else (
                    df_strat.iloc[i + 1]["open"] if i + 1 < len(df_strat) else bar_close
                )
                if sig.action == "exit" and strategy.position.side != "flat":
                    trade = self._close_position(strategy, float(exec_price), ts, sig.reason or "signal_exit")
                    if trade:
                        equity += trade.pnl
                        trades.append(trade)
                elif sig.action == "buy":
                    if strategy.position.side == "short":
                        trade = self._close_position(strategy, float(exec_price), ts, "flip_to_long")
                        if trade:
                            equity += trade.pnl
                            trades.append(trade)
                    if strategy.position.side == "flat":
                        self._open_position(strategy, "long", float(exec_price), ts, sig)
                elif sig.action == "sell":
                    if strategy.position.side == "long":
                        trade = self._close_position(strategy, float(exec_price), ts, "flip_to_short")
                        if trade:
                            equity += trade.pnl
                            trades.append(trade)
                    if strategy.position.side == "flat":
                        self._open_position(strategy, "short", float(exec_price), ts, sig)

            # 3. mark-to-market equity & drawdown
            mtm = self._mark_to_market(strategy.position, bar_close)
            cur_equity = equity + mtm
            peak = max(peak, cur_equity)
            dd = (cur_equity - peak) / peak if peak else 0.0
            equity_curve.append({"t": ts.isoformat(), "equity": round(cur_equity, 2)})
            dd_curve.append({"t": ts.isoformat(), "dd": round(dd, 6)})

        # close any open trade at the last bar
        if strategy.position.side != "flat":
            last_close = float(df_strat.iloc[-1]["close"])
            ts = ts_index[-1]
            trade = self._close_position(strategy, last_close, ts, "end_of_data")
            if trade:
                equity += trade.pnl
                trades.append(trade)
                if equity_curve:
                    equity_curve[-1]["equity"] = round(equity, 2)

        if strategy_error_count > 0:
            logger.warning(
                "strategy.on_bar raised %d times during backtest (first: %s)",
                strategy_error_count, first_strategy_error,
            )

        metrics = compute_metrics(
            trades=[t.to_dict() for t in trades],
            equity_curve=equity_curve,
            initial_capital=self.initial_capital,
        )
        # Surface a code-gen issue when the strategy crashed on every bar (no
        # signals = looks like a "valid 0-trade strategy" otherwise).
        if strategy_error_count > 0 and len(trades) == 0:
            metrics["strategy_runtime_error"] = first_strategy_error
            metrics["strategy_runtime_error_count"] = strategy_error_count

        return BacktestResult(
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            drawdown_curve=dd_curve,
            params=dict(strategy.params),
            instrument=instrument,
            timeframe=timeframe,
        )

    # -- internals -------------------------------------------------------------

    def _open_position(self, strategy: StrategyBase, side: str, price: float,
                       ts: pd.Timestamp, sig: Signal):
        adj = self.slippage
        entry = price + adj if side == "long" else price - adj
        strategy.position = Position(
            side=side,
            entry_price=entry,
            entry_time=ts,
            size=self.position_size,
            sl=sig.sl,
            tp=sig.tp,
        )

    def _close_position(self, strategy: StrategyBase, price: float,
                        ts: pd.Timestamp, reason: str) -> Optional[Trade]:
        pos = strategy.position
        if pos.side == "flat":
            return None
        adj = self.slippage
        exit_price = price - adj if pos.side == "long" else price + adj
        if pos.side == "long":
            pnl_per_unit = exit_price - pos.entry_price
        else:
            pnl_per_unit = pos.entry_price - exit_price
        pnl = pnl_per_unit * pos.size - self.commission
        pnl_pct = (pnl_per_unit / pos.entry_price) if pos.entry_price else 0.0
        # Raw points = pre-size, pre-commission directional price distance.
        # Long: exit_price − entry_price ; Short: entry_price − exit_price
        points = pnl_per_unit

        trade = Trade(
            side=pos.side,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            exit_time=ts,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            points=points,
            bars_held=0,
            exit_reason=reason,
        )
        strategy.position = Position(side="flat")
        return trade

    def _check_sl_tp(self, pos: Position, bar_high: float, bar_low: float):
        if pos.side == "long":
            if pos.sl is not None and bar_low <= pos.sl:
                return True, pos.sl, "stop_loss"
            if pos.tp is not None and bar_high >= pos.tp:
                return True, pos.tp, "take_profit"
        elif pos.side == "short":
            if pos.sl is not None and bar_high >= pos.sl:
                return True, pos.sl, "stop_loss"
            if pos.tp is not None and bar_low <= pos.tp:
                return True, pos.tp, "take_profit"
        return False, 0.0, ""

    def _mark_to_market(self, pos: Position, price: float) -> float:
        if pos.side == "long":
            return (price - pos.entry_price) * pos.size
        if pos.side == "short":
            return (pos.entry_price - price) * pos.size
        return 0.0


def run_backtest(
    strategy: StrategyBase,
    df: pd.DataFrame,
    instrument: str = "",
    timeframe: str = "",
    **bt_kwargs,
) -> BacktestResult:
    return Backtester(**bt_kwargs).run(strategy, df, instrument=instrument, timeframe=timeframe)
