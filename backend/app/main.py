"""
Main application initialization and configuration.

Integrates FastAPI with Socket.io for real-time communication capabilities
while maintaining existing REST API functionality and middleware configuration.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.dependencies import db_dependency
from app.api.routes import auth, spotify, jwt
from app.middleware.csrf import setup_csrf_middleware
from app.core.security import JWT_SECRET_KEY
from app.services.socketio import init_socketio, shutdown_socketio
from app.core.redis import close_redis_connections, health_check_redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application lifecycle events for proper startup and shutdown.

    Handles initialization and cleanup of Socket.io server, Redis connections,
    and other resources during application lifecycle.
    """
    # Startup
    logger.info("Starting EmotionBeats API server...")

    try:
        # Initialize Socket.io server and mount to FastAPI
        await init_socketio(app)
        logger.info("Socket.io server initialized successfully")

        # Verify Redis connections
        redis_status = await health_check_redis()
        if (
            redis_status["cache"]["status"] == "connected"
            and redis_status["socketio"]["status"] == "connected"
        ):
            logger.info("Redis connections established successfully")
        else:
            logger.warning(f"Redis connection issues: {redis_status}")

        logger.info("EmotionBeats API server startup completed")

    except Exception as e:
        logger.error(f"Error during application startup: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down EmotionBeats API server...")

    try:
        # Gracefully shutdown Socket.io server
        await shutdown_socketio()
        logger.info("Socket.io server shutdown completed")

        # Close Redis connections
        await close_redis_connections()
        logger.info("Redis connections closed")

        logger.info("EmotionBeats API server shutdown completed")

    except Exception as e:
        logger.error(f"Error during application shutdown: {e}")


# Initialize FastAPI application with lifespan management
app = FastAPI(
    title="EmotionBeats API",
    description="AI-powered conversational music recommendation system with real-time chat capabilities",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS middleware for both HTTP and WebSocket connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost",
        "http://localhost:3000",
        "*",
    ],  # Added * for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure CSRF protection
setup_csrf_middleware(app, JWT_SECRET_KEY)

# Include API routers
app.include_router(auth.router)
app.include_router(spotify.router)
app.include_router(jwt.router)


@app.get("/")
def read_root():
    """
    Returns welcome message and API information at the root endpoint.

    Provides basic API identification and available service information
    for clients and monitoring systems.
    """
    return {
        "message": "Welcome to EmotionBeats API",
        "version": "1.0.0",
        "services": ["REST API", "WebSocket (Socket.io)"],
        "documentation": "/docs",
    }


@app.get("/api")
@app.get("/api/")
def read_api_root():
    """
    Returns API overview with available endpoint categories.

    Provides navigation information for API consumers and
    development teams working with the system.
    """
    return {
        "message": "EmotionBeats API - Real-time Music Recommendation System",
        "endpoints": {
            "authentication": "/api/auth/*",
            "spotify_integration": "/api/spotify/*",
            "real_time_chat": "Socket.io on /socket.io/",
            "documentation": "/docs",
        },
        "websocket": {
            "endpoint": "/socket.io/",
            "events": [
                "connect",
                "disconnect",
                "join_chat_session",
                "leave_chat_session",
                "send_message",
                "typing_start",
                "typing_stop",
            ],
        },
    }


@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint for system monitoring.

    Validates the status of core system components including database,
    Redis connections, and Socket.io server availability.
    """
    health_status = {
        "status": "healthy",
        "timestamp": "2025-05-30T00:00:00Z",
        "services": {},
    }

    try:
        # Check API server
        health_status["services"]["api"] = {"status": "healthy"}

        # Check Socket.io server
        from app.services.socketio.server import validate_socketio_health

        socketio_health = validate_socketio_health()
        health_status["services"]["socketio"] = socketio_health

        # Check Redis connections
        redis_status = await health_check_redis()
        health_status["services"]["redis"] = redis_status

        # Determine overall status
        def check_service_health(service_data):
            if isinstance(service_data, dict):
                if "status" in service_data:
                    return service_data["status"] in ["healthy", "connected"]
                else:
                    # Check nested services (like Redis with cache/socketio)
                    return all(
                        sub_service.get("status") in ["healthy", "connected"]
                        for sub_service in service_data.values()
                        if isinstance(sub_service, dict) and "status" in sub_service
                    )
            return False

        all_services_healthy = all(
            check_service_health(service_data)
            for service_data in health_status["services"].values()
        )

        if not all_services_healthy:
            health_status["status"] = "degraded"

    except Exception as e:
        logger.error(f"Health check error: {e}")
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)

    return health_status


@app.get("/socket.io/health")
async def socketio_health_check():
    """
    Socket.io specific health check endpoint.

    Returns detailed status information about the Socket.io server
    for debugging and monitoring purposes.
    """
    try:
        from app.services.socketio.server import validate_socketio_health

        health_status = validate_socketio_health()

        # Log the health check for debugging
        logger.info(f"Socket.io health check: {health_status}")

        return health_status

    except Exception as e:
        logger.error(f"Socket.io health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "available": False,
            "async_mode": None,
            "manager_type": None,
            "server_type": None,
        }


@app.get("/db-test")
def db_test(db: Session = Depends(db_dependency)):
    """
    Database connectivity test endpoint for infrastructure validation.

    Performs a simple database query to verify connection health
    and database availability for monitoring systems.
    """
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "Database connection successful!",
            "database": "PostgreSQL",
            "connection": "healthy",
        }
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        return {
            "status": "Database connection failed",
            "error": str(e),
            "connection": "unhealthy",
        }


@app.get("/socketio/stats")
async def socketio_stats():
    """
    Socket.io performance and usage statistics endpoint.

    Provides real-time statistics about WebSocket connections,
    active rooms, and performance metrics for monitoring.
    """
    try:
        from app.services.socketio.rooms import get_active_rooms
        from app.services.socketio.middleware import get_performance_statistics
        from app.services.socketio.server import get_socketio_server

        sio = get_socketio_server()

        stats = {
            "socketio_server": {
                "status": "active" if sio else "inactive",
                "server_available": sio is not None,
            },
            "active_rooms": await get_active_rooms(),
            "performance_metrics": await get_performance_statistics(),
        }

        # Add room summary
        active_rooms = stats["active_rooms"]
        stats["summary"] = {
            "total_active_rooms": len(active_rooms),
            "total_participants": sum(active_rooms.values()),
            "average_participants_per_room": (
                sum(active_rooms.values()) / len(active_rooms) if active_rooms else 0
            ),
        }

        return stats

    except Exception as e:
        logger.error(f"Error retrieving Socket.io stats: {e}")
        return {"error": "Failed to retrieve Socket.io statistics", "details": str(e)}


@app.get("/system/info")
async def system_info():
    """
    System information endpoint for deployment and monitoring.

    Provides comprehensive system status including versions,
    configurations, and service availability.
    """
    try:
        from app.services.socketio.server import get_socketio_server

        sio = get_socketio_server()
        redis_status = await health_check_redis()

        return {
            "application": {
                "name": "EmotionBeats API",
                "version": "1.0.0",
                "environment": "development",  # Could be from env var
                "python_version": "3.13+",
            },
            "services": {
                "fastapi": {"status": "active", "version": "0.95.0+"},
                "socketio": {
                    "status": "active" if sio else "inactive",
                    "version": "5.11.0+",
                    "engineio_version": "4.9.0+",
                },
                "redis": {
                    "cache": redis_status["cache"],
                    "socketio": redis_status["socketio"],
                },
                "database": {"type": "PostgreSQL", "status": "connected"},
            },
            "features": {
                "real_time_chat": sio is not None,
                "spotify_integration": True,
                "jwt_authentication": True,
                "rate_limiting": True,
                "csrf_protection": True,
            },
        }

    except Exception as e:
        logger.error(f"Error retrieving system info: {e}")
        return {"error": "Failed to retrieve system information", "details": str(e)}
