"""
Authentication routes for Spotify OAuth and token management.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional

from app.db.models import User
from app.db.session import get_db
from app.schemas.spotify import SpotifyAuthSchema
from app.services.spotify.auth import SpotifyAuthService
from app.utils.datetime_helper import utc_now
from app.core.security import (
    create_access_token,
    create_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Required scopes for our application
SPOTIFY_SCOPES = [
    "user-read-email",
    "user-read-private",
    "playlist-read-private",
    "playlist-modify-public",
    "playlist-modify-private",
    "user-top-read",
]


@router.get("/spotify/login", response_model=SpotifyAuthSchema)
async def spotify_login():
    """Generate Spotify login URL."""
    # Generate a random state for CSRF protection
    state = str(uuid.uuid4())
    auth_url = SpotifyAuthService.get_auth_url(scopes=SPOTIFY_SCOPES, state=state)
    return {"auth_url": auth_url}


@router.get("/spotify/callback")
async def spotify_callback(
    response: Response,
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Handle Spotify OAuth callback.

    Exchanges authorization code for tokens, retrieves user profile,
    and creates or updates the user in the database.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Spotify auth error: {error}")

    try:
        # Exchange code for tokens
        token_data = await SpotifyAuthService.get_tokens(code)

        # Connect a spotify client and get user profile
        from app.services.spotify.client import SpotifyClient

        client = SpotifyClient(access_token=token_data.access_token)
        user_profile = await client.get_user_profile()

        # Check if user exists
        user = db.query(User).filter(User.spotify_id == user_profile.id).first()

        if user:
            # Update existing user - use setattr to handle SQLAlchemy Column types
            setattr(user, "spotify_access_token", token_data.access_token)
            setattr(
                user,
                "spotify_refresh_token",
                token_data.refresh_token if token_data.refresh_token else None,
            )
            user.spotify_token_expiry = utc_now() + timedelta(
                seconds=token_data.expires_in
            )
        else:
            # Create new user
            user = User(
                username=user_profile.display_name or f"user_{user_profile.id}",
                email=user_profile.email,
                password_hash="dummy_hash_for_oauth_user",
                spotify_id=user_profile.id,
                is_active=True,
                role="user",  # Default role
            )
            # Add user to session before setting Spotify tokens
            db.add(user)
            # Flush to generate an ID
            db.flush()

            # Now set the Spotify tokens
            setattr(user, "spotify_access_token", token_data.access_token)
            setattr(
                user,
                "spotify_refresh_token",
                token_data.refresh_token if token_data.refresh_token else None,
            )
            user.spotify_token_expiry = utc_now() + timedelta(
                seconds=token_data.expires_in
            )

        db.commit()

        # Generate JWT tokens
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role}
        )
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        # Set tokens as cookies
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )

        # Redirect to frontend with success and include tokens in query params
        # This allows the frontend to store tokens in session/local storage if needed
        return RedirectResponse(
            url=f"https://localhost/auth/success?user_id={user.id}&access_token={access_token}&refresh_token={refresh_token}",
            status_code=303,  # See Other
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")


@router.get("/logout")
async def logout(response: Response):
    """
    Log out the user.

    Clears authentication cookies.
    """
    # Clear cookies
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    response.delete_cookie(key="csrf_token")

    return {"message": "Logged out successfully"}
