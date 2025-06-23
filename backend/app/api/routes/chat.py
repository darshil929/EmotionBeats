"""
API routes for chat session management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatHistoryResponse,
)
from app.services.chat.session_manager import (
    create_session,
    get_user_sessions,
    get_session_with_messages,
    update_session,
    delete_session,
)
from app.db.models import User

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post(
    "/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED
)
async def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new chat session.

    Args:
        session_data: Chat session data
        current_user: Authenticated user
        db: Database session
    """
    try:
        session = await create_session(
            db=db,
            user_id=str(current_user.id),
            session_name=session_data.name,
            session_context=session_data.context,
        )
        return session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat session: {str(e)}",
        )


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a list of the user's chat sessions.

    Args:
        limit: Maximum number of sessions to return
        offset: Number of sessions to skip
        active_only: If true, only return active sessions
        current_user: Authenticated user
        db: Database session
    """
    try:
        sessions = await get_user_sessions(
            db=db,
            user_id=str(current_user.id),
            limit=limit,
            offset=offset,
            active_only=active_only,
        )
        return sessions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat sessions: {str(e)}",
        )


@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_session(
    session_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    before_message_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific chat session with its messages.

    Args:
        session_id: Chat session ID
        limit: Maximum number of messages to return
        before_message_id: Return messages before this ID (for pagination)
        current_user: Authenticated user
        db: Database session
    """
    try:
        session_with_messages = await get_session_with_messages(
            db=db,
            session_id=str(session_id),
            user_id=str(current_user.id),
            limit=limit,
            before_message_id=str(before_message_id) if before_message_id else None,
        )

        if not session_with_messages:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found",
            )

        return session_with_messages
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat session: {str(e)}",
        )


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    session_id: UUID,
    session_data: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a chat session.

    Args:
        session_id: Chat session ID
        session_data: Updated chat session data
        current_user: Authenticated user
        db: Database session
    """
    try:
        session = await update_session(
            db=db,
            session_id=str(session_id),
            user_id=str(current_user.id),
            is_active=session_data.is_active,
            session_name=session_data.name,
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found",
            )

        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update chat session: {str(e)}",
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a chat session.

    Args:
        session_id: Chat session ID
        current_user: Authenticated user
        db: Database session
    """
    try:
        success = await delete_session(
            db=db,
            session_id=str(session_id),
            user_id=str(current_user.id),
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found",
            )

        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete chat session: {str(e)}",
        )
