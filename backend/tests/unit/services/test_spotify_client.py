"""Unit tests for SpotifyClient core functionality."""

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.models import User
from app.services.spotify.client import SpotifyClient
from app.schemas.spotify import SpotifyTokenSchema
from app.utils.datetime_helper import utc_now


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    return session


@pytest.fixture
def valid_user():
    """Create a user with valid Spotify tokens."""
    user = MagicMock(spec=User)
    user.spotify_access_token = "valid_access_token"
    user.spotify_refresh_token = "valid_refresh_token"
    user.spotify_token_expiry = utc_now() + timedelta(hours=1)  # Not expired
    return user


@pytest.fixture
def expired_user():
    """Create a user with expired Spotify tokens."""
    user = MagicMock(spec=User)
    user.spotify_access_token = "expired_access_token"
    user.spotify_refresh_token = "valid_refresh_token"
    user.spotify_token_expiry = utc_now() - timedelta(hours=1)  # Expired
    return user


@pytest.fixture
def token_schema():
    """Create a token schema for refresh response."""
    return SpotifyTokenSchema(
        access_token="new_access_token",
        token_type="Bearer",
        expires_in=3600,
        scope="user-read-private",
    )


class TestSpotifyClientCore:
    """Tests for the core functionality of SpotifyClient."""

    def test_init(self):
        """Test client initialization with different parameter combinations."""
        # Basic initialization with just access token
        client = SpotifyClient(access_token="test_token")
        assert client.access_token == "test_token"
        assert client.refresh_token is None
        assert client.expires_at is None

        # Complete initialization with all parameters
        expires_at = utc_now()
        client = SpotifyClient(
            access_token="test_token",
            refresh_token="refresh_token",
            expires_at=expires_at,
        )
        assert client.access_token == "test_token"
        assert client.refresh_token == "refresh_token"
        assert client.expires_at == expires_at

    @pytest.mark.asyncio
    async def test_for_user_valid_token(self, mock_db_session, valid_user):
        """Test for_user with a valid, non-expired token."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            valid_user
        )

        client = await SpotifyClient.for_user(mock_db_session, "user_id")

        assert client.access_token == valid_user.spotify_access_token
        assert client.refresh_token == valid_user.spotify_refresh_token
        assert client.expires_at == valid_user.spotify_token_expiry

        # Verify that token refresh was not attempted
        assert not mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_for_user_expired_token(
        self, mock_db_session, expired_user, token_schema
    ):
        """Test for_user with an expired token that needs refreshing."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            expired_user
        )

        with patch(
            "app.services.spotify.auth.SpotifyAuthService.refresh_token",
            new_callable=AsyncMock,
        ) as mock_refresh:
            mock_refresh.return_value = token_schema

            client = await SpotifyClient.for_user(mock_db_session, "user_id")

            mock_refresh.assert_called_once_with(expired_user.spotify_refresh_token)

            # Verify user record was updated
            assert expired_user.spotify_access_token == token_schema.access_token
            assert mock_db_session.commit.called

            # Verify the client has the new token
            assert client.access_token == token_schema.access_token

    @pytest.mark.asyncio
    async def test_for_user_not_found(self, mock_db_session):
        """Test for_user when the user is not found in the database."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="User not found"):
            await SpotifyClient.for_user(mock_db_session, "user_id")

    @pytest.mark.asyncio
    async def test_for_user_not_authenticated(self, mock_db_session, valid_user):
        """Test for_user when the user has no Spotify access token."""
        valid_user.spotify_access_token = None
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            valid_user
        )

        with pytest.raises(ValueError, match="User not authenticated with Spotify"):
            await SpotifyClient.for_user(mock_db_session, "user_id")

    @pytest.mark.asyncio
    async def test_for_user_missing_refresh_token(self, mock_db_session, expired_user):
        """Test for_user when token is expired but no refresh token is available."""
        expired_user.spotify_refresh_token = None
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            expired_user
        )

        with pytest.raises(ValueError, match="Refresh token not available"):
            await SpotifyClient.for_user(mock_db_session, "user_id")

    @pytest.mark.asyncio
    async def test_for_user_with_refresh_token_in_response(
        self, mock_db_session, expired_user, token_schema
    ):
        """Test for_user when a new refresh token is included in the refresh response."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            expired_user
        )

        # Add a refresh token to the token schema
        token_schema.refresh_token = "new_refresh_token"

        with patch(
            "app.services.spotify.auth.SpotifyAuthService.refresh_token",
            new_callable=AsyncMock,
        ) as mock_refresh:
            mock_refresh.return_value = token_schema

            await SpotifyClient.for_user(mock_db_session, "user_id")

            # Verify both tokens were updated
            assert expired_user.spotify_access_token == token_schema.access_token
            assert expired_user.spotify_refresh_token == token_schema.refresh_token
            assert mock_db_session.commit.called
