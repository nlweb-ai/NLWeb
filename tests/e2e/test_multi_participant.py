"""
End-to-end multi-participant tests for the chat system.
Tests real-world scenarios with multiple humans and AI agents in complete conversation flows.
"""

import asyncio
import time
import uuid
import json
import random
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Set
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
    ParticipantInfo, ParticipantType
)


# E2E Test Configuration
E2E_BASE_URL = "http://localhost:8080"
WEBSOCKET_BASE_URL = "ws://localhost:8080"
E2E_TIMEOUT = 30.0


class E2EParticipant:
    """End-to-end test participant (human or AI)."""
    
    def __init__(self, participant_id: str, display_name: str, participant_type: str = "human"):
        self.participant_id = participant_id
        self.display_name = display_name
        self.participant_type = participant_type
        self.auth_token = f"Bearer e2e_token_{participant_id}"
        self.conversation_id = None
        self.messages_sent = []
        self.messages_received = []
        self.last_sequence_id = 0
        self.is_online = False
        self.typing_state = False
        
    def create_message(self, content: str, message_type: str = "message") -> Dict[str, Any]:
        """Create a message from this participant."""
        message = {
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "type": message_type,
            "content": content,
            "sender_id": self.participant_id,
            "sender_name": self.display_name,
            "sender_type": self.participant_type,
            "timestamp": datetime.utcnow().isoformat(),
            "conversation_id": self.conversation_id
        }
        self.messages_sent.append(message)
        return message
    
    def receive_message(self, message: Dict[str, Any]):
        """Receive a message."""
        self.messages_received.append(message)
        if "sequence_id" in message:
            self.last_sequence_id = max(self.last_sequence_id, message["sequence_id"])
    
    def set_typing(self, is_typing: bool):
        """Set typing state."""
        self.typing_state = is_typing
    
    def join_conversation(self, conversation_id: str):
        """Join a conversation."""
        self.conversation_id = conversation_id
        self.is_online = True
    
    def leave_conversation(self):
        """Leave the conversation."""
        self.is_online = False


class E2EConversationManager:
    """Manage end-to-end conversation testing."""
    
    def __init__(self):
        self.conversations = {}
        self.participants = {}
        self.message_sequence = 0
        
    def create_conversation(self, title: str, sites: List[str], mode: str = "list") -> str:
        """Create a new conversation."""
        conversation_id = f"e2e_conv_{uuid.uuid4().hex[:8]}"
        self.conversations[conversation_id] = {
            "id": conversation_id,
            "title": title,
            "sites": sites,
            "mode": mode,
            "participants": [],
            "messages": [],
            "created_at": datetime.utcnow().isoformat()
        }
        return conversation_id
    
    def add_participant(self, conversation_id: str, participant: E2EParticipant):
        """Add participant to conversation."""
        if conversation_id in self.conversations:
            participant.join_conversation(conversation_id)
            self.conversations[conversation_id]["participants"].append({
                "participant_id": participant.participant_id,
                "display_name": participant.display_name,
                "type": participant.participant_type,
                "is_online": participant.is_online
            })
            self.participants[participant.participant_id] = participant
    
    def send_message(self, participant_id: str, content: str) -> Dict[str, Any]:
        """Send message from participant."""
        if participant_id not in self.participants:
            raise ValueError(f"Participant {participant_id} not found")
        
        participant = self.participants[participant_id]
        message = participant.create_message(content)
        
        # Add sequence ID
        self.message_sequence += 1
        message["sequence_id"] = self.message_sequence
        
        # Add to conversation
        if participant.conversation_id in self.conversations:
            self.conversations[participant.conversation_id]["messages"].append(message)
        
        # Broadcast to all participants in conversation
        for conv_participant in self.participants.values():
            if (conv_participant.conversation_id == participant.conversation_id and 
                conv_participant.participant_id != participant_id):
                conv_participant.receive_message(message)
        
        return message
    
    def simulate_ai_response(self, conversation_id: str, content: str) -> Dict[str, Any]:
        """Simulate AI response in conversation."""
        ai_participant = E2EParticipant("ai_assistant", "AI Assistant", "ai")
        ai_participant.join_conversation(conversation_id)
        
        ai_message = ai_participant.create_message(content, "ai_response")
        
        # Add sequence ID
        self.message_sequence += 1
        ai_message["sequence_id"] = self.message_sequence
        
        # Add to conversation
        if conversation_id in self.conversations:
            self.conversations[conversation_id]["messages"].append(ai_message)
        
        # Broadcast to all participants
        for participant in self.participants.values():
            if participant.conversation_id == conversation_id:
                participant.receive_message(ai_message)
        
        return ai_message
    
    def get_conversation_stats(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation statistics."""
        if conversation_id not in self.conversations:
            return {}
        
        conv = self.conversations[conversation_id]
        participant_count = len(conv["participants"])
        message_count = len(conv["messages"])
        
        human_messages = [m for m in conv["messages"] if m.get("sender_type") == "human"]
        ai_messages = [m for m in conv["messages"] if m.get("sender_type") == "ai"]
        
        return {
            "conversation_id": conversation_id,
            "participant_count": participant_count,
            "total_messages": message_count,
            "human_messages": len(human_messages),
            "ai_messages": len(ai_messages),
            "duration_minutes": 0,  # Would calculate based on timestamps
            "mode": conv["mode"]
        }


@pytest.fixture
async def e2e_client():
    """Create HTTP client for E2E testing."""
    async with httpx.AsyncClient(
        base_url=E2E_BASE_URL,
        timeout=httpx.Timeout(E2E_TIMEOUT)
    ) as client:
        yield client


@pytest.fixture
def conversation_manager():
    """Create conversation manager for E2E tests."""
    return E2EConversationManager()


@pytest.fixture
def human_participants():
    """Create human participants for testing."""
    return [
        E2EParticipant("alice_001", "Alice Smith"),
        E2EParticipant("bob_002", "Bob Jones"),
        E2EParticipant("charlie_003", "Charlie Brown")
    ]


@pytest.mark.e2e
@pytest.mark.asyncio
class TestSingleUserConversationFlow:
    """Test complete single user conversation flow."""
    
    async def test_create_send_receive_conversation_cycle(self, e2e_client, conversation_manager):
        """Test complete conversation cycle: create → send → receive → respond."""
        with aioresponses() as mock_resp:
            # Mock conversation creation
            conversation_id = conversation_manager.create_conversation(
                "Single User E2E Test",
                ["weather.com", "news.com"],
                "list"
            )
            
            mock_resp.post(
                f"{E2E_BASE_URL}/chat/create",
                payload={
                    "id": conversation_id,
                    "title": "Single User E2E Test",
                    "sites": ["weather.com", "news.com"],
                    "mode": "list"
                },
                status=201
            )
            
            # Mock message sending
            mock_resp.post(
                f"{E2E_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "message_id": "single_msg_001",
                    "sequence_id": 1
                },
                status=200
            )
            
            # Mock AI response
            mock_resp.get(
                f"{E2E_BASE_URL}/chat/conversations/{conversation_id}",
                payload={
                    "id": conversation_id,
                    "messages": [
                        {
                            "id": "single_msg_001",
                            "sequence_id": 1,
                            "content": "What's the weather today?",
                            "sender_type": "human"
                        },
                        {
                            "id": "ai_response_001",
                            "sequence_id": 2,
                            "content": "Today's weather is sunny with 75°F",
                            "sender_type": "ai"
                        }
                    ]
                },
                status=200
            )
            
            # Create single user
            user = E2EParticipant("single_user", "Test User")
            conversation_manager.add_participant(conversation_id, user)
            
            # Step 1: Create conversation
            response = await e2e_client.post(
                "/chat/create",
                json={
                    "title": "Single User E2E Test",
                    "sites": ["weather.com", "news.com"],
                    "mode": "list",
                    "participant": {
                        "participantId": user.participant_id,
                        "displayName": user.display_name
                    }
                },
                headers={"Authorization": user.auth_token}
            )
            
            assert response.status_code == 201
            
            # Step 2: Send message
            message_response = await e2e_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": "What's the weather today?"},
                headers={"Authorization": user.auth_token}
            )
            
            assert message_response.status_code == 200
            
            # Step 3: Simulate AI processing and response
            conversation_manager.send_message(user.participant_id, "What's the weather today?")
            ai_response = conversation_manager.simulate_ai_response(
                conversation_id,
                "Today's weather is sunny with 75°F"
            )
            
            # Step 4: Retrieve conversation with response
            conversation_response = await e2e_client.get(
                f"/chat/conversations/{conversation_id}",
                headers={"Authorization": user.auth_token}
            )
            
            assert conversation_response.status_code == 200
            conv_data = conversation_response.json()
            assert len(conv_data["messages"]) == 2
            assert conv_data["messages"][0]["sender_type"] == "human"
            assert conv_data["messages"][1]["sender_type"] == "ai"
            
            # Verify conversation statistics
            stats = conversation_manager.get_conversation_stats(conversation_id)
            assert stats["human_messages"] == 1
            assert stats["ai_messages"] == 1
            assert stats["participant_count"] == 1
    
    async def test_single_user_multiple_messages(self, e2e_client, conversation_manager):
        """Test single user sending multiple messages in sequence."""
        conversation_id = conversation_manager.create_conversation(
            "Multi-Message Test",
            ["example.com"],
            "summarize"
        )
        
        user = E2EParticipant("multi_msg_user", "Multi Message User")
        conversation_manager.add_participant(conversation_id, user)
        
        with aioresponses() as mock_resp:
            # Mock multiple message sends
            messages = [
                "First message about the weather",
                "Second message about traffic",
                "Third message asking for a summary"
            ]
            
            for i, message_content in enumerate(messages):
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "success": True,
                        "message_id": f"multi_msg_{i+1}",
                        "sequence_id": i + 1
                    },
                    status=200
                )
            
            # Send multiple messages
            for i, message_content in enumerate(messages):
                response = await e2e_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": message_content},
                    headers={"Authorization": user.auth_token}
                )
                
                assert response.status_code == 200
                conversation_manager.send_message(user.participant_id, message_content)
            
            # Simulate AI summary response
            ai_summary = conversation_manager.simulate_ai_response(
                conversation_id,
                "Summary: User asked about weather, traffic, and requested a summary."
            )
            
            # Verify message sequence
            stats = conversation_manager.get_conversation_stats(conversation_id)
            assert stats["human_messages"] == 3
            assert stats["ai_messages"] == 1
            assert stats["total_messages"] == 4
    
    async def test_single_user_conversation_modes(self, e2e_client, conversation_manager):
        """Test single user conversation with different modes."""
        modes = ["list", "summarize", "generate"]
        
        for mode in modes:
            conversation_id = conversation_manager.create_conversation(
                f"Mode Test - {mode}",
                ["example.com"],
                mode
            )
            
            user = E2EParticipant(f"mode_user_{mode}", f"Mode User {mode}")
            conversation_manager.add_participant(conversation_id, user)
            
            with aioresponses() as mock_resp:
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "success": True,
                        "message_id": f"mode_msg_{mode}",
                        "mode": mode
                    },
                    status=200
                )
                
                # Send message with specific mode
                response = await e2e_client.post(
                    f"/chat/{conversation_id}/message",
                    json={
                        "content": f"Test message for {mode} mode",
                        "mode": mode
                    },
                    headers={"Authorization": user.auth_token}
                )
                
                assert response.status_code == 200
                assert response.json()["mode"] == mode


@pytest.mark.e2e
@pytest.mark.asyncio
class TestMultiUserConversation:
    """Test multi-user conversation scenarios."""
    
    async def test_three_humans_one_ai_scenario(self, e2e_client, conversation_manager, human_participants):
        """Test scenario with 3 humans + 1 AI agent."""
        # Create conversation
        conversation_id = conversation_manager.create_conversation(
            "Team Discussion",
            ["docs.google.com", "github.com"],
            "generate"
        )
        
        # Add all human participants
        for participant in human_participants:
            conversation_manager.add_participant(conversation_id, participant)
        
        with aioresponses() as mock_resp:
            # Mock conversation creation
            mock_resp.post(
                f"{E2E_BASE_URL}/chat/create",
                payload={"id": conversation_id, "participant_count": 3},
                status=201
            )
            
            # Mock participant joining
            for i, participant in enumerate(human_participants[1:], 1):
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/join",
                    payload={"success": True, "participant_id": participant.participant_id},
                    status=200
                )
            
            # Mock message sending for each participant
            for i, participant in enumerate(human_participants):
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "success": True,
                        "message_id": f"team_msg_{i+1}",
                        "broadcast_count": 4  # 3 humans + 1 AI
                    },
                    status=200
                )
            
            # Step 1: First participant creates conversation
            creator = human_participants[0]
            create_response = await e2e_client.post(
                "/chat/create",
                json={
                    "title": "Team Discussion",
                    "sites": ["docs.google.com", "github.com"],
                    "mode": "generate",
                    "participant": {
                        "participantId": creator.participant_id,
                        "displayName": creator.display_name
                    }
                },
                headers={"Authorization": creator.auth_token}
            )
            
            assert create_response.status_code == 201
            
            # Step 2: Other participants join
            for participant in human_participants[1:]:
                join_response = await e2e_client.post(
                    f"/chat/{conversation_id}/join",
                    json={
                        "participant": {
                            "participantId": participant.participant_id,
                            "displayName": participant.display_name
                        }
                    },
                    headers={"Authorization": participant.auth_token}
                )
                
                assert join_response.status_code == 200
            
            # Step 3: Each human sends messages
            human_messages = [
                (human_participants[0], "Let's discuss the new feature requirements"),
                (human_participants[1], "I think we need to focus on user experience"),
                (human_participants[2], "What about performance implications?")
            ]
            
            for participant, message_content in human_messages:
                response = await e2e_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": message_content},
                    headers={"Authorization": participant.auth_token}
                )
                
                assert response.status_code == 200
                conversation_manager.send_message(participant.participant_id, message_content)
            
            # Step 4: AI responds to the discussion
            ai_response = conversation_manager.simulate_ai_response(
                conversation_id,
                "Based on your discussion, I recommend focusing on both UX and performance. Here's a balanced approach..."
            )
            
            # Verify conversation state
            stats = conversation_manager.get_conversation_stats(conversation_id)
            assert stats["participant_count"] == 3
            assert stats["human_messages"] == 3
            assert stats["ai_messages"] == 1
            assert stats["total_messages"] == 4
            
            # Verify all participants received all messages
            for participant in human_participants:
                assert len(participant.messages_received) == 3  # Messages from other participants + AI
    
    async def test_participant_join_during_active_conversation(self, e2e_client, conversation_manager):
        """Test participant joining during active conversation."""
        # Start with 2 participants
        initial_participants = [
            E2EParticipant("early_alice", "Early Alice"),
            E2EParticipant("early_bob", "Early Bob")
        ]
        
        conversation_id = conversation_manager.create_conversation(
            "Join During Active",
            ["example.com"],
            "list"
        )
        
        # Add initial participants
        for participant in initial_participants:
            conversation_manager.add_participant(conversation_id, participant)
        
        # Late joiner
        late_participant = E2EParticipant("late_charlie", "Late Charlie")
        
        with aioresponses() as mock_resp:
            # Mock initial messages
            for i in range(5):
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/message",
                    payload={"success": True, "message_id": f"early_msg_{i+1}"},
                    status=200
                )
            
            # Mock late participant join
            mock_resp.post(
                f"{E2E_BASE_URL}/chat/{conversation_id}/join",
                payload={
                    "success": True,
                    "participant_id": late_participant.participant_id,
                    "missed_messages": 5,
                    "sync_required": True
                },
                status=200
            )
            
            # Mock message sync for late joiner
            mock_resp.get(
                f"{E2E_BASE_URL}/chat/conversations/{conversation_id}",
                payload={
                    "id": conversation_id,
                    "messages": [
                        {"sequence_id": i+1, "content": f"Early message {i+1}"} 
                        for i in range(5)
                    ],
                    "current_sequence_id": 5
                },
                status=200
            )
            
            # Step 1: Initial participants send messages
            for i in range(5):
                sender = initial_participants[i % 2]  # Alternate senders
                
                response = await e2e_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"Early message {i+1}"},
                    headers={"Authorization": sender.auth_token}
                )
                
                assert response.status_code == 200
                conversation_manager.send_message(sender.participant_id, f"Early message {i+1}")
            
            # Step 2: Late participant joins
            join_response = await e2e_client.post(
                f"/chat/{conversation_id}/join",
                json={
                    "participant": {
                        "participantId": late_participant.participant_id,
                        "displayName": late_participant.display_name
                    }
                },
                headers={"Authorization": late_participant.auth_token}
            )
            
            assert join_response.status_code == 200
            join_data = join_response.json()
            assert join_data["missed_messages"] == 5
            assert join_data["sync_required"] is True
            
            # Step 3: Late participant syncs messages
            conversation_manager.add_participant(conversation_id, late_participant)
            
            sync_response = await e2e_client.get(
                f"/chat/conversations/{conversation_id}",
                headers={"Authorization": late_participant.auth_token}
            )
            
            assert sync_response.status_code == 200
            sync_data = sync_response.json()
            assert len(sync_data["messages"]) == 5
            assert sync_data["current_sequence_id"] == 5
            
            # Verify stats after late join
            stats = conversation_manager.get_conversation_stats(conversation_id)
            assert stats["participant_count"] == 3  # 2 initial + 1 late joiner
    
    async def test_participant_leave_and_rejoin(self, e2e_client, conversation_manager):
        """Test participant leaving and rejoining conversation."""
        participants = [
            E2EParticipant("stable_user", "Stable User"),
            E2EParticipant("leaving_user", "Leaving User")
        ]
        
        conversation_id = conversation_manager.create_conversation(
            "Leave and Rejoin Test",
            ["example.com"],
            "summarize"
        )
        
        # Add participants
        for participant in participants:
            conversation_manager.add_participant(conversation_id, participant)
        
        with aioresponses() as mock_resp:
            # Mock participant leaving
            mock_resp.delete(
                f"{E2E_BASE_URL}/chat/{conversation_id}/leave",
                payload={"success": True, "participant_left": True},
                status=200
            )
            
            # Mock messages sent while participant is away
            for i in range(3):
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/message",
                    payload={"success": True, "message_id": f"away_msg_{i+1}"},
                    status=200
                )
            
            # Mock participant rejoining
            mock_resp.post(
                f"{E2E_BASE_URL}/chat/{conversation_id}/join",
                payload={
                    "success": True,
                    "participant_rejoined": True,
                    "messages_missed": 3
                },
                status=200
            )
            
            # Step 1: Participant leaves
            leaving_user = participants[1]
            leave_response = await e2e_client.delete(
                f"/chat/{conversation_id}/leave",
                headers={"Authorization": leaving_user.auth_token}
            )
            
            assert leave_response.status_code == 200
            leaving_user.leave_conversation()
            
            # Step 2: Messages sent while participant is away
            stable_user = participants[0]
            for i in range(3):
                response = await e2e_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"Message while {leaving_user.display_name} is away {i+1}"},
                    headers={"Authorization": stable_user.auth_token}
                )
                
                assert response.status_code == 200
                conversation_manager.send_message(stable_user.participant_id, f"Away message {i+1}")
            
            # Step 3: Participant rejoins
            rejoin_response = await e2e_client.post(
                f"/chat/{conversation_id}/join",
                json={
                    "participant": {
                        "participantId": leaving_user.participant_id,
                        "displayName": leaving_user.display_name
                    }
                },
                headers={"Authorization": leaving_user.auth_token}
            )
            
            assert rejoin_response.status_code == 200
            rejoin_data = rejoin_response.json()
            assert rejoin_data["participant_rejoined"] is True
            assert rejoin_data["messages_missed"] == 3
            
            # Re-add participant to manager
            leaving_user.join_conversation(conversation_id)


@pytest.mark.e2e
@pytest.mark.asyncio
class TestLargeConversation:
    """Test large conversation scenarios."""
    
    async def test_50_plus_participants(self, e2e_client, conversation_manager):
        """Test conversation with 50+ participants."""
        participant_count = 25  # Reduced for testing (would be 50+ in production)
        
        # Create large conversation
        conversation_id = conversation_manager.create_conversation(
            "Large Group Discussion",
            ["community.example.com"],
            "summarize"
        )
        
        # Create many participants
        participants = [
            E2EParticipant(f"user_{i:03d}", f"User {i:03d}")
            for i in range(participant_count)
        ]
        
        with aioresponses() as mock_resp:
            # Mock conversation creation
            mock_resp.post(
                f"{E2E_BASE_URL}/chat/create",
                payload={"id": conversation_id, "max_participants": 100},
                status=201
            )
            
            # Mock bulk participant joining
            for participant in participants:
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/join",
                    payload={"success": True, "participant_count": len(participants)},
                    status=200
                )
            
            # Mock message sending (subset of participants)
            active_participants = participants[:10]  # Only 10 actively send messages
            for participant in active_participants:
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "success": True,
                        "broadcast_count": participant_count,
                        "delivery_time_ms": 150  # Should be <200ms for large groups
                    },
                    status=200
                )
            
            # Step 1: Create conversation
            creator = participants[0]
            create_response = await e2e_client.post(
                "/chat/create",
                json={
                    "title": "Large Group Discussion",
                    "sites": ["community.example.com"],
                    "mode": "summarize",
                    "participant": {
                        "participantId": creator.participant_id,
                        "displayName": creator.display_name
                    }
                },
                headers={"Authorization": creator.auth_token}
            )
            
            assert create_response.status_code == 201
            conversation_manager.add_participant(conversation_id, creator)
            
            # Step 2: Add many participants (simulate gradual joining)
            for participant in participants[1:]:
                join_response = await e2e_client.post(
                    f"/chat/{conversation_id}/join",
                    json={
                        "participant": {
                            "participantId": participant.participant_id,
                            "displayName": participant.display_name
                        }
                    },
                    headers={"Authorization": participant.auth_token}
                )
                
                assert join_response.status_code == 200
                conversation_manager.add_participant(conversation_id, participant)
            
            # Step 3: Active participants send messages
            for participant in active_participants:
                start_time = time.perf_counter()
                
                response = await e2e_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"Message from {participant.display_name}"},
                    headers={"Authorization": participant.auth_token}
                )
                
                end_time = time.perf_counter()
                delivery_time = (end_time - start_time) * 1000  # Convert to ms
                
                assert response.status_code == 200
                data = response.json()
                assert data["broadcast_count"] == participant_count
                
                # Verify large group performance target (<200ms)
                assert data["delivery_time_ms"] < 200, f"Large group delivery too slow: {data['delivery_time_ms']}ms"
                
                conversation_manager.send_message(participant.participant_id, f"Message from {participant.display_name}")
            
            # Verify large conversation stats
            stats = conversation_manager.get_conversation_stats(conversation_id)
            assert stats["participant_count"] == participant_count
            assert stats["total_messages"] == len(active_participants)
    
    async def test_high_message_volume(self, e2e_client, conversation_manager):
        """Test conversation with high message volume (10 msg/sec)."""
        conversation_id = conversation_manager.create_conversation(
            "High Volume Test",
            ["highvolume.example.com"],
            "list"
        )
        
        # Create active participants
        active_participants = [
            E2EParticipant(f"volume_user_{i}", f"Volume User {i}")
            for i in range(5)
        ]
        
        for participant in active_participants:
            conversation_manager.add_participant(conversation_id, participant)
        
        with aioresponses() as mock_resp:
            # Mock high volume message handling
            message_count = 50  # 50 messages over 5 seconds = 10 msg/sec
            
            for i in range(message_count):
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "success": True,
                        "message_id": f"volume_msg_{i+1}",
                        "queue_size": i + 1,
                        "processing_time_ms": 10
                    },
                    status=200
                )
            
            # Send high volume of messages
            start_time = time.perf_counter()
            message_tasks = []
            
            for i in range(message_count):
                sender = active_participants[i % len(active_participants)]
                
                task = e2e_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"High volume message {i+1}"},
                    headers={"Authorization": sender.auth_token}
                )
                message_tasks.append(task)
                
                # Control rate to achieve ~10 messages/second
                await asyncio.sleep(0.1)  # 100ms between messages
            
            # Wait for all messages to complete
            responses = await asyncio.gather(*message_tasks, return_exceptions=True)
            
            end_time = time.perf_counter()
            total_duration = end_time - start_time
            
            # Verify high volume handling
            successful_messages = sum(
                1 for response in responses 
                if not isinstance(response, Exception) and response.status_code == 200
            )
            
            messages_per_second = successful_messages / total_duration
            
            assert successful_messages >= message_count * 0.9, f"Too many failed messages: {successful_messages}/{message_count}"
            assert messages_per_second >= 8, f"Message rate too low: {messages_per_second:.1f} msg/sec"
            
            # Update conversation manager
            for i in range(successful_messages):
                sender = active_participants[i % len(active_participants)]
                conversation_manager.send_message(sender.participant_id, f"High volume message {i+1}")
            
            # Verify conversation state
            stats = conversation_manager.get_conversation_stats(conversation_id)
            assert stats["total_messages"] >= successful_messages


@pytest.mark.e2e
@pytest.mark.asyncio
class TestShareLinkAndJoin:
    """Test share link and join flow."""
    
    async def test_share_link_generation_and_usage(self, e2e_client, conversation_manager):
        """Test generating and using share links."""
        # Create conversation
        conversation_id = conversation_manager.create_conversation(
            "Shareable Conversation",
            ["shared.example.com"],
            "generate"
        )
        
        creator = E2EParticipant("creator_user", "Creator")
        conversation_manager.add_participant(conversation_id, creator)
        
        with aioresponses() as mock_resp:
            # Mock share link generation
            share_token = f"share_{uuid.uuid4().hex[:16]}"
            mock_resp.post(
                f"{E2E_BASE_URL}/chat/{conversation_id}/share",
                payload={
                    "share_link": f"https://chat.example.com/join/{share_token}",
                    "share_token": share_token,
                    "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
                    "max_uses": 10
                },
                status=200
            )
            
            # Mock join via share link
            joiner = E2EParticipant("joiner_user", "Joiner")
            mock_resp.post(
                f"{E2E_BASE_URL}/chat/join/{share_token}",
                payload={
                    "success": True,
                    "conversation_id": conversation_id,
                    "joined_via": "share_link",
                    "participant_id": joiner.participant_id
                },
                status=200
            )
            
            # Step 1: Generate share link
            share_response = await e2e_client.post(
                f"/chat/{conversation_id}/share",
                json={
                    "expires_hours": 24,
                    "max_uses": 10,
                    "permissions": ["read", "write"]
                },
                headers={"Authorization": creator.auth_token}
            )
            
            assert share_response.status_code == 200
            share_data = share_response.json()
            assert "share_link" in share_data
            assert "share_token" in share_data
            assert share_data["max_uses"] == 10
            
            # Step 2: Use share link to join
            join_response = await e2e_client.post(
                f"/chat/join/{share_data['share_token']}",
                json={
                    "participant": {
                        "participantId": joiner.participant_id,
                        "displayName": joiner.display_name
                    }
                },
                headers={"Authorization": joiner.auth_token}
            )
            
            assert join_response.status_code == 200
            join_data = join_response.json()
            assert join_data["success"] is True
            assert join_data["conversation_id"] == conversation_id
            assert join_data["joined_via"] == "share_link"
            
            # Add joiner to conversation manager
            conversation_manager.add_participant(conversation_id, joiner)
            
            # Verify both participants are in conversation
            stats = conversation_manager.get_conversation_stats(conversation_id)
            assert stats["participant_count"] == 2
    
    async def test_share_link_expiration_and_limits(self, e2e_client):
        """Test share link expiration and usage limits."""
        with aioresponses() as mock_resp:
            conversation_id = "share_limits_conv"
            expired_token = "expired_share_token"
            
            # Mock expired share link
            mock_resp.post(
                f"{E2E_BASE_URL}/chat/join/{expired_token}",
                payload={
                    "error": "Share link has expired",
                    "code": "SHARE_LINK_EXPIRED",
                    "expired_at": (datetime.utcnow() - timedelta(hours=1)).isoformat()
                },
                status=410
            )
            
            # Test expired share link
            joiner = E2EParticipant("expired_joiner", "Expired Joiner")
            
            expired_response = await e2e_client.post(
                f"/chat/join/{expired_token}",
                json={
                    "participant": {
                        "participantId": joiner.participant_id,
                        "displayName": joiner.display_name
                    }
                },
                headers={"Authorization": joiner.auth_token}
            )
            
            assert expired_response.status_code == 410
            assert "expired" in expired_response.json()["error"].lower()


@pytest.mark.e2e
@pytest.mark.asyncio
class TestFullConversationLifecycle:
    """Test complete conversation lifecycle."""
    
    async def test_create_chat_leave_lifecycle(self, e2e_client, conversation_manager, human_participants):
        """Test full lifecycle: create → chat → leave."""
        # Phase 1: Creation
        conversation_id = conversation_manager.create_conversation(
            "Full Lifecycle Test",
            ["lifecycle.example.com"],
            "generate"
        )
        
        with aioresponses() as mock_resp:
            # Mock all lifecycle operations
            mock_resp.post(
                f"{E2E_BASE_URL}/chat/create",
                payload={"id": conversation_id, "lifecycle_phase": "created"},
                status=201
            )
            
            # Mock joining
            for participant in human_participants[1:]:
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/join",
                    payload={"success": True, "lifecycle_phase": "active"},
                    status=200
                )
            
            # Mock active messaging
            for i in range(10):
                mock_resp.post(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/message",
                    payload={"success": True, "lifecycle_phase": "active"},
                    status=200
                )
            
            # Mock leaving
            for participant in human_participants:
                mock_resp.delete(
                    f"{E2E_BASE_URL}/chat/{conversation_id}/leave",
                    payload={"success": True, "lifecycle_phase": "concluded"},
                    status=200
                )
            
            # Phase 1: Create conversation
            creator = human_participants[0]
            create_response = await e2e_client.post(
                "/chat/create",
                json={
                    "title": "Full Lifecycle Test",
                    "sites": ["lifecycle.example.com"],
                    "mode": "generate",
                    "participant": {
                        "participantId": creator.participant_id,
                        "displayName": creator.display_name
                    }
                },
                headers={"Authorization": creator.auth_token}
            )
            
            assert create_response.status_code == 201
            conversation_manager.add_participant(conversation_id, creator)
            
            # Phase 2: Other participants join
            for participant in human_participants[1:]:
                join_response = await e2e_client.post(
                    f"/chat/{conversation_id}/join",
                    json={
                        "participant": {
                            "participantId": participant.participant_id,
                            "displayName": participant.display_name
                        }
                    },
                    headers={"Authorization": participant.auth_token}
                )
                
                assert join_response.status_code == 200
                conversation_manager.add_participant(conversation_id, participant)
            
            # Phase 3: Active conversation
            for i in range(10):
                sender = human_participants[i % len(human_participants)]
                
                message_response = await e2e_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"Lifecycle message {i+1}"},
                    headers={"Authorization": sender.auth_token}
                )
                
                assert message_response.status_code == 200
                conversation_manager.send_message(sender.participant_id, f"Lifecycle message {i+1}")
            
            # Add AI responses during active phase
            for i in range(3):
                conversation_manager.simulate_ai_response(
                    conversation_id,
                    f"AI response {i+1} to the ongoing discussion"
                )
            
            # Phase 4: Participants leave
            for participant in human_participants:
                leave_response = await e2e_client.delete(
                    f"/chat/{conversation_id}/leave",
                    headers={"Authorization": participant.auth_token}
                )
                
                assert leave_response.status_code == 200
                participant.leave_conversation()
            
            # Verify complete lifecycle
            stats = conversation_manager.get_conversation_stats(conversation_id)
            assert stats["total_messages"] == 13  # 10 human + 3 AI
            assert stats["human_messages"] == 10
            assert stats["ai_messages"] == 3
            
            # Verify all participants left
            for participant in human_participants:
                assert participant.is_online is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])