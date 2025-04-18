from sqlalchemy import Column, DateTime, ForeignKey, Float, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class ChatMessage(Base):
    """Individual message within a chat session."""

    chat_session_id = Column(
        UUID(as_uuid=True), ForeignKey("chatsession.id"), nullable=False
    )
    sender = Column(String(10), nullable=False)  # 'user' or 'ai'
    content = Column(Text, nullable=False)

    # Emotion analysis
    detected_emotion = Column(String(20), nullable=True)
    emotion_confidence = Column(Float, nullable=True)

    # Timestamp
    sent_at = Column(DateTime, nullable=False)

    # Relationships
    chat_session = relationship("ChatSession", back_populates="messages")
