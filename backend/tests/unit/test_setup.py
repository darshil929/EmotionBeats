"""
Basic tests to validate that the testing infrastructure is correctly set up.

These tests ensure the test database is accessible and the test client
can make requests to the application.
"""

from sqlalchemy import text

def test_database_connection(db_session):
    """
    Validates that the test database connection is working properly.
    
    This test ensures that the database session fixture is correctly configured
    and can execute basic SQL queries.
    """
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1

def test_app_health_endpoint(client):
    """
    Validates that the application health endpoint is accessible.
    
    This test ensures that the FastAPI application is correctly configured
    and the test client can make requests to it.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
