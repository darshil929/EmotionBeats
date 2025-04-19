from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.dependencies import db_dependency
from app.api.routes import auth, spotify

app = FastAPI(title="EmotionBeats API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(spotify.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to EmotionBeats API"}

@app.get("/api")
@app.get("/api/")
def read_api_root():
    return {"message": "EmotionBeats API - Available endpoints: /api/auth/spotify/login, /api/spotify/*"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/db-test")
def db_test(db: Session = Depends(db_dependency)):
    try:
        # Use text() to wrap raw SQL in SQLAlchemy 2.0+
        result = db.execute(text("SELECT 1"))
        return {"status": "Database connection successful!"}
    except Exception as e:
        return {"status": "Database connection failed", "error": str(e)}
