"""Strategy base class.

All generated strategies inherit from `StrategyBase`. The backtester walks the
DataFrame bar-by-bar (after the strategy's `prepare()` step has computed any
indicators in a vectorised way) and calls `on_bar()` for each candle.

Contract:
    - `prepare(df)` runs ONCE on the whole DataFrame and may attach
      pre-computed indicator columns. It MUST return the (possibly augmented)
      DataFrame.
    - `on_bar(i, row, df)` runs for each bar `i` and returns either:
          None, OR
          {"action": "buy" | "sell" | "exit", "reason": str, "size": float?}
    - The backtester handles position bookkeeping and P&L. Strategies should
      stay stateless apart from `self.position` (managed by the backtester).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence
import pandas as pd


@dataclass
class Signal:
    action: str           # "buy" | "sell" | "exit"
    reason: str = ""
    size: float = 1.0     # multiplier (units / contracts)
    sl: Optional[float] = None
    tp: Optional[float] = None


@dataclass(eq=False)  # custom __eq__ below tolerates `position == 0/+/-` from LLM-gen code
class Position:
    side: str             # "long" | "short" | "flat"
    entry_price: float = 0.0
    entry_time: Optional[pd.Timestamp] = None
    size: float = 0.0
    sl: Optional[float] = None
    tp: Optional[float] = None

    # --- comparison helpers --------------------------------------------------
    # Generated strategies sometimes write `if self.position == 0:` (treating
    # position as an int sign — flat=0, long=+, short=-) instead of the canonical
    # `self.position.side == "flat"`. Both should work.
    def _signed(self) -> int:
        return {"long": 1, "short": -1, "flat": 0}.get(self.side, 0)

    def __eq__(self, other):
        if isinstance(other, Position):
            return (self.side, self.entry_price, self.entry_time,
                    self.size, self.sl, self.tp) == (
                    other.side, other.entry_price, other.entry_time,
                    other.size, other.sl, other.tp)
        if isinstance(other, (int, float)):
            return self._signed() == other
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        return NotImplemented if eq is NotImplemented else not eq

    def __gt__(self, other):
        if isinstance(other, (int, float)):
            return self._signed() > other
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, (int, float)):
            return self._signed() < other
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, (int, float)):
            return self._signed() >= other
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, (int, float)):
            return self._signed() <= other
        return NotImplemented

    def __bool__(self):
        # `if self.position:` should mean "in a position".
        return self.side != "flat"

    def __hash__(self):
        return hash((self.side, self.entry_price, self.entry_time,
                     self.size, self.sl, self.tp))


class StrategyBase:
    """Base class. Subclasses override `prepare` and `on_bar`."""

    name: str = "base"
    description: str = ""
    default_params: Dict[str, Any] = {}
    param_ranges: Dict[str, Sequence] = {}   # for the optimizer

    # --- lifecycle -----------------------------------------------------------

    def __init__(self, **params):
        merged = {**self.default_params, **params}
        self.params: Dict[str, Any] = merged
        # Mutable state – owned by the backtester:
        self.position: Position = Position(side="flat")
        self.trades: List[Dict[str, Any]] = []

    # --- to be overridden ---------------------------------------------------

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-compute any indicators in a vectorised way. Default: no-op."""
        return df

    def on_bar(self, i: int, row: pd.Series, df: pd.DataFrame) -> Optional[Signal]:
        """Return a Signal or None for the current bar."""
        raise NotImplementedError

    # --- helpers (utility for subclasses) -----------------------------------

    def long(self, reason: str = "", **kw) -> Signal:
        return Signal(action="buy", reason=reason, **kw)

    def short(self, reason: str = "", **kw) -> Signal:
        return Signal(action="sell", reason=reason, **kw)

    def exit(self, reason: str = "") -> Signal:
        return Signal(action="exit", reason=reason)

    # --- description for LLM ------------------------------------------------

    @classmethod
    def describe(cls) -> Dict[str, Any]:
        return {
            "name": cls.name,
            "description": cls.description,
            "default_params": cls.default_params,
            "param_ranges": {k: list(v) for k, v in cls.param_ranges.items()},
        }

    # --- transparency: explain exactly what ran -----------------------------

    def explain(self) -> Dict[str, Any]:
        """Return a structured explanation of the rules + parameters that
        actually executed, so the UI can show the user what code ran."""
        return {
            "name": self.name,
            "description": self.description,
            "params": dict(self.params),
            "entry_rules": self.entry_rules(),
            "exit_rules": self.exit_rules(),
            "indicators": self.indicators_used(),
            "code_snippet": self.code_snippet(),
        }

    def entry_rules(self) -> List[str]:
        return []

    def exit_rules(self) -> List[str]:
        return []

    def indicators_used(self) -> List[str]:
        return []

    def code_snippet(self) -> str:
        """Return the actual Python source of `on_bar` for full transparency."""
        import inspect
        try:
            return inspect.getsource(self.on_bar)
        except Exception:
            return ""
