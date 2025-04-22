import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.models import User
from app.db.session import get_db
from app.schemas.spotify import SpotifyAuthSchema
from app.services.spotify.auth import SpotifyAuthService
from app.utils.datetime_helper import utc_now

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
    code: str, state: str = None, error: str = None, db: Session = Depends(get_db)
):
    """Handle Spotify OAuth callback."""
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
            # Update existing user
            user.spotify_access_token = token_data.access_token
            user.spotify_refresh_token = token_data.refresh_token
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
                spotify_access_token=token_data.access_token,
                spotify_refresh_token=token_data.refresh_token,
                spotify_token_expiry=utc_now()
                + timedelta(seconds=token_data.expires_in),
                is_active=True,
            )
            db.add(user)

        db.commit()

        # Redirect to frontend with success - UPDATED URL
        return RedirectResponse(url=f"https://localhost/auth/success?user_id={user.id}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")


@router.get("/logout")
async def logout():
    """Log out the user."""
    return {"message": "Logged out successfully"}
