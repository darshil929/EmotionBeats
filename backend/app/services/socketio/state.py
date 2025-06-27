"""
Session state management for Socket.io with Redis.

This module provides functions for storing and retrieving session state,
tracking user presence, and managing Socket.io connection information.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Set

from app.core.redis import get_redis_cache
from app.utils.datetime_helper import utc_now

# Configure logger
logger = logging.getLogger(__name__)

# Redis key prefixes
SESSION_PREFIX = "socketio:session:"
PRESENCE_PREFIX = "socketio:presence:"
CONNECTION_PREFIX = "socketio:connection:"

# Expiration times in seconds
SESSION_EXPIRY = 86400  # 24 hours
PRESENCE_EXPIRY = 300  # 5 minutes


async def store_session_data(sid: str, data: Dict[str, Any]) -> bool:
    """
    Store session data in Redis.

    Args:
        sid: Socket.io session ID
        data: Session data to store

    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis_cache()
        session_key = f"{SESSION_PREFIX}{sid}"

        # Store session data with expiry
        await redis.set(session_key, json.dumps(data), ex=SESSION_EXPIRY)

        return True
    except Exception as e:
        logger.error(f"Error storing session data for {sid}: {e}")
        return False


async def get_session_data(sid: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve session data from Redis.

    Args:
        sid: Socket.io session ID

    Returns:
        Session data dictionary, or None if not found
    """
    try:
        redis = await get_redis_cache()
        session_key = f"{SESSION_PREFIX}{sid}"

        # Get session data
        session_data = await redis.get(session_key)

        if not session_data:
            return None

        return json.loads(session_data)
    except Exception as e:
        logger.error(f"Error retrieving session data for {sid}: {e}")
        return None


async def update_session_data(sid: str, updates: Dict[str, Any]) -> bool:
    """
    Update specific fields in session data.

    Args:
        sid: Socket.io session ID
        updates: Dictionary of fields to update

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get current session data
        current_data = await get_session_data(sid)

        if current_data is None:
            current_data = {}

        # Update fields
        current_data.update(updates)

        # Store updated session
        return await store_session_data(sid, current_data)
    except Exception as e:
        logger.error(f"Error updating session data for {sid}: {e}")
        return False


async def delete_session_data(sid: str) -> bool:
    """
    Delete session data from Redis.

    Args:
        sid: Socket.io session ID

    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis_cache()
        session_key = f"{SESSION_PREFIX}{sid}"

        # Delete session data
        await redis.delete(session_key)

        return True
    except Exception as e:
        logger.error(f"Error deleting session data for {sid}: {e}")
        return False


async def set_user_presence(user_id: str, sid: str, status: str = "online") -> bool:
    """
    Set a user's presence status and associate it with a session ID.

    Args:
        user_id: User ID
        sid: Socket.io session ID
        status: Presence status (online, away, busy, etc.)

    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis_cache()
        presence_key = f"{PRESENCE_PREFIX}{user_id}"
        connection_key = f"{CONNECTION_PREFIX}{user_id}"

        # Store presence data with expiry
        presence_data = {
            "user_id": user_id,
            "status": status,
            "last_active": utc_now().isoformat(),
        }

        await redis.set(presence_key, json.dumps(presence_data), ex=PRESENCE_EXPIRY)

        # Add session ID to user's connection set
        await redis.sadd(connection_key, sid)
        await redis.expire(connection_key, SESSION_EXPIRY)

        return True
    except Exception as e:
        logger.error(f"Error setting presence for user {user_id}: {e}")
        return False


async def get_user_presence(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a user's presence status.

    Args:
        user_id: User ID

    Returns:
        Presence data dictionary, or None if not found
    """
    try:
        redis = await get_redis_cache()
        presence_key = f"{PRESENCE_PREFIX}{user_id}"

        # Get presence data
        presence_data = await redis.get(presence_key)

        if not presence_data:
            return None

        return json.loads(presence_data)
    except Exception as e:
        logger.error(f"Error getting presence for user {user_id}: {e}")
        return None


async def get_user_connections(user_id: str) -> Set[str]:
    """
    Get all active session IDs for a user.

    Args:
        user_id: User ID

    Returns:
        Set of session IDs
    """
    try:
        redis = await get_redis_cache()
        connection_key = f"{CONNECTION_PREFIX}{user_id}"

        # Get all session IDs for the user
        return set(await redis.smembers(connection_key))
    except Exception as e:
        logger.error(f"Error getting connections for user {user_id}: {e}")
        return set()


async def remove_user_connection(user_id: str, sid: str) -> bool:
    """
    Remove a session ID from a user's connection set.

    Args:
        user_id: User ID
        sid: Socket.io session ID to remove

    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis_cache()
        connection_key = f"{CONNECTION_PREFIX}{user_id}"

        # Remove session ID from user's connection set
        await redis.srem(connection_key, sid)

        # Check if user has any remaining connections
        remaining = await redis.scard(connection_key)

        if remaining == 0:
            # User has no more active connections, mark as offline
            presence_key = f"{PRESENCE_PREFIX}{user_id}"

            presence_data = await redis.get(presence_key)
            if presence_data:
                data = json.loads(presence_data)
                data["status"] = "offline"
                data["last_active"] = utc_now().isoformat()

                await redis.set(presence_key, json.dumps(data), ex=PRESENCE_EXPIRY)

        return True
    except Exception as e:
        logger.error(f"Error removing connection for user {user_id}: {e}")
        return False


async def get_online_users() -> List[str]:
    """
    Get a list of all online user IDs.

    Returns:
        List of user IDs with online status
    """
    try:
        redis = await get_redis_cache()

        # Get all presence keys
        presence_keys = await redis.keys(f"{PRESENCE_PREFIX}*")

        online_users = []
        for key in presence_keys:
            # Extract user ID from key
            user_id = key.replace(PRESENCE_PREFIX, "")

            # Get presence data
            presence_data = await redis.get(key)
            if presence_data:
                data = json.loads(presence_data)
                if data.get("status") == "online":
                    online_users.append(user_id)

        return online_users
    except Exception as e:
        logger.error(f"Error getting online users: {e}")
        return []


async def touch_session(sid: str) -> bool:
    """
    Refresh the expiration time for a session.

    Args:
        sid: Socket.io session ID

    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis_cache()
        session_key = f"{SESSION_PREFIX}{sid}"

        # Refresh expiration time
        await redis.expire(session_key, SESSION_EXPIRY)

        return True
    except Exception as e:
        logger.error(f"Error touching session for {sid}: {e}")
        return False


async def touch_presence(user_id: str) -> bool:
    """
    Refresh the expiration time for a user's presence data.

    Args:
        user_id: User ID

    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis_cache()
        presence_key = f"{PRESENCE_PREFIX}{user_id}"

        # Update last active time
        presence_data = await redis.get(presence_key)
        if presence_data:
            data = json.loads(presence_data)
            data["last_active"] = utc_now().isoformat()

            await redis.set(presence_key, json.dumps(data), ex=PRESENCE_EXPIRY)

        return True
    except Exception as e:
        logger.error(f"Error touching presence for user {user_id}: {e}")
        return False
