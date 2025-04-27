"""
Test configuration and fixtures for pytest.
"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.base import Base
from app.main import app
from app.dependencies import db_dependency

# Set the testing environment flag
os.environ["TESTING"] = "True"

# Use main database for testing - simpler approach
DATABASE_URL = "postgresql://postgres:postgres@db:5432/postgres"


@pytest.fixture(scope="session")
def test_engine():
    """Create an engine connected to the test database."""
    engine = create_engine(DATABASE_URL)

    # Drop all tables and recreate them for testing
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup - drop all tables
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a new database session for a test."""
    connection = test_engine.connect()
    transaction = connection.begin()

    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """Create a test client with a session override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[db_dependency] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    from app.db.models import User

    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# Reset test environment at the end of session
def pytest_sessionfinish(session, exitstatus):
    """Clean up after all tests have run."""
    os.environ.pop("TESTING", None)


# Alias for compatibility
@pytest.fixture
def db(db_session):
    """Alias for db_session."""
    return db_session
