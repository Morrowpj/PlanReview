import pytest
from fastapi import status
from datetime import datetime, timedelta
import jwt

class TestUserRegistration:
    """Test user signup functionality"""
    
    def test_signup_success(self, client, test_user_data):
        """Test successful user registration"""
        response = client.post("/api/signup", json=test_user_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert data["message"] == "Signup successful"

    def test_signup_duplicate_user(self, client, created_user, test_user_data):
        """Test registration with existing username"""
        response = client.post("/api/signup", json=test_user_data)
        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "already registered" in data["detail"]

    def test_signup_missing_username(self, client):
        """Test registration without username"""
        response = client.post("/api/signup", json={"password": "test123"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_signup_missing_password(self, client):
        """Test registration without password"""
        response = client.post("/api/signup", json={"username": "test@example.com"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_signup_empty_fields(self, client):
        """Test registration with empty fields"""
        response = client.post("/api/signup", json={"username": "", "password": ""})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestUserLogin:
    """Test user login functionality"""

    def test_login_success(self, client, created_user, test_user_data):
        """Test successful login"""
        response = client.post("/api/login", json=test_user_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data
        assert data["user_id"] == created_user.user_id
        assert data["username"] == created_user.username

    def test_login_invalid_username(self, client):
        """Test login with non-existent username"""
        response = client.post("/api/login", json={
            "username": "nonexistent@example.com",
            "password": "password123"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "Invalid credentials" in data["detail"]

    def test_login_invalid_password(self, client, created_user):
        """Test login with wrong password"""
        response = client.post("/api/login", json={
            "username": created_user.username,
            "password": "wrongpassword"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert "Invalid credentials" in data["detail"]

    def test_login_missing_credentials(self, client):
        """Test login without credentials"""
        response = client.post("/api/login", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_account_lockout(self, client, created_user, db_session):
        """Test account lockout after 5 failed attempts"""
        # Make 4 failed login attempts (should get 401)
        for _ in range(4):
            response = client.post("/api/login", json={
                "username": created_user.username,
                "password": "wrongpassword"
            })
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # 5th attempt should lock the account
        response = client.post("/api/login", json={
            "username": created_user.username,
            "password": "wrongpassword"
        })
        assert response.status_code == status.HTTP_423_LOCKED
        data = response.json()
        assert "Account locked" in data["detail"]

    def test_login_lockout_reset(self, client, created_user, test_user_data, db_session):
        """Test that successful login resets failed attempts"""
        # Make 3 failed attempts
        for _ in range(3):
            client.post("/api/login", json={
                "username": created_user.username,
                "password": "wrongpassword"
            })

        # Successful login should reset attempts
        response = client.post("/api/login", json=test_user_data)
        assert response.status_code == status.HTTP_200_OK

        # Should be able to make failed attempts again
        response = client.post("/api/login", json={
            "username": created_user.username,
            "password": "wrongpassword"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestTokenEndpoints:
    """Test OAuth2 token endpoints"""

    def test_oauth2_token_endpoint(self, client, created_user, test_user_data):
        """Test OAuth2 compatible token endpoint"""
        response = client.post("/api/token", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data

    def test_token_validation(self, client, auth_headers):
        """Test accessing protected endpoint with valid token"""
        response = client.get("/api/me", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "user_id" in data
        assert "username" in data

    def test_expired_token(self, client, created_user):
        """Test access with expired token"""
        from api.dependencies.auth import SECRET_KEY, ALGORITHM
        
        # Create expired token
        expired_data = {
            "sub": created_user.username,
            "user_id": created_user.user_id,
            "exp": datetime.utcnow() - timedelta(minutes=1)  # Expired 1 minute ago
        }
        expired_token = jwt.encode(expired_data, SECRET_KEY, algorithm=ALGORITHM)
        headers = {"Authorization": f"Bearer {expired_token}"}
        
        response = client.get("/api/me", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token(self, client):
        """Test access with malformed token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/me", headers=headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_no_token(self, client):
        """Test access to protected endpoint without token"""
        response = client.get("/api/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUserInfo:
    """Test user information endpoints"""

    def test_get_current_user(self, client, auth_headers, created_user):
        """Test getting current user information"""
        response = client.get("/api/me", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user_id"] == created_user.user_id
        assert data["username"] == created_user.username
        assert data["email"] == created_user.email

    def test_get_user_unauthorized(self, client):
        """Test getting user info without authentication"""
        response = client.get("/api/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestLogout:
    """Test logout functionality"""

    def test_logout_success(self, client, auth_headers):
        """Test successful logout"""
        response = client.post("/api/logout", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert data["message"] == "Logged out successfully"

    def test_logout_unauthorized(self, client):
        """Test logout without authentication"""
        response = client.post("/api/logout")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED