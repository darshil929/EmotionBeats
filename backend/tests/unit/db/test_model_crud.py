"""
Tests for CRUD operations on database models.

This module tests Create, Read, Update, and Delete operations
for all major models in the application.
"""

import pytest
from datetime import timedelta

from app.db.models import (
    User,
    Preferences,
    ChatSession,
    ChatMessage,
    Playlist,
    PlaylistTrack,
)
from app.utils.datetime_helper import utc_now


class TestUserCRUD:
    """Tests for User model CRUD operations."""

    def test_user_create(self, db_session):
        """Test creating a new user."""
        # Create user
        user = User(
            username="cruduser",
            email="crud@example.com",
            password_hash="hashvalue",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # Verify user exists
        retrieved = db_session.query(User).filter(User.username == "cruduser").first()
        assert retrieved is not None
        assert retrieved.email == "crud@example.com"

    def test_user_read(self, test_user, db_session):
        """Test reading user data."""
        # Retrieve by ID
        retrieved = db_session.query(User).filter(User.id == test_user.id).first()
        assert retrieved is not None
        assert retrieved.username == test_user.username
        assert retrieved.email == test_user.email

        # Retrieve by username
        by_username = (
            db_session.query(User).filter(User.username == test_user.username).first()
        )
        assert by_username is not None
        assert by_username.id == test_user.id

    def test_user_update(self, test_user, db_session):
        """Test updating user data."""
        # Update user
        test_user.username = "updated_username"
        test_user.email = "updated@example.com"
        db_session.commit()

        # Verify changes
        retrieved = db_session.query(User).filter(User.id == test_user.id).first()
        assert retrieved.username == "updated_username"
        assert retrieved.email == "updated@example.com"

    def test_user_delete(self, db_session):
        """Test deleting a user."""
        # Create temporary user
        temp_user = User(
            username="temp_user",
            email="temp@example.com",
            password_hash="hashvalue",
            is_active=True,
        )
        db_session.add(temp_user)
        db_session.commit()

        # Get ID for later verification
        user_id = temp_user.id

        # Delete user
        db_session.delete(temp_user)
        db_session.commit()

        # Verify user no longer exists
        retrieved = db_session.query(User).filter(User.id == user_id).first()
        assert retrieved is None


class TestPreferencesCRUD:
    """Tests for Preferences model CRUD operations."""

    def test_preferences_create(self, test_user, db_session):
        """Test creating new preferences."""
        # Create preferences
        prefs = Preferences(
            user_id=test_user.id,
            preferred_genres=["rock", "jazz"],
            preferred_artists=["Artist1", "Artist2"],
            preferred_moods=["happy", "energetic"],
            disliked_genres=["country"],
        )
        db_session.add(prefs)
        db_session.commit()

        # Verify preferences exist
        retrieved = (
            db_session.query(Preferences)
            .filter(Preferences.user_id == test_user.id)
            .first()
        )
        assert retrieved is not None
        assert "rock" in retrieved.preferred_genres
        assert "Artist1" in retrieved.preferred_artists

    def test_preferences_read(self, test_user, db_session):
        """Test reading preferences."""
        # Create preferences
        prefs = Preferences(
            user_id=test_user.id,
            preferred_genres=["pop", "electronic"],
            preferred_artists=["Artist3", "Artist4"],
            preferred_moods=["calm", "focused"],
        )
        db_session.add(prefs)
        db_session.commit()
        prefs_id = prefs.id

        # Read by ID
        retrieved = (
            db_session.query(Preferences).filter(Preferences.id == prefs_id).first()
        )
        assert retrieved is not None
        assert "pop" in retrieved.preferred_genres

        # Read by user_id
        by_user = (
            db_session.query(Preferences)
            .filter(Preferences.user_id == test_user.id)
            .first()
        )
        assert by_user is not None
        assert by_user.id == prefs_id

    def test_preferences_update(self, test_user, db_session):
        """Test updating preferences."""
        # Create preferences
        prefs = Preferences(
            user_id=test_user.id,
            preferred_genres=["indie", "folk"],
            preferred_moods=["reflective"],
        )
        db_session.add(prefs)
        db_session.commit()

        # Update preferences
        prefs.preferred_genres = ["indie", "folk", "classical"]
        prefs.preferred_moods = ["reflective", "melancholic"]
        db_session.commit()

        # Verify changes
        db_session.refresh(prefs)
        assert "classical" in prefs.preferred_genres
        assert "melancholic" in prefs.preferred_moods

    def test_preferences_delete(self, test_user, db_session):
        """Test deleting preferences."""
        # Create preferences
        prefs = Preferences(user_id=test_user.id, preferred_genres=["blues", "soul"])
        db_session.add(prefs)
        db_session.commit()
        prefs_id = prefs.id

        # Delete preferences
        db_session.delete(prefs)
        db_session.commit()

        # Verify preferences no longer exist
        retrieved = (
            db_session.query(Preferences).filter(Preferences.id == prefs_id).first()
        )
        assert retrieved is None


class TestChatSessionCRUD:
    """Tests for ChatSession model CRUD operations."""

    def test_chat_session_create(self, test_user, db_session):
        """Test creating a new chat session."""
        # Create chat session
        now = utc_now()
        session = ChatSession(
            user_id=test_user.id,
            session_identifier="test_session_1",
            start_timestamp=now,
            detected_emotions={"happy": 0.8, "sad": 0.2},
            session_context={"topic": "music recommendations"},
            is_active=True,
            created_at=now,
        )
        db_session.add(session)
        db_session.commit()

        # Verify session exists
        retrieved = (
            db_session.query(ChatSession)
            .filter(ChatSession.session_identifier == "test_session_1")
            .first()
        )
        assert retrieved is not None
        assert retrieved.user_id == test_user.id
        assert retrieved.detected_emotions["happy"] == 0.8

    def test_chat_session_with_messages(self, test_user, db_session):
        """Test creating a chat session with messages."""
        # Create chat session
        now = utc_now()
        session = ChatSession(
            user_id=test_user.id,
            session_identifier="test_session_2",
            start_timestamp=now,
            is_active=True,
            created_at=now,
        )
        db_session.add(session)
        db_session.commit()

        # Add messages to session
        messages = [
            ChatMessage(
                chat_session_id=session.id,
                sender="user",
                content="Hello, I'm feeling happy today",
                detected_emotion="happy",
                emotion_confidence=0.9,
                sent_at=now,
            ),
            ChatMessage(
                chat_session_id=session.id,
                sender="ai",
                content="That's great! Would you like some upbeat music?",
                sent_at=now + timedelta(seconds=1),
            ),
        ]
        for msg in messages:
            db_session.add(msg)
        db_session.commit()

        # Retrieve session with messages
        retrieved = (
            db_session.query(ChatSession).filter(ChatSession.id == session.id).first()
        )

        # Verify messages are associated with session
        assert len(retrieved.messages) == 2
        assert retrieved.messages[0].sender == "user"
        assert retrieved.messages[1].sender == "ai"
        assert "happy" in retrieved.messages[0].detected_emotion


class TestPlaylistCRUD:
    """Tests for Playlist model CRUD operations."""

    @pytest.fixture
    def chat_session(self, test_user, db_session):
        """Create a chat session for testing."""
        session = ChatSession(
            user_id=test_user.id,
            session_identifier="playlist_test_session",
            start_timestamp=utc_now(),
            is_active=True,
            created_at=utc_now(),
        )
        db_session.add(session)
        db_session.commit()
        return session

    def test_playlist_create(self, test_user, chat_session, db_session):
        """Test creating a new playlist."""
        # Create playlist
        playlist = Playlist(
            user_id=test_user.id,
            chat_session_id=chat_session.id,
            name="Test Happy Playlist",
            description="A playlist for happy moods",
            spotify_playlist_id="sp123",
            emotion_context="happy",
            track_count=0,
            is_public=True,
        )
        db_session.add(playlist)
        db_session.commit()

        # Verify playlist exists
        retrieved = (
            db_session.query(Playlist)
            .filter(Playlist.spotify_playlist_id == "sp123")
            .first()
        )
        assert retrieved is not None
        assert retrieved.name == "Test Happy Playlist"
        assert retrieved.emotion_context == "happy"

    def test_playlist_with_tracks(self, test_user, chat_session, db_session):
        """Test creating a playlist with tracks."""
        # Create playlist
        playlist = Playlist(
            user_id=test_user.id,
            chat_session_id=chat_session.id,
            name="Test Playlist with Tracks",
            description="A playlist with tracks",
            spotify_playlist_id="sp456",
            emotion_context="energetic",
            track_count=0,
            is_public=True,
        )
        db_session.add(playlist)
        db_session.commit()

        # Add tracks to playlist
        now = utc_now()
        tracks = [
            PlaylistTrack(
                playlist_id=playlist.id,
                spotify_track_id="track1",
                track_name="Happy Song",
                artist_name="Happy Artist",
                position=0,
                added_at=now,
            ),
            PlaylistTrack(
                playlist_id=playlist.id,
                spotify_track_id="track2",
                track_name="Energetic Song",
                artist_name="Energetic Artist",
                position=1,
                added_at=now,
            ),
        ]
        for track in tracks:
            db_session.add(track)

        # Update track count
        playlist.track_count = len(tracks)
        db_session.commit()

        # Retrieve playlist with tracks
        retrieved = (
            db_session.query(Playlist).filter(Playlist.id == playlist.id).first()
        )

        # Verify tracks are associated with playlist
        assert retrieved.track_count == 2
        assert len(retrieved.tracks) == 2
        assert retrieved.tracks[0].track_name == "Happy Song"
        assert retrieved.tracks[1].track_name == "Energetic Song"
