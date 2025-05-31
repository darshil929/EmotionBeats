"""
Socket.io server configuration and FastAPI integration.

Manages the Socket.io AsyncServer instance with Redis adapter for scalability
and handles the lifecycle integration with the FastAPI application.
"""

import os
import json
import logging
from typing import Optional
import socketio
from fastapi import FastAPI

from app.core.redis import get_redis_socketio

logger = logging.getLogger(__name__)

# Socket.io configuration from environment
SOCKETIO_CORS_ORIGINS = json.loads(
    os.getenv("SOCKETIO_CORS_ORIGINS", '["http://localhost:3000", "https://localhost"]')
)
SOCKETIO_PING_TIMEOUT = int(os.getenv("SOCKETIO_PING_TIMEOUT", "60"))
SOCKETIO_PING_INTERVAL = int(os.getenv("SOCKETIO_PING_INTERVAL", "25"))
SOCKETIO_REDIS_URL = os.getenv("SOCKETIO_REDIS_URL", "redis://redis:6379/1")

# Global Socket.io server instance
sio: Optional[socketio.AsyncServer] = None


async def create_socketio_server() -> socketio.AsyncServer:
    """
    Creates and configures the Socket.io AsyncServer instance.

    Configures Redis adapter for horizontal scaling and sets up CORS
    for cross-origin WebSocket connections.
    """
    try:
        # Test Redis connection first
        redis_client = await get_redis_socketio()
        await redis_client.ping()
        logger.info("Redis connection verified for Socket.io")

        # Create Redis adapter using URL (not client object)
        redis_manager = socketio.AsyncRedisManager(SOCKETIO_REDIS_URL)

        # Create AsyncServer with Redis adapter
        server = socketio.AsyncServer(
            client_manager=redis_manager,
            cors_allowed_origins=SOCKETIO_CORS_ORIGINS,
            ping_timeout=SOCKETIO_PING_TIMEOUT,
            ping_interval=SOCKETIO_PING_INTERVAL,
            logger=True,
            engineio_logger=False,
        )

        logger.info("Socket.io server created successfully with Redis adapter")
        return server

    except Exception as e:
        logger.error(f"Failed to create Socket.io server: {e}")
        raise


async def init_socketio(app: FastAPI) -> None:
    """
    Initializes Socket.io server and mounts it to the FastAPI application.

    Creates the Socket.io server instance and configures it with the FastAPI app
    for handling WebSocket connections alongside HTTP requests.
    """
    global sio

    try:
        # Create Socket.io server instance
        sio = await create_socketio_server()

        # Register event handlers after server is created
        from app.services.socketio.events import register_event_handlers

        register_event_handlers()

        # Mount Socket.io to FastAPI application
        app.mount("/socket.io", socketio.ASGIApp(sio, other_asgi_app=app))

        logger.info("Socket.io server initialized and mounted to FastAPI")

    except Exception as e:
        logger.error(f"Failed to initialize Socket.io server: {e}")
        raise


async def shutdown_socketio() -> None:
    """
    Gracefully shuts down the Socket.io server and closes connections.

    Performs cleanup operations during application shutdown to ensure
    all WebSocket connections are properly closed.
    """
    global sio

    if sio:
        try:
            # Disconnect all clients
            await sio.disconnect()
            logger.info("Socket.io server shutdown completed")

        except Exception as e:
            logger.error(f"Error during Socket.io shutdown: {e}")
        finally:
            sio = None


def get_socketio_server() -> Optional[socketio.AsyncServer]:
    """
    Returns the current Socket.io server instance.

    Provides access to the server instance for event emission and
    connection management from other parts of the application.
    """
    return sio


async def emit_to_user(user_id: str, event: str, data: dict) -> bool:
    """
    Emits an event to all sessions belonging to a specific user.

    Broadcasts the event to all active Socket.io sessions associated
    with the given user ID across all server instances.
    """
    if not sio:
        logger.warning("Socket.io server not initialized, cannot emit event")
        return False

    try:
        await sio.emit(event, data, room=f"user_{user_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to emit event {event} to user {user_id}: {e}")
        return False


async def emit_to_session(session_id: str, event: str, data: dict) -> bool:
    """
    Emits an event to a specific chat session room.

    Broadcasts the event to all participants in the specified chat session
    across all server instances using the Redis adapter.
    """
    if not sio:
        logger.warning("Socket.io server not initialized, cannot emit event")
        return False

    try:
        await sio.emit(event, data, room=f"session_{session_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to emit event {event} to session {session_id}: {e}")
        return False
