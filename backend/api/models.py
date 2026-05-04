"""ORM models — mirrors the schemas in the architecture doc (Section 5)."""
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False)
    name = Column(String)
    plan = Column(String, default="free")
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    title = Column(String, default="New Strategy")
    status = Column(String, default="active")
    state = Column(String, default="GREETING")           # state-machine state
    context = Column(JSON, default=dict)                  # parsed strategy, params, last results
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String)                                 # "user" | "assistant"
    content = Column(Text, default="")
    msg_type = Column(String, default="text")             # text | code | results | sf_results | ai_results | improvements
    meta = Column("metadata", JSON, default=dict)         # charts, metrics, action buttons
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Strategy(Base):
    __tablename__ = "strategies"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    name = Column(String, default="Untitled strategy")
    description = Column(Text, default="")
    template = Column(String)                             # template name (e.g. heikin_ashi_ema_cross)
    parsed_logic = Column(JSON, default=dict)             # structured entry/exit rules
    parameters = Column(JSON, default=dict)
    instrument = Column(String)
    timeframe = Column(String)
    backtest_result = Column(JSON, default=dict)
    sf_result = Column(JSON, default=dict)
    ai_filter_result = Column(JSON, default=dict)
    status = Column(String, default="draft")              # draft | optimized | filtered
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
