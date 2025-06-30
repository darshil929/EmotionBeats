from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.db.session import get_db
from app.services.spotify.client import SpotifyClient
from app.schemas.spotify import SpotifyPlaylist, SpotifyTrack, SpotifyUserProfile

router = APIRouter(prefix="/api/spotify", tags=["spotify"])


# TODO: Add proper authentication middleware
# For now, use a simple function to get a user_id from request
async def get_current_user_id(user_id: str):
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@router.get("/me", response_model=SpotifyUserProfile)
async def get_profile(
    user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)
):
    """Get the current user's Spotify profile."""
    try:
        client = await SpotifyClient.for_user(db, user_id)
        return await client.get_user_profile()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=List[SpotifyTrack])
async def search_tracks(
    query: str,
    limit: int = 10,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Search for tracks on Spotify."""
    try:
        client = await SpotifyClient.for_user(db, user_id)
        return await client.search_tracks(query, limit, offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/playlists", response_model=SpotifyPlaylist)
async def create_playlist(
    name: str,
    description: str = "",
    public: bool = True,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new Spotify playlist."""
    try:
        client = await SpotifyClient.for_user(db, user_id)
        spotify_profile = await client.get_user_profile()
        return await client.create_playlist(
            spotify_profile.id, name, description, public
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/playlists/{playlist_id}/tracks")
async def add_tracks_to_playlist(
    playlist_id: str,
    track_uris: List[str],
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Add tracks to a playlist."""
    try:
        client = await SpotifyClient.for_user(db, user_id)
        return await client.add_tracks_to_playlist(playlist_id, track_uris)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations", response_model=List[SpotifyTrack])
async def get_recommendations(
    seed_tracks: str = None,
    seed_artists: str = None,
    seed_genres: str = None,
    limit: int = 20,
    # Target audio features for mood matching
    target_valence: float = None,  # Positivity (0.0 to 1.0)
    target_energy: float = None,  # Energy (0.0 to 1.0)
    target_danceability: float = None,  # Danceability (0.0 to 1.0)
    target_acousticness: float = None,  # Acoustic vs. electric (0.0 to 1.0)
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get track recommendations based on seeds and mood parameters."""
    try:
        client = await SpotifyClient.for_user(db, user_id)

        # Convert comma-separated strings to lists
        seed_tracks_list = seed_tracks.split(",") if seed_tracks else None
        seed_artists_list = seed_artists.split(",") if seed_artists else None
        seed_genres_list = seed_genres.split(",") if seed_genres else None

        # Build target features dictionary
        target_features = {}
        if target_valence is not None:
            target_features["valence"] = target_valence
        if target_energy is not None:
            target_features["energy"] = target_energy
        if target_danceability is not None:
            target_features["danceability"] = target_danceability
        if target_acousticness is not None:
            target_features["acousticness"] = target_acousticness

        # ADD DEBUGGING
        print(
            f"DEBUG: Recommendations request - seeds: tracks={seed_tracks_list}, artists={seed_artists_list}, genres={seed_genres_list}"
        )
        print(f"DEBUG: Target features: {target_features}")

        return await client.get_recommendations(
            seed_tracks=seed_tracks_list,
            seed_artists=seed_artists_list,
            seed_genres=seed_genres_list,
            limit=limit,
            target_features=target_features,
        )
    except Exception as e:
        # ADD DETAILED ERROR LOGGING
        import traceback

        print(f"ERROR in get_recommendations: {str(e)}")
        print(f"ERROR type: {type(e)}")
        print(f"ERROR traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug-token")
async def debug_token(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Debug endpoint to check token status."""
    try:
        from app.db.models import User

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}

        return {
            "user_id": str(user.id),
            "spotify_access_token": user.spotify_access_token,
            "has_token": bool(user.spotify_access_token),
            "token_length": len(user.spotify_access_token)
            if user.spotify_access_token
            else 0,
        }
    except Exception as e:
        return {"error": str(e)}
