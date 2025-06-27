"""
Socket.io event handlers for different message types.

This module defines the event handlers for various Socket.io events,
including connection management, chat messages, and delivery confirmations.
"""

import logging
import uuid
from typing import Dict, Any

from app.services.socketio.server import socketio_server
from app.services.socketio.rooms import join_room, leave_room, get_room_participants
from app.services.socketio.message_queue import enqueue_message, confirm_delivery
from app.utils.datetime_helper import utc_now

# Configure logger
logger = logging.getLogger(__name__)


async def handle_connect(sid: str, environ: Dict[str, Any]) -> None:
    """
    Handle client connection event.

    Args:
        sid: Session ID of the connected client
        environ: WSGI environment dictionary
    """
    logger.info(f"Client connected: {sid}")

    # Initialize session data
    await socketio_server.save_session(
        sid,
        {
            "connected_at": utc_now().isoformat(),
            "rooms": [],
            "user_id": None,
            "is_authenticated": False,
        },
    )

    # Acknowledge connection to client
    await socketio_server.emit(
        "connect_confirmed",
        {"status": "connected", "sid": sid, "timestamp": utc_now().isoformat()},
        room=sid,
    )


async def handle_disconnect(sid: str) -> None:
    """
    Handle client disconnection event.

    Args:
        sid: Session ID of the disconnected client
    """
    try:
        # Get session data before it's removed
        session = await socketio_server.get_session(sid)

        # Leave all rooms
        if session and "rooms" in session:
            for room in session["rooms"]:
                await leave_room(sid, room)

        logger.info(f"Client disconnected: {sid}")
    except Exception as e:
        logger.error(f"Error during disconnect handler: {e}")


async def handle_authenticate(sid: str, data: Dict[str, Any]) -> None:
    """
    Handle client authentication.

    Args:
        sid: Session ID of the client
        data: Authentication data containing user_id
    """
    user_id = data.get("user_id")

    if not user_id:
        await socketio_server.emit(
            "auth_error",
            {"status": "error", "message": "User ID is required"},
            room=sid,
        )
        return

    # Update session with authentication info
    session = await socketio_server.get_session(sid)
    session["user_id"] = user_id
    session["is_authenticated"] = True
    await socketio_server.save_session(sid, session)

    # Notify client of successful authentication
    await socketio_server.emit(
        "auth_confirmed",
        {
            "status": "authenticated",
            "user_id": user_id,
            "timestamp": utc_now().isoformat(),
        },
        room=sid,
    )

    logger.info(f"Client authenticated: {sid}, user_id: {user_id}")


async def handle_join_room(sid: str, data: Dict[str, Any]) -> None:
    """
    Handle client joining a room.

    Args:
        sid: Session ID of the client
        data: Room data containing room_id
    """
    room_id = data.get("room_id")

    if not room_id:
        await socketio_server.emit(
            "room_error",
            {"status": "error", "message": "Room ID is required"},
            room=sid,
        )
        return

    # Join room and update session
    session = await socketio_server.get_session(sid)

    # Ensure client is authenticated
    if not session.get("is_authenticated"):
        await socketio_server.emit(
            "room_error",
            {"status": "error", "message": "Authentication required to join rooms"},
            room=sid,
        )
        return

    # Join the room
    await join_room(sid, room_id)

    # Update session
    if "rooms" not in session:
        session["rooms"] = []
    if room_id not in session["rooms"]:
        session["rooms"].append(room_id)
    await socketio_server.save_session(sid, session)

    # Notify room of new participant
    participants = await get_room_participants(room_id)
    await socketio_server.emit(
        "room_update",
        {
            "room_id": room_id,
            "participants": participants,
            "action": "join",
            "user_id": session.get("user_id"),
            "timestamp": utc_now().isoformat(),
        },
        room=room_id,
    )

    logger.info(f"Client {sid} joined room: {room_id}")


async def handle_leave_room(sid: str, data: Dict[str, Any]) -> None:
    """
    Handle client leaving a room.

    Args:
        sid: Session ID of the client
        data: Room data containing room_id
    """
    room_id = data.get("room_id")

    if not room_id:
        await socketio_server.emit(
            "room_error",
            {"status": "error", "message": "Room ID is required"},
            room=sid,
        )
        return

    # Get session data
    session = await socketio_server.get_session(sid)

    # Leave the room
    await leave_room(sid, room_id)

    # Update session
    if "rooms" in session and room_id in session["rooms"]:
        session["rooms"].remove(room_id)
        await socketio_server.save_session(sid, session)

    # Notify room of participant leaving
    participants = await get_room_participants(room_id)
    await socketio_server.emit(
        "room_update",
        {
            "room_id": room_id,
            "participants": participants,
            "action": "leave",
            "user_id": session.get("user_id"),
            "timestamp": utc_now().isoformat(),
        },
        room=room_id,
    )

    logger.info(f"Client {sid} left room: {room_id}")


async def handle_chat_message(sid: str, data: Dict[str, Any]) -> None:
    """
    Handle chat message event.

    Args:
        sid: Session ID of the client
        data: Message data containing room_id and content
    """
    # Validate required fields
    room_id = data.get("room_id")
    content = data.get("content")

    if not room_id or not content:
        await socketio_server.emit(
            "message_error",
            {"status": "error", "message": "Room ID and content are required"},
            room=sid,
        )
        return

    # Get session data
    session = await socketio_server.get_session(sid)

    # Ensure client is authenticated
    if not session.get("is_authenticated"):
        await socketio_server.emit(
            "message_error",
            {"status": "error", "message": "Authentication required to send messages"},
            room=sid,
        )
        return

    # Ensure client is in the room
    if "rooms" not in session or room_id not in session["rooms"]:
        await socketio_server.emit(
            "message_error",
            {
                "status": "error",
                "message": "You must join the room before sending messages",
            },
            room=sid,
        )
        return

    # Generate message ID for tracking
    message_id = str(uuid.uuid4())
    timestamp = utc_now().isoformat()
    user_id = session.get("user_id")

    # Create message object
    message = {
        "id": message_id,
        "room_id": room_id,
        "content": content,
        "sender_id": user_id,
        "sender_sid": sid,
        "timestamp": timestamp,
        "delivered": False,
    }

    # Enqueue message for processing
    await enqueue_message(message)

    # Emit message to room
    await socketio_server.emit("chat_message", message, room=room_id)

    # Send delivery confirmation to sender
    await socketio_server.emit(
        "message_sent",
        {
            "message_id": message_id,
            "status": "sent",
            "room_id": room_id,
            "timestamp": utc_now().isoformat(),
        },
        room=sid,
    )

    logger.info(f"Message sent to room {room_id} by user {user_id}")


async def handle_message_received(sid: str, data: Dict[str, Any]) -> None:
    """
    Handle message received confirmation from client.

    Args:
        sid: Session ID of the client
        data: Data containing message_id to confirm delivery
    """
    message_id = data.get("message_id")

    if not message_id:
        await socketio_server.emit(
            "delivery_error",
            {"status": "error", "message": "Message ID is required"},
            room=sid,
        )
        return

    # Get session data
    session = await socketio_server.get_session(sid)

    # Mark message as delivered
    await confirm_delivery(message_id, session.get("user_id"))

    logger.debug(f"Message {message_id} confirmed received by client {sid}")


async def handle_typing(sid: str, data: Dict[str, Any]) -> None:
    """
    Handle typing indicator events.

    Args:
        sid: Session ID of the client
        data: Data containing room_id and typing status
    """
    room_id = data.get("room_id")
    is_typing = data.get("is_typing", False)

    if not room_id:
        await socketio_server.emit(
            "typing_error",
            {"status": "error", "message": "Room ID is required"},
            room=sid,
        )
        return

    # Get session data
    session = await socketio_server.get_session(sid)
    user_id = session.get("user_id")

    if not user_id:
        await socketio_server.emit(
            "typing_error",
            {"status": "error", "message": "Authentication required"},
            room=sid,
        )
        return

    # Broadcast typing status to room, except sender
    await socketio_server.emit(
        "typing_indicator",
        {
            "room_id": room_id,
            "user_id": user_id,
            "is_typing": is_typing,
            "timestamp": utc_now().isoformat(),
        },
        room=room_id,
        skip_sid=sid,
    )


# Register event handlers with Socket.io server
def register_handlers():
    """Register all event handlers with the Socket.io server."""
    socketio_server.on("connect", handle_connect)
    socketio_server.on("disconnect", handle_disconnect)
    socketio_server.on("authenticate", handle_authenticate)
    socketio_server.on("join_room", handle_join_room)
    socketio_server.on("leave_room", handle_leave_room)
    socketio_server.on("chat_message", handle_chat_message)
    socketio_server.on("message_received", handle_message_received)
    socketio_server.on("typing", handle_typing)


# Register handlers when module is imported
register_handlers()
