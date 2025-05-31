"""
Socket.io event handlers for real-time communication.

Manages all Socket.io events including connection management, messaging,
typing indicators, presence detection, and chat session interactions.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.services.socketio.server import get_socketio_server
from app.services.socketio.auth import (
    authenticate_user_connection,
    check_room_access_permission,
    get_user_from_session,
    handle_authentication_failure,
    extract_token_from_handshake,
)
from app.services.socketio.rooms import (
    join_user_to_room,
    leave_user_from_room,
    broadcast_to_room,
    cleanup_user_sessions,
    user_sessions,
)
from app.db.session import SessionLocal
from app.db.models import ChatMessage
from app.utils.datetime_helper import utc_now

logger = logging.getLogger(__name__)

# Active typing users tracking: session_id -> {user_id: timestamp}
typing_users: Dict[str, Dict[str, datetime]] = {}


async def handle_connect(
    sid: str, environ: Dict[str, Any], auth: Optional[Dict[str, Any]] = None
):
    """
    Handles new Socket.io client connections.

    Authenticates the connecting user and establishes the session
    for real-time communication capabilities.
    """
    try:
        logger.info(f"New Socket.io connection attempt: {sid}")

        sio = get_socketio_server()
        if not sio:
            logger.error("Socket.io server not available")
            return False

        # Extract authentication data
        if not auth:
            # Try to extract token from handshake if not in auth
            token = extract_token_from_handshake(environ)
            if token:
                auth = {"token": token}

        if not auth:
            error_response = await handle_authentication_failure(
                sid, "No authentication provided"
            )
            await sio.emit("auth_error", error_response, room=sid)
            await sio.disconnect(sid)
            return False

        # Authenticate user
        is_authenticated, user = await authenticate_user_connection(sid, auth)

        if not is_authenticated or not user:
            error_response = await handle_authentication_failure(
                sid, "Authentication failed"
            )
            await sio.emit("auth_error", error_response, room=sid)
            await sio.disconnect(sid)
            return False

        # Store user session mapping
        user_sessions[sid] = user.id

        # Send successful connection response
        await sio.emit(
            "connected",
            {
                "success": True,
                "user_id": str(user.id),
                "username": user.username,
                "message": "Connected successfully",
            },
            room=sid,
        )

        logger.info(f"User {user.username} connected successfully with session {sid}")
        return True

    except Exception as e:
        logger.error(f"Error during connection for {sid}: {e}")
        sio = get_socketio_server()
        if sio:
            await sio.emit(
                "connection_error", {"error": "Internal server error"}, room=sid
            )
            await sio.disconnect(sid)
        return False


async def handle_disconnect(sid: str):
    """
    Handles Socket.io client disconnections.

    Performs cleanup operations including room departure notifications
    and session data cleanup.
    """
    try:
        user_id = user_sessions.get(sid)

        if user_id:
            logger.info(f"User {user_id} disconnecting with session {sid}")

            # Clean up all user sessions and room memberships
            await cleanup_user_sessions(user_id)

            # Clean up typing indicators
            await cleanup_typing_indicators(user_id)

        else:
            logger.info(f"Anonymous session {sid} disconnected")

    except Exception as e:
        logger.error(f"Error during disconnect for {sid}: {e}")


async def handle_join_chat_session(sid: str, data: Dict[str, Any]):
    """
    Handles user requests to join a specific chat session room.

    Validates permissions and adds the user to the appropriate room
    for real-time message exchange.
    """
    try:
        session_id = data.get("session_id")
        user_id = user_sessions.get(sid)

        sio = get_socketio_server()
        if not sio:
            return

        if not session_id or not user_id:
            await sio.emit(
                "join_error",
                {"error": "Missing session_id or user not authenticated"},
                room=sid,
            )
            return

        # Check room access permission
        has_access = await check_room_access_permission(user_id, session_id)
        if not has_access:
            await sio.emit(
                "join_error", {"error": "Access denied to chat session"}, room=sid
            )
            return

        # Join user to room
        joined = await join_user_to_room(sid, session_id, user_id)

        if joined:
            await sio.emit(
                "joined_session",
                {
                    "success": True,
                    "session_id": session_id,
                    "message": "Successfully joined chat session",
                },
                room=sid,
            )

            logger.info(f"User {user_id} joined chat session {session_id}")
        else:
            await sio.emit(
                "join_error", {"error": "Failed to join chat session"}, room=sid
            )

    except Exception as e:
        logger.error(f"Error joining chat session for {sid}: {e}")
        sio = get_socketio_server()
        if sio:
            await sio.emit("join_error", {"error": "Internal server error"}, room=sid)


async def handle_leave_chat_session(sid: str, data: Dict[str, Any]):
    """
    Handles user requests to leave a chat session room.

    Removes the user from the room and notifies other participants
    about the departure.
    """
    try:
        session_id = data.get("session_id")
        user_id = user_sessions.get(sid)

        sio = get_socketio_server()
        if not sio:
            return

        if not session_id:
            await sio.emit("leave_error", {"error": "Missing session_id"}, room=sid)
            return

        # Leave room
        left = await leave_user_from_room(sid, session_id)

        if left:
            await sio.emit(
                "left_session",
                {
                    "success": True,
                    "session_id": session_id,
                    "message": "Successfully left chat session",
                },
                room=sid,
            )

            if user_id:
                logger.info(f"User {user_id} left chat session {session_id}")
        else:
            await sio.emit(
                "leave_error", {"error": "Failed to leave chat session"}, room=sid
            )

    except Exception as e:
        logger.error(f"Error leaving chat session for {sid}: {e}")
        sio = get_socketio_server()
        if sio:
            await sio.emit("leave_error", {"error": "Internal server error"}, room=sid)


async def handle_send_message(sid: str, data: Dict[str, Any]):
    """
    Handles message sending within a chat session.

    Validates the message, persists it to database, and broadcasts
    to all participants in the session room.
    """
    try:
        session_id = data.get("session_id")
        content = data.get("content")
        user_id = user_sessions.get(sid)

        sio = get_socketio_server()
        if not sio:
            return

        if not session_id or not content or not user_id:
            await sio.emit(
                "message_error",
                {"error": "Missing required fields: session_id, content"},
                room=sid,
            )
            return

        # Validate content length
        if len(content.strip()) == 0:
            await sio.emit(
                "message_error", {"error": "Message content cannot be empty"}, room=sid
            )
            return

        if len(content) > 2000:  # Message length limit
            await sio.emit(
                "message_error",
                {"error": "Message too long (max 2000 characters)"},
                room=sid,
            )
            return

        # Verify user has access to session
        has_access = await check_room_access_permission(user_id, session_id)
        if not has_access:
            await sio.emit(
                "message_error", {"error": "Access denied to chat session"}, room=sid
            )
            return

        # Save message to database
        message_id = await save_message_to_database(session_id, user_id, content)

        if not message_id:
            await sio.emit(
                "message_error", {"error": "Failed to save message"}, room=sid
            )
            return

        # Get user info for broadcast
        user = await get_user_from_session(sid, user_sessions)
        username = user.username if user else "Unknown"

        # Prepare message data for broadcast
        message_data = {
            "message_id": str(message_id),
            "session_id": session_id,
            "user_id": user_id,
            "username": username,
            "content": content,
            "timestamp": utc_now().isoformat(),
            "sender": "user",
        }

        # Broadcast message to all participants in the room
        await broadcast_to_room(session_id, "new_message", message_data)

        # Send delivery confirmation to sender
        await sio.emit(
            "message_sent",
            {
                "success": True,
                "message_id": str(message_id),
                "timestamp": message_data["timestamp"],
            },
            room=sid,
        )

        logger.info(f"Message sent by user {user_id} in session {session_id}")

    except Exception as e:
        logger.error(f"Error sending message for {sid}: {e}")
        sio = get_socketio_server()
        if sio:
            await sio.emit(
                "message_error", {"error": "Internal server error"}, room=sid
            )


async def handle_typing_start(sid: str, data: Dict[str, Any]):
    """
    Handles typing indicator start events.

    Notifies other participants in the session that a user
    has started typing a message.
    """
    try:
        session_id = data.get("session_id")
        user_id = user_sessions.get(sid)

        if not session_id or not user_id:
            return

        # Verify access
        has_access = await check_room_access_permission(user_id, session_id)
        if not has_access:
            return

        # Track typing user
        if session_id not in typing_users:
            typing_users[session_id] = {}

        typing_users[session_id][user_id] = utc_now()

        # Get username
        user = await get_user_from_session(sid, user_sessions)
        username = user.username if user else "Unknown"

        # Broadcast typing indicator to other participants
        await broadcast_to_room(
            session_id,
            "user_typing",
            {"user_id": user_id, "username": username, "is_typing": True},
            exclude_sid=sid,
        )

        logger.debug(f"User {user_id} started typing in session {session_id}")

    except Exception as e:
        logger.error(f"Error handling typing start for {sid}: {e}")


async def handle_typing_stop(sid: str, data: Dict[str, Any]):
    """
    Handles typing indicator stop events.

    Notifies other participants that a user has stopped
    typing and cleans up typing state.
    """
    try:
        session_id = data.get("session_id")
        user_id = user_sessions.get(sid)

        if not session_id or not user_id:
            return

        # Clean up typing state
        if session_id in typing_users and user_id in typing_users[session_id]:
            del typing_users[session_id][user_id]

            if not typing_users[session_id]:
                del typing_users[session_id]

        # Get username
        user = await get_user_from_session(sid, user_sessions)
        username = user.username if user else "Unknown"

        # Broadcast typing stop to other participants
        await broadcast_to_room(
            session_id,
            "user_typing",
            {"user_id": user_id, "username": username, "is_typing": False},
            exclude_sid=sid,
        )

        logger.debug(f"User {user_id} stopped typing in session {session_id}")

    except Exception as e:
        logger.error(f"Error handling typing stop for {sid}: {e}")


async def handle_message_delivered(sid: str, data: Dict[str, Any]):
    """
    Handles message delivery confirmation from clients.

    Tracks message delivery status for reliable communication
    and potential retry mechanisms.
    """
    try:
        message_id = data.get("message_id")
        user_id = user_sessions.get(sid)

        if not message_id or not user_id:
            return

        # Log delivery confirmation
        logger.debug(f"Message {message_id} delivered to user {user_id}")

        # Update delivery status in database if needed
        await update_message_delivery_status(message_id, user_id, "delivered")

    except Exception as e:
        logger.error(f"Error handling message delivery for {sid}: {e}")


async def handle_message_read(sid: str, data: Dict[str, Any]):
    """
    Handles message read confirmation from clients.

    Tracks read receipts for enhanced user experience
    and conversation state management.
    """
    try:
        message_id = data.get("message_id")
        user_id = user_sessions.get(sid)

        if not message_id or not user_id:
            return

        # Log read confirmation
        logger.debug(f"Message {message_id} read by user {user_id}")

        # Update read status in database if needed
        await update_message_delivery_status(message_id, user_id, "read")

    except Exception as e:
        logger.error(f"Error handling message read for {sid}: {e}")


def register_event_handlers():
    """
    Registers all event handlers with the Socket.io server.

    This function is called after the Socket.io server is created
    to bind all event handlers to their respective events.
    """
    sio = get_socketio_server()
    if not sio:
        logger.error("Cannot register events: Socket.io server not available")
        return

    # Register event handlers
    sio.on("connect", handle_connect)
    sio.on("disconnect", handle_disconnect)
    sio.on("join_chat_session", handle_join_chat_session)
    sio.on("leave_chat_session", handle_leave_chat_session)
    sio.on("send_message", handle_send_message)
    sio.on("typing_start", handle_typing_start)
    sio.on("typing_stop", handle_typing_stop)
    sio.on("message_delivered", handle_message_delivered)
    sio.on("message_read", handle_message_read)

    logger.info("Socket.io event handlers registered successfully")


async def save_message_to_database(
    session_id: str, user_id: str, content: str
) -> Optional[str]:
    """
    Persists a chat message to the database.

    Creates a new ChatMessage record with the provided content
    and returns the message ID for reference.
    """
    db = SessionLocal()
    try:
        # Create new message record
        message = ChatMessage(
            chat_session_id=session_id,
            sender="user",
            content=content,
            sent_at=utc_now(),
        )

        db.add(message)
        db.commit()
        db.refresh(message)

        logger.debug(f"Message saved to database with ID {message.id}")
        return str(message.id)

    except Exception as e:
        logger.error(f"Error saving message to database: {e}")
        db.rollback()
        return None
    finally:
        db.close()


async def update_message_delivery_status(
    message_id: str, user_id: str, status: str
) -> bool:
    """
    Updates message delivery or read status in the database.

    Tracks message state for delivery confirmation and read receipts
    to enhance communication reliability.
    """
    try:
        # Implementation would depend on specific delivery tracking requirements
        # For now, just log the status update
        logger.debug(
            f"Message {message_id} status updated to {status} for user {user_id}"
        )
        return True

    except Exception as e:
        logger.error(f"Error updating message delivery status: {e}")
        return False


async def cleanup_typing_indicators(user_id: str) -> None:
    """
    Removes typing indicators for a disconnected user.

    Cleans up typing state when users disconnect to prevent
    stale typing indicators in chat sessions.
    """
    try:
        sessions_to_clean = []

        # Find sessions where user was typing
        for session_id, users in typing_users.items():
            if user_id in users:
                sessions_to_clean.append(session_id)

        # Clean up and notify
        for session_id in sessions_to_clean:
            if user_id in typing_users[session_id]:
                del typing_users[session_id][user_id]

                # Notify other participants
                await broadcast_to_room(
                    session_id, "user_typing", {"user_id": user_id, "is_typing": False}
                )

                if not typing_users[session_id]:
                    del typing_users[session_id]

        logger.debug(f"Cleaned up typing indicators for user {user_id}")

    except Exception as e:
        logger.error(f"Error cleaning up typing indicators: {e}")
