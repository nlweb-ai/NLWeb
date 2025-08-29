"""
WebSocket infrastructure for multi-participant chat.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict
import weakref
from aiohttp import web
import logging

from chat.schemas import QueueFullError
from chat.metrics import ChatMetrics

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class WebSocketError(Exception):
    """Base WebSocket error"""
    pass


class ParticipantLimitError(WebSocketError):
    """Raised when participant limit is reached"""
    def __init__(self, conversation_id: str, current_count: int, limit: int):
        self.conversation_id = conversation_id
        self.current_count = current_count
        self.limit = limit
        super().__init__(
            f"Participant limit reached for conversation {conversation_id}: "
            f"{current_count}/{limit} participants"
        )


@dataclass
class ConnectionConfig:
    """Configuration for WebSocket connections"""
    ping_interval: int = 30  # seconds
    pong_timeout: int = 600  # 10 minutes
    max_retries: int = 10


class WebSocketConnection:
    """Represents a single WebSocket connection from a human participant"""
    
    def __init__(
        self,
        websocket: web.WebSocketResponse,
        participant_id: str,
        conversation_id: str,
        participant_name: Optional[str] = None,
        config: Optional[ConnectionConfig] = None
    ):
        self.websocket = websocket
        self.ws = websocket  # Alias for backward compatibility
        self.participant_id = participant_id
        self.user_id = participant_id  # Alias for backward compatibility
        self.participant_name = participant_name or f"User {participant_id}"
        self.user_name = self.participant_name  # Alias
        self.conversation_id = conversation_id
        self.config = config or ConnectionConfig()
        self.state = ConnectionState.CONNECTED
        self.last_pong_time = datetime.utcnow()
        self.heartbeat_task = None
        
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message to this connection"""
        if self.state == ConnectionState.CONNECTED and not self.ws.closed:
            try:
                await self.ws.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {self.user_id}: {e}")
                self.state = ConnectionState.FAILED
    
    async def heartbeat(self) -> None:
        """Send periodic pings to keep connection alive"""
        while self.state == ConnectionState.CONNECTED:
            try:
                await self.ws.ping()
                await asyncio.sleep(self.config.ping_interval)
                
                # Check for timeout
                if self.is_timed_out():
                    logger.warning(f"Connection timeout for user {self.user_id}")
                    await self.close()
                    break
                    
            except Exception as e:
                logger.error(f"Heartbeat error for {self.user_id}: {e}")
                break
    
    def handle_pong(self) -> None:
        """Handle pong response"""
        self.last_pong_time = datetime.utcnow()
    
    def is_timed_out(self) -> bool:
        """Check if connection has timed out"""
        timeout_threshold = datetime.utcnow() - timedelta(seconds=self.config.pong_timeout)
        return self.last_pong_time < timeout_threshold
    
    async def close(self) -> None:
        """Close the connection"""
        self.state = ConnectionState.DISCONNECTED
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if not self.ws.closed:
            await self.ws.close()


class WebSocketManager:
    """
    Manages all WebSocket connections for the chat system.
    Tracks connections per conversation and handles broadcasting.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, max_connections_per_participant: int = 1):
        self.config = config or {}
        self.max_participants = self.config.get("max_participants", 100)
        self.queue_size_limit = self.config.get("queue_size_limit", 1000)
        self.max_connections_per_participant = max_connections_per_participant
        
        # Connection configuration
        self.connection_config = ConnectionConfig(
            ping_interval=self.config.get("ping_interval", 30),
            pong_timeout=self.config.get("pong_timeout", 600),
            max_retries=self.config.get("max_retries", 10)
        )
        
        # Storage: conversation_id -> user_id -> connection
        self._connections: Dict[str, Dict[str, WebSocketConnection]] = defaultdict(dict)
        
        # Queue sizes per conversation
        self._queue_sizes: Dict[str, int] = defaultdict(int)
        
        # Participant verification callback (set by conversation manager)
        self.verify_participant_callback = None
        
        # Get participants callback (set by conversation manager)
        self.get_participants_callback = None
        
        # Metrics
        self.metrics = ChatMetrics()
        
        # Cleanup task
        self._cleanup_task = None
        self._running = True
        
        # Start periodic cleanup
        self._start_cleanup_task()
    
    async def join_conversation(
        self,
        ws: web.WebSocketResponse,
        user_id: str,
        user_name: str,
        conversation_id: str
    ) -> WebSocketConnection:
        """
        Join a conversation with participant limit enforcement.
        
        Args:
            ws: The WebSocket connection
            user_id: Unique user identifier
            user_name: Display name
            conversation_id: Conversation to join
            
        Returns:
            WebSocketConnection instance
            
        Raises:
            ParticipantLimitError: If participant limit reached
        """
        # Check participant limit
        current_count = self.get_connection_count(conversation_id)
        
        if current_count >= self.max_participants:
            raise ParticipantLimitError(
                conversation_id=conversation_id,
                current_count=current_count,
                limit=self.max_participants
            )
        
        # Create connection
        connection = WebSocketConnection(
            websocket=ws,
            participant_id=user_id,
            user_name=user_name,
            conversation_id=conversation_id,
            config=self.connection_config
        )
        
        # Store connection
        self._connections[conversation_id][user_id] = connection
        
        # Start heartbeat
        connection.heartbeat_task = asyncio.create_task(connection.heartbeat())
        
        # Track metrics
        self.metrics.track_connection(user_id, "connect")
        
        # Log
        logger.info(f"User {user_id} joined conversation {conversation_id}")
        
        return connection
    
    async def leave_conversation(self, user_id: str, conversation_id: str) -> None:
        """Remove a user from a conversation"""
        if conversation_id in self._connections:
            if user_id in self._connections[conversation_id]:
                connection = self._connections[conversation_id][user_id]
                await connection.close()
                del self._connections[conversation_id][user_id]
                
                # Clean up empty conversations
                if not self._connections[conversation_id]:
                    del self._connections[conversation_id]
                
                # Track metrics
                self.metrics.track_connection(user_id, "disconnect")
                
                logger.info(f"User {user_id} left conversation {conversation_id}")
    
    async def broadcast_message(
        self,
        conversation_id: str,
        message: Dict[str, Any],
        exclude_user_id: Optional[str] = None
    ) -> None:
        """
        Broadcast a message to all participants in a conversation.
        O(N) complexity where N is number of participants.
        
        Args:
            conversation_id: The conversation ID
            message: Message to broadcast
            exclude_user_id: Optional user to exclude (usually the sender)
        """
        
        if conversation_id not in self._connections:
            return
        
        # Get all connections for conversation
        connections = self._connections[conversation_id]
        
        # Debug: log what we're doing (commented out for performance)
        # print(f"[WebSocket] Broadcasting to conversation {conversation_id}")
        # print(f"[WebSocket] Exclude user: {exclude_user_id}")
        # print(f"[WebSocket] Active connections: {list(connections.keys())}")
        
        # Send to all participants except excluded
        tasks = []
        msg_type = message.get('message_type', message.get('type', 'unknown'))
        msg_content = message.get('content', '')[:50] if message.get('content') else 'NO_CONTENT'
        sender = message.get('sender_info', {}).get('id', 'unknown') if message.get('sender_info') else 'unknown'
        
        
        for user_id, connection in connections.items():
            if user_id != exclude_user_id:
                tasks.append(connection.send_message(message))
            else:
        
        # Send all messages concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_connection_count(self, conversation_id: str) -> int:
        """Get number of active connections for a conversation"""
        return len(self._connections.get(conversation_id, {}))
    
    def get_active_participants(self, conversation_id: str) -> List[str]:
        """Get list of active participant IDs"""
        return list(self._connections.get(conversation_id, {}).keys())
    
    def can_accept_message(self, conversation_id: str) -> bool:
        """Check if conversation can accept new messages"""
        return self._queue_sizes[conversation_id] < self.queue_size_limit
    
    def update_queue_size(self, conversation_id: str, size: int) -> None:
        """Update queue size for a conversation"""
        self._queue_sizes[conversation_id] = size
        self.metrics.update_queue_depth(conversation_id, size)
    
    async def cleanup_dead_connections(self) -> None:
        """Remove dead connections"""
        for conv_id in list(self._connections.keys()):
            for user_id in list(self._connections[conv_id].keys()):
                connection = self._connections[conv_id][user_id]
                
                # Check if connection is dead
                if (connection.ws.closed or 
                    connection.state == ConnectionState.FAILED or
                    connection.is_timed_out()):
                    
                    await self.leave_conversation(user_id, conv_id)
    
    def _start_cleanup_task(self) -> None:
        """Start periodic cleanup task"""
        async def cleanup_loop():
            while self._running:
                try:
                    await asyncio.sleep(60)  # Run every minute
                    await self.cleanup_dead_connections()
                except Exception as e:
                    logger.error(f"Cleanup error: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def shutdown(self) -> None:
        """Shutdown the manager"""
        self._running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for conv_id in list(self._connections.keys()):
            for user_id in list(self._connections[conv_id].keys()):
                await self.leave_conversation(user_id, conv_id)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        total_connections = sum(
            len(connections) for connections in self._connections.values()
        )
        
        connections_per_conv = {
            conv_id: len(connections)
            for conv_id, connections in self._connections.items()
        }
        
        avg_queue_depth = (
            sum(self._queue_sizes.values()) / len(self._queue_sizes)
            if self._queue_sizes else 0
        )
        
        return {
            "active_connections": total_connections,
            "active_conversations": len(self._connections),
            "connections_per_conversation": connections_per_conv,
            "messages_per_second": 0,  # TODO: Implement message rate tracking
            "average_queue_depth": avg_queue_depth,
            "max_queue_depth": max(self._queue_sizes.values()) if self._queue_sizes else 0
        }
    
    async def broadcast_to_conversation(
        self,
        conversation_id: str,
        message: Dict[str, Any]
    ) -> None:
        """
        Broadcast message to all participants in a conversation.
        Alias for broadcast_message for consistency with conversation manager.
        
        Args:
            conversation_id: The conversation ID
            message: The message to broadcast
        """
        await self.broadcast_message(conversation_id, message)
    
    async def add_connection(self, conversation_id: str, connection: WebSocketConnection) -> None:
        """
        Add a WebSocket connection with participant verification.
        
        Args:
            conversation_id: The conversation ID
            connection: The WebSocket connection
            
        Raises:
            WebSocketError: If participant is not authorized
        """
        # Verify participant if callback is set
        if self.verify_participant_callback:
            is_participant = await self.verify_participant_callback(
                conversation_id, connection.participant_id
            )
            if not is_participant:
                raise WebSocketError(
                    f"User {connection.participant_id} is not a participant in conversation {conversation_id}"
                )
        
        # Store connection
        if conversation_id not in self._connections:
            self._connections[conversation_id] = {}
        
        self._connections[conversation_id][connection.participant_id] = connection
        
        # Start heartbeat
        connection.heartbeat_task = asyncio.create_task(connection.heartbeat())
        
        # Note: Don't send participant list here - let the main handler control message order
        # Note: Don't broadcast join yet - let the main handler do it after sending connected message
        logger.info(f"User {connection.participant_id} connected to conversation {conversation_id}")
    
    async def remove_connection(self, conversation_id: str, participant_id: str) -> None:
        """
        Remove a WebSocket connection and broadcast leave event.
        
        Args:
            conversation_id: The conversation ID
            participant_id: The participant ID
        """
        if conversation_id in self._connections:
            if participant_id in self._connections[conversation_id]:
                connection = self._connections[conversation_id][participant_id]
                participant_name = connection.participant_name
                
                # Close and remove connection
                await connection.close()
                del self._connections[conversation_id][participant_id]
                
                # Clean up empty conversations
                if not self._connections[conversation_id]:
                    del self._connections[conversation_id]
                
                # Broadcast participant leave
                await self.broadcast_participant_update(
                    conversation_id=conversation_id,
                    action="leave",
                    participant_id=participant_id,
                    participant_name=participant_name,
                    participant_type="human"
                )
                
                logger.info(f"User {participant_id} disconnected from conversation {conversation_id}")
    
    async def broadcast_participant_update(
        self,
        conversation_id: str,
        action: str,
        participant_id: str,
        participant_name: str,
        participant_type: str,
        exclude_participant: Optional[str] = None
    ) -> None:
        """
        Broadcast participant join/leave update to all connections.
        
        Args:
            conversation_id: The conversation ID
            action: "join" or "leave"
            participant_id: The participant's ID
            participant_name: The participant's display name
            participant_type: "human" or "ai"
            exclude_participant: Optional participant ID to exclude from broadcast
        """
        # Get current participant list if callback is set
        participants = []
        participant_count = 0
        
        if self.get_participants_callback:
            participants_data = await self.get_participants_callback(conversation_id)
            participants = participants_data.get("participants", [])
            participant_count = participants_data.get("count", 0)
        
        # Build update message
        update_message = {
            "type": "participant_update",
            "action": action,
            "participant": {
                "participantId": participant_id,
                "displayName": participant_name,
                "type": participant_type
            },
            "participants": participants,
            "participant_count": participant_count,
            "conversation_id": conversation_id,
            "timestamp": int(time.time() * 1000)
        }
        
        # Broadcast to all connections except excluded participant
        await self.broadcast_message(conversation_id, update_message, exclude_user_id=exclude_participant)
    
    async def _send_participant_list(self, conversation_id: str, connection: WebSocketConnection) -> None:
        """
        Send current participant list to a newly connected user.
        
        Args:
            conversation_id: The conversation ID
            connection: The WebSocket connection
        """
        if self.get_participants_callback:
            participants_data = await self.get_participants_callback(conversation_id)
            
            participant_list_message = {
                "type": "participant_list",
                "participants": participants_data.get("participants", []),
                "participant_count": participants_data.get("count", 0),
                "conversation_id": conversation_id,
                "timestamp": int(time.time() * 1000)
            }
            
            await connection.send_message(participant_list_message)


async def authenticate_websocket(request: web.Request) -> Dict[str, Any]:
    """
    Authenticate WebSocket connection.
    
    Args:
        request: The WebSocket upgrade request
        
    Returns:
        User information dict
        
    Raises:
        HTTPUnauthorized: If authentication fails
    """
    # Try to get token from header or query param
    token = request.headers.get('Authorization')
    if not token and 'token' in request.query:
        token = f"Bearer {request.query['token']}"
    
    # For now, return a mock user for testing
    # In production, this would validate the token and return user info
    if token:
        # Extract user ID from token (simplified for testing)
        return {
            "id": "user_123",
            "name": "Test User"
        }
    
    raise web.HTTPUnauthorized(text="Invalid authentication token")


# Reconnection helpers for client-side logic
def calculate_backoff(attempt: int) -> int:
    """
    Calculate exponential backoff delay.
    
    Args:
        attempt: Current retry attempt (0-based)
        
    Returns:
        Delay in seconds (max 30)
    """
    delay = min(2 ** attempt, 30)
    return delay


class ReconnectionState:
    """Client-side reconnection state tracker"""
    
    def __init__(self, max_retries: int = 10):
        self.max_retries = max_retries
        self.attempt = 0
        self.last_attempt_time = None
    
    def should_retry(self) -> bool:
        """Check if should retry connection"""
        return self.attempt < self.max_retries
    
    def record_failure(self) -> None:
        """Record a connection failure"""
        self.attempt += 1
        self.last_attempt_time = datetime.utcnow()
    
    def get_backoff(self) -> int:
        """Get current backoff delay"""
        return calculate_backoff(self.attempt)
    
    def reset(self) -> None:
        """Reset state on successful connection"""
        self.attempt = 0
        self.last_attempt_time = None