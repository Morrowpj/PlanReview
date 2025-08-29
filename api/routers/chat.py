from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import psycopg2.extras

from api.utils import get_db, Conversations
from api.schemas.chat import ChatRequest, ChatResponse
from api.schemas.auth import UserResponse
from api.dependencies.auth import get_current_user

# Import the chat modules (these would need to be available in your environment)
try:
    import udochat
except ImportError:
    udochat = None

router = APIRouter(prefix="/api", tags=["chat"])

def save_conversation_to_db(
    conversation_id: int, 
    user_message: str, 
    ai_response: str, 
    user_id: int,
    prompt_id: str,
    conversation_api_id: str,
    db: Session
) -> int:
    """Save or update conversation in the database"""
    try:
        if conversation_id:
            # Update existing conversation
            conversation = db.query(Conversations).filter(
                Conversations.conversation_id == conversation_id,
                Conversations.user_id == user_id
            ).first()
            
            if conversation:
                # Append new messages to existing history
                current_history = conversation.conversation_history if conversation.conversation_history else []
                new_messages = [
                    {"role": "user", "content": user_message, "timestamp": datetime.now().isoformat()},
                    {"role": "assistant", "content": ai_response, "timestamp": datetime.now().isoformat()}
                ]
                updated_history = current_history + new_messages
                
                # Force SQLAlchemy to detect the change by creating a new list
                conversation.conversation_history = updated_history
                conversation.last_message_at = datetime.utcnow()
                conversation.updated_at = datetime.utcnow()
                
                # Mark the conversation_history field as modified to ensure SQLAlchemy saves it
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(conversation, 'conversation_history')
                
                db.commit()
                return conversation_id
        
        # Create new conversation
        # Generate title from first user message (truncate if too long)
        title = user_message[:50] + "..." if len(user_message) > 50 else user_message
        
        conversation_history = [
            {"role": "user", "content": user_message, "timestamp": datetime.now().isoformat()},
            {"role": "assistant", "content": ai_response, "timestamp": datetime.now().isoformat()}
        ]
        
        new_conversation = Conversations(
            title=title,
            conversation_history=conversation_history,
            user_id=user_id,
            last_message_at=datetime.utcnow()
        )
        
        db.add(new_conversation)
        db.commit()
        db.refresh(new_conversation)
        return new_conversation.conversation_id
        
    except Exception as e:
        print(f"Error saving conversation: {e}")
        db.rollback()
        return conversation_id  # Return original ID if update fails

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """Send a chat message and get AI response"""
    if not request.message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is required"
        )
    
    if udochat is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat service not available"
        )
    
    try:
        # Get AI response
        result = udochat.create_flask_response(
            request.message, 
            prompt_id=request.assistant_id, 
            conversation_id=request.thread_id
        )
        
        if result.get('status') == 'success':
            # Save conversation to database
            conversation_id = save_conversation_to_db(
                request.conversation_id, 
                request.message, 
                result.get('response', ''), 
                current_user.user_id,
                result.get('prompt_id'),
                result.get('conversation_id'),
                db
            )
            result['conversation_id'] = conversation_id
        
        return ChatResponse(**result)
        
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )