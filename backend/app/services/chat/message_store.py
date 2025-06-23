"""
Service for storing and retrieving chat messages.
"""

import logging
from typing import List, Optional, Any

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, ChatSession
from app.schemas.chat import ChatMessageResponse
from app.utils.datetime_helper import utc_now

logger = logging.getLogger(__name__)


async def store_message(
    db: Session,
    session_id: str,
    sender: str,
    content: str,
    user_id: str,
    emotion: Optional[str] = None,
    emotion_confidence: Optional[float] = None,
) -> ChatMessage:
    """
    Store a new chat message in the database.

    Args:
        db: Database session
        session_id: Chat session ID
        sender: Message sender ('user' or 'ai')
        content: Message content
        user_id: User ID (for authorization)
        emotion: Optional detected emotion
        emotion_confidence: Optional emotion confidence score

    Returns:
        Created chat message

    Raises:
        ValueError: If the session doesn't exist or doesn't belong to the user
    """
    # Verify the session exists and belongs to the user
    session = (
        db.query(ChatSession)
        .filter(and_(ChatSession.id == session_id, ChatSession.user_id == user_id))
        .first()
    )

    if not session:
        logger.error(
            f"Session {session_id} not found or doesn't belong to user {user_id}"
        )
        raise ValueError("Chat session not found or unauthorized")

    # Create message
    now = utc_now()
    message = ChatMessage(
        chat_session_id=session_id,
        sender=sender,
        content=content,
        detected_emotion=emotion,
        emotion_confidence=emotion_confidence,
        sent_at=now,
    )

    # Update session timestamps
    session.updated_at = now
    if sender == "user" and session.end_timestamp:
        # Re-open session if user sends a new message
        session.end_timestamp = None
        session.is_active = True

    db.add(message)
    db.commit()
    db.refresh(message)

    logger.info(f"Stored message {message.id} in session {session_id}")
    return message


async def get_message(
    db: Session,
    message_id: str,
    user_id: str,
) -> Optional[ChatMessage]:
    """
    Get a specific chat message.

    Args:
        db: Database session
        message_id: Message ID
        user_id: User ID (for authorization)

    Returns:
        Chat message or None if not found
    """
    # Query for the message and join with session to verify ownership
    message = (
        db.query(ChatMessage)
        .join(ChatSession, ChatMessage.chat_session_id == ChatSession.id)
        .filter(and_(ChatMessage.id == message_id, ChatSession.user_id == user_id))
        .first()
    )

    return message


async def get_session_messages(
    db: Session,
    session_id: str,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    before_timestamp: Optional[Any] = None,
) -> List[ChatMessageResponse]:
    """
    Get messages for a specific chat session.

    Args:
        db: Database session
        session_id: Chat session ID
        user_id: User ID (for authorization)
        limit: Maximum number of messages to return
        offset: Number of messages to skip
        before_timestamp: Return messages before this timestamp

    Returns:
        List of chat messages
    """
    # Verify session ownership
    session = (
        db.query(ChatSession)
        .filter(and_(ChatSession.id == session_id, ChatSession.user_id == user_id))
        .first()
    )

    if not session:
        logger.warning(
            f"Session {session_id} not found or doesn't belong to user {user_id}"
        )
        return []

    # Query for messages
    query = db.query(ChatMessage).filter(ChatMessage.chat_session_id == session_id)

    # Apply timestamp filter if provided
    if before_timestamp:
        query = query.filter(ChatMessage.sent_at < before_timestamp)

    # Apply pagination and order (newest first)
    messages = (
        query.order_by(desc(ChatMessage.sent_at)).offset(offset).limit(limit).all()
    )

    # Convert to response models
    return [
        ChatMessageResponse(
            id=str(message.id),
            content=message.content,
            sender=message.sender,
            timestamp=message.sent_at,
            emotion=message.detected_emotion,
            emotion_confidence=message.emotion_confidence,
        )
        for message in messages
    ]


async def update_message_emotions(
    db: Session,
    message_id: str,
    user_id: str,
    emotion: str,
    emotion_confidence: float,
) -> Optional[ChatMessage]:
    """
    Update emotion detection results for a message.

    Args:
        db: Database session
        message_id: Message ID
        user_id: User ID (for authorization)
        emotion: Detected emotion
        emotion_confidence: Emotion confidence score

    Returns:
        Updated message or None if not found
    """
    # Get the message and verify ownership
    message = await get_message(db, message_id, user_id)

    if not message:
        return None

    # Update emotion data
    message.detected_emotion = emotion
    message.emotion_confidence = emotion_confidence

    # Update session emotion context
    session = (
        db.query(ChatSession).filter(ChatSession.id == message.chat_session_id).first()
    )

    if session and session.detected_emotions is not None:
        # Initialize or update emotions dictionary
        emotions_dict = session.detected_emotions or {}

        # Update with new emotion
        if emotion in emotions_dict:
            # Average with existing value
            existing_count = emotions_dict.get(f"{emotion}_count", 1)
            new_count = existing_count + 1

            emotions_dict[emotion] = (
                emotions_dict[emotion] * existing_count + emotion_confidence
            ) / new_count
            emotions_dict[f"{emotion}_count"] = new_count
        else:
            emotions_dict[emotion] = emotion_confidence
            emotions_dict[f"{emotion}_count"] = 1

        session.detected_emotions = emotions_dict

    db.commit()
    db.refresh(message)

    logger.info(
        f"Updated emotion for message {message_id}: {emotion} ({emotion_confidence})"
    )
    return message


async def delete_messages(
    db: Session,
    session_id: str,
    user_id: str,
) -> int:
    """
    Delete all messages in a chat session.

    Args:
        db: Database session
        session_id: Chat session ID
        user_id: User ID (for authorization)

    Returns:
        Number of messages deleted

    Raises:
        ValueError: If the session doesn't exist or doesn't belong to the user
    """
    # Verify session ownership
    session = (
        db.query(ChatSession)
        .filter(and_(ChatSession.id == session_id, ChatSession.user_id == user_id))
        .first()
    )

    if not session:
        raise ValueError("Chat session not found or unauthorized")

    # Delete messages
    result = (
        db.query(ChatMessage).filter(ChatMessage.chat_session_id == session_id).delete()
    )

    db.commit()

    logger.info(f"Deleted {result} messages from session {session_id}")
    return result
