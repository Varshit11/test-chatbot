"""Saved-strategies endpoints."""
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..db import get_db
from ..models import Strategy
from ..schemas import StrategyOut, StrategyDetail

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=List[StrategyOut])
def list_saved(db: Session = Depends(get_db)):
    return db.query(Strategy).order_by(desc(Strategy.updated_at)).all()


@router.get("/{strategy_id}", response_model=StrategyDetail)
def get_saved(strategy_id: str, db: Session = Depends(get_db)):
    s = db.get(Strategy, strategy_id)
    if not s:
        raise HTTPException(404, "Strategy not found")
    return StrategyDetail(
        id=s.id,
        name=s.name,
        description=s.description,
        template=s.template,
        instrument=s.instrument,
        timeframe=s.timeframe,
        status=s.status,
        created_at=s.created_at,
        updated_at=s.updated_at,
        parsed_logic=s.parsed_logic or {},
        parameters=s.parameters or {},
        backtest_result=s.backtest_result or {},
        sf_result=s.sf_result or {},
        ai_filter_result=s.ai_filter_result or {},
    )


@router.delete("/{strategy_id}")
def delete_saved(strategy_id: str, db: Session = Depends(get_db)):
    s = db.get(Strategy, strategy_id)
    if not s:
        raise HTTPException(404, "Strategy not found")
    db.delete(s)
    db.commit()
    return {"ok": True}
