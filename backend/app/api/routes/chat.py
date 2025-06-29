"""
REST API endpoints related to chat functionality.

This module provides endpoints for managing chat sessions, retrieving message
history, and interacting with the Socket.io real-time communication system.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User, ChatSession, ChatMessage
from app.dependencies import get_current_user
from app.services.socketio.rooms import (
    create_room,
    get_room_metadata,
    get_room_participants,
    get_user_rooms,
)
from app.services.socketio.message_queue import (
    get_room_messages,
    enqueue_message,
)
from app.utils.datetime_helper import utc_now

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new chat session.

    Creates both a database record and a Socket.io room for the session.
    """
    # Generate a unique session identifier
    session_identifier = str(uuid.uuid4())
    now = utc_now()

    # Create database record
    db_session = ChatSession(
        user_id=user.id,
        session_identifier=session_identifier,
        start_timestamp=now,
        is_active=True,
        created_at=now,
        session_context={},
        detected_emotions={},
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    # Create Socket.io room
    room_id = await create_room(
        creator_id=str(user.id),
        name=f"Chat Session {session_identifier[:8]}",
        metadata={
            "session_db_id": str(db_session.id),
            "session_identifier": session_identifier,
            "type": "chat_session",
        },
    )

    # Store the room_id in the database session
    db_session.socketio_room_id = room_id
    db.commit()
    db.refresh(db_session)

    return {
        "id": str(db_session.id),
        "session_identifier": session_identifier,
        "room_id": room_id,
        "socketio_room_id": room_id,
        "created_at": now,
        "is_active": True,
    }


@router.get("/sessions")
async def get_user_chat_sessions(
    active_only: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all chat sessions for the current user.

    Returns:
        List of chat sessions belonging to the user.
    """
    query = db.query(ChatSession).filter(ChatSession.user_id == user.id)

    if active_only:
        query = query.filter(ChatSession.is_active is True)

    sessions = query.order_by(ChatSession.created_at.desc()).all()

    return [
        {
            "id": str(session.id),
            "session_identifier": session.session_identifier,
            "start_timestamp": session.start_timestamp,
            "end_timestamp": session.end_timestamp,
            "is_active": session.is_active,
            "created_at": session.created_at,
        }
        for session in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_chat_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get details for a specific chat session.

    Args:
        session_id: ID of the chat session to retrieve

    Returns:
        Chat session details
    """
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
        )

    # Get Socket.io room metadata if it exists
    room_metadata = await get_room_metadata(str(session.id))

    return {
        "id": str(session.id),
        "session_identifier": session.session_identifier,
        "start_timestamp": session.start_timestamp,
        "end_timestamp": session.end_timestamp,
        "is_active": session.is_active,
        "created_at": session.created_at,
        "detected_emotions": session.detected_emotions,
        "room_metadata": room_metadata,
    }


@router.post("/sessions/{session_id}/messages")
async def create_chat_message(
    session_id: str,
    message: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new message in a chat session.

    Args:
        session_id: ID of the chat session
        message: Message content

    Returns:
        Created message details
    """
    # Verify chat session exists and belongs to user
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
        )

    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Chat session is not active"
        )

    # Create message in database
    content = message.get("content")
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content is required",
        )

    now = utc_now()
    db_message = ChatMessage(
        chat_session_id=session.id,
        sender="user",
        content=content,
        sent_at=now,
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)

    # Create Socket.io message
    socketio_message = {
        "id": str(db_message.id),
        "room_id": session.socketio_room_id or str(session.id),
        "content": content,
        "sender_id": str(user.id),
        "sender_sid": "api",
        "message_type": "chat",
        "timestamp": now.isoformat(),
        "metadata": {"db_message_id": str(db_message.id), "sent_via": "api"},
    }

    # Enqueue message for Socket.io delivery
    await enqueue_message(socketio_message)

    return {
        "id": str(db_message.id),
        "content": db_message.content,
        "sender": db_message.sender,
        "sent_at": db_message.sent_at,
        "chat_session_id": str(db_message.chat_session_id),
    }


@router.get("/sessions/{session_id}/messages")
async def get_chat_session_messages(
    session_id: str,
    limit: int = 50,
    before_timestamp: Optional[float] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get messages for a specific chat session.

    Args:
        session_id: ID of the chat session
        limit: Maximum number of messages to return
        before_timestamp: Get messages before this timestamp (for pagination)

    Returns:
        List of messages in the chat session
    """
    # Verify chat session exists and belongs to user
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
        )

    # Query messages from database
    query = db.query(ChatMessage).filter(ChatMessage.chat_session_id == session.id)

    if before_timestamp:
        # Convert timestamp to datetime for comparison
        from datetime import datetime, timezone

        before_dt = datetime.fromtimestamp(before_timestamp, tz=timezone.utc)
        query = query.filter(ChatMessage.sent_at < before_dt)

    messages = query.order_by(ChatMessage.sent_at.desc()).limit(limit).all()

    # Format messages for response
    formatted_messages = [
        {
            "id": str(msg.id),
            "content": msg.content,
            "sender": msg.sender,
            "sent_at": msg.sent_at,
            "detected_emotion": msg.detected_emotion,
            "emotion_confidence": msg.emotion_confidence,
        }
        for msg in messages
    ]

    return formatted_messages


@router.get("/sessions/{session_id}/realtime-messages")
async def get_realtime_messages(
    session_id: str,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get real-time messages from Socket.io for a chat session.

    This endpoint is useful for retrieving the most recent messages
    from the Socket.io message queue, including those that might not
    yet be persisted to the database.

    Args:
        session_id: ID of the chat session
        limit: Maximum number of messages to return

    Returns:
        List of real-time messages
    """
    # Verify chat session exists and belongs to user
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
        )

    # Get messages from Socket.io message queue
    messages = await get_room_messages(str(session.id), limit)

    return messages


@router.post("/sessions/{session_id}/end")
async def end_chat_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    End an active chat session.

    Args:
        session_id: ID of the chat session to end

    Returns:
        Updated chat session details
    """
    # Verify chat session exists and belongs to user
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
        )

    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat session is already ended",
        )

    # Update session status
    session.is_active = False
    session.end_timestamp = utc_now()
    db.commit()
    db.refresh(session)

    return {
        "id": str(session.id),
        "session_identifier": session.session_identifier,
        "start_timestamp": session.start_timestamp,
        "end_timestamp": session.end_timestamp,
        "is_active": session.is_active,
        "message": "Chat session ended successfully",
    }


@router.get("/rooms")
async def get_user_active_rooms(
    user: User = Depends(get_current_user),
):
    """
    Get all active Socket.io rooms for the current user.

    Returns:
        List of active rooms
    """
    # Get rooms from Socket.io
    room_ids = await get_user_rooms(str(user.id))

    # Get metadata for each room
    rooms = []
    for room_id in room_ids:
        metadata = await get_room_metadata(room_id)
        if metadata:
            participants = await get_room_participants(room_id)
            rooms.append(
                {
                    "room_id": room_id,
                    "metadata": metadata,
                    "participant_count": len(participants),
                }
            )

    return rooms


@router.get("/rooms/{room_id}/participants")
async def get_room_users(
    room_id: str,
    user: User = Depends(get_current_user),
):
    """
    Get participants in a Socket.io room.

    Args:
        room_id: ID of the room

    Returns:
        List of participants in the room
    """
    # Check if user is in the room
    user_rooms = await get_user_rooms(str(user.id))
    if room_id not in user_rooms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this room",
        )

    # Get room participants
    participants = await get_room_participants(room_id)

    return participants
