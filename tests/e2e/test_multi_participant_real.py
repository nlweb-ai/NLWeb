"""
End-to-end multi-participant tests for the chat system using real server.
Tests real-world scenarios with multiple humans and AI agents in complete conversation flows.
"""

import asyncio
import time
import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pytest
import pytest_asyncio
import httpx
import websockets

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../code/python'))

from chat.schemas import (
    ChatMessage, MessageType, MessageStatus,
    ParticipantInfo, ParticipantType
)


# E2E Test Configuration
E2E_BASE_URL = "http://localhost:8000"
WEBSOCKET_BASE_URL = "ws://localhost:8000"
E2E_TIMEOUT = 30.0


class E2EWebSocketClient:
    """WebSocket client for E2E testing."""
    
    def __init__(self, conversation_id: str, auth_token: str):
        self.conversation_id = conversation_id
        self.auth_token = auth_token
        self.websocket = None
        self.received_messages = []
        self.is_connected = False
        self._receive_task = None
        
    async def connect(self):
        """Connect to WebSocket."""
        try:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = self.auth_token
                
            self.websocket = await websockets.connect(
                f"{WEBSOCKET_BASE_URL}/chat/ws/{self.conversation_id}",
                additional_headers=headers if headers else None
            )
            
            self.is_connected = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Wait for connection confirmation
            await asyncio.sleep(0.1)
            return True
            
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            self.is_connected = False
            return False
    
    async def _receive_loop(self):
        """Receive messages in background."""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                self.received_messages.append(data)
        except Exception as e:
            print(f"Receive error: {e}")
        finally:
            self.is_connected = False
    
    async def send_message(self, content: str, sites: List[str] = None, mode: str = "list"):
        """Send a message through WebSocket."""
        if not self.is_connected or not self.websocket:
            raise Exception("Not connected")
        
        message = {
            "type": "message",
            "content": content,
            "message_id": f"msg_{uuid.uuid4().hex[:8]}",
            "sites": sites or ["example.com"],
            "mode": mode
        }
        
        await self.websocket.send(json.dumps(message))
        return message
    
    async def wait_for_message(self, message_type: str = None, timeout: float = 5.0):
        """Wait for a specific type of message."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            for msg in self.received_messages:
                if message_type is None or msg.get('type') == message_type:
                    return msg
            await asyncio.sleep(0.1)
        
        return None
    
    async def disconnect(self):
        """Disconnect WebSocket."""
        self.is_connected = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            await self.websocket.close()
            self.websocket = None


@pytest.fixture
async def e2e_client():
    """Create HTTP client for E2E testing."""
    async with httpx.AsyncClient(
        base_url=E2E_BASE_URL,
        timeout=httpx.Timeout(E2E_TIMEOUT)
    ) as client:
        yield client


@pytest.mark.e2e
@pytest.mark.asyncio
class TestSingleUserConversationFlow:
    """Test complete single user conversation flow."""
    
    async def test_create_send_receive_conversation_cycle(self, e2e_client):
        """Test complete conversation cycle: create → send → receive."""
        # Create conversation
        user_token = "Bearer e2e_single_user"
        
        response = await e2e_client.post(
            "/chat/create",
            json={
                "title": "Single User E2E Test",
                "sites": ["weather.com", "news.com"],
                "mode": "list",
                "participants": [{
                    "user_id": "single_user",
                    "name": "Test User"
                }],
                "enable_ai": False
            },
            headers={"Authorization": user_token}
        )
        
        assert response.status_code == 201
        data = response.json()
        conversation_id = data["conversation_id"]
        
        # Connect via WebSocket
        ws_client = E2EWebSocketClient(conversation_id, user_token)
        connected = await ws_client.connect()
        assert connected
        
        # Wait for connection confirmation
        conn_msg = await ws_client.wait_for_message('connected', timeout=2.0)
        assert conn_msg is not None
        
        # Send message via WebSocket
        await ws_client.send_message("What's the weather today?")
        
        # Wait for message acknowledgment
        ack_msg = await ws_client.wait_for_message('message_ack', timeout=5.0)
        assert ack_msg is not None
        
        # Get conversation details
        conv_response = await e2e_client.get(
            f"/chat/conversations/{conversation_id}",
            headers={"Authorization": user_token}
        )
        
        assert conv_response.status_code == 200
        conv_data = conv_response.json()
        assert conv_data["id"] == conversation_id
        assert len(conv_data["messages"]) >= 1
        
        # Cleanup
        await ws_client.disconnect()
    
    async def test_single_user_multiple_messages(self, e2e_client):
        """Test single user sending multiple messages in sequence."""
        user_token = "Bearer e2e_multi_msg_user"
        
        # Create conversation
        response = await e2e_client.post(
            "/chat/create",
            json={
                "title": "Multi-Message Test",
                "sites": ["example.com"],
                "mode": "summarize",
                "participants": [{
                    "user_id": "multi_msg_user",
                    "name": "Multi Message User"
                }],
                "enable_ai": False
            },
            headers={"Authorization": user_token}
        )
        
        assert response.status_code == 201
        conversation_id = response.json()["conversation_id"]
        
        # Connect via WebSocket
        ws_client = E2EWebSocketClient(conversation_id, user_token)
        await ws_client.connect()
        
        # Wait for connection
        await ws_client.wait_for_message('connected', timeout=2.0)
        
        # Send multiple messages
        messages = [
            "First message about the weather",
            "Second message about traffic",
            "Third message asking for a summary"
        ]
        
        for msg_content in messages:
            await ws_client.send_message(msg_content)
            await asyncio.sleep(0.2)  # Small delay between messages
        
        # Wait for acknowledgments
        await asyncio.sleep(1.0)
        
        # Verify messages were received
        ack_count = sum(1 for msg in ws_client.received_messages if msg.get('type') == 'message_ack')
        assert ack_count >= len(messages)
        
        await ws_client.disconnect()


@pytest.mark.e2e
@pytest.mark.asyncio
class TestMultiUserConversation:
    """Test multi-user conversation scenarios."""
    
    async def test_three_humans_scenario(self, e2e_client):
        """Test scenario with 3 humans."""
        # Create conversation with first user
        creator_token = "Bearer e2e_alice_001"
        
        response = await e2e_client.post(
            "/chat/create",
            json={
                "title": "Team Discussion",
                "sites": ["docs.google.com", "github.com"],
                "mode": "generate",
                "participants": [{
                    "user_id": "alice_001",
                    "name": "Alice Smith"
                }],
                "enable_ai": False
            },
            headers={"Authorization": creator_token}
        )
        
        assert response.status_code == 201
        conversation_id = response.json()["conversation_id"]
        
        # Other participants join
        participants = [
            {"user_id": "bob_002", "name": "Bob Jones", "token": "Bearer e2e_bob_002"},
            {"user_id": "charlie_003", "name": "Charlie Brown", "token": "Bearer e2e_charlie_003"}
        ]
        
        for participant in participants:
            join_response = await e2e_client.post(
                f"/chat/{conversation_id}/join",
                json={
                    "participant": {
                        "user_id": participant["user_id"],
                        "name": participant["name"]
                    }
                },
                headers={"Authorization": participant["token"]}
            )
            
            assert join_response.status_code == 200
        
        # Create WebSocket connections for all participants
        ws_clients = []
        
        # Creator
        creator_ws = E2EWebSocketClient(conversation_id, creator_token)
        await creator_ws.connect()
        ws_clients.append(creator_ws)
        
        # Other participants
        for participant in participants:
            ws = E2EWebSocketClient(conversation_id, participant["token"])
            await ws.connect()
            ws_clients.append(ws)
        
        # Wait for connections
        await asyncio.sleep(0.5)
        
        # Each participant sends a message
        messages = [
            (ws_clients[0], "Let's discuss the new feature requirements"),
            (ws_clients[1], "I think we need to focus on user experience"),
            (ws_clients[2], "What about performance implications?")
        ]
        
        for ws_client, content in messages:
            await ws_client.send_message(content)
            await asyncio.sleep(0.3)
        
        # Wait for message propagation
        await asyncio.sleep(1.0)
        
        # Verify all clients received messages
        for ws_client in ws_clients:
            ack_count = sum(1 for msg in ws_client.received_messages if msg.get('type') == 'message_ack')
            assert ack_count >= 1
        
        # Cleanup
        for ws_client in ws_clients:
            await ws_client.disconnect()
    
    async def test_participant_join_during_active_conversation(self, e2e_client):
        """Test participant joining during active conversation."""
        # Create conversation
        creator_token = "Bearer e2e_early_alice"
        
        response = await e2e_client.post(
            "/chat/create",
            json={
                "title": "Join During Active",
                "sites": ["example.com"],
                "mode": "list",
                "participants": [{
                    "user_id": "early_alice",
                    "name": "Early Alice"
                }],
                "enable_ai": False
            },
            headers={"Authorization": creator_token}
        )
        
        assert response.status_code == 201
        conversation_id = response.json()["conversation_id"]
        
        # First participant joins
        bob_token = "Bearer e2e_early_bob"
        bob_join_response = await e2e_client.post(
            f"/chat/{conversation_id}/join",
            json={
                "participant": {
                    "user_id": "early_bob",
                    "name": "Early Bob"
                }
            },
            headers={"Authorization": bob_token}
        )
        assert bob_join_response.status_code == 200
        
        # Connect early participants
        alice_ws = E2EWebSocketClient(conversation_id, creator_token)
        bob_ws = E2EWebSocketClient(conversation_id, bob_token)
        
        await alice_ws.connect()
        await bob_ws.connect()
        await asyncio.sleep(0.5)
        
        # Send some messages
        for i in range(3):
            if i % 2 == 0:
                await alice_ws.send_message(f"Early message {i+1}")
            else:
                await bob_ws.send_message(f"Early message {i+1}")
            await asyncio.sleep(0.2)
        
        # Late participant joins
        charlie_token = "Bearer e2e_late_charlie"
        join_response = await e2e_client.post(
            f"/chat/{conversation_id}/join",
            json={
                "participant": {
                    "user_id": "late_charlie",
                    "name": "Late Charlie"
                }
            },
            headers={"Authorization": charlie_token}
        )
        
        assert join_response.status_code == 200
        
        # Late participant connects
        charlie_ws = E2EWebSocketClient(conversation_id, charlie_token)
        await charlie_ws.connect()
        
        # Get conversation history
        history_response = await e2e_client.get(
            f"/chat/conversations/{conversation_id}",
            headers={"Authorization": charlie_token}
        )
        
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert len(history_data["messages"]) >= 3
        
        # Cleanup
        await alice_ws.disconnect()
        await bob_ws.disconnect()
        await charlie_ws.disconnect()
    
    async def test_participant_leave_and_rejoin(self, e2e_client):
        """Test participant leaving and rejoining conversation."""
        # Create conversation
        stable_token = "Bearer e2e_stable_user"
        
        response = await e2e_client.post(
            "/chat/create",
            json={
                "title": "Leave and Rejoin Test",
                "sites": ["example.com"],
                "mode": "summarize",
                "participants": [{
                    "user_id": "stable_user",
                    "name": "Stable User"
                }],
                "enable_ai": False
            },
            headers={"Authorization": stable_token}
        )
        
        assert response.status_code == 201
        conversation_id = response.json()["conversation_id"]
        
        # Add leaving user
        leaving_token = "Bearer e2e_leaving_user"
        join_response = await e2e_client.post(
            f"/chat/{conversation_id}/join",
            json={
                "participant": {
                    "user_id": "leaving_user",
                    "name": "Leaving User"
                }
            },
            headers={"Authorization": leaving_token}
        )
        
        assert join_response.status_code == 200
        
        # Both connect via WebSocket
        stable_ws = E2EWebSocketClient(conversation_id, stable_token)
        leaving_ws = E2EWebSocketClient(conversation_id, leaving_token)
        
        await stable_ws.connect()
        await leaving_ws.connect()
        await asyncio.sleep(0.5)
        
        # Leaving user disconnects and leaves
        await leaving_ws.disconnect()
        
        leave_response = await e2e_client.delete(
            f"/chat/{conversation_id}/leave",
            headers={"Authorization": leaving_token}
        )
        
        assert leave_response.status_code == 200
        
        # Stable user sends messages while other is away
        for i in range(3):
            await stable_ws.send_message(f"Message while user is away {i+1}")
            await asyncio.sleep(0.2)
        
        # User rejoins
        rejoin_response = await e2e_client.post(
            f"/chat/{conversation_id}/join",
            json={
                "participant": {
                    "user_id": "leaving_user",
                    "name": "Leaving User"
                }
            },
            headers={"Authorization": leaving_token}
        )
        
        assert rejoin_response.status_code == 200
        
        # Cleanup
        await stable_ws.disconnect()


@pytest.mark.e2e
@pytest.mark.asyncio
class TestLargeConversation:
    """Test large conversation scenarios."""
    
    async def test_many_participants(self, e2e_client):
        """Test conversation with many participants."""
        participant_count = 10  # Reduced for testing
        
        # Create conversation
        creator_token = "Bearer e2e_large_creator"
        
        response = await e2e_client.post(
            "/chat/create",
            json={
                "title": "Large Group Discussion",
                "sites": ["community.example.com"],
                "mode": "summarize",
                "participants": [{
                    "user_id": "user_000",
                    "name": "User 000"
                }],
                "enable_ai": False
            },
            headers={"Authorization": creator_token}
        )
        
        assert response.status_code == 201
        conversation_id = response.json()["conversation_id"]
        
        # Add many participants
        for i in range(1, participant_count):
            token = f"Bearer e2e_user_{i:03d}"
            join_response = await e2e_client.post(
                f"/chat/{conversation_id}/join",
                json={
                    "participant": {
                        "user_id": f"user_{i:03d}",
                        "name": f"User {i:03d}"
                    }
                },
                headers={"Authorization": token}
            )
            
            assert join_response.status_code == 200
        
        # Create WebSocket connections for a subset of active users
        active_count = 5
        ws_clients = []
        
        for i in range(active_count):
            token = f"Bearer e2e_user_{i:03d}" if i > 0 else creator_token
            ws = E2EWebSocketClient(conversation_id, token)
            await ws.connect()
            ws_clients.append(ws)
        
        await asyncio.sleep(0.5)
        
        # Active users send messages
        for i, ws_client in enumerate(ws_clients):
            await ws_client.send_message(f"Message from User {i:03d}")
            await asyncio.sleep(0.1)
        
        # Wait for message propagation
        await asyncio.sleep(1.0)
        
        # Verify messages were sent
        for ws_client in ws_clients:
            ack_count = sum(1 for msg in ws_client.received_messages if msg.get('type') == 'message_ack')
            assert ack_count >= 1
        
        # Cleanup
        for ws_client in ws_clients:
            await ws_client.disconnect()


@pytest.mark.e2e
@pytest.mark.asyncio
class TestFullConversationLifecycle:
    """Test complete conversation lifecycle."""
    
    async def test_create_chat_leave_lifecycle(self, e2e_client):
        """Test full lifecycle: create → chat → leave."""
        participants = [
            {"user_id": "lifecycle_alice", "name": "Alice", "token": "Bearer e2e_lifecycle_alice"},
            {"user_id": "lifecycle_bob", "name": "Bob", "token": "Bearer e2e_lifecycle_bob"},
            {"user_id": "lifecycle_charlie", "name": "Charlie", "token": "Bearer e2e_lifecycle_charlie"}
        ]
        
        # Phase 1: Create conversation
        creator = participants[0]
        response = await e2e_client.post(
            "/chat/create",
            json={
                "title": "Full Lifecycle Test",
                "sites": ["lifecycle.example.com"],
                "mode": "generate",
                "participants": [{
                    "user_id": creator["user_id"],
                    "name": creator["name"]
                }],
                "enable_ai": False
            },
            headers={"Authorization": creator["token"]}
        )
        
        assert response.status_code == 201
        conversation_id = response.json()["conversation_id"]
        
        # Phase 2: Other participants join
        for participant in participants[1:]:
            join_response = await e2e_client.post(
                f"/chat/{conversation_id}/join",
                json={
                    "participant": {
                        "user_id": participant["user_id"],
                        "name": participant["name"]
                    }
                },
                headers={"Authorization": participant["token"]}
            )
            
            assert join_response.status_code == 200
        
        # Phase 3: Active conversation
        ws_clients = []
        for participant in participants:
            ws = E2EWebSocketClient(conversation_id, participant["token"])
            await ws.connect()
            ws_clients.append(ws)
        
        await asyncio.sleep(0.5)
        
        # Send messages
        for i in range(6):
            ws_client = ws_clients[i % len(ws_clients)]
            await ws_client.send_message(f"Lifecycle message {i+1}")
            await asyncio.sleep(0.2)
        
        # Wait for messages
        await asyncio.sleep(1.0)
        
        # Phase 4: Participants leave
        for ws_client in ws_clients:
            await ws_client.disconnect()
        
        for participant in participants:
            leave_response = await e2e_client.delete(
                f"/chat/{conversation_id}/leave",
                headers={"Authorization": participant["token"]}
            )
            
            assert leave_response.status_code == 200
        
        # Verify conversation still exists but all participants left
        conv_response = await e2e_client.get(
            f"/chat/conversations/{conversation_id}",
            headers={"Authorization": creator["token"]}
        )
        
        # Should get 404 since user left
        assert conv_response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])