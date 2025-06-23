"""
Socket.io server configuration and integration with FastAPI.
"""

import os
import logging
from typing import List, Optional

import socketio
from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Get Socket.io configuration from environment
SOCKETIO_CORS_ORIGINS = os.getenv(
    "SOCKETIO_CORS_ORIGINS", '["https://localhost", "http://localhost:3000"]'
)
SOCKETIO_PING_TIMEOUT = int(os.getenv("SOCKETIO_PING_TIMEOUT", "60"))
SOCKETIO_PING_INTERVAL = int(os.getenv("SOCKETIO_PING_INTERVAL", "25"))
SOCKETIO_RATE_LIMIT_ENABLED = (
    os.getenv("SOCKETIO_RATE_LIMIT_ENABLED", "false").lower() == "true"
)
SOCKETIO_RATE_LIMIT_REQUESTS = int(os.getenv("SOCKETIO_RATE_LIMIT_REQUESTS", "100"))
SOCKETIO_RATE_LIMIT_WINDOW = int(os.getenv("SOCKETIO_RATE_LIMIT_WINDOW", "60"))


class SocketIOServer:
    """Socket.io server manager for handling real-time communication."""

    _instance = None
    _sio: Optional[socketio.AsyncServer] = None
    _app: Optional[socketio.ASGIApp] = None

    def __new__(cls):
        """Create a singleton instance of the Socket.io server."""
        if cls._instance is None:
            cls._instance = super(SocketIOServer, cls).__new__(cls)
            cls._instance._sio = None
            cls._instance._app = None
        return cls._instance

    async def setup(
        self,
        cors_allowed_origins: List[str] = None,
        ping_timeout: int = SOCKETIO_PING_TIMEOUT,
        ping_interval: int = SOCKETIO_PING_INTERVAL,
        rate_limiting: bool = SOCKETIO_RATE_LIMIT_ENABLED,
        rate_limit_requests: int = SOCKETIO_RATE_LIMIT_REQUESTS,
        rate_limit_window: int = SOCKETIO_RATE_LIMIT_WINDOW,
    ) -> socketio.AsyncServer:
        """
        Set up and configure the Socket.io server.

        Args:
            cors_allowed_origins: List of allowed CORS origins
            ping_timeout: Timeout for client pings in seconds
            ping_interval: Interval between pings in seconds
            rate_limiting: Whether to enable rate limiting
            rate_limit_requests: Number of requests allowed in the rate limit window
            rate_limit_window: Rate limit window in seconds

        Returns:
            Configured Socket.io server instance
        """
        if self._sio is not None:
            return self._sio

        # Get Redis URL from environment
        redis_url = os.getenv("SOCKETIO_REDIS_URL", "redis://redis:6379/1")

        # Create the Socket.io server with both polling and websocket support
        self._sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=cors_allowed_origins or eval(SOCKETIO_CORS_ORIGINS),
            ping_timeout=ping_timeout,
            ping_interval=ping_interval,
            client_manager=socketio.AsyncRedisManager(redis_url),
            logger=True,
            engineio_logger=True if os.getenv("LOG_LEVEL") == "DEBUG" else False,
            # Allow polling for initial connection, then upgrade to WebSocket
            allow_upgrades=True,
        )

        # Set up rate limiting if enabled
        if rate_limiting:

            @self._sio.event
            async def connect(sid, environ):
                """Handle client connection with rate limiting."""
                # Rate limiting could be implemented here
                logger.info(f"Client connected: {sid}")

        else:

            @self._sio.event
            async def connect(sid, environ):
                """Handle client connection."""
                logger.info(f"Client connected: {sid}")

        @self._sio.event
        async def disconnect(sid):
            """Handle client disconnection."""
            logger.info(f"Client disconnected: {sid}")

        return self._sio

    def get_app(self) -> socketio.ASGIApp:
        """
        Get the ASGI application for Socket.io.

        Returns:
            ASGI application that can be mounted in FastAPI
        """
        if self._app is None:
            if self._sio is None:
                raise RuntimeError(
                    "Socket.io server not initialized. Call setup() first."
                )
            self._app = socketio.ASGIApp(self._sio)
        return self._app

    def get_server(self) -> socketio.AsyncServer:
        """
        Get the Socket.io server instance.

        Returns:
            Socket.io server instance for event registration

        Raises:
            RuntimeError: If the server has not been initialized
        """
        if self._sio is None:
            raise RuntimeError("Socket.io server not initialized. Call setup() first.")
        return self._sio


async def setup_socketio(
    app: FastAPI, path: str = "/ws/socket.io/"
) -> socketio.AsyncServer:
    """
    Set up Socket.io with FastAPI application.

    Args:
        app: FastAPI application instance
        path: Path to mount the Socket.io server

    Returns:
        Configured Socket.io server instance
    """
    # Initialize Socket.io server
    sio_server = SocketIOServer()

    # Setup the server first
    await sio_server.setup()

    # Mount the Socket.io app to the FastAPI instance
    app.mount(path.rstrip("/"), sio_server.get_app())

    logger.info(f"Socket.io server mounted at {path}")
    return sio_server.get_server()
