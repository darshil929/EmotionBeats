"""
Dependency injection functions for the API.
"""

from fastapi import Depends, HTTPException, Cookie, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, Tuple

from app.db.session import get_db
from app.db.models import User
from app.core.security import verify_token


# Database dependency
db_dependency = get_db

# OAuth2 scheme for token extraction from Authorization header
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/auth/token",
    auto_error=False,  # Don't auto-raise errors to allow cookie fallback
)


async def get_token(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    access_token_cookie: Optional[str] = Cookie(None),
) -> str:
    """
    Extract token from either Authorization header or cookie.

    Prioritizes the Authorization header token if available.
    """
    if token:
        return token
    if access_token_cookie:
        return access_token_cookie

    # No token found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: str = Depends(get_token), db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from a JWT token.

    Verifies the token and fetches the corresponding user from the database.
    """
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("User ID not found in token")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_premium_user(user: User = Depends(get_current_user)) -> User:
    """
    Get the current user if they have premium privileges.

    Verifies that the user has either premium or admin role.
    """
    if user.role not in ["premium", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required",
        )
    return user


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """
    Get the current user if they have admin privileges.

    Verifies that the user has admin role.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


async def validate_socket_token(
    token: str, db: Session
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Validate a JWT token for Socket.io connections.

    Args:
        token: JWT token to validate
        db: Database session

    Returns:
        Tuple of (is_valid, user_data)
    """
    try:
        # Verify the token
        payload = verify_token(token)
        user_id = payload.get("sub")

        if not user_id:
            return False, None

        # Get the user from the database
        user = db.query(User).filter(User.id == user_id).first()

        if not user or not user.is_active:
            return False, None

        # Return user data for Socket.io session
        return True, {"user_id": str(user.id), "role": user.role, "authenticated": True}

    except Exception:
        return False, None


async def socketio_auth(sid: str, environ: Dict[str, Any], db: Session) -> bool:
    """
    Authenticate a Socket.io connection.

    This function is used by the Socket.io server to authenticate
    connections before allowing them.

    Args:
        sid: Socket.io session ID
        environ: WSGI environment dict, containing headers
        db: Database session

    Returns:
        True if authenticated, False otherwise
    """
    try:
        # Extract token from query parameters or headers
        query = environ.get("QUERY_STRING", "")
        headers = environ.get("HTTP_AUTHORIZATION", "")

        token = None

        # Try to get token from Authorization header
        if headers.startswith("Bearer "):
            token = headers[7:]  # Remove "Bearer " prefix

        # If not in headers, try to get from query string
        if not token:
            import urllib.parse

            params = dict(urllib.parse.parse_qsl(query))
            token = params.get("token")

        # If token found, validate it
        if token:
            is_valid, user_data = await validate_socket_token(token, db)

            if is_valid and user_data:
                # Import Socket.io server here to avoid circular imports
                from app.services.socketio.server import SocketIOServer

                sio = SocketIOServer().get_server()

                # Store user data in Socket.io session
                await sio.save_session(sid, user_data)
                return True

        return False

    except Exception:
        return False
