"""Unit tests for main FastAPI application."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.dependencies import db_dependency


@pytest.fixture
def client():
    """Create a TestClient instance for testing the API."""
    return TestClient(app)


class TestAppConfiguration:
    """Tests for application initialization and configuration."""

    def test_app_title(self):
        """Test app is created with the correct title."""
        assert app.title == "EmotionBeats API"

    def test_cors_middleware(self, client):
        """Test CORS middleware by checking response headers."""
        # Make a request with an Origin header
        response = client.get("/", headers={"Origin": "http://localhost:3000"})

        # Check for CORS headers in the response
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )

        # Ensure credentials are allowed (as specified in our middleware)
        assert "access-control-allow-credentials" in response.headers
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_routers_included(self):
        """Test that required routers are included."""
        # Get all route paths
        route_paths = [route.path for route in app.routes]

        # Check for API endpoints
        assert "/api/auth/spotify/login" in route_paths
        # Check for a few key routes to ensure both routers are included
        assert any(path.startswith("/api/spotify/") for path in route_paths)


class TestEndpoints:
    """Tests for API endpoints."""

    def test_root_endpoint(self, client):
        """Test the root endpoint returns the welcome message."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Welcome to EmotionBeats API"}

    def test_api_root_endpoint(self, client):
        """Test the API root endpoints."""
        # Test /api
        response_1 = client.get("/api")
        assert response_1.status_code == 200
        assert "message" in response_1.json()
        assert "EmotionBeats API" in response_1.json()["message"]

        # Test /api/
        response_2 = client.get("/api/")
        assert response_2.status_code == 200
        assert response_2.json() == response_1.json()

    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_db_test_success(self, client):
        """Test database test endpoint when connection succeeds."""
        # Save original dependency
        original_dependency = app.dependency_overrides.get(db_dependency)

        try:
            # Create a mock that succeeds
            mock_db = MagicMock()

            # Override the dependency
            app.dependency_overrides[db_dependency] = lambda: mock_db

            # Test the endpoint
            response = client.get("/db-test")
            assert response.status_code == 200
            assert response.json() == {"status": "Database connection successful!"}
        finally:
            # Restore original dependency
            if original_dependency:
                app.dependency_overrides[db_dependency] = original_dependency
            else:
                if db_dependency in app.dependency_overrides:
                    del app.dependency_overrides[db_dependency]

    def test_db_test_error(self, client):
        """Test database test endpoint when connection fails."""
        # Save original dependency
        original_dependency = app.dependency_overrides.get(db_dependency)

        try:
            # Create a mock that fails
            mock_db = MagicMock()
            mock_db.execute.side_effect = SQLAlchemyError("Database error")

            # Override the dependency
            app.dependency_overrides[db_dependency] = lambda: mock_db

            # Test the endpoint
            response = client.get("/db-test")
            assert response.status_code == 200  # Note: The endpoint always returns 200
            assert response.json()["status"] == "Database connection failed"
            assert "error" in response.json()
        finally:
            # Restore original dependency
            if original_dependency:
                app.dependency_overrides[db_dependency] = original_dependency
            else:
                if db_dependency in app.dependency_overrides:
                    del app.dependency_overrides[db_dependency]
