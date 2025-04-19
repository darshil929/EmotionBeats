"""
Tests for authentication routes.

This module tests the Spotify authentication flow and token management.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import json
from datetime import datetime, timedelta

from app.api.routes import auth
from app.services.spotify.auth import SpotifyAuthService
from app.schemas.spotify import SpotifyTokenSchema

# Test data
MOCK_STATE = "test_state_123"
MOCK_CODE = "test_auth_code"
MOCK_ACCESS_TOKEN = "mock_access_token"
MOCK_REFRESH_TOKEN = "mock_refresh_token"
MOCK_SPOTIFY_ID = "spotify_user_123"


@pytest.fixture
def mock_spotify_token():
    """Return mock Spotify token data."""
    return SpotifyTokenSchema(
        access_token=MOCK_ACCESS_TOKEN,
        refresh_token=MOCK_REFRESH_TOKEN,
        token_type="Bearer",
        expires_in=3600,
        scope="user-read-email user-read-private playlist-modify-public"
    )


@pytest.fixture
def mock_spotify_profile():
    """Return mock Spotify user profile."""
    return {
        "id": MOCK_SPOTIFY_ID,
        "display_name": "Test User",
        "email": "test@example.com",
        "uri": f"spotify:user:{MOCK_SPOTIFY_ID}",
        "images": [{"url": "https://example.com/image.jpg"}]
    }


def test_spotify_login(client):
    """
    Test generating a Spotify login URL.
    
    This test verifies that the login endpoint returns a properly
    formatted authentication URL.
    """
    # Patch the UUID generation for consistent state value
    with patch('uuid.uuid4', return_value=MOCK_STATE):
        # Test the endpoint
        response = client.get("/api/auth/spotify/login")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        
        # Verify URL contains expected parameters
        auth_url = data["auth_url"]
        assert "accounts.spotify.com/authorize" in auth_url
        assert f"state={MOCK_STATE}" in auth_url
        assert "response_type=code" in auth_url
        assert "scope=" in auth_url  # Scopes should be included


@pytest.mark.asyncio
async def test_spotify_callback_success(client, db_session, mock_spotify_token, mock_spotify_profile):
    """
    Test successful Spotify OAuth callback.
    
    This test mocks the token exchange and user profile retrieval
    to simulate a successful authentication flow.
    """
    # Mock token exchange
    with patch.object(
        SpotifyAuthService, 'get_tokens', 
        new_callable=AsyncMock,
        return_value=mock_spotify_token
    ) as mock_get_tokens:
        
        # Mock Spotify client profile retrieval
        with patch('app.services.spotify.client.SpotifyClient') as MockClient:
            # Configure the mock client
            mock_client_instance = MockClient.return_value
            mock_client_instance.get_user_profile = AsyncMock(return_value=MagicMock(**mock_spotify_profile))
            
            # Call the callback endpoint
            response = client.get(f"/api/auth/spotify/callback?code={MOCK_CODE}&state={MOCK_STATE}")
            
            # Verify the token service was called correctly
            mock_get_tokens.assert_called_once_with(MOCK_CODE)
            
            # Verify the client was instantiated with the token
            MockClient.assert_called_once_with(access_token=MOCK_ACCESS_TOKEN)
            
            # Verify profile was requested
            mock_client_instance.get_user_profile.assert_called_once()
            
            # Check database for user creation
            from app.db.models import User
            user = db_session.query(User).filter(User.spotify_id == MOCK_SPOTIFY_ID).first()
            assert user is not None
            assert user.spotify_access_token == MOCK_ACCESS_TOKEN
            assert user.spotify_refresh_token == MOCK_REFRESH_TOKEN
            
            # Verify response is a redirect to the success page
            assert response.status_code in (302, 307)  # Redirect status codes
            assert "auth/success" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_spotify_callback_error(client):
    """
    Test Spotify OAuth callback with error parameter.
    
    This test verifies that the callback endpoint properly
    handles error responses from Spotify.
    """
    error_msg = "access_denied"
    response = client.get(f"/api/auth/spotify/callback?error={error_msg}")
    
    # Verify proper error handling
    assert response.status_code == 400
    assert "error" in response.json()
    assert error_msg in response.json()["detail"]


def test_logout(client):
    """
    Test user logout.
    
    This test verifies that the logout endpoint returns
    the expected success message.
    """
    response = client.get("/api/auth/logout")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "logged out" in response.json()["message"].lower()
