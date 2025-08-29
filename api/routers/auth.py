from typing import Annotated
from datetime import datetime, timedelta
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash
import os

from api.utils import get_db, UserData
from api.schemas.auth import UserLogin, UserSignup, Token, UserResponse, ApiResponse
from api.dependencies.auth import get_current_user

router = APIRouter(prefix="/api", tags=["authentication"])

# Security configuration
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
MAX_LOGIN_ATTEMPTS = 5

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/signup", response_model=ApiResponse)
async def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    username = user_data.username.strip()
    password = user_data.password
    pwd_hash = generate_password_hash(password)

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username and password required for signup"
        )

    try:
        # Check if user already exists
        existing_user = db.query(UserData).filter(UserData.username == username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered"
            )

        # Create new user
        new_user = UserData(
            username=username,
            email=username,  # Using username as email for now
            password_hash=pwd_hash,
            login_attempts=0,
            last_login=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return ApiResponse(ok=True, message="Signup successful")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Signup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server error"
        )

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    username = user_credentials.username.strip()
    password = user_credentials.password

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required for signin"
        )

    try:
        # Get user with row-level locking to prevent race conditions
        user = db.query(UserData).filter(UserData.username == username).with_for_update().first()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Check lockout
        if user.login_attempts >= MAX_LOGIN_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked due to too many attempts"
            )

        # Verify password
        if check_password_hash(user.password_hash, password):
            # Success: reset attempts and update last_login
            user.login_attempts = 0
            user.last_login = datetime.utcnow()
            db.commit()

            # Create access token
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": username, "user_id": user.user_id},
                expires_delta=access_token_expires
            )

            return Token(
                access_token=access_token,
                token_type="bearer",
                user_id=user.user_id,
                username=username
            )
        else:
            # Failure: increment attempts
            user.login_attempts = (user.login_attempts or 0) + 1
            db.commit()

            if user.login_attempts >= MAX_LOGIN_ATTEMPTS:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account locked due to too many attempts"
                )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server error"
        )

@router.post("/logout", response_model=ApiResponse)
async def logout(current_user: Annotated[UserResponse, Depends(get_current_user)]):
    # In JWT, logout is typically handled client-side by removing the token
    # Server-side logout would require token blacklisting, which we're not implementing here
    return ApiResponse(ok=True, message="Logged out successfully")

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], 
    db: Session = Depends(get_db)
):
    """OAuth2 compatible token endpoint"""
    user_credentials = UserLogin(username=form_data.username, password=form_data.password)
    return await login(user_credentials, db)

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: Annotated[UserResponse, Depends(get_current_user)]):
    """Get current user information"""
    return current_user