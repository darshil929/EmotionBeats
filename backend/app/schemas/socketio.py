"""
Pydantic models for Socket.io message formats.

This module defines the data structures for messages exchanged via Socket.io,
providing validation and type checking for real-time communication.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import uuid


class MessageType(str, Enum):
    """Types of messages that can be sent via Socket.io."""

    CHAT = "chat"
    SYSTEM = "system"
    NOTIFICATION = "notification"


class DeliveryStatus(str, Enum):
    """Possible delivery statuses for messages."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ConnectionEvent(BaseModel):
    """Connection event data."""

    status: str
    sid: str
    timestamp: datetime


class AuthenticationRequest(BaseModel):
    """Authentication request from client."""

    user_id: str
    token: Optional[str] = None


class AuthenticationResponse(BaseModel):
    """Authentication response to client."""

    status: str
    user_id: str
    timestamp: datetime


class RoomParticipant(BaseModel):
    """Information about a room participant."""

    user_id: str
    sid: str
    joined_at: datetime


class RoomEvent(BaseModel):
    """Room join/leave event data."""

    room_id: str
    action: str = Field(..., description="join or leave")
    user_id: str
    timestamp: datetime
    participants: List[RoomParticipant]


class RoomRequest(BaseModel):
    """Request to join or leave a room."""

    room_id: str
    metadata: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    """Chat message data model."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    room_id: str
    content: str
    sender_id: str
    sender_sid: str
    message_type: MessageType = MessageType.CHAT
    timestamp: datetime
    delivered: bool = False
    metadata: Optional[Dict[str, Any]] = None


class MessageDeliveryConfirmation(BaseModel):
    """Confirmation of message delivery."""

    message_id: str
    status: DeliveryStatus
    room_id: str
    timestamp: datetime


class MessageReceived(BaseModel):
    """Message received confirmation from client."""

    message_id: str
    room_id: Optional[str] = None


class TypingIndicator(BaseModel):
    """Typing indicator event."""

    room_id: str
    user_id: str
    is_typing: bool
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response for Socket.io events."""

    status: str = "error"
    message: str
    code: Optional[int] = None


class RoomMetadata(BaseModel):
    """Room metadata information."""

    id: str
    name: str
    created_at: datetime
    created_by: str
    is_private: bool = False
    is_active: bool = True
    updated_at: Optional[datetime] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    max_participants: Optional[int] = None
    custom_data: Optional[Dict[str, Any]] = None


class CreateRoomRequest(BaseModel):
    """Request to create a new room."""

    name: str
    is_private: bool = False
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CreateRoomResponse(BaseModel):
    """Response after room creation."""

    room_id: str
    status: str = "created"
    metadata: RoomMetadata
