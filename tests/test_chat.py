import pytest
from fastapi import status
from datetime import datetime

class TestChatFunctionality:
    """Test chat functionality with AI integration"""

    def test_chat_new_conversation(self, client, auth_headers, mock_udochat):
        """Test starting a new chat conversation"""
        chat_data = {
            "message": "Hello, I need help with my project",
            "assistant_id": "test_assistant",
            "thread_id": None,
            "conversation_id": None
        }
        
        response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "success"
        assert data["response"] == "This is a test AI response"
        assert "conversation_id" in data
        
        # Verify udochat was called
        mock_udochat.create_flask_response.assert_called_once_with(
            "Hello, I need help with my project",
            prompt_id="test_assistant",
            conversation_id=None
        )

    def test_chat_existing_conversation(self, client, auth_headers, mock_udochat, test_conversation):
        """Test continuing existing conversation"""
        chat_data = {
            "message": "Follow-up question",
            "assistant_id": "test_assistant",
            "thread_id": "existing_thread",
            "conversation_id": test_conversation.conversation_id
        }
        
        response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "success"
        assert data["conversation_id"] == test_conversation.conversation_id

    def test_chat_empty_message(self, client, auth_headers):
        """Test sending empty message"""
        chat_data = {
            "message": "",
            "assistant_id": "test_assistant"
        }
        
        response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Message is required" in data["detail"]

    def test_chat_unauthorized(self, client, mock_udochat):
        """Test chat without authentication"""
        chat_data = {
            "message": "Hello",
            "assistant_id": "test_assistant"
        }
        
        response = client.post("/api/chat", json=chat_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_chat_conversation_saved(self, client, auth_headers, mock_udochat, db_session):
        """Test that chat conversation is saved to database"""
        chat_data = {
            "message": "Test message for saving",
            "assistant_id": "test_assistant"
        }
        
        response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify conversation was created in database
        from api.utils.models import Conversations
        conversation = db_session.query(Conversations).filter(
            Conversations.conversation_id == data["conversation_id"]
        ).first()
        
        assert conversation is not None
        assert len(conversation.conversation_history) == 2  # User message + AI response
        assert conversation.conversation_history[0]["role"] == "user"
        assert conversation.conversation_history[0]["content"] == "Test message for saving"
        assert conversation.conversation_history[1]["role"] == "assistant"
        assert conversation.conversation_history[1]["content"] == "This is a test AI response"

    def test_chat_service_unavailable(self, client, auth_headers, mocker):
        """Test when udochat module is unavailable"""
        # Mock udochat as None (service unavailable)
        mocker.patch('api.routers.chat.udochat', None)
        
        chat_data = {
            "message": "Hello",
            "assistant_id": "test_assistant"
        }
        
        response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "Chat service not available" in data["detail"]


class TestConversationSaving:
    """Test conversation saving functionality"""

    def test_save_new_conversation(self, client, auth_headers, mock_udochat, db_session):
        """Test creating new conversation in database"""
        chat_data = {
            "message": "This is a new conversation",
            "assistant_id": "test_assistant"
        }
        
        response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Check conversation was created
        from api.utils.models import Conversations
        conversations = db_session.query(Conversations).all()
        assert len(conversations) == 1
        
        conversation = conversations[0]
        assert conversation.conversation_id == data["conversation_id"]
        assert len(conversation.conversation_history) == 2

    def test_update_existing_conversation(self, client, auth_headers, mock_udochat, test_conversation, db_session):
        """Test appending to existing conversation"""
        original_history_length = len(test_conversation.conversation_history)
        
        chat_data = {
            "message": "Follow-up message",
            "conversation_id": test_conversation.conversation_id
        }
        
        response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        # Refresh conversation from database
        db_session.refresh(test_conversation)
        
        # Should have 2 more messages (user + assistant)
        assert len(test_conversation.conversation_history) == original_history_length + 2
        
        # Check new messages were appended
        new_user_msg = test_conversation.conversation_history[-2]
        new_ai_msg = test_conversation.conversation_history[-1]
        
        assert new_user_msg["role"] == "user"
        assert new_user_msg["content"] == "Follow-up message"
        assert new_ai_msg["role"] == "assistant"
        assert new_ai_msg["content"] == "This is a test AI response"

    def test_conversation_title_generation(self, client, auth_headers, mock_udochat, db_session):
        """Test proper title generation from first message"""
        long_message = "This is a very long message that should be truncated when used as a conversation title because it exceeds the maximum length limit"
        
        chat_data = {
            "message": long_message,
            "assistant_id": "test_assistant"
        }
        
        response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Check conversation title
        from api.utils.models import Conversations
        conversation = db_session.query(Conversations).filter(
            Conversations.conversation_id == data["conversation_id"]
        ).first()
        
        # Title should be truncated to 50 characters + "..."
        assert len(conversation.title) == 53  # 50 chars + "..."
        assert conversation.title.endswith("...")
        assert conversation.title.startswith("This is a very long message that should be trunca")

    def test_conversation_timestamp(self, client, auth_headers, mock_udochat, db_session):
        """Test proper timestamp handling in messages"""
        chat_data = {
            "message": "Test timestamp",
            "assistant_id": "test_assistant"
        }
        
        before_request = datetime.now()
        response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        after_request = datetime.now()
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Check message timestamps
        from api.utils.models import Conversations
        conversation = db_session.query(Conversations).filter(
            Conversations.conversation_id == data["conversation_id"]
        ).first()
        
        user_timestamp = datetime.fromisoformat(conversation.conversation_history[0]["timestamp"])
        ai_timestamp = datetime.fromisoformat(conversation.conversation_history[1]["timestamp"])
        
        # Timestamps should be within request timeframe
        assert before_request <= user_timestamp <= after_request
        assert before_request <= ai_timestamp <= after_request
        
        # AI timestamp should be after user timestamp
        assert ai_timestamp >= user_timestamp

    def test_chat_error_handling(self, client, auth_headers, mock_udochat):
        """Test chat error handling when AI service fails"""
        # Mock AI service to return error
        mock_udochat.create_flask_response.return_value = {
            "status": "error",
            "error": "AI service temporarily unavailable"
        }
        
        chat_data = {
            "message": "Test error handling",
            "assistant_id": "test_assistant"
        }
        
        response = client.post("/api/chat", json=chat_data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "error"
        assert data["error"] == "AI service temporarily unavailable"