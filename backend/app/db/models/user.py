from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User model for authentication and profile."""

    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    # Spotify integration
    spotify_id = Column(String(50), unique=True, index=True, nullable=True)
    spotify_access_token = Column(Text, nullable=True)
    spotify_refresh_token = Column(Text, nullable=True)
    spotify_token_expiry = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Relationships
    preferences = relationship("Preferences", back_populates="user", uselist=False)
    chat_sessions = relationship("ChatSession", back_populates="user")
    playlists = relationship("Playlist", back_populates="user")
