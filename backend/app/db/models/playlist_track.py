from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PlaylistTrack(Base):
    """Individual track within a playlist."""

    playlist_id = Column(UUID(as_uuid=True), ForeignKey("playlist.id"), nullable=False)

    # Track details
    spotify_track_id = Column(String(50), nullable=False)
    track_name = Column(String(255), nullable=False)
    artist_name = Column(String(255), nullable=False)
    position = Column(Integer, nullable=False)
    added_at = Column(DateTime, nullable=False)

    # Relationships
    playlist = relationship("Playlist", back_populates="tracks")
