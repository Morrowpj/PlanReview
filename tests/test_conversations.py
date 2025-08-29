import pytest
from fastapi import status
from datetime import datetime

class TestGetConversations:
    """Test getting user conversations"""

    def test_get_empty_conversations(self, client, auth_headers):
        """Test user with no conversations"""
        response = client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert data["conversations"] == []

    def test_get_user_conversations(self, client, auth_headers, test_conversation):
        """Test user with conversations"""
        response = client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert len(data["conversations"]) == 1
        
        conversation = data["conversations"][0]
        assert conversation["conversation_id"] == test_conversation.conversation_id
        assert conversation["title"] == test_conversation.title
        assert conversation["conversation_type"] == "chat"
        assert conversation["is_favorite"] is False

    def test_conversations_ordering(self, client, auth_headers, created_user, db_session):
        """Test conversations ordered by last_message_at"""
        from api.utils.models import Conversations
        
        # Create multiple conversations with different timestamps
        older_conversation = Conversations(
            title="Older Conversation",
            user_id=created_user.user_id,
            conversation_history=[],
            last_message_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        newer_conversation = Conversations(
            title="Newer Conversation",
            user_id=created_user.user_id,
            conversation_history=[],
            last_message_at=datetime(2023, 1, 2, 12, 0, 0)
        )
        
        db_session.add(older_conversation)
        db_session.add(newer_conversation)
        db_session.commit()
        
        response = client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Should be ordered by newest first
        assert len(data["conversations"]) == 2
        assert data["conversations"][0]["title"] == "Newer Conversation"
        assert data["conversations"][1]["title"] == "Older Conversation"

    def test_get_conversations_unauthorized(self, client):
        """Test getting conversations without authentication"""
        response = client.get("/api/conversations")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_conversations_user_isolation(self, client, auth_headers, second_user, db_session):
        """Test users only see their own conversations"""
        from api.utils.models import Conversations
        
        # Create conversation for second user
        other_user, _ = second_user
        other_conversation = Conversations(
            title="Other User's Conversation",
            user_id=other_user.user_id,
            conversation_history=[],
            last_message_at=datetime.utcnow()
        )
        db_session.add(other_conversation)
        db_session.commit()
        
        # First user should not see second user's conversation
        response = client.get("/api/conversations", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert len(data["conversations"]) == 0


class TestGetConversationMessages:
    """Test getting specific conversation messages"""

    def test_get_conversation_messages(self, client, auth_headers, test_conversation):
        """Test getting valid conversation messages"""
        conversation_id = test_conversation.conversation_id
        response = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert data["conversation_id"] == conversation_id
        assert data["title"] == test_conversation.title
        assert len(data["messages"]) == 2
        
        # Check message structure
        message = data["messages"][0]
        assert "role" in message
        assert "content" in message
        assert "timestamp" in message
        assert message["role"] == "user"
        assert message["content"] == "Hello"

    def test_get_nonexistent_conversation(self, client, auth_headers):
        """Test getting non-existent conversation"""
        response = client.get("/api/conversations/99999", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"]

    def test_get_other_user_conversation(self, client, auth_headers, second_user, db_session):
        """Test accessing another user's conversation"""
        from api.utils.models import Conversations
        
        # Create conversation for second user
        other_user, _ = second_user
        other_conversation = Conversations(
            title="Other User's Conversation",
            user_id=other_user.user_id,
            conversation_history=[{"role": "user", "content": "test", "timestamp": "2023-01-01T12:00:00"}],
            last_message_at=datetime.utcnow()
        )
        db_session.add(other_conversation)
        db_session.commit()
        db_session.refresh(other_conversation)
        
        # Try to access other user's conversation
        response = client.get(f"/api/conversations/{other_conversation.conversation_id}", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_empty_conversation_history(self, client, auth_headers, created_user, db_session):
        """Test conversation with no message history"""
        from api.utils.models import Conversations
        
        empty_conversation = Conversations(
            title="Empty Conversation",
            user_id=created_user.user_id,
            conversation_history=None,
            last_message_at=datetime.utcnow()
        )
        db_session.add(empty_conversation)
        db_session.commit()
        db_session.refresh(empty_conversation)
        
        response = client.get(f"/api/conversations/{empty_conversation.conversation_id}", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["messages"] == []

    def test_conversation_message_format(self, client, auth_headers, created_user, db_session):
        """Test proper message structure in conversation"""
        from api.utils.models import Conversations
        
        conversation = Conversations(
            title="Test Message Format",
            user_id=created_user.user_id,
            conversation_history=[
                {
                    "role": "user",
                    "content": "Hello AI",
                    "timestamp": "2023-01-01T12:00:00"
                },
                {
                    "role": "assistant", 
                    "content": "Hello! How can I help you?",
                    "timestamp": "2023-01-01T12:00:05"
                }
            ],
            last_message_at=datetime.utcnow()
        )
        db_session.add(conversation)
        db_session.commit()
        db_session.refresh(conversation)
        
        response = client.get(f"/api/conversations/{conversation.conversation_id}", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        messages = data["messages"]
        assert len(messages) == 2
        
        # Check first message
        user_msg = messages[0]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "Hello AI"
        assert user_msg["timestamp"] == "2023-01-01T12:00:00"
        
        # Check second message
        assistant_msg = messages[1]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["content"] == "Hello! How can I help you?"
        assert assistant_msg["timestamp"] == "2023-01-01T12:00:05"

    def test_get_conversation_unauthorized(self, client):
        """Test getting conversation without authentication"""
        response = client.get("/api/conversations/1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED