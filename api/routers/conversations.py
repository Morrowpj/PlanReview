from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.utils import get_db, Conversations
from api.schemas.conversations import ConversationsListResponse, ConversationDetailResponse, ConversationResponse, ConversationMessage
from api.schemas.auth import UserResponse
from api.dependencies.auth import get_current_user

router = APIRouter(prefix="/api", tags=["conversations"])

@router.get("/conversations", response_model=ConversationsListResponse)
async def get_conversations(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Get all conversations for the current user"""
    try:
        conversations = db.query(Conversations).filter(
            Conversations.user_id == current_user.user_id,
            Conversations.is_active == True
        ).order_by(Conversations.last_message_at.desc()).all()
        
        conversation_responses = []
        for conv in conversations:
            conversation_responses.append(ConversationResponse(
                conversation_id=conv.conversation_id,
                title=conv.title,
                last_message_at=conv.last_message_at,
                conversation_type=conv.conversation_type,
                is_favorite=conv.is_favorite
            ))
        
        return ConversationsListResponse(ok=True, conversations=conversation_responses)
        
    except Exception as e:
        print(f"Error fetching conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch conversations"
        )

@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_messages(
    conversation_id: int,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Get messages for a specific conversation"""
    try:
        conversation = db.query(Conversations).filter(
            Conversations.conversation_id == conversation_id,
            Conversations.user_id == current_user.user_id,
            Conversations.is_active == True
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Convert conversation_history to ConversationMessage objects
        messages = []
        if conversation.conversation_history:
            for msg in conversation.conversation_history:
                messages.append(ConversationMessage(
                    role=msg.get("role", ""),
                    content=msg.get("content", ""),
                    timestamp=msg.get("timestamp", "")
                ))
        
        return ConversationDetailResponse(
            ok=True,
            conversation_id=conversation_id,
            title=conversation.title,
            messages=messages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching conversation messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch conversation messages"
        )