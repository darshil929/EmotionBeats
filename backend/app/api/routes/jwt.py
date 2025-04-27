"""
JWT authentication routes for token management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.schemas.auth import Token
from app.core.security import (
    create_access_token,
    verify_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token/refresh", response_model=Token)
async def refresh_token(
    response: Response,
    refresh_token: str = None,
    refresh_token_cookie: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """
    Refresh an access token using a refresh token.

    Accepts refresh token from either request body or cookie.
    """
    token = refresh_token or refresh_token_cookie
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is required",
        )

    try:
        payload = verify_token(token, token_type="refresh")
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
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
            "refresh_token": token,
            "token_type": "bearer",
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )


@router.post("/token/validate")
async def validate_token(token: str = None, access_token_cookie: str = Cookie(None)):
    """
    Validate an access token.

    Accepts token from either request body or cookie.
    """
    token_to_validate = token or access_token_cookie
    if not token_to_validate:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is required",
        )

    try:
        payload = verify_token(token_to_validate)
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
    return {"message": "Successfully logged out"}
