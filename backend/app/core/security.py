"""
Security utilities for JWT authentication and password hashing.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

from jose import jwt
from passlib.context import CryptContext

import os

# Security configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("JWT_SECRET_KEY must be set in production")
    JWT_SECRET_KEY = "dev-secret-key-never-use-in-production"

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT access token with a specified expiration time.

    Args:
        data: Payload data to include in the token

    Returns:
        Encoded JWT access token
    """
    to_encode = data.copy()

    # Set token expiration
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})

    # Create and return the encoded token
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token with a longer expiration time.

    Args:
        data: Payload data to include in the token

    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()

    # Set token expiration
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})

    # Create and return the encoded token
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token to verify
        token_type: Type of token ("access" or "refresh")

    Returns:
        Token payload if valid

    Raises:
        ValueError: If token is invalid or has wrong type
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])

        # Verify token type matches expected type
        if payload.get("type") != token_type:
            raise ValueError(f"Token is not a {token_type} token")

        return payload
    except jwt.JWTError:
        raise ValueError("Invalid token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches hash, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password for secure storage.

    Args:
        password: Plain text password to hash

    Returns:
        Securely hashed password
    """
    return pwd_context.hash(password)
