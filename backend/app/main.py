"""
Main application initialization and configuration.
"""

import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.dependencies import db_dependency
from app.api.routes import auth, spotify, jwt, chat
from app.middleware.csrf import setup_csrf_middleware
from app.core.security import JWT_SECRET_KEY
from app.services.socketio.server import setup_socketio
from app.services.socketio.events import register_handlers
from app.core.redis import close_redis_connections

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(title="EmotionBeats API")

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "file://",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure CSRF protection
setup_csrf_middleware(app, JWT_SECRET_KEY)

# Include routers
app.include_router(auth.router)
app.include_router(spotify.router)
app.include_router(jwt.router)
app.include_router(chat.router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    # Set up Socket.io server
    sio = await setup_socketio(app)
    # Register Socket.io event handlers
    register_handlers(sio)
    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    # Close Redis connections
    await close_redis_connections()
    logger.info("Application shutdown complete")


@app.get("/")
def read_root():
    """Return a welcome message at the root endpoint."""
    return {"message": "Welcome to EmotionBeats API"}


@app.get("/api")
@app.get("/api/")
def read_api_root():
    """Return a message with available API endpoints."""
    return {
        "message": "EmotionBeats API - Available endpoints: /api/auth/spotify/login, /api/spotify/*, /api/chat/*"
    }


@app.get("/api/health")
def health_check():
    """Health check endpoint to verify the API is running."""
    return {"status": "healthy"}


@app.get("/api/db-test")
def db_test(db: Session = Depends(db_dependency)):
    """Test the database connection."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "Database connection successful!"}
    except Exception as e:
        return {"status": "Database connection failed", "error": str(e)}
