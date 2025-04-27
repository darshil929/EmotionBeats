"""
Tests for database models.

This module tests the functionality of SQLAlchemy models.
"""

from sqlalchemy import text


def test_database_connection(db_session):
    """Test basic database connection."""
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_user_model(db_session, test_user):
    """Test User model creation and retrieval."""
    # User is created by the fixture
    # Verify user was created
    assert test_user.id is not None
    assert test_user.username == "testuser"
    assert test_user.email == "test@example.com"

    # Retrieve user from database
    from app.db.models import User

    retrieved_user = db_session.query(User).filter(User.id == test_user.id).first()
    assert retrieved_user is not None
    assert retrieved_user.username == "testuser"


def test_preferences_model(db_session, test_user):
    """Test Preferences model creation and relationship."""
    from app.db.models import Preferences

    # Create preferences for user
    preferences = Preferences(
        user_id=test_user.id,
        preferred_genres=["rock", "jazz"],
        preferred_artists=["Artist1", "Artist2"],
        preferred_moods=["happy", "calm"],
    )
    db_session.add(preferences)
    db_session.commit()
    db_session.refresh(preferences)

    # Verify preferences
    assert preferences.id is not None
    assert preferences.user_id == test_user.id
    assert "rock" in preferences.preferred_genres

    # Test relationship
    db_session.refresh(test_user)
    assert test_user.preferences is not None
    assert test_user.preferences.preferred_genres == ["rock", "jazz"]
