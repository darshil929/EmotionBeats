"""
Test configuration and fixtures for pytest.

This module contains shared fixtures that can be used by all tests.
"""

import asyncio
import os
import pytest
from typing import AsyncGenerator, Generator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.dependencies import db_dependency

# Create test database connection - this runs for every test session
@pytest.fixture(scope="session")
def db_engine():
    """
    Creates a test database engine for the test session.
    
    This fixture provides a database engine for test operations
    that is separate from the development database.
    """
    return engine

@pytest.fixture(scope="function")
def db(db_engine) -> Generator[Session, None, None]:
    """
    Creates a fresh database session for a test.
    
    The session is rolled back after the test completes to ensure
    test isolation.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    
    # Create a session bound to the connection
    session = SessionLocal(bind=connection)
    
    try:
        # Check database connection
        session.execute(text("SELECT 1"))
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

@pytest.fixture
def client():
    """
    Creates a test client for the FastAPI application.
    
    This client can be used to make requests to the application
    during tests.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    
    with TestClient(app) as client:
        yield client
