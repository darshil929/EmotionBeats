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
    os.getenv("SOCKETIO_CORS_ORIGINS", '["*"]')  # Allow all origins in development
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
    for cross-origin WebSocket connections. Updated for Python 3.13 compatibility.
    """
    try:
        logger.info("Creating Socket.io server with Python 3.13 compatibility...")

        # Try to connect to Redis first
        try:
            redis_client = await get_redis_socketio()
            await redis_client.ping()
            logger.info("Redis connection verified for Socket.io")

            # Create Redis adapter using URL
            redis_manager = socketio.AsyncRedisManager(SOCKETIO_REDIS_URL)
            logger.info("Using Redis adapter for Socket.io")

            # Create AsyncServer with Redis adapter
            server = socketio.AsyncServer(
                client_manager=redis_manager,
                cors_allowed_origins=SOCKETIO_CORS_ORIGINS,
                ping_timeout=SOCKETIO_PING_TIMEOUT,
                ping_interval=SOCKETIO_PING_INTERVAL,
                logger=True,
                engineio_logger=False,  # Disable to reduce noise
                async_mode="asgi",  # Explicitly set ASGI mode
                transports=["websocket", "polling"],  # Explicit transport support
            )

        except Exception as redis_error:
            logger.warning(
                f"Redis connection failed, using in-memory manager: {redis_error}"
            )

            # Fallback to in-memory manager
            server = socketio.AsyncServer(
                cors_allowed_origins=SOCKETIO_CORS_ORIGINS,
                ping_timeout=SOCKETIO_PING_TIMEOUT,
                ping_interval=SOCKETIO_PING_INTERVAL,
                logger=True,
                engineio_logger=False,
                async_mode="asgi",  # Explicit ASGI mode
                transports=["websocket", "polling"],
            )

        logger.info("Socket.io server created successfully")
        logger.info(f"CORS origins: {SOCKETIO_CORS_ORIGINS}")
        logger.info(f"Async mode: {server.async_mode}")
        logger.info(f"Transports: {server.eio.transports}")

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
        logger.info("Initializing Socket.io server...")

        # Create Socket.io server instance
        sio = await create_socketio_server()

        # Register event handlers after server is created
        from app.services.socketio.events import register_event_handlers

        register_event_handlers()

        # Create the ASGI app with proper configuration
        socketio_asgi_app = socketio.ASGIApp(
            sio,
            other_asgi_app=app,
            socketio_path="socket.io",  # Explicit path specification
        )

        # Mount Socket.io to FastAPI application
        app.mount("/socket.io", socketio_asgi_app)

        logger.info("Socket.io server initialized and mounted to FastAPI successfully")
        logger.info("Socket.io available at: /socket.io/")

        # Verify the server is working
        if sio and hasattr(sio, "async_mode"):
            logger.info(f"Socket.io async mode confirmed: {sio.async_mode}")

    except Exception as e:
        logger.error(f"Failed to initialize Socket.io server: {e}")
        # Don't raise - let the app start without Socket.io but log the issue
        sio = None
        logger.warning("Application will start without Socket.io functionality")


async def shutdown_socketio() -> None:
    """
    Gracefully shuts down the Socket.io server and closes connections.

    Performs cleanup operations during application shutdown to ensure
    all WebSocket connections are properly closed.
    """
    global sio

    if sio:
        try:
            logger.info("Shutting down Socket.io server...")
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
        logger.debug(f"Event {event} emitted to user {user_id}")
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
        logger.debug(f"Event {event} emitted to session {session_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to emit event {event} to session {session_id}: {e}")
        return False


def validate_socketio_health() -> dict:
    """
    Validates Socket.io server health and returns status information.

    Provides comprehensive health check data for monitoring and debugging.
    """
    if not sio:
        return {
            "status": "unhealthy",
            "error": "Socket.io server not initialized",
            "available": False,
            "async_mode": None,
            "manager_type": None,
            "server_type": None,
        }

    try:
        health_data = {
            "status": "healthy",
            "available": True,
            "async_mode": getattr(sio, "async_mode", "unknown"),
            "server_type": type(sio).__name__,
        }

        # Add manager information
        if hasattr(sio, "manager"):
            health_data["manager_type"] = type(sio.manager).__name__

        # Add transport information
        if hasattr(sio, "eio") and hasattr(sio.eio, "transports"):
            health_data["transports"] = list(sio.eio.transports)

        # Add configuration details
        health_data["ping_timeout"] = SOCKETIO_PING_TIMEOUT
        health_data["ping_interval"] = SOCKETIO_PING_INTERVAL
        health_data["cors_origins"] = SOCKETIO_CORS_ORIGINS

        return health_data

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "available": False,
            "async_mode": None,
            "manager_type": None,
            "server_type": None,
        }
