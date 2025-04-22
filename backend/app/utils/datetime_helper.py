"""Utility functions for datetime operations."""

from datetime import datetime, UTC


def utc_now():
    """Return the current UTC datetime in a timezone-aware format.

    This is the preferred replacement for the deprecated datetime.utcnow().
    """
    return datetime.now(UTC)
