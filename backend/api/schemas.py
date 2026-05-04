"""Pydantic schemas for API I/O."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime


class ConversationOut(BaseModel):
    id: str
    title: str
    status: str
    state: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    msg_type: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    @classmethod
    def from_orm_model(cls, m) -> "MessageOut":
        return cls(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            msg_type=m.msg_type,
            metadata=m.meta or {},
            created_at=m.created_at,
        )


class ConversationDetail(ConversationOut):
    messages: List[MessageOut] = []
    context: Dict[str, Any] = {}


class CreateConversationIn(BaseModel):
    title: Optional[str] = None


class SendMessageIn(BaseModel):
    content: str
    action: Optional[str] = None    # e.g. "confirm", "run_finder", "run_filter", "save"
    payload: Optional[Dict[str, Any]] = None


class StrategyOut(BaseModel):
    id: str
    name: str
    description: str
    template: Optional[str]
    instrument: Optional[str]
    timeframe: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StrategyDetail(StrategyOut):
    parsed_logic: Dict[str, Any] = {}
    parameters: Dict[str, Any] = {}
    backtest_result: Dict[str, Any] = {}
    sf_result: Dict[str, Any] = {}
    ai_filter_result: Dict[str, Any] = {}


class InstrumentOut(BaseModel):
    symbol: str
    name: str
    exchange: str
    asset_class: str
    timeframes: List[str]


class IndicatorOut(BaseModel):
    name: str
    category: str
    description: str
    params: Dict[str, Any]
    returns: str


class TemplateOut(BaseModel):
    name: str
    description: str
    default_params: Dict[str, Any]
    param_ranges: Dict[str, List[Any]]
