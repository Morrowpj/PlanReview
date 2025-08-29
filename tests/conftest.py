import pytest
import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import jwt

# Set environment variables for testing
os.environ['TESTING'] = 'True'
os.environ['DB_USER'] = 'test'
os.environ['DB_PASSWORD'] = 'test'
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'test'

# Import after setting environment variables
from api.main import app
from api.utils.models import Base, UserData, Conversations, ReviewRooms
from api.utils.database import get_db
from werkzeug.security import generate_password_hash

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

fake = Faker()

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
def db_session():
    """Create a clean database for each test"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def override_get_db(db_session):
    """Override the database dependency"""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass
    return _override_get_db

@pytest.fixture
def client(override_get_db):
    """Create test client with database override"""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def test_user_data():
    """Generate test user data"""
    return {
        "username": fake.email(),
        "password": "TestPassword123!"
    }

@pytest.fixture
def created_user(db_session, test_user_data):
    """Create a user in the database"""
    user = UserData(
        username=test_user_data["username"],
        email=test_user_data["username"],
        password_hash=generate_password_hash(test_user_data["password"]),
        login_attempts=0,
        last_login=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def auth_token(created_user, test_user_data):
    """Generate JWT token for authenticated requests"""
    from api.dependencies.auth import SECRET_KEY, ALGORITHM
    
    data = {
        "sub": created_user.username,
        "user_id": created_user.user_id,
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }
    token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    return token

@pytest.fixture
def auth_headers(auth_token):
    """Generate authorization headers"""
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture
def test_conversation(db_session, created_user):
    """Create a test conversation"""
    conversation = Conversations(
        title="Test Conversation",
        user_id=created_user.user_id,
        conversation_history=[
            {"role": "user", "content": "Hello", "timestamp": datetime.now().isoformat()},
            {"role": "assistant", "content": "Hi there!", "timestamp": datetime.now().isoformat()}
        ],
        last_message_at=datetime.utcnow()
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation

@pytest.fixture
def test_pdf_content():
    """Generate test PDF content"""
    # This is a minimal PDF content for testing
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n174\n%%EOF"

@pytest.fixture
def test_review_room(db_session, created_user, test_pdf_content):
    """Create a test review room with PDF"""
    review_room = ReviewRooms(
        title="Test Review Room",
        user_id=created_user.user_id,
        pdf_files=[test_pdf_content],
        last_message_at=datetime.utcnow()
    )
    db_session.add(review_room)
    db_session.commit()
    db_session.refresh(review_room)
    return review_room

@pytest.fixture
def mock_udochat(mocker):
    """Mock udochat service"""
    mock = MagicMock()
    mock.create_flask_response.return_value = {
        "status": "success",
        "response": "This is a test AI response",
        "prompt_id": "test_prompt",
        "conversation_id": "test_conversation"
    }
    mocker.patch('api.routers.chat.udochat', mock)
    return mock

@pytest.fixture
def mock_planreview(mocker):
    """Mock planreview service"""
    mock = MagicMock()
    mock.submit_plan_to_stormwater_reviewer.return_value = {
        "status": "success",
        "comments_data": {
            "comments": [
                {"type": "info", "message": "Test review comment"}
            ]
        },
        "prompt_id": "test_prompt",
        "conversation_id": "test_conversation"
    }
    mock.submit_plan_to_reviewer.return_value = {
        "status": "success",
        "comments_data": {
            "comments": [
                {"type": "info", "message": "Test review comment"}
            ]
        },
        "prompt_id": "test_prompt", 
        "conversation_id": "test_conversation"
    }
    mock.load_reviewers.return_value = {
        "reviewers": [
            {"name": "Stormwater Reviewer", "description": "Reviews stormwater plans"},
            {"name": "Building Reviewer", "description": "Reviews building plans"}
        ]
    }
    mocker.patch('api.routers.reviewrooms.planreview', mock)
    return mock

@pytest.fixture
def second_user(db_session):
    """Create a second user for isolation testing"""
    user_data = {
        "username": fake.email(),
        "password": "TestPassword123!"
    }
    user = UserData(
        username=user_data["username"],
        email=user_data["username"],
        password_hash=generate_password_hash(user_data["password"]),
        login_attempts=0,
        last_login=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, user_data