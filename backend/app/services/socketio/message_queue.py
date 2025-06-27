"""
Message processing and delivery tracking for Socket.io communication.

This module provides functions for enqueueing messages, tracking delivery status,
and retrieving message history using Redis as the backing store.
"""

import json
import logging
from typing import Dict, Any, List, Optional
import uuid

from app.core.redis import get_redis_cache
from app.utils.datetime_helper import utc_now

# Configure logger
logger = logging.getLogger(__name__)

# Redis key prefixes
MESSAGE_KEY_PREFIX = "message:"
ROOM_MESSAGES_PREFIX = "room:"
USER_MESSAGES_PREFIX = "user:"

# Message expiration time (in seconds)
MESSAGE_EXPIRY = 86400  # 24 hours


async def enqueue_message(message: Dict[str, Any]) -> str:
    """
    Store a message in Redis and add it to the room's message list.

    Args:
        message: Message data dictionary

    Returns:
        The message ID
    """
    message_id = message.get("id") or str(uuid.uuid4())
    message["id"] = message_id

    if "timestamp" not in message:
        message["timestamp"] = utc_now().isoformat()

    room_id = message.get("room_id")
    sender_id = message.get("sender_id")

    if not room_id or not sender_id:
        raise ValueError("Message must contain room_id and sender_id")

    redis = await get_redis_cache()

    # Store message data with expiry
    message_key = f"{MESSAGE_KEY_PREFIX}{message_id}"
    await redis.set(message_key, json.dumps(message), ex=MESSAGE_EXPIRY)

    # Add to room's message list
    room_key = f"{ROOM_MESSAGES_PREFIX}{room_id}:messages"
    await redis.zadd(room_key, {message_id: utc_now().timestamp()})
    await redis.expire(room_key, MESSAGE_EXPIRY)

    # Add to room's pending deliveries set
    pending_key = f"{ROOM_MESSAGES_PREFIX}{room_id}:pending"
    await redis.sadd(pending_key, message_id)
    await redis.expire(pending_key, MESSAGE_EXPIRY)

    logger.debug(f"Message {message_id} enqueued for room {room_id}")
    return message_id


async def confirm_delivery(message_id: str, user_id: str) -> bool:
    """
    Mark a message as delivered for a specific user.

    Args:
        message_id: ID of the message
        user_id: ID of the user who received the message

    Returns:
        True if delivery was confirmed, False otherwise
    """
    redis = await get_redis_cache()

    # Get message data
    message_key = f"{MESSAGE_KEY_PREFIX}{message_id}"
    message_data = await redis.get(message_key)

    if not message_data:
        logger.warning(
            f"Cannot confirm delivery for non-existent message: {message_id}"
        )
        return False

    message = json.loads(message_data)
    room_id = message.get("room_id")

    if not room_id:
        logger.warning(f"Message {message_id} has no room_id")
        return False

    # Add user to message's delivered set
    delivered_key = f"{MESSAGE_KEY_PREFIX}{message_id}:delivered"
    await redis.sadd(delivered_key, user_id)
    await redis.expire(delivered_key, MESSAGE_EXPIRY)

    # Remove from user's unread set if it exists
    user_unread_key = f"{USER_MESSAGES_PREFIX}{user_id}:unread"
    await redis.srem(user_unread_key, message_id)

    logger.debug(f"Message {message_id} delivery confirmed by user {user_id}")
    return True


async def get_room_messages(
    room_id: str, limit: int = 50, before: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Get recent messages for a room with pagination.

    Args:
        room_id: Room ID to get messages for
        limit: Maximum number of messages to return
        before: Timestamp to get messages before (for pagination)

    Returns:
        List of message objects, newest first
    """
    redis = await get_redis_cache()
    room_key = f"{ROOM_MESSAGES_PREFIX}{room_id}:messages"

    # Get message IDs from room's sorted set
    if before is None:
        # Get most recent messages
        message_ids = await redis.zrevrange(room_key, 0, limit - 1, withscores=True)
    else:
        # Get messages before the specified timestamp
        message_ids = await redis.zrevrangebyscore(
            room_key, before, "-inf", start=0, num=limit, withscores=True
        )

    # Get message data for each ID
    messages = []
    for message_id, score in message_ids:
        message_key = f"{MESSAGE_KEY_PREFIX}{message_id}"
        message_data = await redis.get(message_key)

        if message_data:
            message = json.loads(message_data)
            messages.append(message)

    return messages


async def get_pending_messages(room_id: str) -> List[Dict[str, Any]]:
    """
    Get messages pending delivery for a room.

    Args:
        room_id: Room ID to get pending messages for

    Returns:
        List of message objects
    """
    redis = await get_redis_cache()
    pending_key = f"{ROOM_MESSAGES_PREFIX}{room_id}:pending"

    # Get message IDs from room's pending set
    message_ids = await redis.smembers(pending_key)

    # Get message data for each ID
    messages = []
    for message_id in message_ids:
        message_key = f"{MESSAGE_KEY_PREFIX}{message_id}"
        message_data = await redis.get(message_key)

        if message_data:
            message = json.loads(message_data)
            messages.append(message)

    return messages


async def mark_message_delivered_to_all(message_id: str) -> bool:
    """
    Mark a message as delivered to all recipients and remove from pending.

    Args:
        message_id: ID of the message

    Returns:
        True if the message was marked as delivered, False otherwise
    """
    redis = await get_redis_cache()

    # Get message data
    message_key = f"{MESSAGE_KEY_PREFIX}{message_id}"
    message_data = await redis.get(message_key)

    if not message_data:
        logger.warning(f"Cannot mark non-existent message as delivered: {message_id}")
        return False

    message = json.loads(message_data)
    room_id = message.get("room_id")

    if not room_id:
        logger.warning(f"Message {message_id} has no room_id")
        return False

    # Remove from room's pending deliveries set
    pending_key = f"{ROOM_MESSAGES_PREFIX}{room_id}:pending"
    await redis.srem(pending_key, message_id)

    # Update message's delivered status
    message["delivered"] = True
    await redis.set(message_key, json.dumps(message), ex=MESSAGE_EXPIRY)

    logger.debug(f"Message {message_id} marked as delivered to all recipients")
    return True


async def get_user_unread_count(user_id: str) -> int:
    """
    Get the count of unread messages for a user.

    Args:
        user_id: ID of the user

    Returns:
        Count of unread messages
    """
    redis = await get_redis_cache()
    user_unread_key = f"{USER_MESSAGES_PREFIX}{user_id}:unread"

    return await redis.scard(user_unread_key)
