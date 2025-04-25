"""Unit tests for SpotifyAuthService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote

from app.services.spotify.auth import SpotifyAuthService, AUTH_URL, TOKEN_URL
from app.schemas.spotify import SpotifyTokenSchema


@pytest.fixture
def auth_code():
    """Sample authorization code."""
    return "test_auth_code"


@pytest.fixture
def refresh_token():
    """Sample refresh token."""
    return "test_refresh_token"


@pytest.fixture
def token_response():
    """Sample token response from Spotify."""
    return {
        "access_token": "new_access_token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "new_refresh_token",
        "scope": "user-read-private user-read-email",
    }


class TestSpotifyAuthService:
    """Tests for the SpotifyAuthService class."""

    def test_get_auth_url(self):
        """Test generation of Spotify authorization URL."""
        # Set up test environment variables
        with (
            patch("app.services.spotify.auth.SPOTIFY_CLIENT_ID", "test_client_id"),
            patch(
                "app.services.spotify.auth.SPOTIFY_REDIRECT_URI",
                "https://test.com/callback",
            ),
        ):
            scopes = ["user-read-private", "user-read-email"]
            auth_url = SpotifyAuthService.get_auth_url(scopes)

            # Verify URL structure and parameters
            assert AUTH_URL in auth_url
            assert "client_id=test_client_id" in auth_url
            assert "response_type=code" in auth_url
            assert quote("https://test.com/callback", safe="") in auth_url
            assert "scope=" in auth_url
            assert "state=" not in auth_url

            # Test with optional state parameter
            state = "test_state"
            auth_url_with_state = SpotifyAuthService.get_auth_url(scopes, state)
            assert f"state={state}" in auth_url_with_state

    @pytest.mark.asyncio
    async def test_get_tokens(self, auth_code, token_response):
        """Test exchange of authorization code for tokens."""
        with (
            patch("app.services.spotify.auth.SPOTIFY_CLIENT_ID", "test_client_id"),
            patch(
                "app.services.spotify.auth.SPOTIFY_CLIENT_SECRET", "test_client_secret"
            ),
            patch(
                "app.services.spotify.auth.SPOTIFY_REDIRECT_URI",
                "https://test.com/callback",
            ),
            patch(
                "httpx.AsyncClient.__aenter__", new_callable=AsyncMock
            ) as mock_client,
        ):
            # Configure mock response
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = token_response

            # Set up async mock
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.post = mock_post

            # Call the method
            result = await SpotifyAuthService.get_tokens(auth_code)

            # Verify request details
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args

            assert args[0] == TOKEN_URL
            assert "Basic " in kwargs["headers"]["Authorization"]
            assert kwargs["data"]["grant_type"] == "authorization_code"
            assert kwargs["data"]["code"] == auth_code

            # Verify result
            assert isinstance(result, SpotifyTokenSchema)
            assert result.access_token == token_response["access_token"]
            assert result.refresh_token == token_response["refresh_token"]

    @pytest.mark.asyncio
    async def test_refresh_token(self, refresh_token, token_response):
        """Test refreshing an expired access token."""
        # Remove refresh_token from response since it's not always returned
        token_response_without_refresh = token_response.copy()
        token_response_without_refresh.pop("refresh_token")

        with (
            patch("app.services.spotify.auth.SPOTIFY_CLIENT_ID", "test_client_id"),
            patch(
                "app.services.spotify.auth.SPOTIFY_CLIENT_SECRET", "test_client_secret"
            ),
            patch(
                "httpx.AsyncClient.__aenter__", new_callable=AsyncMock
            ) as mock_client,
        ):
            # Configure mock response
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = token_response_without_refresh

            # Set up async mock
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.post = mock_post

            # Call the method
            result = await SpotifyAuthService.refresh_token(refresh_token)

            # Verify request details
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args

            assert args[0] == TOKEN_URL
            assert "Basic " in kwargs["headers"]["Authorization"]
            assert kwargs["data"]["grant_type"] == "refresh_token"
            assert kwargs["data"]["refresh_token"] == refresh_token

            # Verify result
            assert isinstance(result, SpotifyTokenSchema)
            assert result.access_token == token_response_without_refresh["access_token"]
            assert result.refresh_token is None

    @pytest.mark.asyncio
    async def test_get_tokens_error(self, auth_code):
        """Test error handling during token exchange."""
        with (
            patch("app.services.spotify.auth.SPOTIFY_CLIENT_ID", "test_client_id"),
            patch(
                "app.services.spotify.auth.SPOTIFY_CLIENT_SECRET", "test_client_secret"
            ),
            patch(
                "httpx.AsyncClient.__aenter__", new_callable=AsyncMock
            ) as mock_client,
        ):
            # Configure mock error response
            mock_response = MagicMock()
            api_error = Exception("API Error")
            mock_response.raise_for_status.side_effect = api_error

            # Set up async mock
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.post = mock_post

            with pytest.raises(Exception) as exc_info:
                await SpotifyAuthService.get_tokens(auth_code)

            assert "API Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_refresh_token_error(self, refresh_token):
        """Test error handling during token refresh."""
        with (
            patch("app.services.spotify.auth.SPOTIFY_CLIENT_ID", "test_client_id"),
            patch(
                "app.services.spotify.auth.SPOTIFY_CLIENT_SECRET", "test_client_secret"
            ),
            patch(
                "httpx.AsyncClient.__aenter__", new_callable=AsyncMock
            ) as mock_client,
        ):
            # Configure mock error response
            mock_response = MagicMock()
            api_error = Exception("API Error")
            mock_response.raise_for_status.side_effect = api_error

            # Set up async mock
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.post = mock_post

            with pytest.raises(Exception) as exc_info:
                await SpotifyAuthService.refresh_token(refresh_token)

            assert "API Error" in str(exc_info.value)
