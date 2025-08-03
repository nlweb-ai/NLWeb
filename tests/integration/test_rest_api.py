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
from aioresponses import aioresponses

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../code/python'))

from chat.schemas import (
    ChatMessage, MessageType, MessageStatus,
    ParticipantInfo, ParticipantType, QueueFullError
)


# Test Configuration
API_BASE_URL = "http://localhost:8080"
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
        "participantId": "user_test_123",
        "displayName": "Test User",
        "email": "test@example.com"
    }


@pytest.fixture
def multi_participants():
    """Multiple participant data for testing."""
    return [
        {
            "participantId": "user_alice_123", 
            "displayName": "Alice Smith",
            "email": "alice@example.com"
        },
        {
            "participantId": "user_bob_456",
            "displayName": "Bob Jones", 
            "email": "bob@example.com"
        },
        {
            "participantId": "user_charlie_789",
            "displayName": "Charlie Brown",
            "email": "charlie@example.com"
        }
    ]


@pytest.mark.integration
@pytest.mark.asyncio
class TestConversationCreation:
    """Test conversation creation endpoints."""
    
    async def test_single_participant_conversation(self, api_client, valid_oauth_token, sample_participant):
        """Test creating a single participant conversation."""
        with aioresponses() as mock_resp:
            # Mock successful creation
            conversation_id = f"conv_{uuid.uuid4().hex[:8]}"
            expected_response = {
                "id": conversation_id,
                "title": "Weather Discussion",
                "sites": ["weather.com"],
                "mode": "list",
                "participants": [sample_participant],
                "created_at": datetime.utcnow().isoformat()
            }
            
            mock_resp.post(
                f"{API_BASE_URL}/chat/create",
                payload=expected_response,
                status=201
            )
            
            # Create conversation
            payload = {
                "title": "Weather Discussion",
                "sites": ["weather.com"],
                "mode": "list",
                "participant": sample_participant
            }
            
            headers = {**TEST_HEADERS, "Authorization": valid_oauth_token}
            response = await api_client.post("/chat/create", json=payload, headers=headers)
            
            assert response.status_code == 201
            data = response.json()
            assert data["title"] == "Weather Discussion"
            assert data["sites"] == ["weather.com"]
            assert data["mode"] == "list"
            assert len(data["participants"]) == 1
            assert data["participants"][0]["participantId"] == sample_participant["participantId"]
    
    async def test_multi_participant_conversation(self, api_client, valid_oauth_token, multi_participants):
        """Test creating conversation with 2-5 humans."""
        with aioresponses() as mock_resp:
            conversation_id = f"conv_{uuid.uuid4().hex[:8]}"
            expected_response = {
                "id": conversation_id,
                "title": "Team Discussion",
                "sites": ["docs.google.com"],
                "mode": "generate",
                "participants": multi_participants[:3],  # 3 participants
                "created_at": datetime.utcnow().isoformat()
            }
            
            mock_resp.post(
                f"{API_BASE_URL}/chat/create",
                payload=expected_response,
                status=201
            )
            
            payload = {
                "title": "Team Discussion",
                "sites": ["docs.google.com"],
                "mode": "generate",
                "participant": multi_participants[0],
                "additional_participants": multi_participants[1:3]
            }
            
            headers = {**TEST_HEADERS, "Authorization": valid_oauth_token}
            response = await api_client.post("/chat/create", json=payload, headers=headers)
            
            assert response.status_code == 201
            data = response.json()
            assert len(data["participants"]) == 3
    
    async def test_invalid_participant_data(self, api_client, valid_oauth_token):
        """Test creation with invalid participant data."""
        with aioresponses() as mock_resp:
            mock_resp.post(
                f"{API_BASE_URL}/chat/create",
                payload={"error": "Invalid participant data", "code": "INVALID_PARTICIPANT"},
                status=400
            )
            
            # Missing required fields
            payload = {
                "title": "Test Conversation",
                "sites": ["example.com"],
                "mode": "list",
                "participant": {
                    "participantId": "user_123"
                    # Missing displayName and email
                }
            }
            
            headers = {**TEST_HEADERS, "Authorization": valid_oauth_token}
            response = await api_client.post("/chat/create", json=payload, headers=headers)
            
            assert response.status_code == 400
            assert "Invalid participant data" in response.json()["error"]
    
    async def test_missing_required_fields(self, api_client, valid_oauth_token, sample_participant):
        """Test creation with missing required fields."""
        with aioresponses() as mock_resp:
            mock_resp.post(
                f"{API_BASE_URL}/chat/create",
                payload={"error": "Missing required field: sites", "code": "MISSING_FIELD"},
                status=400
            )
            
            # Missing sites field
            payload = {
                "title": "Incomplete Conversation",
                "mode": "list",
                "participant": sample_participant
                # Missing sites
            }
            
            headers = {**TEST_HEADERS, "Authorization": valid_oauth_token}
            response = await api_client.post("/chat/create", json=payload, headers=headers)
            
            assert response.status_code == 400
            assert "Missing required field" in response.json()["error"]
    
    async def test_participant_limit_enforcement(self, api_client, valid_oauth_token):
        """Test participant limit enforcement."""
        with aioresponses() as mock_resp:
            mock_resp.post(
                f"{API_BASE_URL}/chat/create",
                payload={
                    "error": "Participant limit exceeded (100 max)",
                    "code": "PARTICIPANT_LIMIT_EXCEEDED"
                },
                status=429
            )
            
            # Try to create with too many participants
            participants = [
                {"participantId": f"user_{i}", "displayName": f"User {i}", "email": f"user{i}@example.com"}
                for i in range(101)  # Exceed limit
            ]
            
            payload = {
                "title": "Overcrowded Conversation",
                "sites": ["example.com"],
                "mode": "list",
                "participant": participants[0],
                "additional_participants": participants[1:]
            }
            
            headers = {**TEST_HEADERS, "Authorization": valid_oauth_token}
            response = await api_client.post("/chat/create", json=payload, headers=headers)
            
            assert response.status_code == 429
            assert "Participant limit exceeded" in response.json()["error"]


@pytest.mark.integration
@pytest.mark.asyncio
class TestConversationRetrieval:
    """Test conversation retrieval endpoints."""
    
    async def test_list_all_conversations_for_user(self, api_client, valid_oauth_token):
        """Test listing all conversations for a user."""
        with aioresponses() as mock_resp:
            expected_conversations = [
                {
                    "id": "conv_001",
                    "title": "First Conversation",
                    "sites": ["site1.com"],
                    "mode": "list",
                    "participants": [{"participantId": "user_123", "displayName": "User"}],
                    "created_at": "2024-01-01T10:00:00Z",
                    "updated_at": "2024-01-01T11:00:00Z",
                    "last_message_preview": "Last message content...",
                    "participant_count": 2,
                    "unread_count": 0
                },
                {
                    "id": "conv_002",
                    "title": "Second Conversation",
                    "sites": ["site2.com"],
                    "mode": "summarize",
                    "participants": [{"participantId": "user_123", "displayName": "User"}],
                    "created_at": "2024-01-01T09:00:00Z",
                    "updated_at": "2024-01-01T10:30:00Z",
                    "last_message_preview": "Another message...",
                    "participant_count": 3,
                    "unread_count": 2
                }
            ]
            
            mock_resp.get(
                f"{API_BASE_URL}/chat/my-conversations",
                payload=expected_conversations,
                status=200
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["id"] == "conv_001"
            assert data[1]["id"] == "conv_002"
            assert all("last_message_preview" in conv for conv in data)
    
    async def test_get_specific_conversation_with_full_history(self, api_client, valid_oauth_token):
        """Test getting specific conversation with full message history."""
        with aioresponses() as mock_resp:
            conversation_id = "conv_detail_001"
            expected_conversation = {
                "id": conversation_id,
                "title": "Detailed Conversation",
                "sites": ["example.com"],
                "mode": "generate",
                "participants": [
                    {"participantId": "user_123", "displayName": "Alice", "type": "human", "isOnline": True},
                    {"participantId": "user_456", "displayName": "Bob", "type": "human", "isOnline": False},
                    {"participantId": "nlweb_1", "displayName": "AI Assistant", "type": "ai", "isOnline": True}
                ],
                "messages": [
                    {
                        "id": "msg_001",
                        "sequence_id": 1,
                        "sender_id": "user_123",
                        "content": "Hello everyone",
                        "timestamp": "2024-01-01T10:00:00Z",
                        "type": "message",
                        "status": "delivered"
                    },
                    {
                        "id": "msg_002",
                        "sequence_id": 2,
                        "sender_id": "user_456",
                        "content": "Hi Alice!",
                        "timestamp": "2024-01-01T10:01:00Z",
                        "type": "message",
                        "status": "delivered"
                    },
                    {
                        "id": "msg_003",
                        "sequence_id": 3,
                        "sender_id": "nlweb_1",
                        "content": "Hello Alice and Bob! How can I help?",
                        "timestamp": "2024-01-01T10:01:30Z",
                        "type": "ai_response",
                        "status": "delivered"
                    }
                ],
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:01:30Z"
            }
            
            mock_resp.get(
                f"{API_BASE_URL}/chat/conversations/{conversation_id}",
                payload=expected_conversation,
                status=200
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.get(f"/chat/conversations/{conversation_id}", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == conversation_id
            assert len(data["messages"]) == 3
            assert len(data["participants"]) == 3
            
            # Verify message ordering
            seq_ids = [msg["sequence_id"] for msg in data["messages"]]
            assert seq_ids == [1, 2, 3]
    
    async def test_pagination_handling(self, api_client, valid_oauth_token):
        """Test pagination in conversation retrieval."""
        with aioresponses() as mock_resp:
            # First page
            page1_response = [
                {"id": f"conv_{i}", "title": f"Conversation {i}", "created_at": f"2024-01-0{i}T10:00:00Z"}
                for i in range(1, 11)  # 10 conversations
            ]
            
            mock_resp.get(
                f"{API_BASE_URL}/chat/my-conversations?limit=10&offset=0",
                payload=page1_response,
                status=200
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.get("/chat/my-conversations?limit=10&offset=0", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 10
            assert data[0]["id"] == "conv_1"
            assert data[9]["id"] == "conv_10"
    
    async def test_access_control_cannot_see_others_conversations(self, api_client, valid_oauth_token):
        """Test access control - users can't see others' conversations."""
        with aioresponses() as mock_resp:
            # Attempt to access another user's conversation
            mock_resp.get(
                f"{API_BASE_URL}/chat/conversations/conv_other_user",
                payload={"error": "Conversation not found", "code": "NOT_FOUND"},
                status=404
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.get("/chat/conversations/conv_other_user", headers=headers)
            
            assert response.status_code == 404
            assert response.json()["code"] == "NOT_FOUND"
    
    async def test_empty_conversation_list(self, api_client, valid_oauth_token):
        """Test empty conversation list for new users."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{API_BASE_URL}/chat/my-conversations",
                payload=[],
                status=200
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data == []


@pytest.mark.integration
@pytest.mark.asyncio
class TestJoinLeaveOperations:
    """Test join/leave conversation operations."""
    
    async def test_join_existing_conversation(self, api_client, valid_oauth_token, sample_participant):
        """Test joining an existing conversation."""
        with aioresponses() as mock_resp:
            conversation_id = "conv_join_001"
            expected_response = {
                "success": True,
                "conversation": {
                    "id": conversation_id,
                    "title": "Joinable Conversation",
                    "participants": [
                        {"participantId": "existing_user", "displayName": "Existing User"},
                        sample_participant
                    ]
                }
            }
            
            mock_resp.post(
                f"{API_BASE_URL}/chat/{conversation_id}/join",
                payload=expected_response,
                status=200
            )
            
            payload = {"participant": sample_participant}
            headers = {**TEST_HEADERS, "Authorization": valid_oauth_token}
            response = await api_client.post(f"/chat/{conversation_id}/join", json=payload, headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["conversation"]["participants"]) == 2
    
    async def test_join_when_already_participant(self, api_client, valid_oauth_token, sample_participant):
        """Test joining when already a participant (409 conflict)."""
        with aioresponses() as mock_resp:
            conversation_id = "conv_already_joined"
            mock_resp.post(
                f"{API_BASE_URL}/chat/{conversation_id}/join",
                payload={
                    "error": "Already a participant in this conversation",
                    "code": "ALREADY_PARTICIPANT"
                },
                status=409
            )
            
            payload = {"participant": sample_participant}
            headers = {**TEST_HEADERS, "Authorization": valid_oauth_token}
            response = await api_client.post(f"/chat/{conversation_id}/join", json=payload, headers=headers)
            
            assert response.status_code == 409
            assert response.json()["code"] == "ALREADY_PARTICIPANT"
    
    async def test_join_when_at_capacity(self, api_client, valid_oauth_token, sample_participant):
        """Test joining when conversation is at capacity (429)."""
        with aioresponses() as mock_resp:
            conversation_id = "conv_at_capacity"
            mock_resp.post(
                f"{API_BASE_URL}/chat/{conversation_id}/join",
                payload={
                    "error": "Conversation is at maximum capacity (100 participants)",
                    "code": "CAPACITY_EXCEEDED",
                    "retry_after": 300
                },
                status=429
            )
            
            payload = {"participant": sample_participant}
            headers = {**TEST_HEADERS, "Authorization": valid_oauth_token}
            response = await api_client.post(f"/chat/{conversation_id}/join", json=payload, headers=headers)
            
            assert response.status_code == 429
            assert response.json()["code"] == "CAPACITY_EXCEEDED"
            assert "retry_after" in response.json()
    
    async def test_leave_conversation_successfully(self, api_client, valid_oauth_token):
        """Test leaving a conversation successfully."""
        with aioresponses() as mock_resp:
            conversation_id = "conv_leave_001"
            mock_resp.delete(
                f"{API_BASE_URL}/chat/{conversation_id}/leave",
                payload={"success": True},
                status=200
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.delete(f"/chat/{conversation_id}/leave", headers=headers)
            
            assert response.status_code == 200
            assert response.json()["success"] is True
    
    async def test_last_participant_leaving(self, api_client, valid_oauth_token):
        """Test behavior when last participant leaves."""
        with aioresponses() as mock_resp:
            conversation_id = "conv_last_participant"
            mock_resp.delete(
                f"{API_BASE_URL}/chat/{conversation_id}/leave",
                payload={
                    "success": True,
                    "conversation_archived": True,
                    "message": "Conversation archived as last participant left"
                },
                status=200
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.delete(f"/chat/{conversation_id}/leave", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["conversation_archived"] is True


@pytest.mark.integration
@pytest.mark.asyncio
class TestHealthEndpoint:
    """Test health endpoint functionality."""
    
    async def test_all_subsystems_healthy(self, api_client):
        """Test health endpoint when all subsystems are healthy."""
        with aioresponses() as mock_resp:
            expected_health = {
                "status": "healthy",
                "checks": {
                    "websocket": {
                        "status": "healthy",
                        "connections": 142,
                        "connection_limit": 10000
                    },
                    "storage": {
                        "status": "healthy",
                        "backend": "azure",
                        "latency_ms": 12
                    },
                    "queues": {
                        "status": "healthy",
                        "total_conversations": 89,
                        "queues_near_limit": 2
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            mock_resp.get(
                f"{API_BASE_URL}/health/chat",
                payload=expected_health,
                status=200
            )
            
            start_time = time.perf_counter()
            response = await api_client.get("/health/chat")
            response_time = time.perf_counter() - start_time
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "websocket" in data["checks"]
            assert "storage" in data["checks"] 
            assert "queues" in data["checks"]
            
            # Response time should be <100ms
            assert response_time < 0.1
    
    async def test_degraded_state_detection(self, api_client):
        """Test health endpoint in degraded state."""
        with aioresponses() as mock_resp:
            degraded_health = {
                "status": "degraded",
                "checks": {
                    "websocket": {
                        "status": "healthy",
                        "connections": 8500,  # Near limit
                        "connection_limit": 10000
                    },
                    "storage": {
                        "status": "degraded",
                        "backend": "azure",
                        "latency_ms": 250,  # High latency
                        "error": "Intermittent timeouts"
                    },
                    "queues": {
                        "status": "healthy",
                        "total_conversations": 89,
                        "queues_near_limit": 15  # Many near limit
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            mock_resp.get(
                f"{API_BASE_URL}/health/chat",
                payload=degraded_health,
                status=200
            )
            
            response = await api_client.get("/health/chat")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["checks"]["storage"]["status"] == "degraded"
    
    async def test_metric_accuracy(self, api_client):
        """Test metric accuracy in health response."""
        with aioresponses() as mock_resp:
            health_response = {
                "status": "healthy",
                "checks": {
                    "websocket": {
                        "status": "healthy",
                        "connections": 500,
                        "connection_limit": 10000,
                        "active_conversations": 250,
                        "messages_per_second": 45.7
                    },
                    "storage": {
                        "status": "healthy",
                        "backend": "memory",
                        "latency_ms": 8,
                        "operations_per_second": 1200
                    },
                    "queues": {
                        "status": "healthy",
                        "total_conversations": 250,
                        "average_queue_size": 15.3,
                        "queues_near_limit": 0
                    }
                }
            }
            
            mock_resp.get(
                f"{API_BASE_URL}/health/chat",
                payload=health_response,
                status=200
            )
            
            response = await api_client.get("/health/chat")
            data = response.json()
            
            # Verify numeric metrics
            assert isinstance(data["checks"]["websocket"]["connections"], int)
            assert isinstance(data["checks"]["storage"]["latency_ms"], (int, float))
            assert isinstance(data["checks"]["queues"]["average_queue_size"], (int, float))


@pytest.mark.integration
@pytest.mark.asyncio  
class TestAuthentication:
    """Test authentication handling."""
    
    async def test_valid_token_acceptance(self, api_client, valid_oauth_token):
        """Test valid token acceptance."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{API_BASE_URL}/chat/my-conversations",
                payload=[],
                status=200
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 200
    
    async def test_invalid_token_rejection(self, api_client, invalid_token):
        """Test invalid token rejection."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{API_BASE_URL}/chat/my-conversations",
                payload={"error": "Invalid authentication token", "code": "INVALID_TOKEN"},
                status=401
            )
            
            headers = {"Authorization": invalid_token}
            response = await api_client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 401
            assert response.json()["code"] == "INVALID_TOKEN"
    
    async def test_token_expiry_handling(self, api_client, expired_token):
        """Test expired token handling."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{API_BASE_URL}/chat/my-conversations",
                payload={
                    "error": "Token has expired",
                    "code": "TOKEN_EXPIRED", 
                    "expires_at": "2024-01-01T00:00:00Z"
                },
                status=401
            )
            
            headers = {"Authorization": expired_token}
            response = await api_client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 401
            assert response.json()["code"] == "TOKEN_EXPIRED"
    
    async def test_oauth_vs_email_based_users(self, api_client, valid_oauth_token, valid_email_token):
        """Test OAuth vs email-based user handling."""
        # Test OAuth user
        with aioresponses() as mock_resp:
            oauth_response = [{"id": "conv_oauth", "title": "OAuth User Conversation"}]
            mock_resp.get(
                f"{API_BASE_URL}/chat/my-conversations",
                payload=oauth_response,
                status=200
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 200
            
        # Test email-based user
        with aioresponses() as mock_resp:
            email_response = [{"id": "conv_email", "title": "Email User Conversation"}]
            mock_resp.get(
                f"{API_BASE_URL}/chat/my-conversations",
                payload=email_response,
                status=200
            )
            
            headers = {"Authorization": valid_email_token}
            response = await api_client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorScenarios:
    """Test error scenarios and handling."""
    
    async def test_404_for_nonexistent_conversations(self, api_client, valid_oauth_token):
        """Test 404 for non-existent conversations."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{API_BASE_URL}/chat/conversations/conv_nonexistent",
                payload={"error": "Conversation not found", "code": "NOT_FOUND"},
                status=404
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.get("/chat/conversations/conv_nonexistent", headers=headers)
            
            assert response.status_code == 404
            assert response.json()["code"] == "NOT_FOUND"
    
    async def test_429_rate_limiting(self, api_client, valid_oauth_token, sample_participant):
        """Test 429 rate limiting."""
        with aioresponses() as mock_resp:
            mock_resp.post(
                f"{API_BASE_URL}/chat/create",
                payload={
                    "error": "Rate limit exceeded",
                    "code": "RATE_LIMITED",
                    "retry_after": 60,
                    "limit": "10 requests per minute"
                },
                status=429
            )
            
            payload = {
                "title": "Rate Limited",
                "sites": ["example.com"],
                "mode": "list",
                "participant": sample_participant
            }
            
            headers = {**TEST_HEADERS, "Authorization": valid_oauth_token}
            response = await api_client.post("/chat/create", json=payload, headers=headers)
            
            assert response.status_code == 429
            data = response.json()
            assert data["code"] == "RATE_LIMITED"
            assert "retry_after" in data
            assert "limit" in data
    
    async def test_500_server_errors_with_retry_guidance(self, api_client, valid_oauth_token):
        """Test 500 server errors with retry guidance."""
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{API_BASE_URL}/chat/my-conversations",
                payload={
                    "error": "Internal server error",
                    "code": "INTERNAL_ERROR",
                    "retry_after": 30,
                    "message": "Temporary service disruption. Please retry in 30 seconds."
                },
                status=500
            )
            
            headers = {"Authorization": valid_oauth_token}
            response = await api_client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 500
            data = response.json()
            assert data["code"] == "INTERNAL_ERROR"
            assert "retry_after" in data
            assert "message" in data
    
    async def test_malformed_request_handling(self, api_client, valid_oauth_token):
        """Test malformed request handling."""
        with aioresponses() as mock_resp:
            mock_resp.post(
                f"{API_BASE_URL}/chat/create",
                payload={
                    "error": "Invalid JSON in request body",
                    "code": "MALFORMED_REQUEST"
                },
                status=400
            )
            
            # Send malformed JSON
            headers = {**TEST_HEADERS, "Authorization": valid_oauth_token}
            response = await api_client.post(
                "/chat/create", 
                content='{"invalid": json}',  # Malformed JSON
                headers=headers
            )
            
            assert response.status_code == 400
            assert response.json()["code"] == "MALFORMED_REQUEST"
    
    async def test_network_timeout_handling(self, api_client, valid_oauth_token):
        """Test network timeout handling."""
        with aioresponses() as mock_resp:
            # Mock a very slow response (timeout)
            mock_resp.get(
                f"{API_BASE_URL}/chat/my-conversations",  
                exception=asyncio.TimeoutError("Request timeout")
            )
            
            headers = {"Authorization": valid_oauth_token}
            
            with pytest.raises(httpx.TimeoutException):
                await api_client.get("/chat/my-conversations", headers=headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])