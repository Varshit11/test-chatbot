"""Strategy module: base class and registry of pre-built strategies."""
from .base import StrategyBase, Signal, Position
from .registry import (
    STRATEGY_TEMPLATES,
    get_strategy_class,
    register_strategy,
    list_strategy_templates,
)

__all__ = [
    "StrategyBase",
    "Signal",
    "Position",
    "STRATEGY_TEMPLATES",
    "get_strategy_class",
    "register_strategy",
    "list_strategy_templates",
]
