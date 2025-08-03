"""
Integration tests for REST API endpoints.
Tests conversation creation, retrieval, join/leave operations, health, and auth.
"""

import asyncio
import uuid
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
import httpx

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../code/python'))

from chat.schemas import (
    ChatMessage, MessageType, MessageStatus,
    ParticipantInfo, ParticipantType, QueueFullError
)


# Test Configuration
API_BASE_URL = "http://localhost:8000"
TEST_HEADERS = {"Content-Type": "application/json"}


@pytest.fixture
def valid_oauth_token():
    """Valid OAuth token for testing."""
    return "Bearer valid_oauth_token_123"


@pytest.fixture
def valid_email_token():
    """Valid email-based token for testing."""
    return "Bearer valid_email_token_456"


@pytest.fixture
def invalid_token():
    """Invalid token for testing.""" 
    return "Bearer invalid_token_xyz"


@pytest.fixture
def expired_token():
    """Expired token for testing."""
    return "Bearer expired_token_abc"


@pytest.fixture
async def api_client():
    """Create HTTP client for API testing."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
def sample_participant():
    """Sample participant data."""
    return {
        "user_id": "user_test_123",
        "name": "Test User",
        "email": "test@example.com"
    }


@pytest.fixture
def multi_participants():
    """Multiple participant data for testing."""
    return [
        {
            "user_id": "user_alice_123", 
            "name": "Alice Smith",
            "email": "alice@example.com"
        },
        {
            "user_id": "user_bob_456",
            "name": "Bob Jones", 
            "email": "bob@example.com"
        },
        {
            "user_id": "user_charlie_789",
            "name": "Charlie Brown",
            "email": "charlie@example.com"
        }
    ]


@pytest.mark.integration
@pytest.mark.asyncio
class TestConversationCreation:
    """Test conversation creation endpoints."""
    
    async def test_single_participant_conversation(self):
        """Test creating a single participant conversation."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            payload = {
                "title": "Weather Discussion",
                "sites": ["weather.com"],
                "mode": "list",
                "participants": [{
                    "user_id": "authenticated_user",
                    "name": "Test User"
                }]
            ,
                "enable_ai": False}
            
            response = await client.post("/chat/create", json=payload, headers=headers)
            
            assert response.status_code == 201
            data = response.json()
            assert "conversation_id" in data
            assert data["title"] == "Weather Discussion"
            assert len(data["participants"]) >= 1
    async def test_multi_participant_conversation(self):
        """Test creating a multi-participant conversation."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            payload = {
                "title": "Team Discussion",
                "sites": ["example.com"],
                "mode": "multi",
                "participants": [
                    {
                        "user_id": "authenticated_user",
                        "name": "Alice"
                    },
                    {
                        "user_id": "bob_456",
                        "name": "Bob"
                    }
                ],
                "enable_ai": True
            }
            
            response = await client.post("/chat/create", json=payload, headers=headers)
            
            assert response.status_code == 201
            data = response.json()
            assert len(data["participants"]) >= 2

    async def test_invalid_participant_data(self):
        """Test validation of participant data."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # Missing required field
            payload = {
                "title": "Invalid Test",
                "sites": ["example.com"],
                "participants": [{
                    "name": "Missing ID"
                    # Missing participantId
                }]
            ,
                "enable_ai": False}
            
            response = await client.post("/chat/create", json=payload, headers=headers)
            
            assert response.status_code == 400

    async def test_missing_required_fields(self):
        """Test missing required fields in request."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # Missing title
            payload = {
                "participants": [{
                    "user_id": "test_user",
                    "name": "Test User"
                }]
            ,
                "enable_ai": False}
            
            response = await client.post("/chat/create", json=payload, headers=headers)
            
            assert response.status_code == 400

    async def test_participant_limit_enforcement(self):
        """Test participant limit enforcement."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # Try to create with too many participants (assuming limit is 10)
            participants = []
            for i in range(15):
                participants.append({
                    "user_id": f"user_{i}",
                    "name": f"User {i}"
                })
            
            payload = {
                "title": "Too Many Participants",
                "participants": participants
            }
            
            response = await client.post("/chat/create", json=payload, headers=headers)
            
            # Should either fail or truncate to max allowed
            assert response.status_code in [400, 201]
            if response.status_code == 201:
                data = response.json()
                assert len(data["participants"]) <= 10
    
        
    async def test_join_when_already_participant(self):
        """Test joining when already a participant (409 conflict)."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # First create a conversation with the user
            create_payload = {
                "title": "Test Conversation",
                "participants": [{
                    "user_id": "test_user_123",
                    "name": "Test User"
                }]
            ,
                "enable_ai": False}
            create_response = await client.post("/chat/create", json=create_payload, headers=headers)
            conversation_id = create_response.json()["conversation_id"]
            
            # Try to join again with same user
            join_payload = {
                "participant": {"user_id": "test_user_123", "name": "Test User"}
            }
            response = await client.post(f"/chat/{conversation_id}/join", json=join_payload, headers=headers)
            
            assert response.status_code == 409
            assert "Already a participant" in response.json()["error"]
    
    

@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorScenarios:
    """Test error scenarios and handling."""
    
    async def test_404_for_nonexistent_conversations(self):
        """Test 404 for non-existent conversations."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # Try to get a non-existent conversation
            response = await client.get("/chat/conversations/nonexistent_conv_id", headers=headers)
            
            assert response.status_code == 404
    
    async def test_429_rate_limiting(self):
        """Test rate limiting (if implemented)."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # Make many requests quickly to trigger rate limit (if implemented)
            # Note: This might not trigger on a test server without rate limiting
            for i in range(20):
                payload = {
                    "title": f"Rate Test {i}",
                    "participants": [{
                        "user_id": "test_user",
                        "name": "Test User"
                    }]
                ,
                "enable_ai": False}
                response = await client.post("/chat/create", json=payload, headers=headers)
                
                if response.status_code == 429:
                    assert "error" in response.json()
                    break
    
    async def test_500_server_errors_with_retry_guidance(self):
        """Test server error handling."""
        # Skip this test as we can't force a 500 error on a working server
        pytest.skip("Cannot test 500 errors on a working server")
    
    async def test_malformed_request_handling(self):
        """Test malformed request handling."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # Send malformed JSON
            response = await client.post(
                "/chat/create",
                content='{"invalid": json}',  # Malformed JSON
                headers=headers
            )
            
            assert response.status_code == 400
    
    async def test_network_timeout_handling(self):
        """Test network timeout handling."""
        # Create a client with very short timeout
        async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=0.001) as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            with pytest.raises(httpx.TimeoutException):
                await client.get("/chat/my-conversations", headers=headers)

@pytest.mark.integration
@pytest.mark.asyncio
class TestJoinLeaveOperations:
    """Test join and leave operations."""
    
    async def test_join_existing_conversation(self):
        """Test joining an existing conversation."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # Create a conversation
            create_payload = {
                "title": "Test Conversation",
                "participants": [{
                    "user_id": "creator_123",
                    "name": "Creator"
                }]
            ,
                "enable_ai": False}
            create_response = await client.post("/chat/create", json=create_payload, headers=headers)
            conversation_id = create_response.json()["conversation_id"]
            
            # Join as a new user
            join_payload = {
                "participant": {"user_id": "new_user_456", "name": "New User"}
            }
            response = await client.post(f"/chat/{conversation_id}/join", json=join_payload, headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["conversation"]["participants"]) >= 2
    
    async def test_leave_conversation(self):
        """Test leaving a conversation."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # Create a conversation with multiple participants
            create_payload = {
                "title": "Test Conversation",
                "participants": [
                    {
                        "user_id": "user1_123",
                        "name": "User 1"
                    },
                    {
                        "user_id": "user2_456",
                        "name": "User 2"
                    }
                ]
            ,
                "enable_ai": False}
            create_response = await client.post("/chat/create", json=create_payload, headers=headers)
            conversation_id = create_response.json()["conversation_id"]
            
            # Leave the conversation as user1
            headers["X-User-Id"] = "user1_123"  # Identify which user is leaving
            response = await client.delete(f"/chat/{conversation_id}/leave", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


@pytest.mark.integration
@pytest.mark.asyncio
class TestConversationRetrieval:
    """Test conversation retrieval endpoints."""
    
    async def test_get_conversation_details(self):
        """Test getting conversation details."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # First create a conversation
            create_payload = {
                "title": "Test Conversation",
                "participants": [{
                    "user_id": "test_user_123",
                    "name": "Test User"
                }]
            ,
                "enable_ai": False}
            create_response = await client.post("/chat/create", json=create_payload, headers=headers)
            conversation_id = create_response.json()["conversation_id"]
            
            # Get the conversation details
            response = await client.get(f"/chat/conversations/{conversation_id}", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == conversation_id
            assert data["title"] == "Test Conversation"
            assert len(data["participants"]) >= 1
    
    async def test_list_all_conversations_for_user(self):
        """Test listing user's conversations."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            headers = {
                "Authorization": "Bearer test_token_123",
                "Content-Type": "application/json"
            }
            
            # Now list conversations
            response = await client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert 'conversations' in data
            assert isinstance(data['conversations'], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
