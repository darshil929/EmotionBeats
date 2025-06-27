"""
Room-based session management for Socket.io communication.

This module provides functions for managing room participation,
tracking active users in rooms, and retrieving room information.
"""

import json
import logging
import uuid
from typing import Dict, Any, List, Set, Optional

from app.core.redis import get_redis_cache
from app.services.socketio.server import socketio_server
from app.utils.datetime_helper import utc_now

# Configure logger
logger = logging.getLogger(__name__)

# Redis key prefixes
ROOM_PREFIX = "socketio:room:"
ROOM_PARTICIPANTS_SUFFIX = ":participants"
ROOM_METADATA_SUFFIX = ":metadata"
USER_ROOMS_PREFIX = "socketio:user:"
USER_ROOMS_SUFFIX = ":rooms"

# Room expiration time (in seconds)
ROOM_EXPIRY = 86400  # 24 hours


async def join_room(sid: str, room_id: str) -> bool:
    """
    Add a client to a room and update Redis tracking.

    Args:
        sid: Session ID of the client
        room_id: Room ID to join

    Returns:
        True if the client successfully joined the room
    """
    try:
        # Get session data to get user_id
        session = await socketio_server.get_session(sid)
        user_id = session.get("user_id")

        if not user_id:
            logger.warning(f"Cannot join room without user_id: {sid}")
            return False

        # Add client to Socket.io room
        await socketio_server.enter_room(sid, room_id)

        # Update Redis tracking
        redis = await get_redis_cache()

        # Add user to room participants
        room_participants_key = f"{ROOM_PREFIX}{room_id}{ROOM_PARTICIPANTS_SUFFIX}"
        await redis.sadd(
            room_participants_key,
            json.dumps(
                {"user_id": user_id, "sid": sid, "joined_at": utc_now().isoformat()}
            ),
        )
        await redis.expire(room_participants_key, ROOM_EXPIRY)

        # Add room to user's rooms
        user_rooms_key = f"{USER_ROOMS_PREFIX}{user_id}{USER_ROOMS_SUFFIX}"
        await redis.sadd(user_rooms_key, room_id)
        await redis.expire(user_rooms_key, ROOM_EXPIRY)

        # Create/update room metadata if it doesn't exist
        await _ensure_room_metadata(room_id)

        logger.info(f"User {user_id} (sid: {sid}) joined room {room_id}")
        return True

    except Exception as e:
        logger.error(f"Error joining room {room_id}: {e}")
        return False


async def leave_room(sid: str, room_id: str) -> bool:
    """
    Remove a client from a room and update Redis tracking.

    Args:
        sid: Session ID of the client
        room_id: Room ID to leave

    Returns:
        True if the client successfully left the room
    """
    try:
        # Get session data to get user_id
        session = await socketio_server.get_session(sid)
        user_id = session.get("user_id")

        # Remove client from Socket.io room
        await socketio_server.leave_room(sid, room_id)

        # Update Redis tracking if user_id is available
        if user_id:
            redis = await get_redis_cache()

            # Get existing participants
            room_participants_key = f"{ROOM_PREFIX}{room_id}{ROOM_PARTICIPANTS_SUFFIX}"
            participants = await redis.smembers(room_participants_key)

            # Remove the participant with matching sid
            for participant_json in participants:
                participant = json.loads(participant_json)
                if participant.get("sid") == sid:
                    await redis.srem(room_participants_key, participant_json)

            # Check if user has other sessions in the room
            has_other_sessions = False
            for participant_json in participants:
                participant = json.loads(participant_json)
                if (
                    participant.get("user_id") == user_id
                    and participant.get("sid") != sid
                ):
                    has_other_sessions = True
                    break

            # Only remove from user's rooms if no other sessions
            if not has_other_sessions:
                user_rooms_key = f"{USER_ROOMS_PREFIX}{user_id}{USER_ROOMS_SUFFIX}"
                await redis.srem(user_rooms_key, room_id)

        logger.info(f"Client {sid} left room {room_id}")
        return True

    except Exception as e:
        logger.error(f"Error leaving room {room_id}: {e}")
        return False


async def get_room_participants(room_id: str) -> List[Dict[str, Any]]:
    """
    Get a list of participants in a room.

    Args:
        room_id: Room ID to get participants for

    Returns:
        List of participant information dictionaries
    """
    redis = await get_redis_cache()
    room_participants_key = f"{ROOM_PREFIX}{room_id}{ROOM_PARTICIPANTS_SUFFIX}"

    participants = []
    participant_jsons = await redis.smembers(room_participants_key)

    for participant_json in participant_jsons:
        participants.append(json.loads(participant_json))

    return participants


async def get_room_user_count(room_id: str) -> int:
    """
    Get the number of unique users in a room.

    Args:
        room_id: Room ID to get count for

    Returns:
        Number of unique users
    """
    participants = await get_room_participants(room_id)
    unique_users: Set[str] = set()

    for participant in participants:
        if "user_id" in participant:
            unique_users.add(participant["user_id"])

    return len(unique_users)


async def get_user_rooms(user_id: str) -> List[str]:
    """
    Get a list of rooms a user is participating in.

    Args:
        user_id: User ID to get rooms for

    Returns:
        List of room IDs
    """
    redis = await get_redis_cache()
    user_rooms_key = f"{USER_ROOMS_PREFIX}{user_id}{USER_ROOMS_SUFFIX}"

    return await redis.smembers(user_rooms_key)


async def create_room(
    creator_id: str,
    name: str,
    is_private: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a new room with metadata.

    Args:
        creator_id: ID of the user creating the room
        name: Room name
        is_private: Whether the room is private
        metadata: Additional metadata for the room

    Returns:
        The newly created room ID
    """
    room_id = str(uuid.uuid4())

    # Initialize metadata
    room_metadata = {
        "id": room_id,
        "name": name,
        "created_at": utc_now().isoformat(),
        "created_by": creator_id,
        "is_private": is_private,
        "is_active": True,
    }

    # Add additional metadata if provided
    if metadata:
        room_metadata.update(metadata)

    # Store room metadata
    redis = await get_redis_cache()
    room_metadata_key = f"{ROOM_PREFIX}{room_id}{ROOM_METADATA_SUFFIX}"

    await redis.set(room_metadata_key, json.dumps(room_metadata), ex=ROOM_EXPIRY)

    logger.info(f"Room created: {room_id}, name: {name}, creator: {creator_id}")
    return room_id


async def get_room_metadata(room_id: str) -> Optional[Dict[str, Any]]:
    """
    Get metadata for a room.

    Args:
        room_id: Room ID to get metadata for

    Returns:
        Room metadata dictionary, or None if room doesn't exist
    """
    redis = await get_redis_cache()
    room_metadata_key = f"{ROOM_PREFIX}{room_id}{ROOM_METADATA_SUFFIX}"

    metadata_json = await redis.get(room_metadata_key)

    if not metadata_json:
        return None

    return json.loads(metadata_json)


async def update_room_metadata(room_id: str, metadata: Dict[str, Any]) -> bool:
    """
    Update metadata for a room.

    Args:
        room_id: Room ID to update metadata for
        metadata: New metadata fields to update

    Returns:
        True if the metadata was updated, False otherwise
    """
    current_metadata = await get_room_metadata(room_id)

    if not current_metadata:
        return False

    # Update metadata fields
    current_metadata.update(metadata)
    current_metadata["updated_at"] = utc_now().isoformat()

    # Store updated metadata
    redis = await get_redis_cache()
    room_metadata_key = f"{ROOM_PREFIX}{room_id}{ROOM_METADATA_SUFFIX}"

    await redis.set(room_metadata_key, json.dumps(current_metadata), ex=ROOM_EXPIRY)

    return True


async def _ensure_room_metadata(room_id: str) -> None:
    """
    Ensure room metadata exists, creating a default entry if needed.

    Args:
        room_id: Room ID to ensure metadata for
    """
    metadata = await get_room_metadata(room_id)

    if not metadata:
        # Create default metadata
        await create_room(
            creator_id="system",
            name=f"Room {room_id}",
            is_private=False,
            metadata={"created_by_system": True},
        )
