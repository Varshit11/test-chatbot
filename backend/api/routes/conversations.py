"""Conversation + message endpoints."""
from __future__ import annotations
import logging
import traceback
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..db import get_db
from ..models import Conversation, Message
from ..schemas import (
    ConversationOut, ConversationDetail, MessageOut,
    CreateConversationIn, SendMessageIn,
)
from ..services import orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=List[ConversationOut])
def list_conversations(db: Session = Depends(get_db)):
    rows = db.query(Conversation).order_by(desc(Conversation.updated_at)).all()
    return rows


@router.post("", response_model=ConversationDetail)
def create_conversation(body: CreateConversationIn, db: Session = Depends(get_db)):
    """New conversations start empty (Claude-style clean canvas)."""
    conv = Conversation(title=body.title or "New Strategy", state="GREETING", context={})
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _to_detail(conv)


@router.get("/{conv_id}", response_model=ConversationDetail)
def get_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return _to_detail(conv)


@router.delete("/{conv_id}")
def delete_conversation(conv_id: str, db: Session = Depends(get_db)):
    """Delete a conversation and all its messages. Saved strategies that point
    at this conversation are kept (their `conversation_id` is detached) so the
    user doesn't lose work they explicitly saved."""
    from ..models import Strategy
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    try:
        # Detach saved strategies so the FK doesn't block deletion
        db.query(Strategy).filter(Strategy.conversation_id == conv_id).update(
            {Strategy.conversation_id: None}, synchronize_session=False
        )
        db.delete(conv)
        db.commit()
    except Exception as e:
        logger.exception("delete_conversation failed for %s", conv_id)
        db.rollback()
        raise HTTPException(500, f"Could not delete: {type(e).__name__}: {e}")
    return {"ok": True}


@router.patch("/{conv_id}", response_model=ConversationOut)
def rename_conversation(conv_id: str, body: CreateConversationIn, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if body.title:
        conv.title = body.title
    db.commit()
    db.refresh(conv)
    return conv


@router.post("/{conv_id}/messages", response_model=List[MessageOut])
def send_message(conv_id: str, body: SendMessageIn, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    try:
        new_messages = orchestrator.handle_message(
            db, conv, body.content, action=body.action, payload=body.payload
        )
        db.commit()
        for m in new_messages:
            db.refresh(m)
    except Exception as e:
        # Never let an exception become a raw 500. Roll back, persist a useful
        # error message in chat, and return it as a normal assistant turn so
        # the UI shows something the user can act on.
        logger.exception("send_message failed for conv=%s action=%s", conv_id, body.action)
        try:
            db.rollback()
        except Exception:
            pass
        tb_excerpt = traceback.format_exception_only(type(e), e)[-1].strip()
        err_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=(
                f"⚠️ I hit an unexpected error: `{tb_excerpt}`.\n\n"
                f"Action: `{body.action or 'message'}`. The backend logs have "
                f"the full traceback. You can usually recover by retrying or "
                f"clicking **+ New strategy**."
            ),
            msg_type="text",
            meta={"error": tb_excerpt, "action": body.action},
            created_at=datetime.utcnow(),
        )
        db.add(err_msg)
        try:
            db.commit()
            db.refresh(err_msg)
        except Exception:
            db.rollback()
        return [MessageOut.from_orm_model(err_msg)]

    # also return the just-added user message (the very first message in this exchange)
    user_q = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id, Message.role == "user")
        .order_by(desc(Message.created_at))
        .first()
    )
    out: List[MessageOut] = []
    if user_q:
        out.append(MessageOut.from_orm_model(user_q))
    for m in new_messages:
        out.append(MessageOut.from_orm_model(m))
    return out


# --------------------------------------------------------------------------- #


def _to_detail(conv: Conversation) -> ConversationDetail:
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        status=conv.status,
        state=conv.state,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[MessageOut.from_orm_model(m) for m in conv.messages],
        context=conv.context or {},
    )
