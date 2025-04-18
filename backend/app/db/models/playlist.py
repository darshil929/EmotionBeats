from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin


class Playlist(Base, TimestampMixin):
    """Spotify playlist generated for a user."""

    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    chat_session_id = Column(
        UUID(as_uuid=True), ForeignKey("chatsession.id"), nullable=False
    )

    # Playlist details
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    spotify_playlist_id = Column(String(50), nullable=True)
    emotion_context = Column(String(50), nullable=True)
    track_count = Column(Integer, default=0)
    is_public = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="playlists")
    chat_session = relationship("ChatSession", back_populates="playlists")
    tracks = relationship("PlaylistTrack", back_populates="playlist")
