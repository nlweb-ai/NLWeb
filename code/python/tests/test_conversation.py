"""
Tests for conversation orchestration.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import time
from typing import List, Dict, Any

from chat.schemas import (
    ChatMessage,
    Conversation,
    ParticipantInfo,
    ParticipantType,
    MessageType,
    MessageStatus,
    QueueFullError
)
from chat.participants import BaseParticipant, HumanParticipant, NLWebParticipant

# These imports will fail until we create the module
from chat.conversation import (
    ConversationManager,
    ConversationMode,
    MessageDeliveryError,
    ParticipantFailure
)


class MockParticipant(BaseParticipant):
    """Mock participant for testing"""
    def __init__(self, participant_id: str, participant_type: ParticipantType):
        self.participant_id = participant_id
        self.participant_type = participant_type
        self.messages_received = []
        self.process_message_mock = AsyncMock()
        
    async def process_message(self, message, context, stream_callback=None):
        self.messages_received.append(message)
        return await self.process_message_mock(message, context, stream_callback)
    
    def get_participant_info(self):
        return ParticipantInfo(
            participant_id=self.participant_id,
            name=f"Mock {self.participant_id}",
            participant_type=self.participant_type,
            joined_at=datetime.utcnow()
        )


class TestConversationManager:
    """Test conversation manager orchestration"""
    
    @pytest.fixture
    def manager_config(self):
        """Create test configuration"""
        return {
            "single_mode_timeout": 100,  # ms
            "multi_mode_timeout": 2000,  # ms
            "queue_size_limit": 1000,
            "max_participants": 100
        }
    
    @pytest.fixture
    async def manager(self, manager_config):
        """Create conversation manager"""
        manager = ConversationManager(manager_config)
        yield manager
        await manager.shutdown()
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock storage"""
        storage = AsyncMock()
        # Use a counter for sequence IDs
        self._sequence_counters = {}
        
        async def get_next_sequence_id(conv_id):
            if conv_id not in self._sequence_counters:
                self._sequence_counters[conv_id] = 0
            self._sequence_counters[conv_id] += 1
            return self._sequence_counters[conv_id]
        
        storage.get_next_sequence_id = AsyncMock(side_effect=get_next_sequence_id)
        storage.store_message = AsyncMock()
        return storage
    
    @pytest.mark.asyncio
    async def test_single_mode_detection(self, manager):
        """Test single mode detection (1 human + 1 NLWeb)"""
        # Add 1 human
        human = MockParticipant("user_123", ParticipantType.HUMAN)
        manager.add_participant("conv_abc", human)
        
        # Add 1 NLWeb
        nlweb = MockParticipant("nlweb_1", ParticipantType.AI)
        manager.add_participant("conv_abc", nlweb)
        
        # Should be in single mode
        assert manager.get_conversation_mode("conv_abc") == ConversationMode.SINGLE
        assert manager.get_input_timeout("conv_abc") == 100
    
    @pytest.mark.asyncio
    async def test_multi_mode_detection(self, manager):
        """Test multi mode detection (2+ humans or 3+ total)"""
        # Test with 2 humans + 1 NLWeb
        human1 = MockParticipant("user_123", ParticipantType.HUMAN)
        human2 = MockParticipant("user_456", ParticipantType.HUMAN)
        nlweb = MockParticipant("nlweb_1", ParticipantType.AI)
        
        manager.add_participant("conv_abc", human1)
        manager.add_participant("conv_abc", human2)
        manager.add_participant("conv_abc", nlweb)
        
        # Should be in multi mode
        assert manager.get_conversation_mode("conv_abc") == ConversationMode.MULTI
        assert manager.get_input_timeout("conv_abc") == 2000
    
    @pytest.mark.asyncio
    async def test_mode_change_notification(self, manager):
        """Test mode change broadcasts to all humans"""
        # Start with single mode
        human = MockParticipant("user_123", ParticipantType.HUMAN)
        nlweb = MockParticipant("nlweb_1", ParticipantType.AI)
        
        # Track broadcasts
        broadcasts = []
        manager.broadcast_callback = lambda conv_id, msg: broadcasts.append(msg)
        
        manager.add_participant("conv_abc", human)
        manager.add_participant("conv_abc", nlweb)
        
        # Add another human - should trigger mode change
        human2 = MockParticipant("user_456", ParticipantType.HUMAN)
        manager.add_participant("conv_abc", human2)
        
        # Should have broadcast mode change
        assert len(broadcasts) > 0
        mode_change = next((b for b in broadcasts if b.get("type") == "mode_change"), None)
        assert mode_change is not None
        assert mode_change["mode"] == "multi"
        assert mode_change["input_timeout"] == 2000
    
    @pytest.mark.asyncio
    async def test_message_routing(self, manager, mock_storage):
        """Test message routing to all participants"""
        manager.storage = mock_storage
        
        # Create participants
        human = MockParticipant("user_123", ParticipantType.HUMAN)
        nlweb1 = MockParticipant("nlweb_1", ParticipantType.AI)
        nlweb2 = MockParticipant("nlweb_2", ParticipantType.AI)
        
        manager.add_participant("conv_abc", human)
        manager.add_participant("conv_abc", nlweb1)
        manager.add_participant("conv_abc", nlweb2)
        
        # Send message from human
        message = ChatMessage(
            message_id="msg_123",
            conversation_id="conv_abc",
            sequence_id=0,  # Will be assigned
            sender_id="user_123",
            sender_name="User",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Process message
        result = await manager.process_message(message)
        
        # Should assign sequence ID
        assert result.sequence_id == 1
        
        # Both NLWeb participants should receive it
        assert len(nlweb1.messages_received) == 1
        assert len(nlweb2.messages_received) == 1
        assert nlweb1.messages_received[0].content == "Hello"
        assert nlweb2.messages_received[0].content == "Hello"
        
        # Storage should be called after delivery
        # Wait for async persistence
        await asyncio.sleep(0.1)
        mock_storage.store_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multi_human_message_routing(self, manager, mock_storage):
        """Test messages from multiple humans are routed correctly"""
        manager.storage = mock_storage
        
        # Create multiple humans and NLWeb
        alice = MockParticipant("alice_123", ParticipantType.HUMAN)
        bob = MockParticipant("bob_456", ParticipantType.HUMAN)
        nlweb = MockParticipant("nlweb_1", ParticipantType.AI)
        
        manager.add_participant("conv_multi", alice)
        manager.add_participant("conv_multi", bob)
        manager.add_participant("conv_multi", nlweb)
        
        # Alice sends message
        alice_msg = ChatMessage(
            message_id="msg_1",
            conversation_id="conv_multi",
            sequence_id=0,
            sender_id="alice_123",
            sender_name="Alice",
            content="Hi everyone!",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        await manager.process_message(alice_msg)
        
        # Bob should receive Alice's message
        assert len(bob.messages_received) == 1
        assert bob.messages_received[0].sender_id == "alice_123"
        
        # NLWeb should also receive it
        assert len(nlweb.messages_received) == 1
        
        # Bob sends message
        bob_msg = ChatMessage(
            message_id="msg_2",
            conversation_id="conv_multi",
            sequence_id=0,
            sender_id="bob_456",
            sender_name="Bob",
            content="Hi Alice!",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        await manager.process_message(bob_msg)
        
        # Alice should receive Bob's message
        assert len(alice.messages_received) == 1
        assert alice.messages_received[0].sender_id == "bob_456"
        
        # NLWeb should have both messages
        assert len(nlweb.messages_received) == 2
    
    @pytest.mark.asyncio
    async def test_queue_limit_enforcement(self, manager, mock_storage):
        """Test queue limit enforcement"""
        manager.storage = mock_storage
        manager.queue_size_limit = 3  # Set directly on manager
        
        # Add participants
        human = MockParticipant("user_123", ParticipantType.HUMAN)
        nlweb = MockParticipant("nlweb_1", ParticipantType.AI)
        
        manager.add_participant("conv_limited", human)
        manager.add_participant("conv_limited", nlweb)
        
        # Send messages up to limit
        for i in range(3):
            msg = ChatMessage(
                message_id=f"msg_{i}",
                conversation_id="conv_limited",
                sequence_id=0,
                sender_id="user_123",
                sender_name="User",
                content=f"Message {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            await manager.process_message(msg)
        
        # Fourth message should fail
        msg = ChatMessage(
            message_id="msg_4",
            conversation_id="conv_limited",
            sequence_id=0,
            sender_id="user_123",
            sender_name="User",
            content="This should fail",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        with pytest.raises(QueueFullError) as exc_info:
            await manager.process_message(msg)
        
        assert exc_info.value.conversation_id == "conv_limited"
        assert exc_info.value.queue_size == 3
    
    @pytest.mark.asyncio
    async def test_participant_failure_handling(self, manager, mock_storage):
        """Test handling of participant failures"""
        manager.storage = mock_storage
        
        # Create participants
        human = MockParticipant("user_123", ParticipantType.HUMAN)
        nlweb_good = MockParticipant("nlweb_1", ParticipantType.AI)
        nlweb_bad = MockParticipant("nlweb_2", ParticipantType.AI)
        
        # Make nlweb_bad fail
        nlweb_bad.process_message_mock.side_effect = Exception("Processing failed")
        
        manager.add_participant("conv_abc", human)
        manager.add_participant("conv_abc", nlweb_good)
        manager.add_participant("conv_abc", nlweb_bad)
        
        # Send message
        message = ChatMessage(
            message_id="msg_123",
            conversation_id="conv_abc",
            sequence_id=0,
            sender_id="user_123",
            sender_name="User",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Should not raise - failures are handled gracefully
        result = await manager.process_message(message)
        
        # Good participant should still receive message
        assert len(nlweb_good.messages_received) == 1
        
        # Check failure was logged
        failures = manager.get_participant_failures("conv_abc")
        assert len(failures) > 0
        assert failures[0].participant_id == "nlweb_2"
    
    @pytest.mark.asyncio
    async def test_at_least_once_delivery(self, manager, mock_storage):
        """Test at-least-once delivery with acknowledgments"""
        manager.storage = mock_storage
        
        # Create participants
        human = MockParticipant("user_123", ParticipantType.HUMAN)
        nlweb = MockParticipant("nlweb_1", ParticipantType.AI)
        
        manager.add_participant("conv_abc", human)
        manager.add_participant("conv_abc", nlweb)
        
        # Send message with tracking
        message = ChatMessage(
            message_id="msg_123",
            conversation_id="conv_abc",
            sequence_id=0,
            sender_id="user_123",
            sender_name="User",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        result = await manager.process_message(message, require_ack=True)
        
        # Check acknowledgment
        assert result.status == MessageStatus.DELIVERED
        assert result.metadata is not None
        assert 'delivery_acks' in result.metadata
        assert "nlweb_1" in result.metadata['delivery_acks']
    
    @pytest.mark.asyncio
    async def test_async_persistence(self, manager, mock_storage):
        """Test that persistence happens after delivery"""
        manager.storage = mock_storage
        
        # Track call order
        call_order = []
        
        # Mock participant that tracks when it receives message
        participant = MockParticipant("nlweb_1", ParticipantType.AI)
        original_process = participant.process_message
        
        async def track_process(*args, **kwargs):
            call_order.append("participant_received")
            return await original_process(*args, **kwargs)
        
        participant.process_message = track_process
        
        # Mock storage that tracks when it's called
        original_store = mock_storage.store_message
        
        async def track_store(*args, **kwargs):
            call_order.append("storage_called")
            return await original_store(*args, **kwargs)
        
        mock_storage.store_message = track_store
        
        # Add participants
        human = MockParticipant("user_123", ParticipantType.HUMAN)
        manager.add_participant("conv_abc", human)
        manager.add_participant("conv_abc", participant)
        
        # Send message
        message = ChatMessage(
            message_id="msg_123",
            conversation_id="conv_abc",
            sequence_id=0,
            sender_id="user_123",
            sender_name="User",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        await manager.process_message(message)
        
        # Wait a bit for async operations
        await asyncio.sleep(0.1)
        
        # Participant should receive before storage
        assert call_order.index("participant_received") < call_order.index("storage_called")
    
    @pytest.mark.asyncio
    async def test_nlweb_job_dropping(self, manager, mock_storage):
        """Test dropping oldest NLWeb jobs when queue is full"""
        manager.storage = mock_storage
        manager.config["queue_size_limit"] = 3
        
        # Create slow NLWeb participant
        human = MockParticipant("user_123", ParticipantType.HUMAN)
        slow_nlweb = MockParticipant("nlweb_1", ParticipantType.AI)
        
        # Make NLWeb slow
        async def slow_process(msg, ctx, callback=None):
            await asyncio.sleep(1)  # Simulate slow processing
            return None
        
        slow_nlweb.process_message_mock = slow_process
        
        manager.add_participant("conv_queue", human)
        manager.add_participant("conv_queue", slow_nlweb)
        
        # Send messages rapidly
        for i in range(5):
            msg = ChatMessage(
                message_id=f"msg_{i}",
                conversation_id="conv_queue",
                sequence_id=0,
                sender_id="user_123",
                sender_name="User",
                content=f"Message {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            
            if i < 3:
                await manager.process_message(msg)
            else:
                # Should handle queue management
                try:
                    await manager.process_message(msg)
                except QueueFullError:
                    # Expected for some messages
                    pass
        
        # Check that oldest NLWeb jobs were dropped
        active_jobs = manager.get_active_nlweb_jobs("conv_queue")
        assert len(active_jobs) <= 3
    
    @pytest.mark.asyncio
    async def test_concurrent_sequence_assignment(self, manager, mock_storage):
        """Test atomic sequence ID assignment with concurrent messages"""
        manager.storage = mock_storage
        
        # Mock storage to return incrementing sequence IDs
        sequence_counter = 0
        
        async def get_next_seq(conv_id):
            nonlocal sequence_counter
            sequence_counter += 1
            return sequence_counter
        
        mock_storage.get_next_sequence_id = AsyncMock(side_effect=get_next_seq)
        
        # Create participants
        human1 = MockParticipant("user_123", ParticipantType.HUMAN)
        human2 = MockParticipant("user_456", ParticipantType.HUMAN)
        nlweb = MockParticipant("nlweb_1", ParticipantType.AI)
        
        manager.add_participant("conv_concurrent", human1)
        manager.add_participant("conv_concurrent", human2)
        manager.add_participant("conv_concurrent", nlweb)
        
        # Send multiple messages concurrently
        messages = []
        for i in range(10):
            msg = ChatMessage(
                message_id=f"msg_{i}",
                conversation_id="conv_concurrent",
                sequence_id=0,
                sender_id=f"user_{i % 2 + 1}23",
                sender_name=f"User{i % 2}",
                content=f"Message {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            messages.append(msg)
        
        # Process concurrently
        tasks = [manager.process_message(msg) for msg in messages]
        results = await asyncio.gather(*tasks)
        
        # All should have unique sequence IDs
        sequence_ids = [r.sequence_id for r in results]
        assert len(set(sequence_ids)) == 10
        assert sorted(sequence_ids) == list(range(1, 11))
    
    @pytest.mark.asyncio
    async def test_broadcast_to_all_participants(self, manager, mock_storage):
        """Test that messages are broadcast to ALL participants"""
        manager.storage = mock_storage
        
        # Create multiple participants
        participants = []
        for i in range(5):
            p_type = ParticipantType.HUMAN if i < 3 else ParticipantType.AI
            p = MockParticipant(f"participant_{i}", p_type)
            participants.append(p)
            manager.add_participant("conv_broadcast", p)
        
        # Send message from first participant
        message = ChatMessage(
            message_id="msg_broadcast",
            conversation_id="conv_broadcast",
            sequence_id=0,
            sender_id="participant_0",
            sender_name="Participant 0",
            content="Broadcast test",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        await manager.process_message(message)
        
        # All OTHER participants should receive it
        for i, p in enumerate(participants):
            if i == 0:  # Sender
                assert len(p.messages_received) == 0
            else:
                assert len(p.messages_received) == 1
                assert p.messages_received[0].content == "Broadcast test"


class TestConversationMode:
    """Test conversation mode enum"""
    
    def test_conversation_modes(self):
        """Test conversation mode values"""
        assert ConversationMode.SINGLE.value == "single"
        assert ConversationMode.MULTI.value == "multi"


class TestMessageDeliveryError:
    """Test delivery error handling"""
    
    def test_delivery_error(self):
        """Test message delivery error"""
        error = MessageDeliveryError(
            message_id="msg_123",
            participant_id="nlweb_1",
            reason="Connection failed"
        )
        
        assert error.message_id == "msg_123"
        assert error.participant_id == "nlweb_1"
        assert "Connection failed" in str(error)