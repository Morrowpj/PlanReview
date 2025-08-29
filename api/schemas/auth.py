from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class UserLogin(BaseModel):
    username: str
    password: str

class UserSignup(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    username: str

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None

class UserResponse(BaseModel):
    user_id: int
    username: str
    email: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

class ApiResponse(BaseModel):
    ok: bool
    message: Optional[str] = None
    error: Optional[str] = None