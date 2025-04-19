from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class SpotifyTokenSchema(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: str


class SpotifyAuthSchema(BaseModel):
    auth_url: str


class SpotifyUserProfile(BaseModel):
    id: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    images: Optional[List[Dict[str, Any]]] = None
    uri: str


class SpotifyTrack(BaseModel):
    id: str
    name: str
    artists: List[Dict[str, Any]]
    album: Dict[str, Any]
    duration_ms: int
    uri: str
    preview_url: Optional[str] = None


class SpotifyPlaylist(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    public: bool
    tracks: Dict[str, Any]
    uri: str
    external_urls: Dict[str, str]


class SpotifyAudioFeatures(BaseModel):
    id: str
    danceability: float
    energy: float
    key: int
    loudness: float
    mode: int
    speechiness: float
    acousticness: float
    instrumentalness: float
    liveness: float
    valence: float
    tempo: float
