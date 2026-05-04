"""Registry of pre-built strategy templates."""
from __future__ import annotations
from typing import Dict, Type

from .base import StrategyBase
from .templates import (
    HeikinAshiEMACross,
    EMACrossover,
    RSIMeanReversion,
    BollingerBreakout,
    MACDTrend,
)

STRATEGY_TEMPLATES: Dict[str, Type[StrategyBase]] = {
    HeikinAshiEMACross.name: HeikinAshiEMACross,
    EMACrossover.name: EMACrossover,
    RSIMeanReversion.name: RSIMeanReversion,
    BollingerBreakout.name: BollingerBreakout,
    MACDTrend.name: MACDTrend,
}


def get_strategy_class(name: str) -> Type[StrategyBase]:
    if name not in STRATEGY_TEMPLATES:
        raise KeyError(f"Unknown strategy template: {name}")
    return STRATEGY_TEMPLATES[name]


def register_strategy(cls: Type[StrategyBase]) -> None:
    STRATEGY_TEMPLATES[cls.name] = cls


def list_strategy_templates():
    return [cls.describe() for cls in STRATEGY_TEMPLATES.values()]
