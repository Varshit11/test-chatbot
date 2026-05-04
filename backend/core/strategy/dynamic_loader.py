"""Load a `StrategyBase` subclass from LLM-generated Python source.

The source is executed in a restricted namespace: no imports, no file/NET I/O,
no ``eval``/``exec``. Only whitelisted callables (pandas, numpy, our indicators)
are injected. This is the bridge between "natural language → Claude writes code"
and the bar-by-bar backtester.

The model MUST output a single class definition inheriting ``StrategyBase``,
typically named ``GeneratedStrategy``, with ``prepare`` and ``on_bar`` methods.
"""
from __future__ import annotations

import ast
import builtins as _py_builtins
import textwrap
from typing import Any, Dict, Type

import numpy as np
import pandas as pd

from .base import Signal, StrategyBase
from ..indicators.trend import ema, sma, wma, supertrend, adx
from ..indicators.momentum import rsi, macd, stochastic, roc
from ..indicators.volatility import atr, bollinger_bands, keltner_channel
from ..indicators.volume import vwap, obv
from ..patterns.heikin_ashi import calculate_heikin_ashi
from ..patterns.research import (
    HSPattern,
    find_hs_patterns,
    hs_pattern_return,
    find_all_pivot_points,
    find_doubles_pattern,
)


FORBIDDEN_NAMES = frozenset({
    "open", "exec", "eval", "compile", "__import__", "getattr", "setattr",
    "delattr", "input", "breakpoint", "vars", "dir", "help", "memoryview",
    "importlib", "globals", "locals",
    "__builtins__",
})

# Allowed builtins for the strategy's exec namespace. CRITICAL: Python's class
# statement compiles down to a call to __build_class__, which Python resolves
# from this dict at runtime. Setting __builtins__ to {} (as the previous
# version did) made class definitions fail with "__build_class__ not found".
_ALLOWED_BUILTINS: Dict[str, Any] = {
    # Class machinery
    "__build_class__": _py_builtins.__build_class__,
    "__name__": "<dynamic_strategy>",
    # Common scalar/coercion functions
    "range": range, "min": min, "max": max, "abs": abs,
    "float": float, "int": int, "bool": bool, "str": str,
    "len": len, "round": round, "pow": pow, "sum": sum,
    "enumerate": enumerate, "zip": zip, "sorted": sorted,
    "any": any, "all": all, "reversed": reversed, "map": map, "filter": filter,
    # Containers
    "list": list, "dict": dict, "tuple": tuple, "set": set, "frozenset": frozenset,
    # Type machinery (needed by isinstance checks inside helpers)
    "isinstance": isinstance, "issubclass": issubclass,
    "type": type, "object": object, "super": super, "property": property,
    "staticmethod": staticmethod, "classmethod": classmethod,
    # Constants
    "True": True, "False": False, "None": None,
    # Exceptions the strategy can sensibly raise / catch
    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
    "KeyError": KeyError, "IndexError": IndexError, "ZeroDivisionError": ZeroDivisionError,
    "ArithmeticError": ArithmeticError, "RuntimeError": RuntimeError,
    "StopIteration": StopIteration,
    # Debug only — strategy code may print but it's harmless
    "print": print, "repr": repr,
}


def _inject_math_namespace() -> Dict[str, Any]:
    return {
        "__builtins__": _ALLOWED_BUILTINS,
        "pd": pd,
        "np": np,
        "StrategyBase": StrategyBase,
        "Signal": Signal,
        "ema": ema,
        "sma": sma,
        "wma": wma,
        "supertrend": supertrend,
        "adx": adx,
        "rsi": rsi,
        "macd": macd,
        "stochastic": stochastic,
        "roc": roc,
        "atr": atr,
        "bollinger_bands": bollinger_bands,
        "keltner_channel": keltner_channel,
        "vwap": vwap,
        "obv": obv,
        "calculate_heikin_ashi": calculate_heikin_ashi,
        "HSPattern": HSPattern,
        "find_hs_patterns": find_hs_patterns,
        "hs_pattern_return": hs_pattern_return,
        "find_all_pivot_points": find_all_pivot_points,
        "find_doubles_pattern": find_doubles_pattern,
    }


class _StrategySourceValidator(ast.NodeVisitor):
    """Reject imports and obviously dangerous calls."""

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        raise ValueError("Import statements are not allowed in generated strategy code.")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        raise ValueError("Import-from statements are not allowed in generated strategy code.")

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if isinstance(nodeAttr := node.attr, str) and nodeAttr.startswith("__"):
            raise ValueError(f"Dunder attribute access is not allowed: {nodeAttr}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_NAMES:
                raise ValueError(f"Call to forbidden name `{node.func.id}` is not allowed.")
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.attr, str) and node.func.attr in FORBIDDEN_NAMES:
                raise ValueError(f"Call to forbidden attribute `{node.func.attr}` is not allowed.")
        self.generic_visit(node)


def validate_strategy_source(source: str) -> None:
    """Parse + AST-validate. Does not execute."""
    if not source or not source.strip():
        raise ValueError("Empty generated_python.")
    src = textwrap.dedent(source).strip()
    tree = ast.parse(src, mode="exec")
    _StrategySourceValidator().visit(tree)


def load_strategy_class_from_source(source: str) -> Type[StrategyBase]:
    """Parse, validate, execute once, return the unique ``StrategyBase`` subclass."""
    validate_strategy_source(source)
    src = textwrap.dedent(source).strip()
    tree = ast.parse(src, mode="exec")
    bytecode = compile(tree, "<dynamic_strategy>", "exec")

    ns = _inject_math_namespace()
    exec(bytecode, ns, ns)  # noqa: S102 — intentional sandboxed strategy load

    candidates: list[Type[StrategyBase]] = []
    for v in ns.values():
        if isinstance(v, type) and issubclass(v, StrategyBase) and v is not StrategyBase:
            candidates.append(v)
    if not candidates:
        raise ValueError(
            "No StrategyBase subclass found in generated code. "
            "Define exactly one class that inherits StrategyBase "
            "(recommended name: GeneratedStrategy)."
        )
    named = [c for c in candidates if c.__name__ == "GeneratedStrategy"]
    if named:
        return named[0]
    if len(candidates) > 1:
        raise ValueError(
            f"Multiple StrategyBase subclasses found ({[c.__name__ for c in candidates]}); "
            "use a single class named GeneratedStrategy."
        )
    return candidates[0]
