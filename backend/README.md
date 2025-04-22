# EmotionBeats Backend

The backend component of the EmotionBeats project provides REST API endpoints for authentication, Spotify integration, and playlist management. It serves as the communication layer between the frontend client and external services.

## Implementation Status

### Current Features

- **Authentication System**
  - OAuth2 integration with Spotify
  - JWT token generation and validation
  - User session management

- **Spotify Integration**
  - User profile retrieval
  - Music search functionality
  - Playlist creation and management
  - Track recommendations based on seeds and audio features

- **Database Models**
  - User profiles with Spotify credentials
  - Playlist storage and management
  - Chat session history

### API Endpoints

#### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/spotify/login` | GET | Initiates Spotify OAuth flow |
| `/api/auth/spotify/callback` | GET | Handles Spotify OAuth callback |
| `/api/auth/refresh` | POST | Refreshes JWT access token |

#### Spotify Services

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/spotify/me` | GET | Retrieves user's Spotify profile |
| `/api/spotify/search` | GET | Searches for tracks on Spotify |
| `/api/spotify/playlists` | POST | Creates a new playlist |
| `/api/spotify/playlists/{playlist_id}/tracks` | POST | Adds tracks to a playlist |
| `/api/spotify/recommendations` | GET | Gets track recommendations |

## Technology Details

### FastAPI Framework

The backend utilizes FastAPI, a modern Python web framework optimized for API development with automatic OpenAPI documentation generation. Key components include:

- **Dependency Injection**: For database sessions and authentication
- **Pydantic Models**: For request/response validation
- **Async Support**: For non-blocking I/O operations

### Database Schema

PostgreSQL database with SQLAlchemy ORM mapping:

- **User**: Stores user information and Spotify credentials
- **ChatSession**: Maintains conversation history
- **ChatMessage**: Individual messages in a session
- **Playlist**: Stores created playlist metadata
- **Track**: Individual track information

### Spotify Client

Custom Spotify client implementation with:

- Authentication token management
- Automatic token refresh
- Rate limiting handling
- Error recovery mechanisms

## Testing

### Test Environment Setup

Tests run in a containerized environment to ensure consistency:

```bash
# Build the test container
docker-compose -f docker-compose.test.yml build
```

### Running Tests

#### Run All Tests

```bash
docker-compose -f docker-compose.test.yml run --rm test python -m pytest -v tests/
```

#### Run Specific Test Groups

```bash
# Run API route tests
docker-compose -f docker-compose.test.yml run --rm test python -m pytest -v tests/unit/api/

# Run database model tests
docker-compose -f docker-compose.test.yml run --rm test python -m pytest -v tests/unit/db/

# Run a specific test file
docker-compose -f docker-compose.test.yml run --rm test python -m pytest -v tests/unit/api/test_spotify_routes.py

# Run a specific test function
docker-compose -f docker-compose.test.yml run --rm test python -m pytest -v tests/unit/api/test_spotify_routes.py::test_get_profile
```

### Test Structure

- `tests/unit/api/` - API route tests
  - `test_auth_routes.py` - Authentication endpoint tests
  - `test_spotify_routes.py` - Spotify integration tests
- `tests/unit/db/` - Database model tests
  - `test_model_crud.py` - CRUD operation tests
- `tests/test_db_models.py` - Model structure tests

### Testing Coverage

Current test coverage includes:

- **Authentication Flow**: Login, callback, and token refresh endpoints
- **Spotify API Integration**: Profile retrieval, search, playlist creation, recommendations
- **Database Models**: CRUD operations for all major models
- **Error Handling**: Testing of common error conditions and edge cases

## Next Steps

### Implementation Plan

1. **Emotion Detection Integration**
   - Implement j-hartmann/emotion-english-distilroberta-base model
   - Create endpoints for emotion analysis of user messages
   - Map emotional states to audio features

2. **Preference Extraction**
   - Integrate Llama 3 via Groq API for music preference extraction
   - Develop schema for structured music preferences
   - Implement caching for preference data

3. **Advanced Recommendation Engine**
   - Develop weighted recommendation algorithm combining:
     - Emotional state mapping
     - Extracted preferences
     - Historical listening data
     - Audio feature matching

4. **Performance Optimization**
   - Implement background processing for recommendation generation
   - Add caching layer for frequently accessed data
   - Optimize database queries for scale

5. **Additional Spotify Features**
   - Audio analysis integration
   - Recently played tracks retrieval
   - User's top artists and tracks
