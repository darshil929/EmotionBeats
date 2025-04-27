"""
JWT authentication routes for token management.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, Request, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.db.models import User
from app.schemas.auth import Token
from app.core.security import (
    create_access_token,
    verify_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RefreshTokenRequest(BaseModel):
    """Request model for token refresh."""

    refresh_token: Optional[str] = None


class TokenRequest(BaseModel):
    """Request model for token validation."""

    token: Optional[str] = None


@router.post("/token/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    response: Response,
    data: Optional[RefreshTokenRequest] = Body(default=None),
    db: Session = Depends(get_db),
):
    """
    Refresh an access token using a refresh token.

    Accepts refresh token from either request body or cookie.
    """
    # Extract token from request body or cookie
    refresh_token = None

    # Check if token is in request body
    if data and data.refresh_token:
        refresh_token = data.refresh_token
    # If not in body, check cookies
    elif "refresh_token" in request.cookies:
        refresh_token = request.cookies.get("refresh_token")

    # Validate token presence
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token is required",
        )

    try:
        # Verify the token
        payload = verify_token(refresh_token, token_type="refresh")
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token",
            )

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=401,
                detail="User not found",
            )

        # Create new access token
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role}
        )

        # Set cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid refresh token: {str(e)}",
        )


@router.post("/token/validate")
async def validate_token(
    request: Request, data: Optional[TokenRequest] = Body(default=None)
):
    """
    Validate an access token.

    Accepts token from either request body or cookie.
    """
    # Extract token from request body or cookie
    token = None

    # Check if token is in request body
    if data and data.token:
        token = data.token
    # If not in body, check cookies
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    # Validate token presence
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Token is required",
        )

    try:
        payload = verify_token(token)
        return {
            "valid": True,
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
        }
    except ValueError:
        return {"valid": False}


@router.post("/logout")
async def logout(response: Response):
    """Log out the user by clearing authentication cookies."""
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    response.delete_cookie(key="csrf_token")
    return {"message": "Successfully logged out"}
