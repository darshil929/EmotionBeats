"""
Socket.io authentication middleware.

This module provides functions for authenticating Socket.io connections
using JWT tokens and managing authentication state.
"""

import logging
from typing import Dict, Any, Optional
import functools

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from app.core.security import verify_token
from app.db.models import User
from app.db.session import engine
from app.services.socketio.state import update_session_data, set_user_presence

# Configure logger
logger = logging.getLogger(__name__)

# Create async session maker
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def authenticate_socket(sid: str, auth_data: Dict[str, Any]) -> Optional[User]:
    """
    Authenticate a Socket.io connection using JWT token.

    Args:
        sid: Socket.io session ID
        auth_data: Authentication data containing token

    Returns:
        User object if authentication is successful, None otherwise
    """
    token = auth_data.get("token")

    if not token:
        logger.warning(f"Authentication failed for {sid}: No token provided")
        return None

    try:
        # Verify JWT token
        payload = verify_token(token)
        user_id = payload.get("sub")

        if not user_id:
            logger.warning(f"Authentication failed for {sid}: Invalid token payload")
            return None

        # Get user from database
        async with async_session() as session:
            result = await session.execute(select(User).filter(User.id == user_id))
            user = result.scalars().first()

            if not user:
                logger.warning(f"Authentication failed for {sid}: User not found")
                return None

            if not user.is_active:
                logger.warning(f"Authentication failed for {sid}: User is inactive")
                return None

        # Update session with user data
        await update_session_data(
            sid,
            {
                "user_id": str(user.id),
                "username": user.username,
                "role": user.role,
                "is_authenticated": True,
            },
        )

        # Set user presence
        await set_user_presence(str(user.id), sid, "online")

        logger.info(f"Socket authenticated for user {user.username} ({user.id})")
        return user

    except Exception as e:
        logger.error(f"Authentication error for {sid}: {e}")
        return None


def authenticated_only(f):
    """
    Decorator for Socket.io event handlers that require authentication.

    Args:
        f: The Socket.io event handler function to protect

    Returns:
        A wrapped function that checks authentication before executing
    """

    @functools.wraps(f)
    async def wrapped(sid, *args, **kwargs):
        from app.services.socketio.server import socketio_server

        try:
            # Get session data
            session = await socketio_server.get_session(sid)

            # Check if authenticated
            if not session or not session.get("is_authenticated", False):
                await socketio_server.emit(
                    "auth_error",
                    {
                        "status": "error",
                        "message": "Authentication required",
                        "code": 401,
                    },
                    room=sid,
                )
                return

            # Call the original function
            return await f(sid, *args, **kwargs)

        except Exception as e:
            logger.error(f"Error in authenticated_only decorator: {e}")
            await socketio_server.emit(
                "error",
                {"status": "error", "message": "Internal server error", "code": 500},
                room=sid,
            )

    return wrapped


def role_required(role: str):
    """
    Decorator factory for Socket.io event handlers that require a specific role.

    Args:
        role: The required role (user, premium, admin)

    Returns:
        A decorator that checks if the user has the required role
    """

    def decorator(f):
        @functools.wraps(f)
        async def wrapped(sid, *args, **kwargs):
            from app.services.socketio.server import socketio_server

            try:
                # Get session data
                session = await socketio_server.get_session(sid)

                # Check if authenticated
                if not session or not session.get("is_authenticated", False):
                    await socketio_server.emit(
                        "auth_error",
                        {
                            "status": "error",
                            "message": "Authentication required",
                            "code": 401,
                        },
                        room=sid,
                    )
                    return

                # Check role
                user_role = session.get("role", "user")
                if (
                    user_role != role and user_role != "admin"
                ):  # Admin can access everything
                    await socketio_server.emit(
                        "auth_error",
                        {
                            "status": "error",
                            "message": f"Role '{role}' required",
                            "code": 403,
                        },
                        room=sid,
                    )
                    return

                # Call the original function
                return await f(sid, *args, **kwargs)

            except Exception as e:
                logger.error(f"Error in role_required decorator: {e}")
                await socketio_server.emit(
                    "error",
                    {
                        "status": "error",
                        "message": "Internal server error",
                        "code": 500,
                    },
                    room=sid,
                )

        return wrapped

    return decorator


async def validate_connection(sid: str, environ: Dict[str, Any]) -> bool:
    """
    Validate a new Socket.io connection before accepting.

    This can be used to reject connections based on IP, rate limiting, etc.

    Args:
        sid: Socket.io session ID
        environ: WSGI environment dictionary

    Returns:
        True if the connection should be accepted, False otherwise
    """
    # Example: Check for basic rate limiting
    # In a real implementation, this should use Redis for distributed rate limiting

    # Get client IP
    client_ip = environ.get("REMOTE_ADDR", "unknown")
    logger.info(f"New connection from {client_ip} with sid {sid}")

    # Accept all connections for now
    # In a production environment, add rate limiting, blacklisting, etc.
    return True
