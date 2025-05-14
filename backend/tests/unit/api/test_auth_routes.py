"""
Tests for the authentication routes.

This module tests the authentication flow with Spotify OAuth.
"""

import pytest
from unittest.mock import patch
from fastapi.responses import Response
from fastapi.routing import APIRoute

from app.db.models import User
from app.schemas.spotify import SpotifyTokenSchema, SpotifyUserProfile


@pytest.fixture
def spotify_token_response():
    """Return a mock Spotify token response."""
    return {
        "access_token": "NgCXRKc...MzYjw",
        "token_type": "Bearer",
        "scope": "user-read-private user-read-email playlist-modify-public",
        "expires_in": 3600,
        "refresh_token": "NgAagA...Um_SHo",
    }


@pytest.fixture
def spotify_user_profile():
    """Return a mock Spotify user profile."""
    return {
        "display_name": "Test User",
        "email": "test@example.com",
        "id": "test_spotify_id",
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
def user_with_spotify(db_session):
    """Create a test user with Spotify credentials."""
    user = User(
        username="spotifyuser",
        email="spotify@example.com",
        password_hash="hashed_password",
        spotify_id="existing_spotify_id",
        spotify_access_token="old_access_token",
        spotify_refresh_token="old_refresh_token",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_spotify_login_returns_auth_url(client):
    """Test that the Spotify login endpoint returns a valid auth URL."""
    response = client.get("/api/auth/spotify/login")

    assert response.status_code == 200
    assert "auth_url" in response.json()

    auth_url = response.json()["auth_url"]
    assert "accounts.spotify.com/authorize" in auth_url
    assert "client_id=" in auth_url
    assert "response_type=code" in auth_url
    assert "redirect_uri=" in auth_url


def test_spotify_login_includes_required_scopes(client):
    """Test that the Spotify login URL includes all required scopes."""
    response = client.get("/api/auth/spotify/login")

    assert response.status_code == 200
    auth_url = response.json()["auth_url"]

    # Check for required scopes
    assert "scope=" in auth_url

    # These are the scopes defined in the auth.py router
    required_scopes = [
        "user-read-email",
        "user-read-private",
        "playlist-read-private",
        "playlist-modify-public",
        "playlist-modify-private",
        "user-top-read",
    ]

    for scope in required_scopes:
        assert scope in auth_url


def test_spotify_callback_creates_new_user(
    client, db_session, spotify_token_response, spotify_user_profile, monkeypatch
):
    """Test the callback function directly without going through routing."""
    # Import the actual callback function
    from app.api.routes.auth import spotify_callback

    # Create real async response objects to return from our mocks
    token_response = SpotifyTokenSchema(**spotify_token_response)
    profile_response = SpotifyUserProfile(**spotify_user_profile)

    # Mock the SpotifyAuthService.get_tokens method
    async def mock_get_tokens(*args, **kwargs):
        return token_response

    # Mock the SpotifyClient constructor
    def mock_client_init(self, access_token, refresh_token=None, expires_at=None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        return None

    # Mock the SpotifyClient.get_user_profile method
    async def mock_get_profile(*args, **kwargs):
        return profile_response

    # Apply the monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.auth.SpotifyAuthService.get_tokens", mock_get_tokens
    )
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.__init__", mock_client_init
    )
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.get_user_profile", mock_get_profile
    )

    # Call the callback function directly with mocked dependencies
    import asyncio

    mock_response = Response()
    response = asyncio.run(
        spotify_callback(
            response=mock_response, code="test_code", state="test_state", db=db_session
        )
    )

    # Verify response is a redirect (307 is Temporary Redirect)
    assert response.status_code == 307
    assert "/auth/success?user_id=" in response.headers.get("location", "")

    # Verify user was created in database
    user = db_session.query(User).filter(User.spotify_id == "test_spotify_id").first()
    assert user is not None
    assert user.email == "test@example.com"
    assert user.spotify_access_token == "NgCXRKc...MzYjw"
    assert user.spotify_refresh_token == "NgAagA...Um_SHo"


def test_spotify_callback_updates_existing_user(
    client,
    db_session,
    user_with_spotify,
    spotify_token_response,
    spotify_user_profile,
    monkeypatch,
):
    """Test that the callback endpoint updates an existing user."""
    # Import the actual callback function
    from app.api.routes.auth import spotify_callback

    # Modify profile to match existing user
    existing_profile = spotify_user_profile.copy()
    existing_profile["id"] = "existing_spotify_id"

    # Create real async response objects to return from our mocks
    token_response = SpotifyTokenSchema(**spotify_token_response)
    profile_response = SpotifyUserProfile(**existing_profile)

    # Mock the SpotifyAuthService.get_tokens method
    async def mock_get_tokens(*args, **kwargs):
        return token_response

    # Mock the SpotifyClient constructor
    def mock_client_init(self, access_token, refresh_token=None, expires_at=None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        return None

    # Mock the SpotifyClient.get_user_profile method
    async def mock_get_profile(*args, **kwargs):
        return profile_response

    # Apply the monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.auth.SpotifyAuthService.get_tokens", mock_get_tokens
    )
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.__init__", mock_client_init
    )
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.get_user_profile", mock_get_profile
    )

    # Call the callback function directly with mocked dependencies
    import asyncio

    mock_response = Response()
    response = asyncio.run(
        spotify_callback(
            response=mock_response, code="test_code", state="test_state", db=db_session
        )
    )

    # Verify response is a redirect
    assert response.status_code == 307  # Temporary Redirect
    assert f"/auth/success?user_id={user_with_spotify.id}" in response.headers.get(
        "location", ""
    )

    # Refresh user from database
    db_session.refresh(user_with_spotify)

    # Verify tokens were updated
    assert user_with_spotify.spotify_access_token == "NgCXRKc...MzYjw"
    assert user_with_spotify.spotify_refresh_token == "NgAagA...Um_SHo"


def test_spotify_callback_with_error_param(client):
    """Test error handling when callback has an error parameter."""
    # Include the required 'code' parameter to avoid 422
    response = client.get(
        "/api/auth/spotify/callback?error=access_denied&state=test_state&code=dummy_code"
    )

    assert response.status_code == 400
    assert "detail" in response.json()
    assert "Spotify auth error" in response.json()["detail"]


@patch("app.services.spotify.auth.SpotifyAuthService.get_tokens")
def test_spotify_callback_handles_token_exception(mock_get_tokens, client):
    """Test exception handling during token retrieval."""
    # Mock token retrieval to raise an exception
    mock_get_tokens.side_effect = Exception("Token error")

    response = client.get("/api/auth/spotify/callback?code=test_code&state=test_state")

    # Should return 500 error
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "Authentication error" in response.json()["detail"]


def test_spotify_callback_handles_profile_exception(
    client, spotify_token_response, monkeypatch
):
    """Test exception handling during profile retrieval."""
    # Create token response
    token_response = SpotifyTokenSchema(**spotify_token_response)

    # Mock the SpotifyAuthService.get_tokens method
    async def mock_get_tokens(*args, **kwargs):
        return token_response

    # Mock the SpotifyClient.get_user_profile method to raise an exception
    async def mock_get_profile_error(*args, **kwargs):
        raise Exception("Profile error")

    # Apply the monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.auth.SpotifyAuthService.get_tokens", mock_get_tokens
    )
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.get_user_profile",
        mock_get_profile_error,
    )

    # Import the actual callback function
    from app.api.routes.auth import spotify_callback

    # Call the callback function directly with mocked dependencies
    import asyncio

    mock_response = Response()

    try:
        # This should raise an exception
        mock_response = Response()
        asyncio.run(
            spotify_callback(
                response=mock_response, code="test_code", state="test_state", db=None
            )
        )
        assert False, "Expected an exception but none was raised"
    except Exception as e:
        assert "Profile error" in str(e)


def test_spotify_callback_redirects_to_frontend(
    client, db_session, spotify_token_response, spotify_user_profile, monkeypatch
):
    """Test that successful authentication redirects to the frontend."""
    # Import the actual callback function
    from app.api.routes.auth import spotify_callback

    # Create real async response objects to return from our mocks
    token_response = SpotifyTokenSchema(**spotify_token_response)
    profile_response = SpotifyUserProfile(**spotify_user_profile)

    # Mock the SpotifyAuthService.get_tokens method
    async def mock_get_tokens(*args, **kwargs):
        return token_response

    # Mock the SpotifyClient constructor
    def mock_client_init(self, access_token, refresh_token=None, expires_at=None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        return None

    # Mock the SpotifyClient.get_user_profile method
    async def mock_get_profile(*args, **kwargs):
        return profile_response

    # Apply the monkeypatches
    monkeypatch.setattr(
        "app.services.spotify.auth.SpotifyAuthService.get_tokens", mock_get_tokens
    )
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.__init__", mock_client_init
    )
    monkeypatch.setattr(
        "app.services.spotify.client.SpotifyClient.get_user_profile", mock_get_profile
    )

    # Call the callback function directly with mocked dependencies
    import asyncio

    mock_response = Response()
    response = asyncio.run(
        spotify_callback(
            response=mock_response, code="test_code", state="test_state", db=db_session
        )
    )

    # Should redirect to frontend
    assert response.status_code == 307  # Temporary Redirect
    assert "/auth/success?user_id=" in response.headers.get("location", "")

    # Extract user_id from redirect URL
    redirect_url = response.headers.get("location", "")
    user_id = redirect_url.split("user_id=")[1]

    # Verify user exists in database
    user = db_session.query(User).filter(User.id == user_id).first()
    assert user is not None


def test_logout_returns_success_message(client):
    """Test that the logout endpoint returns a success message."""
    response = client.get("/api/auth/logout")

    assert response.status_code == 200
    assert "message" in response.json()
    assert "Logged out successfully" in response.json()["message"]


def test_available_routes(client):
    """Debug test to list all available routes."""
    print("\nAll routes with patterns:")
    for route in client.app.routes:
        if isinstance(route, APIRoute):
            print(f"Route: {route.path}, Methods: {route.methods}, Name: {route.name}")

    response = client.get("/api/auth/spotify/login")
    assert response.status_code == 200

    # Try the callback with a different path pattern
    response = client.get("/api/auth/spotify/callback/?code=test_code&state=test_state")
    print(f"With trailing slash: {response.status_code}")

    response = client.get("/auth/spotify/callback?code=test_code&state=test_state")
    print(f"Without api prefix: {response.status_code}")
