"""
Dependency injection functions for the API.
"""

from fastapi import Depends, HTTPException, Cookie, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.db.models import User
from app.core.security import verify_token


# Database dependency
db_dependency = get_db

# OAuth2 scheme for token extraction from Authorization header
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/auth/token",
    auto_error=False,  # Don't auto-raise errors to allow cookie fallback
)


async def get_token(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    access_token_cookie: Optional[str] = Cookie(None),
) -> str:
    """
    Extract token from either Authorization header or cookie.

    Prioritizes the Authorization header token if available.
    """
    if token:
        return token
    if access_token_cookie:
        return access_token_cookie

    # No token found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: str = Depends(get_token), db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from a JWT token.

    Verifies the token and fetches the corresponding user from the database.
    """
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("User ID not found in token")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_premium_user(user: User = Depends(get_current_user)) -> User:
    """
    Get the current user if they have premium privileges.

    Verifies that the user has either premium or admin role.
    """
    if user.role not in ["premium", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required",
        )
    return user


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """
    Get the current user if they have admin privileges.

    Verifies that the user has admin role.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user
