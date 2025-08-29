from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: str

class ConversationResponse(BaseModel):
    conversation_id: int
    title: str
    last_message_at: Optional[datetime] = None
    conversation_type: Optional[str] = "chat"
    is_favorite: bool = False

class ConversationDetail(BaseModel):
    conversation_id: int
    title: str
    messages: List[ConversationMessage] = []

class ConversationsListResponse(BaseModel):
    ok: bool
    conversations: List[ConversationResponse] = []

class ConversationDetailResponse(BaseModel):
    ok: bool
    conversation_id: int
    title: str
    messages: List[ConversationMessage] = []