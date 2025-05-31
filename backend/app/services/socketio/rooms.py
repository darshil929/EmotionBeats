"""
Socket.io room management system for chat sessions.

Handles room creation, user management, message broadcasting, and cleanup
operations for real-time chat functionality with session-based isolation.
"""

import logging
from typing import Dict, List, Optional, Set

from app.services.socketio.server import get_socketio_server
from app.db.session import SessionLocal
from app.db.models import ChatSession
from app.core.redis import get_redis_cache

logger = logging.getLogger(__name__)

# In-memory tracking for room participants and user sessions
room_participants: Dict[str, Set[str]] = {}  # room_id -> set of socket_ids
user_sessions: Dict[str, str] = {}  # socket_id -> user_id
user_rooms: Dict[str, Set[str]] = {}  # user_id -> set of room_ids


async def create_chat_room(session_id: str, user_id: str) -> bool:
    """
    Creates a new chat room for the specified session.

    Validates session ownership and initializes room tracking data
    for message broadcasting and participant management.
    """
    if not session_id or not user_id:
        logger.warning("Missing session_id or user_id for room creation")
        return False

    room_name = f"session_{session_id}"

    # Validate session exists and belongs to user
    db = SessionLocal()
    try:
        chat_session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )

        if not chat_session:
            logger.warning(
                f"Chat session {session_id} not found or access denied for user {user_id}"
            )
            return False

        if not chat_session.is_active:
            logger.warning(
                f"Attempted to create room for inactive session {session_id}"
            )
            return False

        # Initialize room tracking
        if room_name not in room_participants:
            room_participants[room_name] = set()
            logger.info(f"Chat room {room_name} created successfully")

        return True

    except Exception as e:
        logger.error(f"Database error during room creation: {e}")
        return False
    finally:
        db.close()


async def join_user_to_room(sid: str, session_id: str, user_id: str) -> bool:
    """
    Adds a user's Socket.io session to a specific chat room.

    Manages room membership, updates tracking data, and handles
    Socket.io room operations for message broadcasting.
    """
    if not sid or not session_id or not user_id:
        logger.warning("Missing required parameters for room join")
        return False

    room_name = f"session_{session_id}"
    sio = get_socketio_server()

    if not sio:
        logger.error("Socket.io server not available for room join")
        return False

    try:
        # Validate room exists or create it
        if room_name not in room_participants:
            room_created = await create_chat_room(session_id, user_id)
            if not room_created:
                return False

        # Add socket to Socket.io room
        await sio.enter_room(sid, room_name)

        # Update tracking data
        room_participants[room_name].add(sid)
        user_sessions[sid] = user_id

        if user_id not in user_rooms:
            user_rooms[user_id] = set()
        user_rooms[user_id].add(room_name)

        # Cache room membership in Redis for persistence
        await cache_room_membership(session_id, user_id, True)

        logger.info(f"User {user_id} joined room {room_name} with socket {sid}")

        # Notify other participants about user joining
        await broadcast_to_room(
            session_id,
            "user_joined",
            {"user_id": user_id, "session_id": session_id},
            exclude_sid=sid,
        )

        return True

    except Exception as e:
        logger.error(f"Error joining user {user_id} to room {room_name}: {e}")
        return False


async def leave_user_from_room(sid: str, session_id: str) -> bool:
    """
    Removes a user's Socket.io session from a chat room.

    Handles cleanup of tracking data, Socket.io room operations,
    and participant notifications when users leave.
    """
    if not sid or not session_id:
        logger.warning("Missing sid or session_id for room leave")
        return False

    room_name = f"session_{session_id}"
    sio = get_socketio_server()
    user_id = user_sessions.get(sid)

    if not sio:
        logger.error("Socket.io server not available for room leave")
        return False

    try:
        # Remove socket from Socket.io room
        await sio.leave_room(sid, room_name)

        # Update tracking data
        if room_name in room_participants:
            room_participants[room_name].discard(sid)

        if sid in user_sessions:
            del user_sessions[sid]

        if user_id and user_id in user_rooms:
            user_rooms[user_id].discard(room_name)
            if not user_rooms[user_id]:
                del user_rooms[user_id]

        # Update Redis cache
        if user_id:
            await cache_room_membership(session_id, user_id, False)

        logger.info(f"Socket {sid} left room {room_name}")

        # Notify other participants about user leaving
        if user_id:
            await broadcast_to_room(
                session_id,
                "user_left",
                {"user_id": user_id, "session_id": session_id},
                exclude_sid=sid,
            )

        # Clean up empty room
        await cleanup_empty_room(room_name)

        return True

    except Exception as e:
        logger.error(f"Error removing socket {sid} from room {room_name}: {e}")
        return False


async def broadcast_to_room(
    session_id: str, event: str, data: dict, exclude_sid: Optional[str] = None
) -> bool:
    """
    Broadcasts an event to all participants in a chat session room.

    Sends the specified event and data to all active Socket.io connections
    in the room, with optional exclusion of a specific socket.
    """
    if not session_id or not event:
        logger.warning("Missing session_id or event for room broadcast")
        return False

    room_name = f"session_{session_id}"
    sio = get_socketio_server()

    if not sio:
        logger.error("Socket.io server not available for broadcast")
        return False

    try:
        # Add session_id to data if not present
        if "session_id" not in data:
            data["session_id"] = session_id

        # Broadcast to room
        if exclude_sid:
            await sio.emit(event, data, room=room_name, skip_sid=exclude_sid)
        else:
            await sio.emit(event, data, room=room_name)

        participant_count = len(room_participants.get(room_name, set()))
        logger.debug(
            f"Broadcasted event {event} to {participant_count} participants in room {room_name}"
        )

        return True

    except Exception as e:
        logger.error(f"Error broadcasting event {event} to room {room_name}: {e}")
        return False


async def get_room_participants(session_id: str) -> List[Dict[str, str]]:
    """
    Retrieves list of participants currently in a chat session room.

    Returns participant information including user IDs and socket IDs
    for the specified chat session.
    """
    if not session_id:
        logger.warning("Missing session_id for participant lookup")
        return []

    room_name = f"session_{session_id}"
    participants = []

    try:
        socket_ids = room_participants.get(room_name, set())

        for sid in socket_ids:
            user_id = user_sessions.get(sid)
            if user_id:
                participants.append({"socket_id": sid, "user_id": user_id})

        logger.debug(f"Retrieved {len(participants)} participants for room {room_name}")
        return participants

    except Exception as e:
        logger.error(f"Error retrieving participants for room {room_name}: {e}")
        return []


async def cleanup_empty_room(room_name: str) -> bool:
    """
    Removes empty rooms from tracking data to prevent memory leaks.

    Performs cleanup operations when a room has no remaining participants
    to maintain system efficiency.
    """
    try:
        if room_name in room_participants and not room_participants[room_name]:
            del room_participants[room_name]
            logger.info(f"Cleaned up empty room {room_name}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error during room cleanup for {room_name}: {e}")
        return False


async def cleanup_user_sessions(user_id: str) -> None:
    """
    Removes all sessions and room memberships for a disconnected user.

    Performs comprehensive cleanup when a user disconnects to ensure
    accurate tracking of active participants.
    """
    try:
        # Find all sockets for this user
        user_socket_ids = [sid for sid, uid in user_sessions.items() if uid == user_id]

        # Remove from all rooms
        rooms_to_clean = user_rooms.get(user_id, set()).copy()

        for sid in user_socket_ids:
            for room_name in rooms_to_clean:
                if room_name.startswith("session_"):
                    session_id = room_name.replace("session_", "")
                    await leave_user_from_room(sid, session_id)

        # Clean up user tracking
        if user_id in user_rooms:
            del user_rooms[user_id]

        logger.info(f"Cleaned up all sessions for user {user_id}")

    except Exception as e:
        logger.error(f"Error during user session cleanup for {user_id}: {e}")


async def cache_room_membership(session_id: str, user_id: str, is_member: bool) -> None:
    """
    Caches room membership information in Redis for persistence.

    Stores membership data to maintain state across server restarts
    and support horizontal scaling scenarios.
    """
    try:
        redis_client = await get_redis_cache()
        cache_key = f"room_membership:{session_id}:{user_id}"

        if is_member:
            await redis_client.setex(cache_key, 3600, "active")  # 1 hour TTL
        else:
            await redis_client.delete(cache_key)

    except Exception as e:
        logger.error(f"Error caching room membership: {e}")


async def get_active_rooms() -> Dict[str, int]:
    """
    Returns statistics about currently active chat rooms.

    Provides monitoring information about room usage and
    participant distribution across the system.
    """
    try:
        room_stats = {}

        for room_name, participants in room_participants.items():
            if room_name.startswith("session_"):
                session_id = room_name.replace("session_", "")
                room_stats[session_id] = len(participants)

        logger.debug(f"Active rooms: {len(room_stats)}")
        return room_stats

    except Exception as e:
        logger.error(f"Error retrieving active room statistics: {e}")
        return {}
