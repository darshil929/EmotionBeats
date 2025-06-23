"""
Service for managing chat sessions.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.db.models import ChatSession, ChatMessage
from app.schemas.chat import (
    ChatSessionResponse,
    ChatHistoryResponse,
    ChatMessageResponse,
)
from app.utils.datetime_helper import utc_now

logger = logging.getLogger(__name__)


async def create_session(
    db: Session,
    user_id: str,
    session_name: Optional[str] = None,
    session_context: Optional[Dict[str, Any]] = None,
) -> ChatSessionResponse:
    """
    Create a new chat session.

    Args:
        db: Database session
        user_id: User ID
        session_name: Optional name for the session
        session_context: Optional context data for the session

    Returns:
        Created chat session
    """
    now = utc_now()
    session_identifier = f"session_{uuid.uuid4().hex[:8]}"

    # Use provided name or generate a default one
    name = session_name or f"Chat {now.strftime('%Y-%m-%d %H:%M')}"

    # Create session
    session = ChatSession(
        user_id=user_id,
        session_identifier=session_identifier,
        start_timestamp=now,
        session_context=session_context or {},
        detected_emotions={},
        is_active=True,
        created_at=now,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(f"Created new chat session {session.id} for user {user_id}")

    # Convert to response model
    return ChatSessionResponse(
        id=str(session.id),
        created_at=session.created_at,
        updated_at=session.start_timestamp,
        name=name,
        is_active=session.is_active,
        context=session.session_context,
    )


async def get_user_sessions(
    db: Session,
    user_id: str,
    limit: int = 10,
    offset: int = 0,
    active_only: bool = False,
) -> List[ChatSessionResponse]:
    """
    Get a list of chat sessions for a user.

    Args:
        db: Database session
        user_id: User ID
        limit: Maximum number of sessions to return
        offset: Number of sessions to skip
        active_only: If true, only return active sessions

    Returns:
        List of chat sessions
    """
    query = db.query(ChatSession).filter(ChatSession.user_id == user_id)

    if active_only:
        query = query.filter(ChatSession.is_active is True)

    # Order by most recent first
    query = query.order_by(desc(ChatSession.start_timestamp))

    # Apply pagination
    sessions = query.offset(offset).limit(limit).all()

    # Convert to response models
    return [
        ChatSessionResponse(
            id=str(session.id),
            created_at=session.created_at,
            updated_at=session.start_timestamp,
            name=session.session_context.get(
                "name", f"Chat {session.start_timestamp.strftime('%Y-%m-%d %H:%M')}"
            ),
            is_active=session.is_active,
            context=session.session_context,
        )
        for session in sessions
    ]


async def get_session_with_messages(
    db: Session,
    session_id: str,
    user_id: str,
    limit: int = 50,
    before_message_id: Optional[str] = None,
) -> Optional[ChatHistoryResponse]:
    """
    Get a chat session with its messages.

    Args:
        db: Database session
        session_id: Chat session ID
        user_id: User ID (for authorization)
        limit: Maximum number of messages to return
        before_message_id: Return messages before this ID (for pagination)

    Returns:
        Chat session with messages or None if not found
    """
    # Get the session and verify ownership
    session = (
        db.query(ChatSession)
        .filter(and_(ChatSession.id == session_id, ChatSession.user_id == user_id))
        .first()
    )

    if not session:
        return None

    # Query for messages
    messages_query = db.query(ChatMessage).filter(
        ChatMessage.chat_session_id == session_id
    )

    # Apply pagination if before_message_id is provided
    if before_message_id:
        before_message = (
            db.query(ChatMessage).filter(ChatMessage.id == before_message_id).first()
        )

        if before_message:
            messages_query = messages_query.filter(
                ChatMessage.sent_at < before_message.sent_at
            )

    # Order by timestamp (oldest first) and apply limit
    messages = messages_query.order_by(ChatMessage.sent_at.desc()).limit(limit).all()

    # Reverse to get oldest first
    messages.reverse()

    # Convert to response models
    message_responses = [
        ChatMessageResponse(
            id=str(msg.id),
            content=msg.content,
            sender=msg.sender,
            timestamp=msg.sent_at,
            emotion=msg.detected_emotion,
            emotion_confidence=msg.emotion_confidence,
        )
        for msg in messages
    ]

    # Create the combined response
    return ChatHistoryResponse(
        id=str(session.id),
        created_at=session.created_at,
        updated_at=session.start_timestamp,
        name=session.session_context.get(
            "name", f"Chat {session.start_timestamp.strftime('%Y-%m-%d %H:%M')}"
        ),
        is_active=session.is_active,
        context=session.session_context,
        messages=message_responses,
    )


async def update_session(
    db: Session,
    session_id: str,
    user_id: str,
    is_active: Optional[bool] = None,
    session_name: Optional[str] = None,
) -> Optional[ChatSessionResponse]:
    """
    Update a chat session.

    Args:
        db: Database session
        session_id: Chat session ID
        user_id: User ID (for authorization)
        is_active: New active status
        session_name: New session name

    Returns:
        Updated chat session or None if not found
    """
    # Get the session and verify ownership
    session = (
        db.query(ChatSession)
        .filter(and_(ChatSession.id == session_id, ChatSession.user_id == user_id))
        .first()
    )

    if not session:
        return None

    # Update fields if provided
    if is_active is not None:
        session.is_active = is_active

        # If closing the session, set end timestamp
        if not is_active and not session.end_timestamp:
            session.end_timestamp = utc_now()

    # Update name in context if provided
    if session_name is not None:
        if not session.session_context:
            session.session_context = {}
        session.session_context["name"] = session_name

    db.commit()
    db.refresh(session)

    # Convert to response model
    return ChatSessionResponse(
        id=str(session.id),
        created_at=session.created_at,
        updated_at=session.updated_at or session.start_timestamp,
        name=session.session_context.get(
            "name", f"Chat {session.start_timestamp.strftime('%Y-%m-%d %H:%M')}"
        ),
        is_active=session.is_active,
        context=session.session_context,
    )


async def delete_session(
    db: Session,
    session_id: str,
    user_id: str,
) -> bool:
    """
    Delete a chat session and its messages.

    Args:
        db: Database session
        session_id: Chat session ID
        user_id: User ID (for authorization)

    Returns:
        True if session was deleted, False if not found
    """
    # Get the session and verify ownership
    session = (
        db.query(ChatSession)
        .filter(and_(ChatSession.id == session_id, ChatSession.user_id == user_id))
        .first()
    )

    if not session:
        return False

    try:
        # Delete all messages in the session
        db.query(ChatMessage).filter(ChatMessage.chat_session_id == session_id).delete()

        # Delete the session
        db.delete(session)
        db.commit()

        logger.info(f"Deleted chat session {session_id} for user {user_id}")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting chat session {session_id}: {str(e)}")
        raise
