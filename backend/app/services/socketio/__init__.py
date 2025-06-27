"""
Socket.io integration package for real-time communication.

This package provides real-time communication capabilities using Socket.io,
including server configuration, event handling, room management, and
message processing.
"""

from app.services.socketio.server import socketio_server
from app.services.socketio.events import register_handlers
from app.services.socketio.rooms import (
    join_room,
    leave_room,
    get_room_participants,
    get_user_rooms,
    create_room,
)
from app.services.socketio.message_queue import (
    enqueue_message,
    get_room_messages,
    get_pending_messages,
)

__all__ = [
    "socketio_server",
    "register_handlers",
    "join_room",
    "leave_room",
    "get_room_participants",
    "get_user_rooms",
    "create_room",
    "enqueue_message",
    "get_room_messages",
    "get_pending_messages",
]

# Ensure event handlers are registered when package is imported
register_handlers()
