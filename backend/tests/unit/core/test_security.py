"""
Tests for JWT authentication security functions.
"""

import pytest
from datetime import datetime, timedelta
from jose import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_password_hash,
    verify_password,
    JWT_SECRET_KEY,
    ALGORITHM,
)


class TestTokenGeneration:
    """Tests for JWT token generation functions."""

    def test_access_token_generation(self):
        """Test that access tokens are generated correctly with expected claims."""
        # Create test data
        data = {"sub": "test-user-id", "role": "user"}

        # Generate token
        token = create_access_token(data)

        # Verify token format and decode
        assert isinstance(token, str)
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])

        # Verify payload data
        assert payload["sub"] == "test-user-id"
        assert payload["role"] == "user"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_refresh_token_generation(self):
        """Test that refresh tokens are generated correctly with expected claims."""
        # Create test data
        data = {"sub": "test-user-id"}

        # Generate token
        token = create_refresh_token(data)

        # Verify token format and decode
        assert isinstance(token, str)
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])

        # Verify payload data
        assert payload["sub"] == "test-user-id"
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_token_expiration(self):
        """Test that token expiration dates are set correctly."""
        # Get current time to compare against token exp claim
        now = datetime.utcnow()

        # Generate tokens
        access_token = create_access_token({"sub": "user-id"})
        refresh_token = create_refresh_token({"sub": "user-id"})

        # Decode tokens
        access_payload = jwt.decode(
            access_token, JWT_SECRET_KEY, algorithms=[ALGORITHM]
        )
        refresh_payload = jwt.decode(
            refresh_token, JWT_SECRET_KEY, algorithms=[ALGORITHM]
        )

        # Convert exp to datetime for comparison
        access_exp = datetime.fromtimestamp(access_payload["exp"])
        refresh_exp = datetime.fromtimestamp(refresh_payload["exp"])

        # Check expiration times (with some tolerance for execution time)
        expected_access_exp = now + timedelta(minutes=15)
        expected_refresh_exp = now + timedelta(days=7)

        # Allow for a small tolerance (3 seconds) in our test
        assert abs((access_exp - expected_access_exp).total_seconds()) < 3
        assert abs((refresh_exp - expected_refresh_exp).total_seconds()) < 3


class TestTokenValidation:
    """Tests for JWT token validation functions."""

    def test_valid_token_verification(self):
        """Test that valid tokens are verified correctly."""
        # Create valid tokens
        access_token = create_access_token({"sub": "user-id"})
        refresh_token = create_refresh_token({"sub": "user-id"})

        # Verify tokens
        access_payload = verify_token(access_token, token_type="access")
        refresh_payload = verify_token(refresh_token, token_type="refresh")

        # Check payload contents
        assert access_payload["sub"] == "user-id"
        assert access_payload["type"] == "access"
        assert refresh_payload["sub"] == "user-id"
        assert refresh_payload["type"] == "refresh"

    def test_invalid_token_verification(self):
        """Test that invalid tokens raise appropriate errors."""
        # Try to verify an invalid token string
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token("invalid-token")

    def test_wrong_token_type(self):
        """Test that tokens with wrong type raise appropriate errors."""
        # Create tokens
        access_token = create_access_token({"sub": "user-id"})
        refresh_token = create_refresh_token({"sub": "user-id"})

        # Verify with wrong type
        with pytest.raises(ValueError, match="Token is not a refresh token"):
            verify_token(access_token, token_type="refresh")

        with pytest.raises(ValueError, match="Token is not a access token"):
            verify_token(refresh_token, token_type="access")

    def test_expired_token(self):
        """Test that expired tokens raise appropriate errors."""
        # Create a payload with a past expiration time
        payload = {"sub": "test-user", "exp": datetime.utcnow() - timedelta(hours=1)}

        # Create the token manually
        expired_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)

        # Verify expired token
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token(expired_token)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_password_hashing(self):
        """Test that password hashing produces different hashes for the same password."""
        password = "secure-password"

        # Generate two hashes for the same password
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different (due to salt)
        assert hash1 != hash2

        # Both hashes should verify against the original password
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)

    def test_password_verification(self):
        """Test password verification against known hashes."""
        password = "another-secure-password"
        wrong_password = "wrong-password"

        # Generate hash
        password_hash = get_password_hash(password)

        # Verify correct password
        assert verify_password(password, password_hash)

        # Verify incorrect password
        assert not verify_password(wrong_password, password_hash)
