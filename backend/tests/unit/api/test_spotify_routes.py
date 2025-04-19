"""
Tests for Spotify API integration routes.

This module tests the Spotify client functionality and API endpoints.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

from app.services.spotify.client import SpotifyClient


@pytest.fixture
def mock_spotify_track():
    """Return a mock Spotify track."""
    return {
        "id": "track123",
        "name": "Test Track",
        "artists": [{"id": "artist123", "name": "Test Artist"}],
        "album": {"id": "album123", "name": "Test Album"},
        "duration_ms": 180000,
        "uri": "spotify:track:track123",
        "preview_url": "https://example.com/preview.mp3"
    }


@pytest.fixture
def mock_spotify_playlist():
    """Return a mock Spotify playlist."""
    return {
        "id": "playlist123",
        "name": "Test Playlist",
        "description": "A test playlist",
        "public": True,
        "tracks": {"total": 0, "items": []},
        "uri": "spotify:playlist:playlist123",
        "external_urls": {"spotify": "https://open.spotify.com/playlist/playlist123"}
    }


@pytest.fixture
def spotify_user(db_session):
    """Create a test user with Spotify credentials."""
    from app.db.models import User
    from datetime import datetime, timedelta
    
    # Create user with Spotify tokens
    user = User(
        username="spotify_test_user",
        email="spotify_test@example.com",
        password_hash="hashed_password",
        spotify_id="spotify_test_id",
        spotify_access_token="test_access_token",
        spotify_refresh_token="test_refresh_token",
        spotify_token_expiry=datetime.utcnow() + timedelta(hours=1),
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_spotify_client_initialization(db_session, spotify_user):
    """
    Test creating a Spotify client from user credentials.
    
    This test verifies that the SpotifyClient.for_user method
    correctly creates a client using user credentials from the database.
    """
    # Create a client from user
    client = await SpotifyClient.for_user(db_session, str(spotify_user.id))
    
    # Verify client has correct tokens
    assert client.access_token == spotify_user.spotify_access_token
    assert client.refresh_token == spotify_user.spotify_refresh_token
    assert client.expires_at == spotify_user.spotify_token_expiry


@pytest.mark.asyncio
async def test_spotify_client_token_refresh(db_session, spotify_user, mock_spotify_token):
    """
    Test token refresh in Spotify client.
    
    This test verifies that expired tokens are automatically refreshed
    when creating a SpotifyClient instance.
    """
    # Set token to expired
    spotify_user.spotify_token_expiry = datetime.utcnow() - timedelta(hours=1)
    db_session.commit()
    
    # Mock token refresh
    with patch('app.services.spotify.auth.SpotifyAuthService.refresh_token',
               new_callable=AsyncMock,
               return_value=mock_spotify_token) as mock_refresh:
        
        # Create client - should trigger refresh
        client = await SpotifyClient.for_user(db_session, str(spotify_user.id))
        
        # Verify refresh was called
        mock_refresh.assert_called_once_with(spotify_user.spotify_refresh_token)
        
        # Verify user was updated
        db_session.refresh(spotify_user)
        assert spotify_user.spotify_access_token == mock_spotify_token.access_token


@pytest.mark.asyncio
async def test_get_profile_endpoint(client, spotify_user):
    """
    Test the profile endpoint.
    
    This test verifies that the profile endpoint correctly returns
    user profile information from Spotify.
    """
    # Mock Spotify client's get_user_profile method
    mock_profile = {
        "id": spotify_user.spotify_id,
        "display_name": "Test Display Name",
        "email": spotify_user.email,
        "uri": f"spotify:user:{spotify_user.spotify_id}"
    }
    
    with patch.object(SpotifyClient, 'for_user', 
                      new_callable=AsyncMock) as mock_for_user:
        
        # Configure mock client
        mock_client = AsyncMock()
        mock_client.get_user_profile = AsyncMock(return_value=mock_profile)
        mock_for_user.return_value = mock_client
        
        # Make request with user_id parameter
        response = client.get(f"/api/spotify/me?user_id={spotify_user.id}")
        
        # Verify SpotifyClient.for_user was called
        mock_for_user.assert_called_once_with(pytest.any(), str(spotify_user.id))
        
        # Verify get_user_profile was called
        mock_client.get_user_profile.assert_called_once()
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["id"] == spotify_user.spotify_id


@pytest.mark.asyncio
async def test_search_tracks_endpoint(client, spotify_user, mock_spotify_track):
    """
    Test the search tracks endpoint.
    
    This test verifies that the search endpoint correctly queries
    Spotify and returns track results.
    """
    # Mock Spotify client's search_tracks method
    with patch.object(SpotifyClient, 'for_user',
                     new_callable=AsyncMock) as mock_for_user:
        
        # Configure mock client
        mock_client = AsyncMock()
        mock_client.search_tracks = AsyncMock(return_value=[mock_spotify_track])
        mock_for_user.return_value = mock_client
        
        # Make request
        query = "test query"
        response = client.get(f"/api/spotify/search?query={query}&user_id={spotify_user.id}")
        
        # Verify search_tracks was called with correct parameters
        mock_client.search_tracks.assert_called_once_with(query, 10, 0)
        
        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == mock_spotify_track["id"]


@pytest.mark.asyncio
async def test_create_playlist_endpoint(client, spotify_user, mock_spotify_playlist):
    """
    Test creating a playlist.
    
    This test verifies that the playlist creation endpoint correctly
    forwards requests to Spotify and returns the created playlist.
    """
    # Mock Spotify client's create_playlist and get_user_profile methods
    with patch.object(SpotifyClient, 'for_user',
                     new_callable=AsyncMock) as mock_for_user:
        
        # Configure mock client
        mock_client = AsyncMock()
        mock_client.get_user_profile = AsyncMock(return_value={"id": spotify_user.spotify_id})
        mock_client.create_playlist = AsyncMock(return_value=mock_spotify_playlist)
        mock_for_user.return_value = mock_client
        
        # Create request data
        playlist_name = "Test Playlist"
        playlist_description = "A test playlist"
        
        # Make request
        response = client.post(
            f"/api/spotify/playlists?user_id={spotify_user.id}",
            params={"name": playlist_name, "description": playlist_description}
        )
        
        # Verify create_playlist was called with correct parameters
        mock_client.create_playlist.assert_called_once_with(
            spotify_user.spotify_id, playlist_name, playlist_description, True
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["id"] == mock_spotify_playlist["id"]
        assert response.json()["name"] == mock_spotify_playlist["name"]
