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
from aiohttp.test_utils import TestServer, TestClient
from aioresponses import aioresponses
import httpx
import re

# Add project root to Python path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../code/python'))

from chat.schemas import (
    ChatMessage, MessageType, MessageStatus, 
    ParticipantInfo, ParticipantType
)
from chat.participants import BaseParticipant, HumanParticipant
from chat.storage import ChatStorageInterface
from chat.conversation import ConversationManager

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


# Integration test fixtures for server and client
@pytest_asyncio.fixture
async def test_app():
    """Create test application without starting server"""
    from webserver.aiohttp_server import AioHTTPServer
    import yaml
    
    # Load test configuration
    config_path = os.path.join(os.path.dirname(__file__), 'config_test.yaml')
    with open(config_path, 'r') as f:
        test_config = yaml.safe_load(f)
    
    # Create server instance with test config
    server = AioHTTPServer(config_path=config_path)
    
    # Create app
    app = await server.create_app()
    
    # Mock authentication middleware
    async def mock_auth_middleware(app, handler):
        async def middleware_handler(request):
            # Add mock user to request from config
            auth_config = test_config.get('auth', {})
            mock_user = auth_config.get('mock_user', {})
            request['user'] = {
                'authenticated': True,
                'id': mock_user.get('user_id', 'test_user_123'),
                'name': mock_user.get('name', 'Test User'),
                'email': mock_user.get('email', 'test@example.com')
            }
            return await handler(request)
        return middleware_handler
    
    # Insert mock auth middleware at the beginning
    app.middlewares.insert(0, mock_auth_middleware)
    
    # Store test config in app for cleanup
    app['test_config'] = test_config
    
    # Mock NLWeb handler if configured
    if not test_config.get('nlweb', {}).get('enabled', False):
        app['nlweb_handler'] = AsyncMock()
        app['nlweb_handler'].process = AsyncMock(return_value=True)
    
    # Mock any other external dependencies
    app['external_api_client'] = AsyncMock()
    
    return app


@pytest_asyncio.fixture
async def test_server(event_loop, test_app):
    """Start test server on configured port"""
    # Get port from test config
    test_config = test_app.get('test_config', {})
    server_config = test_config.get('server', {})
    port = server_config.get('port', 8080)
    
    # Create test server
    test_srv = TestServer(test_app, port=port)
    await test_srv.start_server(loop=event_loop)
    
    yield test_srv
    
    # Cleanup
    await test_srv.close()
    
    # Clean up storage if configured
    if test_config.get('test', {}).get('auto_cleanup', True):
        storage = test_app.get('chat_storage')
        if storage and hasattr(storage.backend, 'clear_all'):
            await storage.backend.clear_all()


@pytest_asyncio.fixture
async def auth_client(test_server):
    """HTTP client with auth headers"""
    import httpx
    
    # Create client with base URL
    client = httpx.AsyncClient(
        base_url=f"http://{test_server.host}:{test_server.port}",
        timeout=30.0,
        headers={
            "Authorization": "Bearer test_token_123",
            "Content-Type": "application/json"
        }
    )
    
    yield client
    
    # Cleanup
    await client.aclose()


@pytest_asyncio.fixture
async def test_conversation(auth_client):
    """Create a test conversation"""
    # Create conversation via API
    response = await auth_client.post(
        "/chat/create",
        json={
            "title": "Test Conversation",
            "participants": [
                {
                    "user_id": "test_user_123",
                    "name": "Test User"
                },
                {
                    "user_id": "test_user_456", 
                    "name": "Another User"
                }
            ],
            "enable_ai": True
        }
    )
    
    assert response.status_code == 201
    conversation_data = response.json()
    
    yield conversation_data
    
    # Cleanup - leave conversation
    try:
        await auth_client.delete(
            f"/chat/{conversation_data['conversation_id']}/leave"
        )
    except Exception:
        pass  # Ignore cleanup errors


@pytest_asyncio.fixture
async def websocket_client(test_server, test_conversation):
    """WebSocket client connected to test conversation"""
    import aiohttp
    
    session = aiohttp.ClientSession()
    
    # Connect to WebSocket
    ws_url = f"ws://{test_server.host}:{test_server.port}/chat/ws/{test_conversation['conversation_id']}"
    ws = await session.ws_connect(
        ws_url,
        headers={"Authorization": "Bearer test_token_123"}
    )
    
    # Wait for connection confirmation
    msg = await ws.receive_json()
    assert msg['type'] == 'connected'
    
    yield ws
    
    # Cleanup
    await ws.close()
    await session.close()


@pytest.fixture
def mock_nlweb_handler():
    """Mock NLWebHandler for testing"""
    handler = AsyncMock()
    
    async def mock_process(query_params, chunk_capture):
        # Simulate NLWeb response
        await chunk_capture.write_stream({
            "type": "nlws",
            "content": "This is a test AI response"
        })
        return True
    
    handler.process = mock_process
    return handler


# Mock external services fixture
@pytest_asyncio.fixture
async def mock_external_services(monkeypatch):
    """Mock all external service calls"""
    # Mock OpenAI API calls
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=AsyncMock(
        choices=[AsyncMock(message=AsyncMock(content="Mocked AI response"))]
    ))
    monkeypatch.setattr("openai.AsyncOpenAI", lambda **kwargs: mock_openai)
    
    # Mock Azure services (only if they exist)
    try:
        import azure.storage.blob
        monkeypatch.setattr("azure.storage.blob.BlobServiceClient", MagicMock)
    except ImportError:
        pass
    
    try:
        import azure.cosmos
        monkeypatch.setattr("azure.cosmos.CosmosClient", MagicMock)
    except ImportError:
        pass
    
    # Mock HTTP requests to external services
    with aioresponses() as mocked:
        # Mock OAuth providers
        mocked.get(re.compile(r'.*google.*userinfo.*'), payload={'email': 'test@gmail.com', 'name': 'Test User'})
        mocked.get(re.compile(r'.*facebook.*me.*'), payload={'email': 'test@fb.com', 'name': 'Test User'})
        mocked.get(re.compile(r'.*microsoft.*me.*'), payload={'mail': 'test@outlook.com', 'displayName': 'Test User'})
        mocked.get(re.compile(r'.*github.*user.*'), payload={'email': 'test@github.com', 'name': 'Test User'})
        
        # Mock NLWeb endpoints
        mocked.post(re.compile(r'.*/ask'), payload={'response': 'Mocked response'})
        mocked.post(re.compile(r'.*/search'), payload={'results': []})
        
        yield mocked


# Storage cleanup fixture
@pytest_asyncio.fixture(autouse=True)
async def cleanup_storage(test_app):
    """Automatically clean up storage between tests"""
    yield
    
    # Clean up after test
    if test_app:
        test_config = test_app.get('test_config', {})
        if test_config.get('test', {}).get('auto_cleanup', True):
            storage = test_app.get('chat_storage')
            if storage and hasattr(storage.backend, '_messages'):
                # Clear memory storage
                storage.backend._messages.clear()
                storage.backend._conversations.clear()
                storage.backend._sequence_counters.clear()
                storage.backend._message_ids.clear()


# Additional test utilities
@pytest.fixture
def test_auth_headers():
    """Standard auth headers for tests"""
    return {
        "Authorization": "Bearer test_token_123",
        "Content-Type": "application/json"
    }


@pytest.fixture
def test_users():
    """Test user data"""
    return [
        {
            "user_id": "test_user_123",
            "name": "Test User",
            "email": "test@example.com"
        },
        {
            "user_id": "test_user_456",
            "name": "Another User",
            "email": "another@example.com"
        },
        {
            "user_id": "test_user_789",
            "name": "Third User",
            "email": "third@example.com"
        }
    ]


# Override the existing api_client fixture to use test server
@pytest_asyncio.fixture
async def api_client(test_server):
    """Override api_client to use test server"""
    async with httpx.AsyncClient(
        base_url=f"http://{test_server.host}:{test_server.port}",
        timeout=30.0
    ) as client:
        yield client