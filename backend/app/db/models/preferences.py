from sqlalchemy import Column, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin


class Preferences(Base, TimestampMixin):
    """User preferences for music recommendations."""

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user.id"), unique=True, nullable=False
    )

    # Music preferences as JSON
    preferred_genres = Column(JSON, default=list)
    preferred_artists = Column(JSON, default=list)
    preferred_eras = Column(JSON, default=list)
    preferred_moods = Column(JSON, default=list)

    # Dislikes
    disliked_genres = Column(JSON, default=list)
    disliked_artists = Column(JSON, default=list)

    # Relationships
    user = relationship("User", back_populates="preferences")
