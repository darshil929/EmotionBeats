"""
Socket.io server configuration and FastAPI integration.

This module provides the core Socket.io server functionality,
initializes the Redis message queue, and handles integration with FastAPI.
"""

import os
import socketio
import logging
from typing import Optional, Dict, Any, Callable
from fastapi import FastAPI

# Configure logger
logger = logging.getLogger(__name__)

# Socket.io configuration from environment variables
SOCKETIO_CORS_ORIGINS = os.getenv(
    "SOCKETIO_CORS_ORIGINS", '["http://localhost:3000", "https://localhost"]'
)
SOCKETIO_PING_TIMEOUT = int(os.getenv("SOCKETIO_PING_TIMEOUT", "60"))
SOCKETIO_PING_INTERVAL = int(os.getenv("SOCKETIO_PING_INTERVAL", "25"))
SOCKETIO_MAX_HTTP_BUFFER_SIZE = int(
    os.getenv("SOCKETIO_MAX_HTTP_BUFFER_SIZE", "1000000")
)
SOCKETIO_REDIS_URL = os.getenv("SOCKETIO_REDIS_URL", "redis://redis:6379/1")


class SocketIOServer:
    """Socket.io server implementation with Redis message queue integration."""

    _instance: Optional["SocketIOServer"] = None
    _initialized: bool = False

    def __new__(cls):
        """Singleton pattern to ensure only one server instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the Socket.io server with Redis message queue."""
        if self._initialized:
            return

        try:
            # Parse CORS origins from environment
            cors_origins = eval(SOCKETIO_CORS_ORIGINS)

            # Initialize Redis manager for message queue
            self.redis_manager = socketio.AsyncRedisManager(SOCKETIO_REDIS_URL)

            # Create Socket.io server
            self.sio = socketio.AsyncServer(
                async_mode="asgi",
                client_manager=self.redis_manager,
                cors_allowed_origins=cors_origins,
                ping_timeout=SOCKETIO_PING_TIMEOUT,
                ping_interval=SOCKETIO_PING_INTERVAL,
                max_http_buffer_size=SOCKETIO_MAX_HTTP_BUFFER_SIZE,
                logger=True,
                engineio_logger=False,
            )

            # Create ASGI app
            self.app = socketio.ASGIApp(self.sio)

            # Set initialized flag
            self._initialized = True
            logger.info("Socket.IO server initialized with Redis message queue")

        except Exception as e:
            logger.error(f"Failed to initialize Socket.IO server: {e}")
            raise

    def mount_to_fastapi(self, fastapi_app: FastAPI, path: str = "/ws") -> None:
        """Mount the Socket.io server to a FastAPI application.

        Args:
            fastapi_app: The FastAPI application to mount to
            path: The URL path to mount the Socket.io server on
        """
        try:
            # Register startup and shutdown events
            fastapi_app.add_event_handler("startup", self.startup_event)
            fastapi_app.add_event_handler("shutdown", self.shutdown_event)

            # Mount Socket.io app to FastAPI
            fastapi_app.mount(path, self.app)
            logger.info(f"Socket.IO server mounted to FastAPI at path: {path}")

        except Exception as e:
            logger.error(f"Failed to mount Socket.IO server to FastAPI: {e}")
            raise

    async def startup_event(self) -> None:
        """Perform startup tasks when the FastAPI application starts."""
        logger.info("Socket.IO server starting up")

    async def shutdown_event(self) -> None:
        """Perform cleanup tasks when the FastAPI application shuts down."""
        logger.info("Socket.IO server shutting down")
        if hasattr(self, "redis_manager") and self.redis_manager:
            await self.redis_manager.disconnect()

    def on(self, event: str, handler: Callable) -> None:
        """Register an event handler.

        Args:
            event: Event name to listen for
            handler: Function to call when the event is received
        """
        self.sio.on(event, handler)

    async def emit(
        self,
        event: str,
        data: Any = None,
        room: Optional[str] = None,
        skip_sid: Optional[str] = None,
    ) -> None:
        """Emit an event to connected clients.

        Args:
            event: Event name to emit
            data: Data to send with the event
            room: Room to emit to, or None for global broadcast
            skip_sid: Session ID to skip, or None to send to all clients
        """
        await self.sio.emit(event, data, room=room, skip_sid=skip_sid)

    async def enter_room(self, sid: str, room: str) -> None:
        """Add a client to a room.

        Args:
            sid: Session ID of the client
            room: Room name to join
        """
        await self.sio.enter_room(sid, room)

    async def leave_room(self, sid: str, room: str) -> None:
        """Remove a client from a room.

        Args:
            sid: Session ID of the client
            room: Room name to leave
        """
        await self.sio.leave_room(sid, room)

    async def get_session(self, sid: str) -> Dict[str, Any]:
        """Get the session data for a client.

        Args:
            sid: Session ID of the client

        Returns:
            Session data dictionary
        """
        return await self.sio.get_session(sid)

    async def save_session(self, sid: str, session: Dict[str, Any]) -> None:
        """Save session data for a client.

        Args:
            sid: Session ID of the client
            session: Session data dictionary to save
        """
        await self.sio.save_session(sid, session)


# Singleton instance for use throughout the application
socketio_server = SocketIOServer()
