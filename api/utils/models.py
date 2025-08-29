import os
import base64
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy.types import TypeDecorator

# PostgreSQL-specific imports
try:
    from sqlalchemy.dialects.postgresql import ARRAY
    from sqlalchemy import LargeBinary
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

Base = declarative_base()

class PDFFilesType(TypeDecorator):
    """Custom type to handle PDF files storage"""
    impl = JSON
    
    def process_bind_param(self, value, dialect):
        """Convert bytes to base64 for JSON storage"""
        if value is None:
            return None
        if isinstance(value, list):
            # Handle empty lists
            if len(value) == 0:
                return []
            # Convert bytes objects to base64 strings for JSON serialization
            return [base64.b64encode(item).decode('utf-8') if isinstance(item, bytes) else item for item in value]
        return value
    
    def process_result_value(self, value, dialect):
        """Convert base64 back to bytes"""
        if value is None:
            return None
        if isinstance(value, list):
            # Handle empty lists
            if len(value) == 0:
                return []
            # Convert base64 strings back to bytes objects
            return [base64.b64decode(item.encode('utf-8')) if isinstance(item, str) else item for item in value]
        return value

class UserData(Base):
    __tablename__ = "userdata"
    
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    login_attempts = Column(Integer, default=0)
    last_login = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Conversations(Base):
    __tablename__ = "conversations"
    
    conversation_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    conversation_history = Column(JSON)
    conversation_type = Column(String, default="chat")
    is_favorite = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_message_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ReviewRooms(Base):
    __tablename__ = "reviewrooms"
    
    review_room_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    
    # Use different column types based on database
    if os.environ.get('TESTING') == 'True' or not POSTGRES_AVAILABLE:
        # For SQLite/testing: use custom type to handle base64 encoding
        pdf_files = Column(PDFFilesType)
    else:
        # For PostgreSQL: use proper ARRAY of BYTEA
        from sqlalchemy import LargeBinary
        from sqlalchemy.dialects.postgresql import ARRAY
        pdf_files = Column(ARRAY(LargeBinary))
    
    review_comments = Column(JSON)
    is_favorite = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_message_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())