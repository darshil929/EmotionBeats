"""Unit tests for database session management."""

from unittest.mock import patch, MagicMock

from app.db.session import get_db


class TestDatabaseURL:
    """Tests for database URL configuration."""

    def test_database_url_default(self):
        """Test default DATABASE_URL behavior."""
        # The actual default value in the Docker environment is postgres
        default_db = "postgresql://postgres:postgres@db:5432/postgres"

        # Test os.getenv is called with the right parameters
        with patch("os.getenv") as mock_getenv:
            mock_getenv.return_value = default_db

            import importlib
            import app.db.session

            importlib.reload(app.db.session)

            # Verify getenv was called with the correct arguments
            mock_getenv.assert_called_with(
                "DATABASE_URL", "postgresql://postgres:postgres@db:5432/emotionbeats"
            )

            # Verify the DATABASE_URL is set to our mock return value
            assert app.db.session.DATABASE_URL == default_db

    def test_database_url_from_env(self):
        """Test DATABASE_URL from environment variable."""
        custom_url = "postgresql://user:pass@custom-host:5432/testdb"
        with patch("os.getenv", return_value=custom_url):
            import importlib
            import app.db.session

            importlib.reload(app.db.session)
            assert app.db.session.DATABASE_URL == custom_url


# The rest of the file remains unchanged
class TestEngineCreation:
    """Tests for SQLAlchemy engine creation."""

    def test_engine_creation(self):
        """Test engine is created with correct DATABASE_URL."""
        with patch("sqlalchemy.create_engine") as mock_create_engine:
            import importlib
            import app.db.session

            importlib.reload(app.db.session)

            # Verify create_engine was called with the DATABASE_URL
            mock_create_engine.assert_called_once()
            # The first positional argument should be the DATABASE_URL
            assert mock_create_engine.call_args[0][0] == app.db.session.DATABASE_URL


class TestSessionFactory:
    """Tests for SQLAlchemy session factory configuration."""

    def test_session_factory_configuration(self):
        """Test session factory is configured with correct parameters."""
        mock_engine = MagicMock()

        with (
            patch("sqlalchemy.create_engine", return_value=mock_engine),
            patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker,
        ):
            import importlib
            import app.db.session

            importlib.reload(app.db.session)

            # Verify sessionmaker was called with correct parameters
            mock_sessionmaker.assert_called_once()
            args = mock_sessionmaker.call_args.kwargs
            assert args["autocommit"] is False
            assert args["autoflush"] is False
            assert args["bind"] is mock_engine


class TestGetDBFunction:
    """Tests for the get_db dependency injection function."""

    def test_get_db_yields_session(self):
        """Test get_db yields a database session."""
        mock_session = MagicMock()

        with patch("app.db.session.SessionLocal", return_value=mock_session):
            db_generator = get_db()
            session = next(db_generator)

            assert session is mock_session

    def test_session_cleanup_after_yield(self):
        """Test session is closed after yielding."""
        mock_session = MagicMock()

        with patch("app.db.session.SessionLocal", return_value=mock_session):
            db_generator = get_db()
            next(db_generator)

            # Simulate end of request context
            try:
                next(db_generator)
            except StopIteration:
                pass

            mock_session.close.assert_called_once()

    def test_session_cleanup_after_exception(self):
        """Test session is closed even when an exception occurs."""
        mock_session = MagicMock()

        with patch("app.db.session.SessionLocal", return_value=mock_session):
            db_generator = get_db()
            next(db_generator)

            # Simulate an exception during request handling
            try:
                db_generator.throw(RuntimeError("Test exception"))
            except RuntimeError:
                # Exception should propagate
                pass

            # Session should still be closed
            mock_session.close.assert_called_once()
