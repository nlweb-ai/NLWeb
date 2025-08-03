"""
Shared pytest configuration and fixtures for multi-participant chat system.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from unittest.mock import MagicMock, AsyncMock

import pytest
import pytest_asyncio
from aiohttp import web
from aioresponses import aioresponses

# Add project root to Python path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from code.python.chat.schemas import (
    ChatMessage, MessageType, MessageStatus, 
    ParticipantInfo, ParticipantType
)
from code.python.chat.participants import BaseParticipant, HumanParticipant
from code.python.chat.storage import ChatStorageInterface
from code.python.chat.conversation import ConversationManager

# Load mock data
MOCK_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'MOCK_DATA.md')


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_storage():
    """Mock storage backend for testing."""
    storage = AsyncMock(spec=ChatStorageInterface)
    
    # Track sequence IDs per conversation
    sequence_counters = {}
    
    async def get_next_sequence_id(conversation_id: str) -> int:
        if conversation_id not in sequence_counters:
            sequence_counters[conversation_id] = 0
        sequence_counters[conversation_id] += 1
        return sequence_counters[conversation_id]
    
    storage.get_next_sequence_id = get_next_sequence_id
    storage.store_message = AsyncMock(return_value=None)
    storage.get_conversation_messages = AsyncMock(return_value=[])
    
    return storage


@pytest.fixture
def conversation_manager(mock_storage):
    """Create a conversation manager with mock storage."""
    config = {
        "single_mode_timeout": 100,
        "multi_mode_timeout": 2000,
        "queue_size_limit": 1000,
        "max_participants": 100
    }
    manager = ConversationManager(config)
    manager.storage = mock_storage
    return manager


@pytest.fixture
def mock_oauth_user():
    """Mock OAuth user data."""
    return {
        "user_id": "oauth_google_123",
        "email": "alice@example.com",
        "name": "Alice Johnson",
        "provider": "google",
        "token": "mock_google_token_123",
        "expires_at": "2024-12-31T23:59:59Z"
    }


@pytest.fixture
def mock_email_user():
    """Mock email user data."""
    return {
        "user_id": "email_user_001",
        "email": "david@example.com",
        "name": "David Wilson",
        "provider": "email"
    }


@pytest.fixture
def human_participant(mock_oauth_user):
    """Create a mock human participant."""
    return HumanParticipant(
        user_id=mock_oauth_user["user_id"],
        user_name=mock_oauth_user["name"]
    )


@pytest.fixture
def mock_nlweb_handler():
    """Mock NLWebHandler for testing."""
    async def mock_handler(query_params, chunk_capture):
        # Simulate NLWeb response
        await chunk_capture.write_stream({"type": "nlws", "content": "Test response"})
    
    return mock_handler


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.send_str = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.closed = False
    return ws


@pytest.fixture
def mock_request(mock_websocket):
    """Mock aiohttp request with WebSocket."""
    request = MagicMock()
    request.headers = {"Authorization": "Bearer mock_token"}
    request.match_info = {"conversation_id": "conv_test_001"}
    request.app = {"websockets": {}}
    return request


@pytest_asyncio.fixture
async def aiohttp_client_session():
    """Create an aiohttp test client session."""
    with aioresponses() as mocked:
        yield mocked


@pytest.fixture
def sample_message():
    """Create a sample chat message."""
    return ChatMessage(
        message_id="msg_test_001",
        conversation_id="conv_test_001",
        sequence_id=1,
        sender_id="oauth_google_123",
        sender_name="Alice Johnson",
        content="Hello, world!",
        message_type=MessageType.TEXT,
        timestamp=datetime.utcnow(),
        status=MessageStatus.DELIVERED
    )


@pytest.fixture
def xss_test_messages():
    """XSS test messages for security testing."""
    return [
        "<script>alert('XSS')</script>",
        '<img src="x" onerror="alert(1)">',
        '<a href="javascript:alert(1)">Click me</a>',
        '"><script>alert(String.fromCharCode(88,83,83))</script>'
    ]


@pytest.fixture
def performance_config():
    """Performance test configuration."""
    return {
        "baseline_latency_target": 1.05,  # 105% of baseline
        "multi_participant_target": 0.2,  # 200ms
        "websocket_handshake_target": 0.05,  # 50ms
        "message_routing_targets": {
            2: 0.001,  # 1ms for 2 participants
            10: 0.005  # 5ms for 10 participants
        },
        "storage_operation_target": 0.05  # 50ms
    }


@pytest.fixture
def load_test_config():
    """Load test configuration."""
    return {
        "normal_load": {
            "concurrent_users": 50,
            "messages_per_minute": 100,
            "duration_minutes": 10
        },
        "peak_load": {
            "concurrent_users": 200,
            "messages_per_minute": 500,
            "duration_minutes": 5
        },
        "stress_test": {
            "concurrent_users": 1000,
            "messages_per_minute": 2000,
            "duration_minutes": 2
        }
    }


@pytest.fixture
def mock_conversation_state():
    """Mock conversation state for testing."""
    return {
        "id": "conv_test_001",
        "title": "Test Conversation",
        "sites": ["example.com"],
        "mode": "list",
        "participants": [],
        "message_count": 0,
        "created_at": datetime.utcnow()
    }


@pytest.fixture
def mock_frontend_config():
    """Mock frontend configuration."""
    return {
        "sites": [
            {"id": "site1", "name": "Example Site", "url": "https://example.com"},
            {"id": "site2", "name": "Test Site", "url": "https://test.com"}
        ],
        "modes": ["list", "summarize", "generate"],
        "wsUrl": "ws://localhost:8080/chat/ws",
        "multiParticipantEnabled": True
    }


@pytest.fixture
def mock_identity():
    """Mock identity for frontend testing."""
    return {
        "participantId": "oauth_google_123",
        "displayName": "Alice Johnson",
        "email": "alice@example.com"
    }


# Test data helpers
def load_mock_users():
    """Load mock users from MOCK_DATA.md."""
    # This would parse the MOCK_DATA.md file
    # For now, return hardcoded data
    return {
        "oauth_users": [
            {
                "user_id": "oauth_google_123",
                "email": "alice@example.com",
                "name": "Alice Johnson",
                "provider": "google",
                "token": "mock_google_token_123"
            }
        ],
        "email_users": [
            {
                "user_id": "email_user_001",
                "email": "david@example.com",
                "name": "David Wilson",
                "provider": "email"
            }
        ]
    }


def create_test_message(
    content: str,
    sender_id: str = "test_user",
    conversation_id: str = "test_conv",
    message_type: MessageType = MessageType.TEXT
) -> ChatMessage:
    """Helper to create test messages."""
    return ChatMessage(
        message_id=f"msg_{datetime.utcnow().timestamp()}",
        conversation_id=conversation_id,
        sequence_id=0,
        sender_id=sender_id,
        sender_name="Test User",
        content=content,
        message_type=message_type,
        timestamp=datetime.utcnow(),
        status=MessageStatus.PENDING
    )


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    config.addinivalue_line(
        "markers", "reliability: mark test as a reliability test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )