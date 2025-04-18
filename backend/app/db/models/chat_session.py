from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class ChatSession(Base):
    """Session for user conversations with the AI."""

    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    session_identifier = Column(String(50), unique=True, nullable=False)
    start_timestamp = Column(DateTime, nullable=False)
    end_timestamp = Column(DateTime, nullable=True)

    # Emotions detected during session
    detected_emotions = Column(JSON, default=dict)

    # Conversation context
    session_context = Column(JSON, default=dict)

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="chat_session")
    playlists = relationship("Playlist", back_populates="chat_session")
