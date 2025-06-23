"""
Socket.io event handlers for chat functionality.
"""

import logging
from typing import Any, Dict

import socketio

from app.services.socketio.message_handler import process_message
from app.utils.datetime_helper import utc_now

logger = logging.getLogger(__name__)


class ChatNamespace:
    """Namespace for chat-related Socket.io events."""

    def __init__(self, sio: socketio.AsyncServer):
        """
        Initialize the chat namespace.

        Args:
            sio: Socket.io server instance
        """
        self.sio = sio
        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """Register all event handlers with the Socket.io server."""
        # Connect and disconnect handlers are handled in server.py
        # Register message handlers
        self.sio.on("message", self.on_message)
        self.sio.on("typing", self.on_typing)
        self.sio.on("stop_typing", self.on_stop_typing)
        self.sio.on("join_room", self.on_join_room)
        self.sio.on("leave_room", self.on_leave_room)
        self.sio.on("read_receipt", self.on_read_receipt)

    async def on_message(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle incoming chat messages.

        Args:
            sid: Session ID of the client
            data: Message data containing content and metadata
        """
        try:
            # Extract message content and metadata
            message_content = data.get("content", "")
            session_id = data.get("session_id")
            user_id = data.get("user_id")

            if not message_content or not session_id:
                await self.sio.emit(
                    "error", {"message": "Invalid message data"}, room=sid
                )
                return

            # Get user data from session store
            user_data = await self.sio.get_session(sid)

            # Verify authentication
            if not user_data or user_data.get("user_id") != user_id:
                await self.sio.emit(
                    "error", {"message": "Authentication required"}, room=sid
                )
                return

            # Process the message through the AI pipeline
            processed_message = await process_message(
                session_id=session_id,
                user_id=user_id,
                content=message_content,
                sid=sid,
            )

            # Emit acknowledgment to the sender
            await self.sio.emit(
                "message_received",
                {"message_id": processed_message.get("id")},
                room=sid,
            )

            # Broadcast the message to the room (session)
            await self.sio.emit(
                "message",
                processed_message,
                room=session_id,
                skip_sid=sid,  # Skip the sender
            )

            logger.info(f"Message processed for session {session_id}")

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await self.sio.emit(
                "error", {"message": f"Error processing message: {str(e)}"}, room=sid
            )

    async def on_typing(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle typing indicator events.

        Args:
            sid: Session ID of the client
            data: Data containing session ID
        """
        try:
            session_id = data.get("session_id")
            user_id = data.get("user_id")

            if not session_id:
                return

            # Get user data from session store
            user_data = await self.sio.get_session(sid)

            # Verify authentication
            if not user_data or user_data.get("user_id") != user_id:
                return

            # Broadcast typing event to the room
            await self.sio.emit(
                "typing",
                {"user_id": user_id, "session_id": session_id},
                room=session_id,
                skip_sid=sid,  # Skip the sender
            )

        except Exception as e:
            logger.error(f"Error handling typing event: {str(e)}")

    async def on_stop_typing(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle stop typing indicator events.

        Args:
            sid: Session ID of the client
            data: Data containing session ID
        """
        try:
            session_id = data.get("session_id")
            user_id = data.get("user_id")

            if not session_id:
                return

            # Get user data from session store
            user_data = await self.sio.get_session(sid)

            # Verify authentication
            if not user_data or user_data.get("user_id") != user_id:
                return

            # Broadcast stop typing event to the room
            await self.sio.emit(
                "stop_typing",
                {"user_id": user_id, "session_id": session_id},
                room=session_id,
                skip_sid=sid,  # Skip the sender
            )

        except Exception as e:
            logger.error(f"Error handling stop typing event: {str(e)}")

    async def on_join_room(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle room join requests.

        Args:
            sid: Session ID of the client
            data: Data containing session ID to join
        """
        try:
            session_id = data.get("session_id")
            user_id = data.get("user_id")

            if not session_id:
                await self.sio.emit(
                    "error", {"message": "Session ID required"}, room=sid
                )
                return

            # Get user data from session store
            user_data = await self.sio.get_session(sid)

            # Verify authentication
            if not user_data or user_data.get("user_id") != user_id:
                await self.sio.emit(
                    "error", {"message": "Authentication required"}, room=sid
                )
                return

            # Add the client to the room
            self.sio.enter_room(sid, session_id)

            # Notify the client
            await self.sio.emit("room_joined", {"session_id": session_id}, room=sid)

            logger.info(f"User {user_id} joined session {session_id}")

        except Exception as e:
            logger.error(f"Error joining room: {str(e)}")
            await self.sio.emit(
                "error", {"message": f"Error joining room: {str(e)}"}, room=sid
            )

    async def on_leave_room(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle room leave requests.

        Args:
            sid: Session ID of the client
            data: Data containing session ID to leave
        """
        try:
            session_id = data.get("session_id")

            if not session_id:
                return

            # Remove the client from the room
            self.sio.leave_room(sid, session_id)

            # Notify the client
            await self.sio.emit("room_left", {"session_id": session_id}, room=sid)

        except Exception as e:
            logger.error(f"Error leaving room: {str(e)}")

    async def on_read_receipt(self, sid: str, data: Dict[str, Any]) -> None:
        """
        Handle read receipt events.

        Args:
            sid: Session ID of the client
            data: Data containing message IDs that were read
        """
        try:
            session_id = data.get("session_id")
            user_id = data.get("user_id")
            message_ids = data.get("message_ids", [])

            if not session_id or not message_ids:
                return

            # Get user data from session store
            user_data = await self.sio.get_session(sid)

            # Verify authentication
            if not user_data or user_data.get("user_id") != user_id:
                return

            # Broadcast read receipt to the room
            await self.sio.emit(
                "read_receipt",
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "message_ids": message_ids,
                    "timestamp": utc_now().isoformat(),
                },
                room=session_id,
            )

        except Exception as e:
            logger.error(f"Error handling read receipt: {str(e)}")


def register_handlers(sio: socketio.AsyncServer) -> None:
    """
    Register all Socket.io event handlers.

    Args:
        sio: Socket.io server instance
    """
    ChatNamespace(sio)
    logger.info("Registered Socket.io event handlers")
