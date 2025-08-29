from typing import Annotated
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os

from api.utils import get_db, UserData
from api.schemas.auth import TokenData, UserResponse

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Security configuration
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if username is None or user_id is None:
            return None
        token_data = TokenData(username=username, user_id=user_id)
        return token_data
    except jwt.PyJWTError:
        return None

def get_user_by_username(db: Session, username: str) -> UserData:
    """Get user from database by username"""
    return db.query(UserData).filter(UserData.username == username).first()

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], 
    db: Session = Depends(get_db)
) -> UserResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception
        
    user = get_user_by_username(db, token_data.username)
    if user is None:
        raise credentials_exception
        
    return UserResponse(
        user_id=user.user_id, 
        username=user.username,
        email=user.email,
        created_at=user.created_at,
        last_login=user.last_login
    )