import pytest
from fastapi import status
from datetime import datetime
import io

class TestFullUserJourney:
    """Test complete user workflows from signup to review"""

    def test_complete_user_workflow(self, client, test_pdf_content, mock_udochat, mock_planreview):
        """Test full user journey: signup -> login -> upload -> chat -> submit review"""
        
        # 1. User Signup
        user_data = {
            "username": "testuser@example.com",
            "password": "TestPassword123!"
        }
        
        signup_response = client.post("/api/signup", json=user_data)
        assert signup_response.status_code == status.HTTP_200_OK
        
        # 2. User Login
        login_response = client.post("/api/login", json=user_data)
        assert login_response.status_code == status.HTTP_200_OK
        login_data = login_response.json()
        
        auth_headers = {"Authorization": f"Bearer {login_data['access_token']}"}
        
        # 3. Upload PDF
        files = {"file": ("test.pdf", io.BytesIO(test_pdf_content), "application/pdf")}
        form_data = {"title": "My Building Plan"}
        
        upload_response = client.post("/api/upload-pdf", files=files, data=form_data, headers=auth_headers)
        assert upload_response.status_code == status.HTTP_200_OK
        upload_data = upload_response.json()
        review_room_id = upload_data["review_room_id"]
        
        # 4. Start Chat Conversation
        chat_data = {
            "message": "I need help with my building plan review",
            "assistant_id": "building_assistant"
        }
        
        chat_response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert chat_response.status_code == status.HTTP_200_OK
        chat_response_data = chat_response.json()
        conversation_id = chat_response_data["conversation_id"]
        
        # 5. Submit Plan for Review
        review_data = {"reviewer_name": "Stormwater Reviewer"}
        
        review_response = client.post(
            f"/api/reviewrooms/{review_room_id}/submit-plan",
            json=review_data,
            headers=auth_headers
        )
        assert review_response.status_code == status.HTTP_200_OK
        
        # 6. Verify all data exists
        # Check conversations
        conversations_response = client.get("/api/conversations", headers=auth_headers)
        assert len(conversations_response.json()["conversations"]) == 1
        
        # Check review rooms
        rooms_response = client.get("/api/reviewrooms", headers=auth_headers)
        assert len(rooms_response.json()["reviewrooms"]) == 1
        
        # Check review comments
        comments_response = client.get(f"/api/reviewrooms/{review_room_id}/comments", headers=auth_headers)
        assert comments_response.status_code == status.HTTP_200_OK
        assert len(comments_response.json()["review_comments"]["comments"]) > 0

    def test_chat_to_conversation_flow(self, client, auth_headers, mock_udochat):
        """Test chat message creates conversation that can be retrieved"""
        
        # Send chat message
        chat_data = {
            "message": "What building codes apply to residential construction?",
            "assistant_id": "building_assistant"
        }
        
        chat_response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert chat_response.status_code == status.HTTP_200_OK
        chat_data_response = chat_response.json()
        conversation_id = chat_data_response["conversation_id"]
        
        # Retrieve conversation
        conv_response = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers)
        assert conv_response.status_code == status.HTTP_200_OK
        conv_data = conv_response.json()
        
        # Verify conversation contains chat messages
        assert len(conv_data["messages"]) == 2
        assert conv_data["messages"][0]["role"] == "user"
        assert conv_data["messages"][0]["content"] == "What building codes apply to residential construction?"
        assert conv_data["messages"][1]["role"] == "assistant"
        assert conv_data["messages"][1]["content"] == "This is a test AI response"
        
        # Continue conversation
        follow_up_data = {
            "message": "Can you be more specific about electrical codes?",
            "conversation_id": conversation_id
        }
        
        follow_up_response = client.post("/api/chat", json=follow_up_data, headers=auth_headers)
        assert follow_up_response.status_code == status.HTTP_200_OK
        
        # Retrieve updated conversation
        updated_conv_response = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers)
        updated_conv_data = updated_conv_response.json()
        
        # Should now have 4 messages
        assert len(updated_conv_data["messages"]) == 4


class TestMultiUserIsolation:
    """Test that multiple users don't see each other's data"""

    def test_multiple_users_isolation(self, client, test_pdf_content, mock_udochat, mock_planreview):
        """Test that multiple users operating simultaneously don't interfere"""
        
        # Create two users
        user1_data = {"username": "user1@example.com", "password": "Password123!"}
        user2_data = {"username": "user2@example.com", "password": "Password123!"}
        
        # Signup both users
        client.post("/api/signup", json=user1_data)
        client.post("/api/signup", json=user2_data)
        
        # Login both users
        user1_login = client.post("/api/login", json=user1_data)
        user2_login = client.post("/api/login", json=user2_data)
        
        user1_headers = {"Authorization": f"Bearer {user1_login.json()['access_token']}"}
        user2_headers = {"Authorization": f"Bearer {user2_login.json()['access_token']}"}
        
        # User 1 uploads PDF
        files1 = {"file": ("user1.pdf", io.BytesIO(test_pdf_content), "application/pdf")}
        form1 = {"title": "User 1 Plan"}
        client.post("/api/upload-pdf", files=files1, data=form1, headers=user1_headers)
        
        # User 2 uploads PDF
        files2 = {"file": ("user2.pdf", io.BytesIO(test_pdf_content), "application/pdf")}
        form2 = {"title": "User 2 Plan"}
        client.post("/api/upload-pdf", files=files2, data=form2, headers=user2_headers)
        
        # User 1 starts chat
        chat1_data = {"message": "User 1 chat message"}
        client.post("/api/chat", json=chat1_data, headers=user1_headers)
        
        # User 2 starts chat
        chat2_data = {"message": "User 2 chat message"}
        client.post("/api/chat", json=chat2_data, headers=user2_headers)
        
        # Verify isolation
        # User 1 should only see their own data
        user1_rooms = client.get("/api/reviewrooms", headers=user1_headers)
        user1_conversations = client.get("/api/conversations", headers=user1_headers)
        
        assert len(user1_rooms.json()["reviewrooms"]) == 1
        assert user1_rooms.json()["reviewrooms"][0]["title"] == "User 1 Plan"
        assert len(user1_conversations.json()["conversations"]) == 1
        
        # User 2 should only see their own data
        user2_rooms = client.get("/api/reviewrooms", headers=user2_headers)
        user2_conversations = client.get("/api/conversations", headers=user2_headers)
        
        assert len(user2_rooms.json()["reviewrooms"]) == 1
        assert user2_rooms.json()["reviewrooms"][0]["title"] == "User 2 Plan"
        assert len(user2_conversations.json()["conversations"]) == 1

    def test_concurrent_user_operations(self, client, test_pdf_content, mock_udochat):
        """Test multiple users performing operations concurrently"""
        
        # Create multiple users
        users = []
        for i in range(3):
            user_data = {"username": f"user{i}@example.com", "password": "Password123!"}
            client.post("/api/signup", json=user_data)
            
            login_response = client.post("/api/login", json=user_data)
            headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
            users.append((user_data, headers))
        
        # All users perform operations simultaneously
        for i, (user_data, headers) in enumerate(users):
            # Upload PDF
            files = {"file": (f"user{i}.pdf", io.BytesIO(test_pdf_content), "application/pdf")}
            form = {"title": f"User {i} Plan"}
            client.post("/api/upload-pdf", files=files, data=form, headers=headers)
            
            # Start chat
            chat_data = {"message": f"User {i} needs help"}
            client.post("/api/chat", json=chat_data, headers=headers)
        
        # Verify each user has exactly their own data
        for i, (user_data, headers) in enumerate(users):
            rooms_response = client.get("/api/reviewrooms", headers=headers)
            conversations_response = client.get("/api/conversations", headers=headers)
            
            assert len(rooms_response.json()["reviewrooms"]) == 1
            assert len(conversations_response.json()["conversations"]) == 1
            
            # Verify content is specific to user
            room_title = rooms_response.json()["reviewrooms"][0]["title"]
            assert f"User {i}" in room_title


class TestSessionPersistence:
    """Test token persistence and session management"""

    def test_session_persistence(self, client, created_user, test_user_data, mock_planreview):
        """Test that token remains valid across multiple requests"""
        
        # Login to get token
        login_response = client.post("/api/login", json=test_user_data)
        assert login_response.status_code == status.HTTP_200_OK
        token_data = login_response.json()
        
        auth_headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        
        # Make multiple authenticated requests
        requests_to_test = [
            ("GET", "/api/me"),
            ("GET", "/api/conversations"),
            ("GET", "/api/reviewrooms"),
            ("GET", "/api/reviewers"),
        ]
        
        for method, endpoint in requests_to_test:
            if method == "GET":
                response = client.get(endpoint, headers=auth_headers)
            # Add other methods as needed
            
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
            # 404 is acceptable for some endpoints when no data exists

    def test_token_expiration_workflow(self, client, created_user):
        """Test workflow when token expires"""
        from api.dependencies.auth import SECRET_KEY, ALGORITHM
        import jwt
        from datetime import timedelta
        
        # Create expired token
        expired_data = {
            "sub": created_user.username,
            "user_id": created_user.user_id,
            "exp": datetime.utcnow() - timedelta(minutes=1)
        }
        expired_token = jwt.encode(expired_data, SECRET_KEY, algorithm=ALGORITHM)
        expired_headers = {"Authorization": f"Bearer {expired_token}"}
        
        # Try to access protected endpoint with expired token
        response = client.get("/api/me", headers=expired_headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # User should be able to login again to get new token
        user_data = {"username": created_user.username, "password": "TestPassword123!"}
        new_login_response = client.post("/api/login", json=user_data)
        assert new_login_response.status_code == status.HTTP_200_OK
        
        # New token should work
        new_token = new_login_response.json()["access_token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}
        
        response = client.get("/api/me", headers=new_headers)
        assert response.status_code == status.HTTP_200_OK


class TestErrorHandling:
    """Test error handling across different scenarios"""

    def test_database_error_handling(self, client, auth_headers):
        """Test API behavior when database operations fail"""
        
        # Test with a malformed conversation ID that would cause database issues
        response = client.get("/api/conversations/999999999", headers=auth_headers)
        
        # Should return 404 (not found) or 500, not crash
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_service_unavailable_graceful_handling(self, client, auth_headers, mocker):
        """Test graceful handling when external services are unavailable"""
        
        # Mock both services as unavailable
        mocker.patch('api.routers.chat.udochat', None)
        mocker.patch('api.routers.reviewrooms.planreview', None)
        
        # Chat should fail gracefully
        chat_data = {"message": "Test message"}
        chat_response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert chat_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Chat service not available" in chat_response.json()["detail"]
        
        # Reviewer endpoint should fail gracefully
        reviewers_response = client.get("/api/reviewers", headers=auth_headers)
        assert reviewers_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Reviewer service not available" in reviewers_response.json()["detail"]

    def test_malformed_request_handling(self, client, auth_headers):
        """Test handling of malformed requests"""
        
        # Malformed JSON in chat request
        response = client.post(
            "/api/chat", 
            data="invalid json", 
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]
        
        # Missing required fields
        response = client.post("/api/chat", json={}, headers=auth_headers)
        assert response.status_code in [status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_400_BAD_REQUEST]


class TestDataConsistency:
    """Test data consistency across operations"""

    def test_conversation_message_consistency(self, client, auth_headers, mock_udochat, db_session):
        """Test that conversation data remains consistent across operations"""
        
        # Start chat
        chat_data = {"message": "First message"}
        chat_response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        conversation_id = chat_response.json()["conversation_id"]
        
        # Continue conversation
        follow_up_data = {"message": "Second message", "conversation_id": conversation_id}
        client.post("/api/chat", json=follow_up_data, headers=auth_headers)
        
        # Retrieve conversation via different endpoints
        direct_response = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers)
        list_response = client.get("/api/conversations", headers=auth_headers)
        
        # Data should be consistent
        direct_messages = direct_response.json()["messages"]
        list_conversation = list_response.json()["conversations"][0]
        
        assert len(direct_messages) == 4  # 2 user + 2 assistant messages
        assert list_conversation["conversation_id"] == conversation_id

    def test_review_room_pdf_consistency(self, client, auth_headers, test_pdf_content, db_session):
        """Test PDF data consistency across operations"""
        
        # Upload PDF
        files = {"file": ("test.pdf", io.BytesIO(test_pdf_content), "application/pdf")}
        form_data = {"title": "Consistency Test"}
        
        upload_response = client.post("/api/upload-pdf", files=files, data=form_data, headers=auth_headers)
        room_id = upload_response.json()["review_room_id"]
        
        # Retrieve PDF info
        info_response = client.get(f"/api/reviewrooms/{room_id}/pdf/info", headers=auth_headers)
        
        # Download actual PDF
        pdf_response = client.get(f"/api/reviewrooms/{room_id}/pdf", headers=auth_headers)
        
        # Check consistency
        assert info_response.json()["has_pdf"] is True
        assert pdf_response.status_code == status.HTTP_200_OK
        assert pdf_response.content == test_pdf_content