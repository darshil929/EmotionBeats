"""
CSRF protection middleware for FastAPI applications.
"""

import os
import secrets
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Middleware for CSRF protection.

    Generates CSRF tokens, sets them in cookies, and verifies tokens
    in request headers for unsafe HTTP methods.
    """

    def __init__(
        self,
        app: ASGIApp,
        secret_key: str,
        token_length: int = 32,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        safe_methods: tuple = ("GET", "HEAD", "OPTIONS"),
    ):
        """Initialize CSRF middleware with configuration."""
        super().__init__(app)
        self.secret_key = secret_key
        self.token_length = token_length
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.safe_methods = safe_methods

    def generate_csrf_token(self) -> str:
        """Generate a secure random token for CSRF protection."""
        return secrets.token_hex(self.token_length)

    async def dispatch(self, request: Request, call_next):
        """
        Process a request through the middleware.

        For safe methods, ensure CSRF token exists in cookies.
        For unsafe methods, validate CSRF token from headers against cookie.
        """
        # Bypass CSRF checks in test environment
        if os.getenv("TESTING") == "True":
            response = await call_next(request)

            # Ensure CSRF cookie exists for test consistency
            if self.cookie_name not in request.cookies:
                csrf_token = self.generate_csrf_token()
                response.set_cookie(
                    key=self.cookie_name,
                    value=csrf_token,
                    httponly=False,  # Must be accessible to JavaScript
                    secure=True,
                    samesite="lax",
                )

            return response

        # Skip CSRF check for safe methods
        if request.method in self.safe_methods:
            response = await call_next(request)

            # Ensure CSRF cookie exists
            if self.cookie_name not in request.cookies:
                csrf_token = self.generate_csrf_token()
                response.set_cookie(
                    key=self.cookie_name,
                    value=csrf_token,
                    httponly=False,  # Must be accessible to JavaScript
                    secure=True,
                    samesite="lax",
                )

            return response

        # For unsafe methods, validate CSRF token
        csrf_cookie = request.cookies.get(self.cookie_name)
        csrf_header = request.headers.get(self.header_name)

        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed",
            )

        return await call_next(request)


def setup_csrf_middleware(app, secret_key):
    """Setup helper function to add CSRF middleware to the FastAPI app."""
    app.add_middleware(CSRFMiddleware, secret_key=secret_key)
