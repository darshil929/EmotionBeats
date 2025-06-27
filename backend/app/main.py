"""
Main application initialization and configuration.
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.dependencies import db_dependency
from app.api.routes import auth, spotify, jwt
from app.middleware.csrf import setup_csrf_middleware
from app.core.security import JWT_SECRET_KEY
from app.services.socketio.server import socketio_server
from app.core.redis import health_check_redis

# Initialize FastAPI application
app = FastAPI(title="EmotionBeats API")

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure CSRF protection
setup_csrf_middleware(app, JWT_SECRET_KEY)

# Mount Socket.io server
socketio_server.mount_to_fastapi(app, path="/ws")

# Include routers
app.include_router(auth.router)
app.include_router(spotify.router)
app.include_router(jwt.router)


@app.get("/")
def read_root():
    """Return a welcome message at the root endpoint."""
    return {"message": "Welcome to EmotionBeats API"}


@app.get("/api")
@app.get("/api/")
def read_api_root():
    """Return a message with available API endpoints."""
    return {
        "message": "EmotionBeats API - Available endpoints: /api/auth/spotify/login, /api/spotify/*, /ws (Socket.IO)"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify the API is running."""
    redis_status = await health_check_redis()

    return {
        "status": "healthy",
        "services": {
            "api": "online",
            "redis": redis_status,
            "socketio": "online" if socketio_server._initialized else "offline",
        },
    }


@app.get("/api/db-test")
def db_test(db: Session = Depends(db_dependency)):
    """Test the database connection."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "Database connection successful!"}
    except Exception as e:
        return {"status": "Database connection failed", "error": str(e)}
