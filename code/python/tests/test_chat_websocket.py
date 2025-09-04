"""
Tests for WebSocket infrastructure.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json
import time
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
import aiohttp

from chat.schemas import (
    Conversation,
    ParticipantInfo,
    ParticipantType,
    QueueFullError
)
from core.schemas import (
    Message,
    MessageType
)

# These imports will fail until we create the module
from chat.websocket import (
    WebSocketManager,
    WebSocketConnection,
    ConnectionState,
    WebSocketError,
    ParticipantLimitError,
    ConnectionConfig
)


class TestWebSocketConnection:
    """Test individual WebSocket connection handling"""
    
    @pytest.fixture
    def mock_ws(self):
        """Create a mock WebSocket"""
        ws = AsyncMock()
        ws.closed = False
        ws.send_str = AsyncMock()
        ws.send_json = AsyncMock()
        ws.ping = AsyncMock()
        ws.pong = AsyncMock()
        ws.close = AsyncMock()
        return ws
    
    @pytest.fixture
    def connection_config(self):
        """Create connection configuration"""
        return ConnectionConfig(
            ping_interval=30,
            pong_timeout=600,  # 10 minutes
            max_retries=10
        )
    
    @pytest.mark.asyncio
    async def test_connection_creation(self, mock_ws, connection_config):
        """Test creating a WebSocket connection"""
        connection = WebSocketConnection(
            ws=mock_ws,
            user_id="user_123",
            user_name="Alice",
            conversation_id="conv_abc",
            config=connection_config
        )
        
        assert connection.user_id == "user_123"
        assert connection.user_name == "Alice"
        assert connection.conversation_id == "conv_abc"
        assert connection.state == ConnectionState.CONNECTED
        assert connection.last_pong_time is not None
    
    @pytest.mark.asyncio
    async def test_send_message(self, mock_ws, connection_config):
        """Test sending a message through connection"""
        connection = WebSocketConnection(
            ws=mock_ws,
            user_id="user_123",
            user_name="Alice",
            conversation_id="conv_abc",
            config=connection_config
        )
        
        message = {
            "type": "message",
            "content": "Hello",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await connection.send_message(message)
        mock_ws.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_heartbeat(self, mock_ws, connection_config):
        """Test heartbeat ping/pong mechanism"""
        connection = WebSocketConnection(
            ws=mock_ws,
            user_id="user_123",
            user_name="Alice",
            conversation_id="conv_abc",
            config=connection_config
        )
        
        # Start heartbeat
        heartbeat_task = asyncio.create_task(connection.heartbeat())
        
        # Wait a bit for first ping
        await asyncio.sleep(0.1)
        
        # Should have sent a ping
        assert mock_ws.ping.called
        
        # Simulate pong response
        connection.handle_pong()
        assert connection.last_pong_time is not None
        
        # Cancel heartbeat
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_connection_timeout(self, mock_ws, connection_config):
        """Test connection timeout when no pong received"""
        # Short timeout for testing
        config = ConnectionConfig(
            ping_interval=0.1,
            pong_timeout=0.2,
            max_retries=10
        )
        
        connection = WebSocketConnection(
            ws=mock_ws,
            user_id="user_123",
            user_name="Alice",
            conversation_id="conv_abc",
            config=config
        )
        
        # Set last pong to old time
        connection.last_pong_time = datetime.utcnow() - timedelta(seconds=1)
        
        # Check if timed out
        assert connection.is_timed_out() is True
        
        # Should close connection
        await connection.close()
        assert connection.state == ConnectionState.DISCONNECTED
        mock_ws.close.assert_called_once()


class TestWebSocketManager:
    """Test WebSocket manager for multiple connections"""
    
    @pytest.fixture
    def manager_config(self):
        """Create manager configuration"""
        return {
            "max_participants": 100,
            "ping_interval": 30,
            "pong_timeout": 600,
            "max_retries": 10,
            "queue_size_limit": 1000
        }
    
    @pytest.fixture
    async def manager(self, manager_config):
        """Create WebSocket manager"""
        manager = WebSocketManager(manager_config)
        yield manager
        await manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_join_conversation(self, manager):
        """Test joining a conversation"""
        mock_ws = AsyncMock()
        mock_ws.closed = False
        
        # Join conversation
        connection = await manager.join_conversation(
            ws=mock_ws,
            user_id="user_123",
            user_name="Alice",
            conversation_id="conv_abc"
        )
        
        assert connection is not None
        assert manager.get_connection_count("conv_abc") == 1
        assert manager.get_active_participants("conv_abc") == ["user_123"]
    
    @pytest.mark.asyncio
    async def test_multiple_humans_join(self, manager):
        """Test multiple humans joining same conversation"""
        # Alice joins
        alice_ws = AsyncMock()
        alice_ws.closed = False
        alice_conn = await manager.join_conversation(
            ws=alice_ws,
            user_id="alice_123",
            user_name="Alice",
            conversation_id="conv_multi"
        )
        
        # Bob joins
        bob_ws = AsyncMock()
        bob_ws.closed = False
        bob_conn = await manager.join_conversation(
            ws=bob_ws,
            user_id="bob_456",
            user_name="Bob",
            conversation_id="conv_multi"
        )
        
        # Charlie joins
        charlie_ws = AsyncMock()
        charlie_ws.closed = False
        charlie_conn = await manager.join_conversation(
            ws=charlie_ws,
            user_id="charlie_789",
            user_name="Charlie",
            conversation_id="conv_multi"
        )
        
        assert manager.get_connection_count("conv_multi") == 3
        participants = manager.get_active_participants("conv_multi")
        assert len(participants) == 3
        assert set(participants) == {"alice_123", "bob_456", "charlie_789"}
    
    @pytest.mark.asyncio
    async def test_participant_limit(self, manager_config):
        """Test participant limit enforcement"""
        # Create manager with small limit
        config = manager_config.copy()
        config["max_participants"] = 2
        manager = WebSocketManager(config)
        
        # Add two participants (up to limit)
        for i in range(2):
            ws = AsyncMock()
            ws.closed = False
            await manager.join_conversation(
                ws=ws,
                user_id=f"user_{i}",
                user_name=f"User{i}",
                conversation_id="conv_limited"
            )
        
        # Third should fail
        ws = AsyncMock()
        ws.closed = False
        with pytest.raises(ParticipantLimitError) as exc_info:
            await manager.join_conversation(
                ws=ws,
                user_id="user_3",
                user_name="User3",
                conversation_id="conv_limited"
            )
        
        assert exc_info.value.conversation_id == "conv_limited"
        assert exc_info.value.current_count == 2
        assert exc_info.value.limit == 2
        
        await manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_broadcast_message(self, manager):
        """Test broadcasting message to all participants"""
        # Create 3 connections
        connections = []
        for i in range(3):
            ws = AsyncMock()
            ws.closed = False
            ws.send_json = AsyncMock()
            conn = await manager.join_conversation(
                ws=ws,
                user_id=f"user_{i}",
                user_name=f"User{i}",
                conversation_id="conv_broadcast"
            )
            connections.append((ws, conn))
        
        # Broadcast message
        message = {
            "type": "message",
            "content": "Hello everyone",
            "sender_id": "user_0"
        }
        
        await manager.broadcast_message("conv_broadcast", message, exclude_user_id="user_0")
        
        # Check that user_1 and user_2 received it, but not user_0
        connections[0][0].send_json.assert_not_called()
        connections[1][0].send_json.assert_called_once_with(message)
        connections[2][0].send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_queue_size_check(self, manager):
        """Test queue size checking before accepting messages"""
        mock_ws = AsyncMock()
        mock_ws.closed = False
        
        # Join conversation
        await manager.join_conversation(
            ws=mock_ws,
            user_id="user_123",
            user_name="Alice",
            conversation_id="conv_queue"
        )
        
        # Set queue size to near limit
        manager.update_queue_size("conv_queue", 999)
        
        # Check if can accept message
        assert manager.can_accept_message("conv_queue") is True
        
        # Set to limit
        manager.update_queue_size("conv_queue", 1000)
        assert manager.can_accept_message("conv_queue") is False
    
    @pytest.mark.asyncio
    async def test_leave_conversation(self, manager):
        """Test leaving a conversation"""
        mock_ws = AsyncMock()
        mock_ws.closed = False
        
        # Join conversation
        connection = await manager.join_conversation(
            ws=mock_ws,
            user_id="user_123",
            user_name="Alice",
            conversation_id="conv_leave"
        )
        
        assert manager.get_connection_count("conv_leave") == 1
        
        # Leave conversation
        await manager.leave_conversation("user_123", "conv_leave")
        
        assert manager.get_connection_count("conv_leave") == 0
        assert manager.get_active_participants("conv_leave") == []
    
    @pytest.mark.asyncio
    async def test_connection_cleanup(self, manager):
        """Test automatic cleanup of dead connections"""
        # Create connection
        mock_ws = AsyncMock()
        mock_ws.closed = False
        connection = await manager.join_conversation(
            ws=mock_ws,
            user_id="user_123",
            user_name="Alice",
            conversation_id="conv_cleanup"
        )
        
        # Simulate connection death
        mock_ws.closed = True
        
        # Run cleanup
        await manager.cleanup_dead_connections()
        
        # Should be removed
        assert manager.get_connection_count("conv_cleanup") == 0
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, manager):
        """Test metrics collection"""
        # Add some connections
        for i in range(5):
            ws = AsyncMock()
            ws.closed = False
            await manager.join_conversation(
                ws=ws,
                user_id=f"user_{i}",
                user_name=f"User{i}",
                conversation_id=f"conv_{i % 2}"  # 2 conversations
            )
        
        # Get metrics
        metrics = manager.get_metrics()
        
        assert metrics["active_connections"] == 5
        assert metrics["active_conversations"] == 2
        assert metrics["connections_per_conversation"]["conv_0"] == 3
        assert metrics["connections_per_conversation"]["conv_1"] == 2
        assert "messages_per_second" in metrics
        assert "average_queue_depth" in metrics


class TestWebSocketAuth:
    """Test WebSocket authentication"""
    
    @pytest.mark.asyncio
    async def test_auth_success(self):
        """Test successful authentication"""
        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer valid_token"}
        
        # No need to patch since authenticate_websocket now handles this internally
        user = await authenticate_websocket(mock_request)
        assert user["id"] == "user_123"
        assert user["name"] == "Test User"
    
    @pytest.mark.asyncio
    async def test_auth_failure(self):
        """Test authentication failure"""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.query = {}
        
        with pytest.raises(web.HTTPUnauthorized):
            await authenticate_websocket(mock_request)
    
    @pytest.mark.asyncio
    async def test_auth_from_query_param(self):
        """Test authentication from query parameter"""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.query = {"token": "valid_token"}
        
        user = await authenticate_websocket(mock_request)
        assert user["id"] == "user_123"


class TestReconnectionLogic:
    """Test client reconnection with exponential backoff"""
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff calculation"""
        from chat.websocket import calculate_backoff
        
        assert calculate_backoff(0) == 1  # 1s
        assert calculate_backoff(1) == 2  # 2s
        assert calculate_backoff(2) == 4  # 4s
        assert calculate_backoff(3) == 8  # 8s
        assert calculate_backoff(4) == 16  # 16s
        assert calculate_backoff(5) == 30  # max 30s
        assert calculate_backoff(10) == 30  # still max 30s
    
    def test_client_reconnection_state(self):
        """Test client reconnection state machine"""
        from chat.websocket import ReconnectionState
        
        state = ReconnectionState(max_retries=10)
        
        # Initial state
        assert state.attempt == 0
        assert state.should_retry() is True
        
        # First failure
        state.record_failure()
        assert state.attempt == 1
        assert state.get_backoff() == 2  # 2^1 = 2
        
        # Multiple failures
        for _ in range(9):
            state.record_failure()
        
        assert state.attempt == 10
        assert state.should_retry() is False  # Exceeded max retries
        
        # Reset on success
        state.reset()
        assert state.attempt == 0
        assert state.should_retry() is True


class TestConnectionState:
    """Test connection state enum"""
    
    def test_connection_states(self):
        """Test all connection states exist"""
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.DISCONNECTING.value == "disconnecting"
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.FAILED.value == "failed"


class TestWebSocketError:
    """Test WebSocket error types"""
    
    def test_websocket_error(self):
        """Test base WebSocket error"""
        error = WebSocketError("Connection failed")
        assert str(error) == "Connection failed"
    
    def test_participant_limit_error(self):
        """Test participant limit error"""
        error = ParticipantLimitError(
            conversation_id="conv_abc",
            current_count=100,
            limit=100
        )
        assert error.conversation_id == "conv_abc"
        assert error.current_count == 100
        assert error.limit == 100
        assert "Participant limit reached" in str(error)


# Import helper for WebSocket auth
async def authenticate_websocket(request):
    """Authenticate WebSocket connection"""
    from chat.websocket import authenticate_websocket as auth_ws
    return await auth_ws(request)