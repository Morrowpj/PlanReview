from typing import Optional, Dict, Any
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    assistant_id: Optional[str] = None
    thread_id: Optional[str] = None
    conversation_id: Optional[int] = None

class ChatResponse(BaseModel):
    status: str
    response: Optional[str] = None
    conversation_id: Optional[int] = None
    prompt_id: Optional[str] = None
    error: Optional[str] = None
    details: Optional[str] = None