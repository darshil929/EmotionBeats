"""Utility functions for datetime operations."""

from datetime import datetime, UTC, timezone


def utc_now():
    """Return the current UTC datetime in a timezone-aware format.

    This is the preferred replacement for the deprecated datetime.utcnow().
    """
    return datetime.now(UTC)


def make_aware(dt):
    """Convert a naive datetime to UTC-aware datetime."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def make_naive(dt):
    """Convert an aware datetime to naive datetime."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt
