import httpx
from typing import List, Dict, Any, Optional
from datetime import timedelta, datetime


from sqlalchemy.orm import Session
from app.db.models import User
from app.schemas.spotify import (
    SpotifyUserProfile,
    SpotifyTrack,
    SpotifyPlaylist,
    SpotifyAudioFeatures,
)
from app.services.spotify.auth import SpotifyAuthService
from app.utils.datetime_helper import utc_now

BASE_URL = "https://api.spotify.com/v1"


class SpotifyClient:
    """Client for interacting with Spotify Web API."""

    def __init__(
        self, access_token: str, refresh_token: str = None, expires_at: datetime = None
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at

    @classmethod
    async def for_user(cls, db: Session, user_id: str) -> "SpotifyClient":
        """Create a client instance for a specific user."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        if not user.spotify_access_token:
            raise ValueError("User not authenticated with Spotify")

        # Check if token is expired
        if user.spotify_token_expiry and user.spotify_token_expiry <= utc_now():
            if not user.spotify_refresh_token:
                raise ValueError("Refresh token not available")

            # Refresh the token
            token_data = await SpotifyAuthService.refresh_token(
                user.spotify_refresh_token
            )

            # Update user record
            user.spotify_access_token = token_data.access_token
            # Add expires_in seconds to current time
            user.spotify_token_expiry = utc_now() + timedelta(
                seconds=token_data.expires_in
            )
            if token_data.refresh_token:
                user.spotify_refresh_token = token_data.refresh_token

            db.commit()

        return cls(
            access_token=user.spotify_access_token,
            refresh_token=user.spotify_refresh_token,
            expires_at=user.spotify_token_expiry,
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Send a request to the Spotify API."""
        url = f"{BASE_URL}{endpoint}"

        default_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        if headers:
            default_headers.update(headers)

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=default_headers,
                timeout=10.0,
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 1))
                # In a real app, you might want to implement proper backoff here
                raise Exception(f"Rate limited. Try again in {retry_after} seconds.")

            response.raise_for_status()
            return response.json() if response.text else {}

    async def get_user_profile(self) -> SpotifyUserProfile:
        """Get the current user's Spotify profile."""
        data = await self._request("GET", "/me")
        return SpotifyUserProfile(**data)

    async def search_tracks(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> List[SpotifyTrack]:
        """Search for tracks on Spotify."""
        params = {
            "q": query,
            "type": "track",
            "limit": limit,
            "offset": offset,
        }

        data = await self._request("GET", "/search", params=params)
        return [
            SpotifyTrack(**item) for item in data.get("tracks", {}).get("items", [])
        ]

    async def create_playlist(
        self, user_id: str, name: str, description: str = "", public: bool = True
    ) -> SpotifyPlaylist:
        """Create a new playlist for a user."""
        endpoint = f"/users/{user_id}/playlists"
        data = {
            "name": name,
            "description": description,
            "public": public,
        }

        response = await self._request("POST", endpoint, data=data)
        return SpotifyPlaylist(**response)

    async def add_tracks_to_playlist(
        self, playlist_id: str, track_uris: List[str]
    ) -> Dict[str, Any]:
        """Add tracks to a playlist."""
        endpoint = f"/playlists/{playlist_id}/tracks"
        data = {
            "uris": track_uris,
        }

        return await self._request("POST", endpoint, data=data)

    async def get_audio_features(self, track_id: str) -> SpotifyAudioFeatures:
        """Get audio features for a track."""
        endpoint = f"/audio-features/{track_id}"
        data = await self._request("GET", endpoint)
        return SpotifyAudioFeatures(**data)

    async def get_recommendations(
        self,
        seed_tracks: Optional[List[str]] = None,
        seed_artists: Optional[List[str]] = None,
        seed_genres: Optional[List[str]] = None,
        limit: int = 20,
        target_features: Optional[Dict[str, float]] = None,
    ) -> List[SpotifyTrack]:
        """Get track recommendations based on seeds and target features."""
        params = {"limit": limit}

        # Add seeds (at least one type of seed is required)
        if seed_tracks:
            params["seed_tracks"] = ",".join(seed_tracks)
        if seed_artists:
            params["seed_artists"] = ",".join(seed_artists)
        if seed_genres:
            params["seed_genres"] = ",".join(seed_genres)

        # Add target audio features for mood matching
        if target_features:
            for key, value in target_features.items():
                params[f"target_{key}"] = value

        data = await self._request("GET", "/recommendations", params=params)
        return [SpotifyTrack(**item) for item in data.get("tracks", [])]
