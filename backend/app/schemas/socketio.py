"""
Pydantic schemas for Socket.io event validation.

Defines request and response models for all Socket.io events to ensure
data consistency, validation, and proper type checking across the system.
"""

from datetime import datetime
from typing import Dict, Optional, Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field, validator


class ConnectionAuthSchema(BaseModel):
    """
    Schema for Socket.io connection authentication data.

    Validates authentication credentials provided during
    WebSocket connection establishment.
    """

    token: str = Field(..., min_length=10, description="JWT authentication token")

    @validator("token")
    def validate_token_format(cls, v):
        """Validates basic token format requirements."""
        if not v or v.isspace():
            raise ValueError("Token cannot be empty or whitespace")
        return v.strip()


class ConnectionResponseSchema(BaseModel):
    """
    Schema for successful Socket.io connection response.

    Provides connection confirmation data sent to clients
    upon successful authentication and connection.
    """

    success: bool = Field(True, description="Connection success status")
    user_id: str = Field(..., description="Authenticated user identifier")
    username: str = Field(
        ..., min_length=1, max_length=50, description="User display name"
    )
    message: str = Field(
        default="Connected successfully", description="Connection status message"
    )


class JoinRoomEventSchema(BaseModel):
    """
    Schema for chat session room join requests.

    Validates data required for users to join specific
    chat session rooms for real-time communication.
    """

    session_id: str = Field(..., description="Chat session identifier to join")

    @validator("session_id")
    def validate_session_id(cls, v):
        """Validates session ID format and requirements."""
        if not v or v.isspace():
            raise ValueError("Session ID cannot be empty")
        try:
            UUID(v)  # Validate UUID format
        except ValueError:
            raise ValueError("Session ID must be a valid UUID")
        return v.strip()


class LeaveRoomEventSchema(BaseModel):
    """
    Schema for chat session room leave requests.

    Validates data for users leaving chat session rooms
    and ending real-time communication participation.
    """

    session_id: str = Field(..., description="Chat session identifier to leave")

    @validator("session_id")
    def validate_session_id(cls, v):
        """Validates session ID format and requirements."""
        if not v or v.isspace():
            raise ValueError("Session ID cannot be empty")
        try:
            UUID(v)
        except ValueError:
            raise ValueError("Session ID must be a valid UUID")
        return v.strip()


class MessageEventSchema(BaseModel):
    """
    Schema for chat message sending events.

    Validates message content and metadata for real-time
    chat message transmission within session rooms.
    """

    session_id: str = Field(..., description="Target chat session identifier")
    content: str = Field(
        ..., min_length=1, max_length=2000, description="Message content"
    )

    @validator("session_id")
    def validate_session_id(cls, v):
        """Validates session ID format."""
        try:
            UUID(v)
        except ValueError:
            raise ValueError("Session ID must be a valid UUID")
        return v.strip()

    @validator("content")
    def validate_content(cls, v):
        """Validates message content requirements."""
        if not v or v.isspace():
            raise ValueError("Message content cannot be empty or whitespace only")
        return v.strip()


class MessageResponseSchema(BaseModel):
    """
    Schema for chat message broadcast data.

    Defines the structure of message data broadcasted
    to all participants in a chat session room.
    """

    message_id: str = Field(..., description="Unique message identifier")
    session_id: str = Field(..., description="Chat session identifier")
    user_id: str = Field(..., description="Message sender identifier")
    username: str = Field(..., description="Sender display name")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message creation timestamp")
    sender: Literal["user", "ai"] = Field(..., description="Message sender type")


class TypingEventSchema(BaseModel):
    """
    Schema for typing indicator events.

    Validates typing start and stop notifications for
    real-time typing status communication.
    """

    session_id: str = Field(..., description="Chat session identifier")

    @validator("session_id")
    def validate_session_id(cls, v):
        """Validates session ID format."""
        try:
            UUID(v)
        except ValueError:
            raise ValueError("Session ID must be a valid UUID")
        return v.strip()


class TypingResponseSchema(BaseModel):
    """
    Schema for typing indicator broadcast data.

    Defines typing status information broadcasted to
    session participants for real-time feedback.
    """

    user_id: str = Field(..., description="User identifier")
    username: str = Field(..., description="User display name")
    is_typing: bool = Field(..., description="Current typing status")
    session_id: Optional[str] = Field(None, description="Chat session identifier")


class DeliveryConfirmationSchema(BaseModel):
    """
    Schema for message delivery and read confirmations.

    Validates delivery status updates for reliable
    message transmission tracking.
    """

    message_id: str = Field(..., description="Message identifier")

    @validator("message_id")
    def validate_message_id(cls, v):
        """Validates message ID format."""
        if not v or v.isspace():
            raise ValueError("Message ID cannot be empty")
        try:
            UUID(v)
        except ValueError:
            raise ValueError("Message ID must be a valid UUID")
        return v.strip()


class PresenceEventSchema(BaseModel):
    """
    Schema for user presence detection events.

    Validates user online/offline status information
    for presence awareness features.
    """

    user_id: str = Field(..., description="User identifier")
    username: str = Field(..., description="User display name")
    status: Literal["online", "offline"] = Field(
        ..., description="User presence status"
    )
    session_id: Optional[str] = Field(None, description="Associated session identifier")


class RoomParticipantSchema(BaseModel):
    """
    Schema for chat room participant information.

    Defines participant data structure for room
    membership and presence tracking.
    """

    socket_id: str = Field(..., description="Socket connection identifier")
    user_id: str = Field(..., description="User identifier")
    username: Optional[str] = Field(None, description="User display name")
    joined_at: Optional[datetime] = Field(None, description="Room join timestamp")


class ErrorResponseSchema(BaseModel):
    """
    Schema for Socket.io error responses.

    Standardizes error information sent to clients
    for consistent error handling and user feedback.
    """

    success: bool = Field(False, description="Operation success status")
    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(), description="Error timestamp"
    )


class SuccessResponseSchema(BaseModel):
    """
    Schema for successful Socket.io operation responses.

    Standardizes success confirmation data for
    consistent client-side response handling.
    """

    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Success confirmation message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(), description="Response timestamp"
    )


class MessageSentConfirmationSchema(BaseModel):
    """
    Schema for message sending confirmation responses.

    Provides delivery confirmation data for sent messages
    including timing and identification information.
    """

    success: bool = Field(True, description="Message send success status")
    message_id: str = Field(..., description="Assigned message identifier")
    timestamp: datetime = Field(..., description="Message send timestamp")
    session_id: Optional[str] = Field(None, description="Target session identifier")


class RoomJoinResponseSchema(BaseModel):
    """
    Schema for chat room join confirmation responses.

    Confirms successful room membership and provides
    session context information.
    """

    success: bool = Field(True, description="Room join success status")
    session_id: str = Field(..., description="Joined session identifier")
    message: str = Field(
        default="Successfully joined chat session",
        description="Join confirmation message",
    )
    participant_count: Optional[int] = Field(
        None, description="Current room participant count"
    )


class RoomLeaveResponseSchema(BaseModel):
    """
    Schema for chat room leave confirmation responses.

    Confirms successful room departure and cleanup
    completion status.
    """

    success: bool = Field(True, description="Room leave success status")
    session_id: str = Field(..., description="Left session identifier")
    message: str = Field(
        default="Successfully left chat session",
        description="Leave confirmation message",
    )


class UserJoinedNotificationSchema(BaseModel):
    """
    Schema for user joined room notification broadcasts.

    Notifies existing participants when new users
    join chat session rooms.
    """

    user_id: str = Field(..., description="Joined user identifier")
    username: Optional[str] = Field(None, description="Joined user display name")
    session_id: str = Field(..., description="Chat session identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(), description="Join event timestamp"
    )


class UserLeftNotificationSchema(BaseModel):
    """
    Schema for user left room notification broadcasts.

    Notifies remaining participants when users
    leave chat session rooms.
    """

    user_id: str = Field(..., description="Left user identifier")
    username: Optional[str] = Field(None, description="Left user display name")
    session_id: str = Field(..., description="Chat session identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(), description="Leave event timestamp"
    )


class RateLimitErrorSchema(BaseModel):
    """
    Schema for rate limiting error responses.

    Provides rate limit violation information and
    retry guidance for client applications.
    """

    error: str = Field(default="Rate limit exceeded", description="Error type")
    event: str = Field(..., description="Rate-limited event name")
    retry_after: int = Field(..., description="Seconds until retry allowed")
    current_limit: Optional[int] = Field(
        None, description="Current rate limit threshold"
    )


class ServerErrorSchema(BaseModel):
    """
    Schema for general server error responses.

    Standardizes internal server error information
    for client-side error handling.
    """

    error: str = Field(default="Internal server error", description="Error type")
    event: str = Field(..., description="Failed event name")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(), description="Error timestamp"
    )
    request_id: Optional[str] = Field(None, description="Request tracking identifier")


class PerformanceMetricsSchema(BaseModel):
    """
    Schema for Socket.io performance metrics data.

    Defines monitoring information structure for
    system performance analysis and optimization.
    """

    event_name: str = Field(..., description="Event name")
    total_requests: int = Field(..., ge=0, description="Total request count")
    average_duration: float = Field(
        ..., ge=0, description="Average execution duration in seconds"
    )
    error_count: int = Field(..., ge=0, description="Total error count")
    error_rate: float = Field(..., ge=0, le=100, description="Error rate percentage")
    last_request: Optional[str] = Field(None, description="Last request timestamp")


class ActiveRoomStatsSchema(BaseModel):
    """
    Schema for active chat room statistics.

    Provides monitoring data for room usage patterns
    and system capacity planning.
    """

    session_id: str = Field(..., description="Chat session identifier")
    participant_count: int = Field(..., ge=0, description="Current participant count")
    created_at: Optional[datetime] = Field(None, description="Room creation timestamp")
    last_activity: Optional[datetime] = Field(
        None, description="Last activity timestamp"
    )


# Event validation mapping for runtime validation
EVENT_SCHEMAS = {
    "join_chat_session": JoinRoomEventSchema,
    "leave_chat_session": LeaveRoomEventSchema,
    "send_message": MessageEventSchema,
    "typing_start": TypingEventSchema,
    "typing_stop": TypingEventSchema,
    "message_delivered": DeliveryConfirmationSchema,
    "message_read": DeliveryConfirmationSchema,
}


def validate_event_data(event_name: str, data: Dict[str, Any]) -> Any:
    """
    Validates Socket.io event data against appropriate schema.

    Performs runtime validation of incoming event data to ensure
    data integrity and consistency across the application.
    """
    schema_class = EVENT_SCHEMAS.get(event_name)

    if not schema_class:
        raise ValueError(f"No validation schema found for event: {event_name}")

    try:
        return schema_class(**data)
    except Exception as e:
        raise ValueError(f"Validation failed for event {event_name}: {str(e)}")


def get_response_schema(event_name: str) -> Optional[type]:
    """
    Returns the appropriate response schema for a given event.

    Provides schema information for consistent response formatting
    and client-side data handling.
    """
    response_mapping = {
        "join_chat_session": RoomJoinResponseSchema,
        "leave_chat_session": RoomLeaveResponseSchema,
        "send_message": MessageSentConfirmationSchema,
        "new_message": MessageResponseSchema,
        "user_typing": TypingResponseSchema,
        "user_joined": UserJoinedNotificationSchema,
        "user_left": UserLeftNotificationSchema,
        "connected": ConnectionResponseSchema,
        "rate_limit_error": RateLimitErrorSchema,
        "server_error": ServerErrorSchema,
        "auth_error": ErrorResponseSchema,
    }

    return response_mapping.get(event_name)
