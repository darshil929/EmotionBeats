"""
Authentication middleware for Socket.io connections.
"""

import json
import logging
import urllib.parse
from typing import Callable, Dict, Any, Optional, Awaitable

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.dependencies import validate_socket_token

logger = logging.getLogger(__name__)


class SocketAuthMiddleware:
    """
    Middleware for authenticating Socket.io connections.

    Validates tokens from query parameters, headers, or cookies.
    """

    def __init__(
        self,
        socketio_app: Any,
    ):
        """
        Initialize the authentication middleware.

        Args:
            socketio_app: The Socket.io ASGI application
        """
        self.socketio_app = socketio_app

    async def __call__(
        self, scope: Dict[str, Any], receive: Callable, send: Callable
    ) -> Awaitable:
        """
        Process a connection request through the authentication middleware.

        Args:
            scope: ASGI connection scope
            receive: ASGI receive function
            send: ASGI send function

        Returns:
            ASGI application awaitable
        """
        # Check if this is a websocket connection
        if scope["type"] != "websocket":
            return await self.socketio_app(scope, receive, send)

        # Authenticate the connection
        authenticated = await self._authenticate_connection(scope)

        if not authenticated:
            # Reject the connection
            close_message = {
                "type": "websocket.close",
                "code": 1008,  # Policy violation
            }
            await send(close_message)
            return

        # Allow the connection to proceed
        return await self.socketio_app(scope, receive, send)

    async def _authenticate_connection(self, scope: Dict[str, Any]) -> bool:
        """
        Authenticate a connection using token from query parameters, headers, or cookies.

        Args:
            scope: ASGI connection scope

        Returns:
            True if authenticated, False otherwise
        """
        token = self._extract_token(scope)

        if not token:
            logger.warning("No authentication token found in Socket.io connection")
            return False

        # Create a database session
        db = SessionLocal()
        try:
            # Validate the token
            is_valid, _ = await validate_socket_token(token, db)

            if not is_valid:
                logger.warning("Invalid authentication token for Socket.io connection")
                return False

            return True

        except Exception as e:
            logger.error(f"Error authenticating Socket.io connection: {str(e)}")
            return False

        finally:
            db.close()

    def _extract_token(self, scope: Dict[str, Any]) -> Optional[str]:
        """
        Extract authentication token from the connection scope.

        Checks query parameters, headers, and cookies in that order.

        Args:
            scope: ASGI connection scope

        Returns:
            Authentication token or None if not found
        """
        # Try to get from query string
        query_string = scope.get("query_string", b"").decode("utf-8")
        if query_string:
            params = dict(urllib.parse.parse_qsl(query_string))
            token = params.get("token")
            if token:
                return token

        # Try to get from headers
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix

        # Try to get from cookies
        cookies_header = headers.get(b"cookie", b"").decode("utf-8")
        if cookies_header:
            cookies = dict(
                cookie.split("=", 1) for cookie in cookies_header.split("; ")
            )
            return cookies.get("access_token")

        return None


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
        # Try to get token from query parameters first
        query_string = environ.get("QUERY_STRING", "")
        params = dict(urllib.parse.parse_qsl(query_string))
        token = params.get("token")

        # If not found, try in auth header
        if not token and "HTTP_AUTHORIZATION" in environ:
            auth_header = environ["HTTP_AUTHORIZATION"]
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        # If not found, check auth data
        if not token and "HTTP_SOCKETIO_AUTH" in environ:
            try:
                auth_data = json.loads(environ["HTTP_SOCKETIO_AUTH"])
                token = auth_data.get("token")
            except json.JSONDecodeError:
                pass

        # Also check the socket.io auth parameter
        if not token and "HTTP_AUTH" in environ:
            try:
                auth_data = json.loads(environ["HTTP_AUTH"])
                token = auth_data.get("token")
            except json.JSONDecodeError:
                pass

        # If still not found, check in cookies
        if not token and "HTTP_COOKIE" in environ:
            cookies = {}
            for cookie in environ["HTTP_COOKIE"].split("; "):
                if "=" in cookie:
                    key, value = cookie.split("=", 1)
                    cookies[key] = value
            token = cookies.get("access_token")

        # Validate the token
        if token:
            is_valid, user_data = await validate_socket_token(token, db)

            if is_valid and user_data:
                # Import Socket.io server here to avoid circular imports
                from app.services.socketio.server import SocketIOServer

                sio = SocketIOServer().get_server()

                # Store user data in Socket.io session
                await sio.save_session(sid, user_data)
                logger.info(
                    f"Authenticated Socket.io connection for user {user_data['user_id']}"
                )
                return True

        logger.warning(
            "Failed to authenticate Socket.io connection: No valid token found"
        )
        return False

    except Exception as e:
        logger.error(f"Error in Socket.io authentication: {str(e)}")
        return False


def apply_socketio_auth(socketio_app: Any) -> Any:
    """
    Apply authentication middleware to a Socket.io application.

    Args:
        socketio_app: The Socket.io ASGI application

    Returns:
        Middleware-wrapped Socket.io application
    """
    return SocketAuthMiddleware(socketio_app)
