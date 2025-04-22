# EmotionBeats: AI-Powered Music Recommendation System

## Project Overview

EmotionBeats is a conversational AI system that generates personalized Spotify playlists based on users' emotional states and music preferences. The application analyzes conversational input to detect emotions and extract music preferences, then leverages the Spotify API to create tailored playlists that match the user's current mood.

The system features a chat interface where users engage in natural conversations about their emotional state and music preferences, receiving real-time recommendations that can be refined through continued interaction.

## System Architecture

EmotionBeats implements a modern microservices architecture:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │◄───►│   Backend   │◄───►│ AI Services │
│  (Next.js)  │     │  (FastAPI)  │     │             │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  Database   │◄───►│ Spotify API │
                    │ (PostgreSQL)│     │             │
                    └─────────────┘     └─────────────┘
```

### Data Flow

1. User messages are sent through the chat interface
2. Backend processes messages for emotion detection and preference extraction
3. Results are combined in the recommendation engine
4. Spotify API is queried for matching tracks
5. Playlists are dynamically created or updated
6. Real-time updates are delivered to the frontend

## Technology Stack

### Frontend
- **Framework**: Next.js with React
- **Styling**: Tailwind CSS with Shadcn components
- **State Management**: Redux Toolkit
- **Music Playback**: Spotify Web Playback SDK

### Backend
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: OAuth2 with JWT
- **API Integration**: Spotify Web API

### AI Components
- **Emotion Detection**: j-hartmann/emotion-english-distilroberta-base
- **Preference Extraction**: Llama 3 from Groq
- **Recommendation Engine**: Custom algorithm mapping emotions to audio features

## Repository Structure

```
emotionbeats/
├── backend/           # FastAPI backend implementation
│   ├── app/           # Application code
│   ├── tests/         # Backend tests
│   └── README.md      # Backend documentation
├── frontend/          # Next.js frontend implementation
│   ├── src/           # Source code
│   │   ├── components/# UI components
│   │   └── pages/     # Next.js pages
│   └── README.md      # Frontend documentation
├── docker/            # Docker configuration files
├── docs/              # Project documentation
└── README.md          
```

## Implementation Status

### Current Progress
The backend implementation has been completed with the following functionality:
- Authentication system with Spotify OAuth integration
- Spotify API client for profile, search, and playlist management
- Database models for users, playlists, and chat sessions
- Comprehensive test suite for API endpoints and database operations

### Next Steps
Upcoming development priorities include:
- Integration of emotion detection model (j-hartmann/emotion-english-distilroberta-base)
- Implementation of preference extraction using Llama 3
- Development of the recommendation engine combining emotional states with music preferences
- Frontend implementation with real-time chat interface

For detailed information about the backend implementation, testing procedures, and planned enhancements, please refer to the [Backend README](./backend/README.md).
