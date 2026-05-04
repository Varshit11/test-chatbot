"""Catalog endpoints: indicators, strategy templates, instruments."""
from __future__ import annotations
from typing import List
from fastapi import APIRouter

from ..schemas import IndicatorOut, TemplateOut, InstrumentOut
from ...core.indicators import list_indicators
from ...core.strategy import list_strategy_templates
from ...data.instruments import list_instruments

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/indicators", response_model=List[IndicatorOut])
def get_indicators():
    return list_indicators()


@router.get("/templates", response_model=List[TemplateOut])
def get_templates():
    return list_strategy_templates()


@router.get("/instruments", response_model=List[InstrumentOut])
def get_instruments():
    return list_instruments()
