"""
Pydantic models for chat-related schemas.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    """Schema for creating a new chat session."""

    name: Optional[str] = None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatSessionUpdate(BaseModel):
    """Schema for updating a chat session."""

    is_active: Optional[bool] = None
    name: Optional[str] = None


class ChatSessionResponse(BaseModel):
    """Schema for chat session response."""

    id: str
    created_at: datetime
    updated_at: datetime
    name: str
    is_active: bool
    context: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class ChatMessageCreate(BaseModel):
    """Schema for creating a new chat message."""

    content: str
    session_id: str
    sender: str = "user"  # 'user' or 'ai'


class ChatMessageResponse(BaseModel):
    """Schema for chat message response."""

    id: str
    content: str
    sender: str  # 'user' or 'ai'
    timestamp: datetime
    emotion: Optional[str] = None
    emotion_confidence: Optional[float] = None

    class Config:
        from_attributes = True


class ChatHistoryResponse(ChatSessionResponse):
    """Schema for chat session with messages."""

    messages: List[ChatMessageResponse] = Field(default_factory=list)


class ChatCompletionRequest(BaseModel):
    """Schema for requesting a chat completion."""

    session_id: str
    message: str


class ChatCompletionResponse(BaseModel):
    """Schema for chat completion response."""

    id: str
    session_id: str
    message: ChatMessageResponse
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EmotionAnalysisResponse(BaseModel):
    """Schema for emotion analysis response."""

    emotion: str
    confidence: float
    audio_features: Optional[Dict[str, float]] = None
    message_id: str
