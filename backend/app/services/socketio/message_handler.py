"""
Message processing pipeline for handling chat messages.
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, Optional

from app.db.models import ChatMessage, ChatSession
from app.db.session import SessionLocal
from app.utils.datetime_helper import utc_now

logger = logging.getLogger(__name__)


async def process_message(
    session_id: str,
    user_id: str,
    content: str,
    sid: str,
) -> Dict[str, Any]:
    """
    Process an incoming chat message.

    This function handles the entire message pipeline:
    1. Store the user message in the database
    2. Process the message (later: emotion detection)
    3. Generate and store AI response

    Args:
        session_id: Chat session identifier
        user_id: User identifier
        content: Message content
        sid: Socket.io session ID

    Returns:
        Processed message data
    """
    # Generate message ID
    message_id = str(uuid.uuid4())
    timestamp = utc_now()

    # Store user message in database
    db_message = await store_message(
        session_id=session_id,
        user_id=user_id,
        content=content,
        sender="user",
        message_id=message_id,
        timestamp=timestamp,
    )

    # Prepare response data
    user_message = {
        "id": str(db_message.id),
        "session_id": session_id,
        "sender": "user",
        "content": content,
        "timestamp": timestamp.isoformat(),
    }

    # Generate AI response (async to not block)
    asyncio.create_task(generate_ai_response(session_id, user_id, content, sid))

    return user_message


async def store_message(
    session_id: str,
    user_id: str,
    content: str,
    sender: str,
    message_id: Optional[str] = None,
    timestamp=None,
    emotion: Optional[str] = None,
    emotion_confidence: Optional[float] = None,
) -> ChatMessage:
    """
    Store a message in the database.

    Args:
        session_id: Chat session identifier
        user_id: User identifier
        content: Message content
        sender: Message sender ('user' or 'ai')
        message_id: Optional message ID
        timestamp: Optional message timestamp
        emotion: Optional detected emotion
        emotion_confidence: Optional emotion confidence score

    Returns:
        Created ChatMessage instance
    """
    if timestamp is None:
        timestamp = utc_now()

    # Use a new database session
    db = SessionLocal()
    try:
        # Verify the chat session exists and belongs to the user
        chat_session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id)
            .filter(ChatSession.user_id == user_id)
            .first()
        )

        if not chat_session:
            logger.error(f"Chat session {session_id} not found for user {user_id}")
            raise ValueError("Chat session not found")

        # Update session's last activity
        chat_session.updated_at = timestamp

        # Create new message
        message = ChatMessage(
            id=message_id or str(uuid.uuid4()),
            chat_session_id=session_id,
            sender=sender,
            content=content,
            detected_emotion=emotion,
            emotion_confidence=emotion_confidence,
            sent_at=timestamp,
        )

        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    except Exception as e:
        db.rollback()
        logger.error(f"Error storing message: {str(e)}")
        raise
    finally:
        db.close()


async def generate_ai_response(
    session_id: str, user_id: str, user_message: str, sid: str
) -> None:
    """
    Generate an AI response to a user message.

    Args:
        session_id: Chat session identifier
        user_id: User identifier
        user_message: User's message content
        sid: Socket.io session ID
    """
    try:
        # TODO: In Phase 3, this will integrate with emotion detection and LLM services
        # For now, implement a simple echo response

        # Add a small delay to simulate processing time
        await asyncio.sleep(1)

        # Simple response generation
        ai_response = f"Echo: {user_message}"

        # Store AI response
        timestamp = utc_now()
        ai_message = await store_message(
            session_id=session_id,
            user_id=user_id,
            content=ai_response,
            sender="ai",
            timestamp=timestamp,
        )

        # Get Socket.io server instance
        from app.services.socketio.server import SocketIOServer

        sio = SocketIOServer().get_server()

        # Prepare response data
        response_data = {
            "id": str(ai_message.id),
            "session_id": session_id,
            "sender": "ai",
            "content": ai_response,
            "timestamp": timestamp.isoformat(),
        }

        # Send AI response to the chat session
        await sio.emit("message", response_data, room=session_id)

        logger.info(f"AI response sent for session {session_id}")

    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        # Notify client of error
        from app.services.socketio.server import SocketIOServer

        sio = SocketIOServer().get_server()
        await sio.emit(
            "error",
            {"message": "Failed to generate response"},
            room=session_id,
        )
