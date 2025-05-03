"""
Authentication schema models using Pydantic.
"""

from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""

    sub: str
    exp: Optional[int] = None
    type: str = "access"
    role: str = "user"


class UserAuth(BaseModel):
    """Schema for user authentication data."""

    username: str
    password: str


class UserResponse(BaseModel):
    """Schema for user data in responses."""

    id: str
    username: str
    email: str
    role: str
    is_active: bool

    class Config:
        orm_mode = True


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str
