"""
Tests for the Spotify API routes.

This module tests all Spotify-related API functionality including
profile retrieval, search, playlist management, and recommendations.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock
from fastapi import HTTPException

from app.db.models import User
from app.schemas.spotify import (
    SpotifyUserProfile,
    SpotifyTrack,
    SpotifyPlaylist,
)


@pytest.fixture
def spotify_profile_data():
    """Return mock Spotify profile data."""
    return {
        "id": "test_spotify_id",
        "display_name": "Test User",
        "email": "test@example.com",
        "images": [
            {
                "url": "https://i.scdn.co/image/ab67616d00001e02ff9ca1bb55ce82ae553c8228",
                "height": 300,
                "width": 300,
            }
        ],
        "uri": "spotify:user:test_spotify_id",
    }


@pytest.fixture
def spotify_tracks_data():
    """Return mock Spotify track search results."""
    return [
        {
            "id": "track1",
            "name": "Test Track 1",
            "artists": [{"id": "artist1", "name": "Test Artist 1"}],
            "album": {
                "id": "album1",
                "name": "Test Album 1",
                "images": [
                    {
                        "url": "https://example.com/image1.jpg",
                        "height": 300,
                        "width": 300,
                    }
                ],
            },
            "duration_ms": 180000,
            "uri": "spotify:track:track1",
            "preview_url": "https://example.com/preview1.mp3",
        },
        {
            "id": "track2",
            "name": "Test Track 2",
            "artists": [{"id": "artist2", "name": "Test Artist 2"}],
            "album": {
                "id": "album2",
                "name": "Test Album 2",
                "images": [
                    {
                        "url": "https://example.com/image2.jpg",
                        "height": 300,
                        "width": 300,
                    }
                ],
            },
            "duration_ms": 210000,
            "uri": "spotify:track:track2",
            "preview_url": "https://example.com/preview2.mp3",
        },
    ]


@pytest.fixture
def spotify_playlist_data():
    """Return mock Spotify playlist data."""
    return {
        "id": "playlist1",
        "name": "Test Playlist",
        "description": "Test playlist description",
        "public": True,
        "tracks": {"total": 0, "items": []},
        "uri": "spotify:playlist:playlist1",
        "external_urls": {"spotify": "https://open.spotify.com/playlist/playlist1"},
    }


@pytest.fixture
def spotify_recommendations_data():
    """Return mock Spotify recommendation data."""
    return [
        {
            "id": "rec1",
            "name": "Recommended Track 1",
            "artists": [{"id": "artist3", "name": "Test Artist 3"}],
            "album": {
                "id": "album3",
                "name": "Test Album 3",
                "images": [
                    {
                        "url": "https://example.com/image3.jpg",
                        "height": 300,
                        "width": 300,
                    }
                ],
            },
            "duration_ms": 195000,
            "uri": "spotify:track:rec1",
            "preview_url": "https://example.com/preview3.mp3",
        },
        {
            "id": "rec2",
            "name": "Recommended Track 2",
            "artists": [{"id": "artist4", "name": "Test Artist 4"}],
            "album": {
                "id": "album4",
                "name": "Test Album 4",
                "images": [
                    {
                        "url": "https://example.com/image4.jpg",
                        "height": 300,
                        "width": 300,
                    }
                ],
            },
            "duration_ms": 220000,
            "uri": "spotify:track:rec2",
            "preview_url": "https://example.com/preview4.mp3",
        },
    ]


@pytest.fixture
def authenticated_user(db_session):
    """Create a test user with Spotify authentication."""
    user = User(
        username="spotifyuser",
        email="spotify@example.com",
        password_hash="hashed_password",
        spotify_id="test_spotify_id",
        spotify_access_token="test_access_token",
        spotify_refresh_token="test_refresh_token",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_get_profile(db_session, authenticated_user, spotify_profile_data, monkeypatch):
    """Test retrieving the user's Spotify profile."""
    # Import the function to test
    from app.api.routes.spotify import get_profile

    # Create profile response
    profile_response = SpotifyUserProfile(**spotify_profile_data)

    # Create a client mock that will be returned by for_user
    client_mock = AsyncMock()
    client_mock.get_user_profile.return_value = profile_response

    # Mock SpotifyClient.for_user
    async def mock_for_user(db, user_id):
        assert user_id == authenticated_user.id
        return client_mock

    # Apply monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.for_user", mock_for_user
    )

    # Call the function
    result = asyncio.run(get_profile(authenticated_user.id, db_session))

    # Assert response
    assert result.id == spotify_profile_data["id"]
    assert result.display_name == spotify_profile_data["display_name"]
    assert result.email == spotify_profile_data["email"]


def test_search_tracks(
    db_session, authenticated_user, spotify_tracks_data, monkeypatch
):
    """Test searching for tracks on Spotify."""
    # Import the function to test
    from app.api.routes.spotify import search_tracks

    # Create track response objects
    track_responses = [SpotifyTrack(**track) for track in spotify_tracks_data]

    # Create a client mock
    client_mock = AsyncMock()
    client_mock.search_tracks.return_value = track_responses

    # Mock SpotifyClient.for_user
    async def mock_for_user(db, user_id):
        assert user_id == authenticated_user.id
        return client_mock

    # Apply monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.for_user", mock_for_user
    )

    # Call the function
    result = asyncio.run(
        search_tracks("test query", 5, 0, authenticated_user.id, db_session)
    )

    # Assert response
    assert len(result) == len(spotify_tracks_data)
    assert result[0].id == spotify_tracks_data[0]["id"]
    assert result[0].name == spotify_tracks_data[0]["name"]
    assert result[1].id == spotify_tracks_data[1]["id"]
    assert result[1].name == spotify_tracks_data[1]["name"]

    # Verify search parameters were passed correctly
    client_mock.search_tracks.assert_called_once_with("test query", 5, 0)


def test_create_playlist(
    db_session,
    authenticated_user,
    spotify_profile_data,
    spotify_playlist_data,
    monkeypatch,
):
    """Test creating a new Spotify playlist."""
    # Import the function to test
    from app.api.routes.spotify import create_playlist

    # Create response objects
    profile_response = SpotifyUserProfile(**spotify_profile_data)
    playlist_response = SpotifyPlaylist(**spotify_playlist_data)

    # Create a client mock
    client_mock = AsyncMock()
    client_mock.get_user_profile.return_value = profile_response
    client_mock.create_playlist.return_value = playlist_response

    # Mock SpotifyClient.for_user
    async def mock_for_user(db, user_id):
        assert user_id == authenticated_user.id
        return client_mock

    # Apply monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.for_user", mock_for_user
    )

    # Call the function
    result = asyncio.run(
        create_playlist(
            "Test Playlist", "A test playlist", True, authenticated_user.id, db_session
        )
    )

    # Assert response
    assert result.id == spotify_playlist_data["id"]
    assert result.name == spotify_playlist_data["name"]
    assert result.description == spotify_playlist_data["description"]
    assert result.public == spotify_playlist_data["public"]

    # Verify method calls
    client_mock.get_user_profile.assert_called_once()
    client_mock.create_playlist.assert_called_once_with(
        profile_response.id, "Test Playlist", "A test playlist", True
    )


def test_add_tracks_to_playlist(db_session, authenticated_user, monkeypatch):
    """Test adding tracks to a Spotify playlist."""
    # Import the function to test
    from app.api.routes.spotify import add_tracks_to_playlist

    # Mock response data
    add_tracks_response = {"snapshot_id": "snapshot123"}

    # Track URIs to add
    track_uris = ["spotify:track:track1", "spotify:track:track2"]

    # Create a client mock
    client_mock = AsyncMock()
    client_mock.add_tracks_to_playlist.return_value = add_tracks_response

    # Mock SpotifyClient.for_user
    async def mock_for_user(db, user_id):
        assert user_id == authenticated_user.id
        return client_mock

    # Apply monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.for_user", mock_for_user
    )

    # Call the function
    result = asyncio.run(
        add_tracks_to_playlist(
            "playlist1", track_uris, authenticated_user.id, db_session
        )
    )

    # Assert response
    assert result == add_tracks_response
    assert result["snapshot_id"] == "snapshot123"

    # Verify method calls
    client_mock.add_tracks_to_playlist.assert_called_once_with("playlist1", track_uris)


def test_get_recommendations(
    db_session, authenticated_user, spotify_recommendations_data, monkeypatch
):
    """Test getting track recommendations from Spotify."""
    # Import the function to test
    from app.api.routes.spotify import get_recommendations

    # Create recommendation response objects
    recommendation_responses = [
        SpotifyTrack(**track) for track in spotify_recommendations_data
    ]

    # Create a client mock
    client_mock = AsyncMock()
    client_mock.get_recommendations.return_value = recommendation_responses

    # Mock SpotifyClient.for_user
    async def mock_for_user(db, user_id):
        assert user_id == authenticated_user.id
        return client_mock

    # Apply monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.for_user", mock_for_user
    )

    # Call the function
    result = asyncio.run(
        get_recommendations(
            seed_tracks="track1",
            limit=2,
            target_valence=0.8,
            target_energy=0.6,
            user_id=authenticated_user.id,
            db=db_session,
        )
    )

    # Assert response
    assert len(result) == len(spotify_recommendations_data)
    assert result[0].id == spotify_recommendations_data[0]["id"]
    assert result[0].name == spotify_recommendations_data[0]["name"]
    assert result[1].id == spotify_recommendations_data[1]["id"]
    assert result[1].name == spotify_recommendations_data[1]["name"]

    # Verify the recommendations were requested with the correct parameters
    client_mock.get_recommendations.assert_called_once()
    call_kwargs = client_mock.get_recommendations.call_args[1]
    assert call_kwargs["seed_tracks"] == ["track1"]
    assert call_kwargs["limit"] == 2
    assert call_kwargs["target_features"]["valence"] == 0.8
    assert call_kwargs["target_features"]["energy"] == 0.6


def test_get_profile_unauthorized(db_session):
    """Test profile retrieval with unauthorized user."""
    from app.api.routes.spotify import get_profile

    non_existent_uuid = "00000000-0000-0000-0000-000000000000"

    # Call with non-existent user_id
    try:
        asyncio.run(get_profile(non_existent_uuid, db_session))
        pytest.fail("Expected an exception but none was raised")
    except HTTPException as exc:
        assert exc.status_code == 500
        assert "User not found" in str(exc.detail)


def test_search_tracks_with_invalid_parameters(
    db_session, authenticated_user, monkeypatch
):
    """Test search tracks with invalid parameters."""
    # Import the function to test
    from app.api.routes.spotify import search_tracks

    # Create a client mock that raises an exception
    client_mock = AsyncMock()
    client_mock.search_tracks.side_effect = ValueError("Invalid search parameters")

    # Mock SpotifyClient.for_user
    async def mock_for_user(db, user_id):
        return client_mock

    # Apply monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.for_user", mock_for_user
    )

    # Call with empty query
    try:
        asyncio.run(search_tracks("", 10, 0, authenticated_user.id, db_session))
        pytest.fail("Expected an exception but none was raised")
    except HTTPException as exc:
        assert exc.status_code == 500
        assert "Invalid search parameters" in str(exc.detail)


def test_create_playlist_validation_error(db_session, authenticated_user, monkeypatch):
    """Test playlist creation with validation errors."""
    # Import the function to test
    from app.api.routes.spotify import create_playlist

    # Create a client mock
    client_mock = AsyncMock()
    client_mock.get_user_profile.return_value = SpotifyUserProfile(
        id="test_id", uri="spotify:user:test_id"
    )
    client_mock.create_playlist.side_effect = ValueError("Invalid playlist parameters")

    # Mock SpotifyClient.for_user
    async def mock_for_user(db, user_id):
        return client_mock

    # Apply monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.for_user", mock_for_user
    )

    # Call with invalid parameters
    try:
        asyncio.run(create_playlist("", "", True, authenticated_user.id, db_session))
        pytest.fail("Expected an exception but none was raised")
    except HTTPException as exc:
        assert exc.status_code == 500
        assert "Invalid playlist parameters" in str(exc.detail)


def test_add_tracks_invalid_track_uris(db_session, authenticated_user, monkeypatch):
    """Test adding invalid track URIs to a playlist."""
    # Import the function to test
    from app.api.routes.spotify import add_tracks_to_playlist

    # Create a client mock that raises an exception
    client_mock = AsyncMock()
    client_mock.add_tracks_to_playlist.side_effect = ValueError("Invalid track URIs")

    # Mock SpotifyClient.for_user
    async def mock_for_user(db, user_id):
        return client_mock

    # Apply monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.for_user", mock_for_user
    )

    # Call with invalid track URIs
    try:
        asyncio.run(
            add_tracks_to_playlist(
                "playlist1", ["invalid:uri"], authenticated_user.id, db_session
            )
        )
        pytest.fail("Expected an exception but none was raised")
    except HTTPException as exc:
        assert exc.status_code == 500
        assert "Invalid track URIs" in str(exc.detail)


def test_get_recommendations_spotify_api_error(
    db_session, authenticated_user, monkeypatch
):
    """Test recommendation retrieval with Spotify API error."""
    # Import the function to test
    from app.api.routes.spotify import get_recommendations

    # Create a client mock that raises an exception
    client_mock = AsyncMock()
    client_mock.get_recommendations.side_effect = Exception(
        "Spotify API error: Rate limited"
    )

    # Mock SpotifyClient.for_user
    async def mock_for_user(db, user_id):
        return client_mock

    # Apply monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.for_user", mock_for_user
    )

    # Call function
    try:
        asyncio.run(
            get_recommendations(
                seed_tracks="track1", user_id=authenticated_user.id, db=db_session
            )
        )
        pytest.fail("Expected an exception but none was raised")
    except HTTPException as exc:
        assert exc.status_code == 500
        assert "Spotify API error" in str(exc.detail)
