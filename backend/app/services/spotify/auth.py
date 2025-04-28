import base64
import os
from typing import Optional
from urllib.parse import urlencode
import httpx
from app.schemas.spotify import SpotifyTokenSchema

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv(
    "SPOTIFY_REDIRECT_URI", "https://localhost/api/auth/spotify/callback"
)

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"


class SpotifyAuthService:
    """Service for Spotify authentication flows."""

    @staticmethod
    def get_auth_url(scopes: list[str], state: Optional[str] = None) -> str:
        """Generate the Spotify authorization URL."""
        params = {
            "client_id": SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": SPOTIFY_REDIRECT_URI,
            "scope": " ".join(scopes),
        }

        if state:
            params["state"] = state

        return f"{AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def get_tokens(code: str) -> SpotifyTokenSchema:
        """Exchange the authorization code for access and refresh tokens."""
        auth_header = base64.b64encode(
            f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(TOKEN_URL, headers=headers, data=data)
            response.raise_for_status()
            return SpotifyTokenSchema(**response.json())

    @staticmethod
    async def refresh_token(refresh_token: str) -> SpotifyTokenSchema:
        """Refresh an expired access token."""
        auth_header = base64.b64encode(
            f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(TOKEN_URL, headers=headers, data=data)
            response.raise_for_status()
            return SpotifyTokenSchema(**response.json())
