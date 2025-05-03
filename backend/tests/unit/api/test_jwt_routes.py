"""
Tests for JWT authentication routes.

This module tests token refresh, validation, and logout endpoints.
"""

import pytest
from datetime import datetime, timedelta, UTC

from app.core.security import (
    create_access_token,
    create_refresh_token,
    JWT_SECRET_KEY,
    ALGORITHM,
)
from app.db.models import User
from jose import jwt


@pytest.fixture
def user_with_role(db_session, request):
    """Create a test user with a specific role."""
    role = request.param if hasattr(request, "param") else "user"

    user = User(
        username=f"{role}_user",
        email=f"{role}@example.com",
        password_hash="hashed_password",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def valid_access_token(user_with_role):
    """Create a valid access token for a user."""
    return create_access_token(
        data={"sub": str(user_with_role.id), "role": user_with_role.role}
    )


@pytest.fixture
def valid_refresh_token(user_with_role):
    """Create a valid refresh token for a user."""
    return create_refresh_token(data={"sub": str(user_with_role.id)})


@pytest.fixture
def expired_token(user_with_role):
    """Create an expired token for testing."""
    payload = {
        "sub": str(user_with_role.id),
        "exp": datetime.now(UTC) - timedelta(minutes=5),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


class TestTokenRefresh:
    """Tests for the token refresh endpoint."""

    def test_refresh_token_valid(self, client, user_with_role, valid_refresh_token):
        """Test successful token refresh with valid refresh token."""
        response = client.post(
            "/api/auth/token/refresh", json={"refresh_token": valid_refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # Verify new access token is valid
        new_token = data["access_token"]
        payload = jwt.decode(new_token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == str(user_with_role.id)
        assert payload["role"] == user_with_role.role

    def test_refresh_token_from_cookie(
        self, client, user_with_role, valid_refresh_token
    ):
        """Test token refresh using a refresh token from cookie."""
        # Set cookie and make request
        client.cookies.update({"refresh_token": valid_refresh_token})

        response = client.post("/api/auth/token/refresh")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_refresh_token_missing(self, client):
        """Test error when refresh token is missing."""
        response = client.post("/api/auth/token/refresh")

        assert response.status_code == 401
        assert "Refresh token is required" in response.json()["detail"]

    def test_refresh_token_invalid(self, client):
        """Test error when refresh token is invalid."""
        response = client.post(
            "/api/auth/token/refresh", json={"refresh_token": "invalid-token"}
        )

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_refresh_token_wrong_type(self, client, valid_access_token):
        """Test error when using an access token for refresh."""
        response = client.post(
            "/api/auth/token/refresh", json={"refresh_token": valid_access_token}
        )

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_refresh_token_user_not_found(self, client, db_session):
        """Test error when user from token doesn't exist."""
        # Create token for non-existent user
        non_existent_id = "00000000-0000-0000-0000-000000000000"
        refresh_token = create_refresh_token(data={"sub": non_existent_id})

        response = client.post(
            "/api/auth/token/refresh", json={"refresh_token": refresh_token}
        )

        assert response.status_code == 401
        assert "User not found" in response.json()["detail"]


class TestTokenValidation:
    """Tests for the token validation endpoint."""

    def test_validate_token_valid(self, client, valid_access_token):
        """Test successful token validation with valid access token."""
        response = client.post(
            "/api/auth/token/validate", json={"token": valid_access_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "user_id" in data
        assert "role" in data

    def test_validate_token_from_cookie(self, client, valid_access_token):
        """Test token validation using a token from cookie."""
        # Set cookie and make request
        client.cookies.update({"access_token": valid_access_token})

        response = client.post("/api/auth/token/validate")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    def test_validate_token_missing(self, client):
        """Test error when token is missing."""
        response = client.post("/api/auth/token/validate")

        assert response.status_code == 401
        assert "Token is required" in response.json()["detail"]

    def test_validate_token_invalid(self, client):
        """Test response when token is invalid."""
        response = client.post(
            "/api/auth/token/validate", json={"token": "invalid-token"}
        )

        assert response.status_code == 200  # Still returns 200 with valid=false
        data = response.json()
        assert data["valid"] is False

    def test_validate_token_expired(self, client, expired_token):
        """Test response when token is expired."""
        response = client.post(
            "/api/auth/token/validate", json={"token": expired_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False


class TestLogout:
    """Tests for the logout endpoint."""

    def test_logout_clears_cookies(self, client):
        """Test that logout endpoint clears authentication cookies."""
        # Set cookies first
        client.cookies.update(
            {"access_token": "some-token", "refresh_token": "some-refresh-token"}
        )

        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]

        # Check for Set-Cookie headers that clear cookies
        cookie_headers = response.headers.get("set-cookie", "")
        assert "access_token=" in cookie_headers
        assert "refresh_token=" in cookie_headers
