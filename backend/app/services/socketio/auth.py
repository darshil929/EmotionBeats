"""
Socket.io authentication integration and access control.

Provides JWT token validation, user authentication, and permission checking
for WebSocket connections using the existing FastAPI authentication system.
"""

import logging
from typing import Optional, Dict, Any, Tuple

from app.core.security import verify_token
from app.db.session import SessionLocal
from app.db.models import User, ChatSession

logger = logging.getLogger(__name__)


async def validate_socketio_token(
    auth_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Validates JWT token provided during Socket.io connection.

    Extracts and verifies the authentication token from the Socket.io
    connection data and returns the decoded payload if valid.
    """
    if not auth_data or not isinstance(auth_data, dict):
        logger.warning("No authentication data provided for Socket.io connection")
        return None

    token = auth_data.get("token")
    if not token:
        logger.warning("No token provided in Socket.io authentication data")
        return None

    try:
        # Verify token using existing security module
        payload = verify_token(token, token_type="access")

        # Extract user information from payload
        user_id = payload.get("sub")
        user_role = payload.get("role", "user")

        if not user_id:
            logger.warning("Token payload missing user ID")
            return None

        return {"user_id": user_id, "role": user_role, "token_payload": payload}

    except ValueError as e:
        logger.warning(f"Invalid token provided for Socket.io connection: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {e}")
        return None


async def authenticate_user_connection(
    sid: str, auth_data: Dict[str, Any]
) -> Tuple[bool, Optional[User]]:
    """
    Authenticates user during Socket.io connection establishment.

    Validates the user's authentication credentials and retrieves the user
    record from the database for session management.
    """
    # Validate token and extract user information
    token_data = await validate_socketio_token(auth_data)
    if not token_data:
        logger.info(f"Authentication failed for Socket.io connection {sid}")
        return False, None

    user_id = token_data["user_id"]

    # Get database session
    db = SessionLocal()
    try:
        # Retrieve user from database
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            logger.warning(f"User {user_id} not found during Socket.io authentication")
            return False, None

        if not user.is_active:
            logger.warning(f"Inactive user {user_id} attempted Socket.io connection")
            return False, None

        logger.info(
            f"User {user.username} authenticated successfully for Socket.io connection {sid}"
        )
        return True, user

    except Exception as e:
        logger.error(f"Database error during user authentication: {e}")
        return False, None
    finally:
        db.close()


async def check_room_access_permission(user_id: str, session_id: str) -> bool:
    """
    Verifies user permission to access a specific chat session room.

    Checks if the user is authorized to join the specified chat session
    based on session ownership and access rules.
    """
    if not user_id or not session_id:
        logger.warning("Missing user_id or session_id for room access check")
        return False

    # Get database session
    db = SessionLocal()
    try:
        # Check if chat session exists and user has access
        chat_session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )

        if not chat_session:
            logger.warning(f"User {user_id} denied access to session {session_id}")
            return False

        if not chat_session.is_active:
            logger.warning(
                f"User {user_id} attempted to access inactive session {session_id}"
            )
            return False

        logger.debug(f"User {user_id} granted access to session {session_id}")
        return True

    except Exception as e:
        logger.error(f"Database error during room access check: {e}")
        return False
    finally:
        db.close()


async def get_user_from_session(
    sid: str, user_sessions: Dict[str, str]
) -> Optional[User]:
    """
    Retrieves user record from database using stored session mapping.

    Looks up the user associated with a Socket.io session ID for
    operations that require user context.
    """
    user_id = user_sessions.get(sid)
    if not user_id:
        logger.warning(f"No user mapping found for Socket.io session {sid}")
        return None

    # Get database session
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            logger.warning(f"User {user_id} not found for session {sid}")
            return None

        return user

    except Exception as e:
        logger.error(f"Database error retrieving user for session {sid}: {e}")
        return None
    finally:
        db.close()


async def handle_authentication_failure(sid: str, error_message: str) -> Dict[str, Any]:
    """
    Handles authentication failure and prepares error response.

    Creates standardized error response for authentication failures
    and logs the incident for security monitoring.
    """
    logger.warning(f"Authentication failure for session {sid}: {error_message}")

    return {
        "success": False,
        "error": "authentication_failed",
        "message": "Authentication required for Socket.io connection",
    }


def extract_token_from_handshake(environ: Dict[str, Any]) -> Optional[str]:
    """
    Extracts authentication token from Socket.io handshake data.

    Searches for JWT token in various locations within the handshake
    data including query parameters and headers.
    """
    try:
        # Check query parameters for token
        query_string = environ.get("QUERY_STRING", "")
        if "token=" in query_string:
            for param in query_string.split("&"):
                if param.startswith("token="):
                    return param.split("=", 1)[1]

        # Check headers for Authorization header
        headers = environ.get("HTTP_AUTHORIZATION")
        if headers and headers.startswith("Bearer "):
            return headers[7:]  # Remove "Bearer " prefix

        logger.debug("No token found in Socket.io handshake data")
        return None

    except Exception as e:
        logger.error(f"Error extracting token from handshake: {e}")
        return None
