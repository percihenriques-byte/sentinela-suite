"""Persistence for Jarvis conversations.

Persisting the transcript lets the client keep chats across sessions and lets
Jarvis itself replay context on the next turn without the client re-uploading
history.
"""
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from sqlmodel import Session, select

from app.models import JarvisConversation, JarvisMessage


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_conversation(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
    conversation_id: UUID | None,
    title_seed: str | None = None,
) -> JarvisConversation:
    if conversation_id is not None:
        conv = session.exec(
            select(JarvisConversation).where(
                JarvisConversation.id == conversation_id,
                JarvisConversation.workspace_id == workspace_id,
                JarvisConversation.deleted_at.is_(None),
            )
        ).first()
        if conv is not None:
            return conv
    conv = JarvisConversation(
        workspace_id=workspace_id,
        user_id=user_id,
        title=(title_seed or "Chat")[:80] if title_seed else None,
    )
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


def append_message(
    session: Session,
    workspace_id: UUID,
    conversation: JarvisConversation,
    role: str,
    content: str,
    *,
    intent: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    fallback: bool = False,
    from_llm: bool = False,
) -> JarvisMessage:
    msg = JarvisMessage(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        role=role,
        content=content,
        intent=intent,
        tool_calls_json=json.dumps(tool_calls, default=str) if tool_calls else None,
        fallback=fallback,
        from_llm=from_llm,
    )
    session.add(msg)
    conversation.last_message_at = _now()
    conversation.updated_at = _now()
    session.add(conversation)
    session.commit()
    session.refresh(msg)
    return msg


def get_history(
    session: Session,
    workspace_id: UUID,
    conversation_id: UUID,
    limit: int = 20,
) -> list[JarvisMessage]:
    stmt = (
        select(JarvisMessage)
        .where(
            JarvisMessage.workspace_id == workspace_id,
            JarvisMessage.conversation_id == conversation_id,
            JarvisMessage.deleted_at.is_(None),
        )
        .order_by(JarvisMessage.created_at.asc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def get_last_assistant_with_tool_calls(
    session: Session,
    workspace_id: UUID,
    conversation_id: UUID,
) -> JarvisMessage | None:
    """Return the most recent assistant message that has tool_calls_json set.

    Robust to ties in ``created_at`` — used for context walks that must find
    the last actionable turn (undo, explain).
    """
    stmt = (
        select(JarvisMessage)
        .where(
            JarvisMessage.workspace_id == workspace_id,
            JarvisMessage.conversation_id == conversation_id,
            JarvisMessage.deleted_at.is_(None),
            JarvisMessage.role == "assistant",
            JarvisMessage.tool_calls_json.is_not(None),
        )
        .order_by(JarvisMessage.created_at.desc(), JarvisMessage.id.desc())
        .limit(1)
    )
    return session.exec(stmt).first()


def get_last_assistant_intent(
    session: Session,
    workspace_id: UUID,
    conversation_id: UUID,
) -> str | None:
    stmt = (
        select(JarvisMessage)
        .where(
            JarvisMessage.workspace_id == workspace_id,
            JarvisMessage.conversation_id == conversation_id,
            JarvisMessage.deleted_at.is_(None),
            JarvisMessage.role == "assistant",
        )
        .order_by(JarvisMessage.created_at.desc(), JarvisMessage.id.desc())
        .limit(1)
    )
    row = session.exec(stmt).first()
    return row.intent if row else None


def get_recent_context(
    session: Session,
    workspace_id: UUID,
    conversation_id: UUID,
    limit: int = 6,
) -> list[JarvisMessage]:
    """Return the MOST RECENT ``limit`` messages in chronological order.

    Unlike ``get_history`` which returns the OLDEST N (used by the /messages
    endpoint), this fetches the tail of the conversation — what the chat
    engine needs to resolve pronouns, ambiguity picks, and 'explain that'.
    """
    stmt = (
        select(JarvisMessage)
        .where(
            JarvisMessage.workspace_id == workspace_id,
            JarvisMessage.conversation_id == conversation_id,
            JarvisMessage.deleted_at.is_(None),
        )
        .order_by(JarvisMessage.created_at.desc())
        .limit(limit)
    )
    rows = list(session.exec(stmt).all())
    rows.reverse()
    return rows
