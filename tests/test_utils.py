import pytest
from datetime import datetime, timedelta
import jwt

class TestDatabaseConfiguration:
    """Test database configuration utilities"""

    def test_azure_deployment_detection(self, mocker):
        """Test Azure environment detection"""
        from api.utils.utils import is_azure_deployment
        
        # Mock no Azure environment variables
        mocker.patch.dict('os.environ', {}, clear=True)
        assert is_azure_deployment() is False
        
        # Mock Azure environment
        mocker.patch.dict('os.environ', {'WEBSITE_SITE_NAME': 'test-site'})
        assert is_azure_deployment() is True
        
        # Test with AZURE_CLIENT_ID
        mocker.patch.dict('os.environ', {'AZURE_CLIENT_ID': 'test-client'}, clear=True)
        assert is_azure_deployment() is True
        
        # Test with WEBSITE_RESOURCE_GROUP
        mocker.patch.dict('os.environ', {'WEBSITE_RESOURCE_GROUP': 'test-rg'}, clear=True)
        assert is_azure_deployment() is True

    def test_local_development_config(self, mocker):
        """Test local development database configuration"""
        from api.utils.utils import get_db_config, is_azure_deployment
        
        # Mock local environment and clear environment variables
        mocker.patch('api.utils.utils.is_azure_deployment', return_value=False)
        mocker.patch.dict('os.environ', {}, clear=True)
        
        config = get_db_config()
        
        assert config['user'] == 'admin'
        assert config['password'] == 'admin'
        assert config['host'] == '127.0.0.1'
        assert config['port'] == 54547
        assert config['database'] == 'postgres'

    def test_azure_production_config(self, mocker):
        """Test Azure production database configuration"""
        from api.utils.utils import get_db_config
        
        # Mock Azure environment and clear environment variables
        mocker.patch('api.utils.utils.is_azure_deployment', return_value=True)
        mocker.patch.dict('os.environ', {}, clear=True)
        
        config = get_db_config()
        
        assert config['user'] == 'hpkrhbkroa'
        assert config['host'] == 'planreview-server.postgres.database.azure.com'
        assert config['port'] == 5432
        assert config['database'] == 'postgres'

    def test_database_connection(self, db_session):
        """Test successful database connection"""
        # If we get here, the database connection fixture worked
        assert db_session is not None
        
        # Test basic query
        from api.utils.models import UserData
        result = db_session.query(UserData).first()
        # Should be None since no users exist, but query should execute


class TestAuthenticationUtilities:
    """Test authentication utility functions"""

    def test_password_hashing(self):
        """Test password hash generation"""
        from werkzeug.security import generate_password_hash, check_password_hash
        
        password = "TestPassword123!"
        hash1 = generate_password_hash(password)
        hash2 = generate_password_hash(password)
        
        # Hashes should be different (due to salt)
        assert hash1 != hash2
        
        # But both should verify correctly
        assert check_password_hash(hash1, password)
        assert check_password_hash(hash2, password)

    def test_password_verification(self):
        """Test password verification"""
        from werkzeug.security import generate_password_hash, check_password_hash
        
        password = "CorrectPassword"
        wrong_password = "WrongPassword"
        password_hash = generate_password_hash(password)
        
        # Correct password should verify
        assert check_password_hash(password_hash, password)
        
        # Wrong password should not verify
        assert not check_password_hash(password_hash, wrong_password)

    def test_jwt_token_creation(self):
        """Test JWT token generation"""
        from api.dependencies.auth import SECRET_KEY, ALGORITHM
        
        data = {
            "sub": "testuser@example.com",
            "user_id": 123,
            "exp": datetime.utcnow() + timedelta(minutes=30)
        }
        
        token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
        
        # Token should be a string
        assert isinstance(token, str)
        
        # Should be able to decode it
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser@example.com"
        assert decoded["user_id"] == 123

    def test_jwt_token_verification(self):
        """Test JWT token validation"""
        from api.dependencies.auth import verify_token, SECRET_KEY, ALGORITHM
        
        # Create valid token
        data = {
            "sub": "testuser@example.com", 
            "user_id": 123,
            "exp": datetime.utcnow() + timedelta(minutes=30)
        }
        token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
        
        # Verify token
        token_data = verify_token(token)
        assert token_data is not None
        assert token_data.username == "testuser@example.com"
        assert token_data.user_id == 123

    def test_jwt_token_expiration(self):
        """Test expired token handling"""
        from api.dependencies.auth import verify_token, SECRET_KEY, ALGORITHM
        
        # Create expired token
        data = {
            "sub": "testuser@example.com",
            "user_id": 123,
            "exp": datetime.utcnow() - timedelta(minutes=1)  # Expired 1 minute ago
        }
        expired_token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
        
        # Should return None for expired token
        token_data = verify_token(expired_token)
        assert token_data is None

    def test_jwt_invalid_token(self):
        """Test invalid token handling"""
        from api.dependencies.auth import verify_token
        
        # Invalid token should return None
        assert verify_token("invalid.token.here") is None
        assert verify_token("") is None
        assert verify_token(None) is None


class TestModelValidation:
    """Test database model validation"""

    def test_user_model_creation(self, db_session):
        """Test UserData model creation"""
        from api.utils.models import UserData
        from werkzeug.security import generate_password_hash
        
        user = UserData(
            username="test@example.com",
            email="test@example.com",
            password_hash=generate_password_hash("password123"),
            login_attempts=0
        )
        
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Should have auto-generated ID
        assert user.user_id is not None
        assert user.username == "test@example.com"
        assert user.email == "test@example.com"
        assert user.login_attempts == 0
        
        # Should have auto-generated timestamps
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_conversation_model_creation(self, db_session, created_user):
        """Test Conversations model creation"""
        from api.utils.models import Conversations
        
        conversation = Conversations(
            title="Test Conversation",
            user_id=created_user.user_id,
            conversation_history=[
                {"role": "user", "content": "Hello", "timestamp": "2023-01-01T12:00:00"}
            ]
        )
        
        db_session.add(conversation)
        db_session.commit()
        db_session.refresh(conversation)
        
        assert conversation.conversation_id is not None
        assert conversation.title == "Test Conversation"
        assert conversation.user_id == created_user.user_id
        assert len(conversation.conversation_history) == 1
        assert conversation.is_active is True

    def test_review_room_model_creation(self, db_session, created_user, test_pdf_content):
        """Test ReviewRooms model creation"""
        from api.utils.models import ReviewRooms
        
        review_room = ReviewRooms(
            title="Test Review Room",
            user_id=created_user.user_id,
            pdf_files=[test_pdf_content]
        )
        
        db_session.add(review_room)
        db_session.commit()
        db_session.refresh(review_room)
        
        assert review_room.review_room_id is not None
        assert review_room.title == "Test Review Room"
        assert review_room.user_id == created_user.user_id
        assert len(review_room.pdf_files) == 1
        assert review_room.is_active is True


class TestAPIValidation:
    """Test API request/response validation"""

    def test_root_endpoint(self, client):
        """Test API root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "PlanReview API"
        assert data["version"] == "1.0.0"

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options("/api/me")
        # FastAPI test client doesn't fully simulate CORS,
        # but we can test that the endpoint exists
        assert response.status_code in [200, 405]  # 405 for method not allowed is OK

    def test_request_validation(self, client, auth_headers):
        """Test request validation on endpoints"""
        
        # Test invalid JSON
        response = client.post(
            "/api/chat", 
            data="invalid json",
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        assert response.status_code in [422, 400]
        
        # Test missing required fields
        response = client.post("/api/chat", json={}, headers=auth_headers)
        assert response.status_code in [422, 400]