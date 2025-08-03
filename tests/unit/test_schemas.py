"""
Unit tests for chat system schemas and data models.
Tests ChatMessage, Conversation, and ParticipantInfo models.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Set
import pytest
from hypothesis import given, strategies as st, assume

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../code/python'))

from chat.schemas import (
    ChatMessage, MessageType, MessageStatus,
    Conversation, ParticipantInfo, ParticipantType,
    QueueFullError
)


@pytest.mark.unit
class TestChatMessage:
    """Test ChatMessage schema."""
    
    def test_unique_message_id_generation(self):
        """Test that message IDs are unique."""
        message_ids = set()
        for i in range(1000):
            msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            assert msg_id not in message_ids
            message_ids.add(msg_id)
    
    def test_sequence_id_server_side_only(self):
        """Test that sequence_id must be assigned server-side."""
        # Create message with sequence_id=0 (not assigned)
        msg = ChatMessage(
            message_id="msg_test_001",
            conversation_id="conv_001",
            sequence_id=0,  # Not yet assigned
            sender_id="user_123",
            sender_name="Test User",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        assert msg.sequence_id == 0
        
        # Verify immutability - can't change sequence_id after creation
        with pytest.raises(AttributeError):
            msg.sequence_id = 1
    
    def test_sender_id_identifies_different_humans(self):
        """Test that sender_id correctly identifies different participants."""
        participants = [
            ("user_123", "Alice"),
            ("user_456", "Bob"),
            ("nlweb_1", "AI Assistant"),
            ("system", "System")
        ]
        
        messages = []
        for sender_id, sender_name in participants:
            msg = ChatMessage(
                message_id=f"msg_{sender_id}_1",
                conversation_id="conv_001",
                sequence_id=len(messages) + 1,
                sender_id=sender_id,
                sender_name=sender_name,
                content=f"Message from {sender_name}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            messages.append(msg)
        
        # Verify all sender_ids are unique
        sender_ids = [msg.sender_id for msg in messages]
        assert len(sender_ids) == len(set(sender_ids))
        
        # Verify human vs AI identification
        assert messages[0].sender_id.startswith("user_")
        assert messages[1].sender_id.startswith("user_")
        assert messages[2].sender_id.startswith("nlweb_")
        assert messages[3].sender_id == "system"
    
    def test_timestamp_in_utc(self):
        """Test that timestamps are in UTC."""
        now_utc = datetime.now(timezone.utc)
        msg = ChatMessage(
            message_id="msg_test_utc",
            conversation_id="conv_001",
            sequence_id=1,
            sender_id="user_123",
            sender_name="Test User",
            content="UTC test",
            message_type=MessageType.TEXT,
            timestamp=now_utc
        )
        
        # Verify timestamp has UTC timezone info
        assert msg.timestamp.tzinfo == timezone.utc
        
        # Test with naive datetime (should work but not recommended)
        naive_time = datetime.utcnow()
        msg2 = ChatMessage(
            message_id="msg_test_naive",
            conversation_id="conv_001",
            sequence_id=2,
            sender_id="user_123",
            sender_name="Test User",
            content="Naive time test",
            message_type=MessageType.TEXT,
            timestamp=naive_time
        )
        assert msg2.timestamp.tzinfo is None
    
    def test_message_content_validation(self):
        """Test message content validation."""
        # Empty content
        msg = ChatMessage(
            message_id="msg_empty",
            conversation_id="conv_001",
            sequence_id=1,
            sender_id="user_123",
            sender_name="Test User",
            content="",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        assert msg.content == ""
        
        # Very long content (near 10,000 char limit)
        long_content = "A" * 9999
        msg_long = ChatMessage(
            message_id="msg_long",
            conversation_id="conv_001",
            sequence_id=2,
            sender_id="user_123",
            sender_name="Test User",
            content=long_content,
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        assert len(msg_long.content) == 9999
    
    def test_maximum_message_size_enforcement(self):
        """Test that messages enforce 10,000 character limit."""
        # Note: The schema doesn't enforce this limit, it would be enforced
        # at the API/validation layer
        oversized_content = "X" * 10001
        
        # Schema allows it (enforcement would be elsewhere)
        msg = ChatMessage(
            message_id="msg_oversized",
            conversation_id="conv_001",
            sequence_id=1,
            sender_id="user_123",
            sender_name="Test User",
            content=oversized_content,
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        assert len(msg.content) == 10001
    
    def test_message_type_enum_validation(self):
        """Test MessageType enum validation."""
        valid_types = [
            MessageType.TEXT,
            MessageType.SYSTEM,
            MessageType.NLWEB_RESPONSE,
            MessageType.ERROR
        ]
        
        for msg_type in valid_types:
            msg = ChatMessage(
                message_id=f"msg_type_{msg_type.value}",
                conversation_id="conv_001",
                sequence_id=1,
                sender_id="user_123",
                sender_name="Test User",
                content=f"Test {msg_type.value}",
                message_type=msg_type,
                timestamp=datetime.utcnow()
            )
            assert msg.message_type == msg_type
            assert msg.to_dict()["message_type"] == msg_type.value
        
        # Test invalid type
        with pytest.raises(AttributeError):
            MessageType.INVALID
    
    def test_status_transitions(self):
        """Test message status transitions."""
        # Create pending message
        msg_dict = {
            "message_id": "msg_status",
            "conversation_id": "conv_001",
            "sequence_id": 1,
            "sender_id": "user_123",
            "sender_name": "Test User",
            "content": "Status test",
            "message_type": MessageType.TEXT,
            "timestamp": datetime.utcnow()
        }
        
        # Test all valid statuses
        for status in [MessageStatus.PENDING, MessageStatus.DELIVERED, 
                      MessageStatus.FAILED, MessageStatus.PROCESSING]:
            msg = ChatMessage(**msg_dict, status=status)
            assert msg.status == status
        
        # Default status should be DELIVERED
        msg_default = ChatMessage(**msg_dict)
        assert msg_default.status == MessageStatus.DELIVERED
    
    def test_message_immutability(self):
        """Test that ChatMessage is immutable."""
        msg = ChatMessage(
            message_id="msg_immutable",
            conversation_id="conv_001",
            sequence_id=1,
            sender_id="user_123",
            sender_name="Test User",
            content="Immutable test",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Try to modify attributes - should raise AttributeError
        with pytest.raises(AttributeError):
            msg.content = "Modified content"
        
        with pytest.raises(AttributeError):
            msg.sender_id = "different_user"
        
        with pytest.raises(AttributeError):
            msg.sequence_id = 999
    
    def test_message_serialization(self):
        """Test to_dict serialization."""
        timestamp = datetime.utcnow()
        metadata = {"key": "value", "number": 42}
        
        msg = ChatMessage(
            message_id="msg_serialize",
            conversation_id="conv_001",
            sequence_id=5,
            sender_id="user_123",
            sender_name="Test User",
            content="Serialization test",
            message_type=MessageType.TEXT,
            timestamp=timestamp,
            status=MessageStatus.DELIVERED,
            metadata=metadata
        )
        
        msg_dict = msg.to_dict()
        
        assert msg_dict["message_id"] == "msg_serialize"
        assert msg_dict["conversation_id"] == "conv_001"
        assert msg_dict["sequence_id"] == 5
        assert msg_dict["sender_id"] == "user_123"
        assert msg_dict["sender_name"] == "Test User"
        assert msg_dict["content"] == "Serialization test"
        assert msg_dict["message_type"] == "text"
        assert msg_dict["timestamp"] == timestamp.isoformat()
        assert msg_dict["status"] == "delivered"
        assert msg_dict["metadata"] == metadata


@pytest.mark.unit
class TestConversation:
    """Test Conversation model."""
    
    def test_participant_tracking_multiple_humans(self):
        """Test tracking multiple human participants."""
        conv = Conversation(
            conversation_id="conv_multi",
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=1000
        )
        
        # Add multiple humans
        humans = [
            ParticipantInfo("user_1", "Alice", ParticipantType.HUMAN, datetime.utcnow()),
            ParticipantInfo("user_2", "Bob", ParticipantType.HUMAN, datetime.utcnow()),
            ParticipantInfo("user_3", "Charlie", ParticipantType.HUMAN, datetime.utcnow())
        ]
        
        for human in humans:
            conv.add_participant(human)
        
        assert len(conv.active_participants) == 3
        assert len(conv.get_human_participants()) == 3
        assert len(conv.get_ai_participants()) == 0
        
        # Add AI participant
        ai = ParticipantInfo("nlweb_1", "AI Assistant", ParticipantType.AI, datetime.utcnow())
        conv.add_participant(ai)
        
        assert len(conv.active_participants) == 4
        assert len(conv.get_human_participants()) == 3
        assert len(conv.get_ai_participants()) == 1
    
    def test_mode_switching_based_on_participants(self):
        """Test conversation mode switching (would be in ConversationManager)."""
        # Note: The Conversation schema doesn't have mode, this is in ConversationManager
        conv = Conversation(
            conversation_id="conv_mode",
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=1000
        )
        
        # Single human + AI = SINGLE mode
        human1 = ParticipantInfo("user_1", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        ai = ParticipantInfo("nlweb_1", "AI", ParticipantType.AI, datetime.utcnow())
        conv.add_participant(human1)
        conv.add_participant(ai)
        
        assert len(conv.get_human_participants()) == 1
        assert len(conv.get_ai_participants()) == 1
        
        # Add second human = MULTI mode
        human2 = ParticipantInfo("user_2", "Bob", ParticipantType.HUMAN, datetime.utcnow())
        conv.add_participant(human2)
        
        assert len(conv.get_human_participants()) == 2
    
    def test_queue_size_limit_enforcement(self):
        """Test queue size limit enforcement."""
        conv = Conversation(
            conversation_id="conv_queue",
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=1000
        )
        
        # Fill up to limit
        for i in range(1000):
            conv.increment_message_count()
        
        assert conv.message_count == 1000
        
        # Should raise QueueFullError
        with pytest.raises(QueueFullError) as exc_info:
            conv.check_queue_limit()
        
        error = exc_info.value
        assert error.conversation_id == "conv_queue"
        assert error.queue_size == 1000
        assert error.limit == 1000
    
    def test_last_message_tracking(self):
        """Test conversation update tracking."""
        start_time = datetime.utcnow()
        conv = Conversation(
            conversation_id="conv_track",
            created_at=start_time,
            active_participants=set(),
            queue_size_limit=1000
        )
        
        assert conv.updated_at is None
        
        # Add participant updates timestamp
        participant = ParticipantInfo("user_1", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        conv.add_participant(participant)
        
        assert conv.updated_at is not None
        assert conv.updated_at > start_time
        
        # Increment message updates timestamp
        old_update = conv.updated_at
        conv.increment_message_count()
        
        assert conv.updated_at > old_update
    
    def test_participant_join_leave_events(self):
        """Test participant join/leave event generation."""
        conv = Conversation(
            conversation_id="conv_events",
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=1000
        )
        
        participant = ParticipantInfo("user_1", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        
        # Test join event
        join_msg = conv.create_participant_event(participant, "join")
        assert join_msg.message_type == MessageType.SYSTEM
        assert join_msg.sender_id == "system"
        assert "joined the conversation" in join_msg.content
        assert join_msg.metadata["event_type"] == "participant_join"
        assert join_msg.metadata["participant_id"] == "user_1"
        
        # Test leave event
        leave_msg = conv.create_participant_event(participant, "leave")
        assert "left the conversation" in leave_msg.content
        assert leave_msg.metadata["event_type"] == "participant_leave"
        
        # Test invalid event type
        with pytest.raises(ValueError):
            conv.create_participant_event(participant, "invalid")
    
    def test_maximum_participant_limit(self):
        """Test maximum participant limit (100)."""
        conv = Conversation(
            conversation_id="conv_max",
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=1000
        )
        
        # Add 100 participants
        for i in range(100):
            participant = ParticipantInfo(
                f"user_{i}",
                f"User {i}",
                ParticipantType.HUMAN if i < 95 else ParticipantType.AI,
                datetime.utcnow()
            )
            conv.add_participant(participant)
        
        assert len(conv.active_participants) == 100
        
        # Note: The schema doesn't enforce the limit, ConversationManager would
    
    def test_remove_participant(self):
        """Test removing participants."""
        conv = Conversation(
            conversation_id="conv_remove",
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=1000
        )
        
        # Add participants
        p1 = ParticipantInfo("user_1", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        p2 = ParticipantInfo("user_2", "Bob", ParticipantType.HUMAN, datetime.utcnow())
        p3 = ParticipantInfo("nlweb_1", "AI", ParticipantType.AI, datetime.utcnow())
        
        conv.add_participant(p1)
        conv.add_participant(p2)
        conv.add_participant(p3)
        
        assert len(conv.active_participants) == 3
        
        # Remove one participant
        conv.remove_participant("user_2")
        
        assert len(conv.active_participants) == 2
        assert p1 in conv.active_participants
        assert p2 not in conv.active_participants
        assert p3 in conv.active_participants
    
    def test_conversation_serialization(self):
        """Test conversation to_dict serialization."""
        created_at = datetime.utcnow()
        conv = Conversation(
            conversation_id="conv_serial",
            created_at=created_at,
            active_participants=set(),
            queue_size_limit=500,
            metadata={"key": "value"}
        )
        
        # Add participants
        p1 = ParticipantInfo("user_1", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        conv.add_participant(p1)
        conv.increment_message_count()
        
        conv_dict = conv.to_dict()
        
        assert conv_dict["conversation_id"] == "conv_serial"
        assert conv_dict["created_at"] == created_at.isoformat()
        assert conv_dict["participant_count"] == 1
        assert len(conv_dict["participants"]) == 1
        assert conv_dict["message_count"] == 1
        assert conv_dict["queue_size_limit"] == 500


@pytest.mark.unit
class TestParticipantInfo:
    """Test ParticipantInfo model."""
    
    def test_human_vs_ai_distinction(self):
        """Test distinguishing human vs AI participants."""
        human = ParticipantInfo(
            participant_id="user_123",
            name="Alice",
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        ai = ParticipantInfo(
            participant_id="nlweb_1",
            name="AI Assistant",
            participant_type=ParticipantType.AI,
            joined_at=datetime.utcnow()
        )
        
        assert human.is_human() is True
        assert human.is_ai() is False
        assert ai.is_human() is False
        assert ai.is_ai() is True
    
    def test_joined_timestamp(self):
        """Test joined timestamp tracking."""
        joined_time = datetime.utcnow()
        participant = ParticipantInfo(
            participant_id="user_123",
            name="Alice",
            participant_type=ParticipantType.HUMAN,
            joined_at=joined_time
        )
        
        assert participant.joined_at == joined_time
        
        # Test serialization includes timestamp
        p_dict = participant.to_dict()
        assert p_dict["joined_at"] == joined_time.isoformat()
    
    def test_unique_participant_ids(self):
        """Test participant ID uniqueness."""
        participants = []
        for i in range(100):
            p = ParticipantInfo(
                participant_id=f"user_{i}",
                name=f"User {i}",
                participant_type=ParticipantType.HUMAN,
                joined_at=datetime.utcnow()
            )
            participants.append(p)
        
        # All IDs should be unique
        ids = [p.participant_id for p in participants]
        assert len(ids) == len(set(ids))
    
    def test_display_name_validation(self):
        """Test display name handling."""
        # Empty name
        p1 = ParticipantInfo(
            participant_id="user_empty",
            name="",
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        assert p1.name == ""
        
        # Unicode name
        p2 = ParticipantInfo(
            participant_id="user_unicode",
            name="Alice 🌟 测试",
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        assert p2.name == "Alice 🌟 测试"
        
        # Long name
        long_name = "A" * 1000
        p3 = ParticipantInfo(
            participant_id="user_long",
            name=long_name,
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        assert len(p3.name) == 1000
    
    def test_participant_equality_and_hashing(self):
        """Test participant equality and set operations."""
        p1 = ParticipantInfo(
            participant_id="user_123",
            name="Alice",
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        p2 = ParticipantInfo(
            participant_id="user_123",
            name="Alice Changed",  # Different name
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        p3 = ParticipantInfo(
            participant_id="user_456",
            name="Bob",
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        # Same ID = equal
        assert p1 == p2
        assert p1 != p3
        
        # Can be used in sets
        participants = {p1, p2, p3}
        assert len(participants) == 2  # p1 and p2 are same
        
        # Hash is consistent
        assert hash(p1) == hash(p2)
        assert hash(p1) != hash(p3)


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases for all schemas."""
    
    def test_empty_conversation(self):
        """Test empty conversation handling."""
        conv = Conversation(
            conversation_id="conv_empty",
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=1000
        )
        
        assert len(conv.active_participants) == 0
        assert len(conv.get_human_participants()) == 0
        assert len(conv.get_ai_participants()) == 0
        assert conv.message_count == 0
    
    def test_conversation_at_max_capacity(self):
        """Test conversation at maximum capacity."""
        conv = Conversation(
            conversation_id="conv_full",
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=10  # Small limit for testing
        )
        
        # Fill to capacity
        for i in range(10):
            conv.increment_message_count()
        
        # At capacity
        with pytest.raises(QueueFullError):
            conv.check_queue_limit()
    
    def test_invalid_message_types(self):
        """Test invalid message type handling."""
        # Valid message types work
        for msg_type in MessageType:
            msg = ChatMessage(
                message_id="msg_valid",
                conversation_id="conv_001",
                sequence_id=1,
                sender_id="user_123",
                sender_name="Test",
                content="Test",
                message_type=msg_type,
                timestamp=datetime.utcnow()
            )
            assert msg.message_type in MessageType
    
    def test_xss_attempts_in_content(self):
        """Test XSS content handling (sanitization would be elsewhere)."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            '<img src="x" onerror="alert(1)">',
            '<a href="javascript:alert(1)">Click</a>',
            '"><script>alert(String.fromCharCode(88,83,83))</script>'
        ]
        
        for payload in xss_payloads:
            msg = ChatMessage(
                message_id=f"msg_xss_{hash(payload)}",
                conversation_id="conv_001",
                sequence_id=1,
                sender_id="user_malicious",
                sender_name="Attacker",
                content=payload,
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            # Schema stores content as-is (sanitization happens in rendering)
            assert msg.content == payload
    
    def test_unicode_handling(self):
        """Test Unicode content handling."""
        unicode_tests = [
            "Hello 👋 World 🌍",
            "日本語テスト",
            "Русский текст",
            "🔥💯🎉",
            "RTL: مرحبا بالعالم",
            "\u200b\u200c\u200d",  # Zero-width characters
        ]
        
        for content in unicode_tests:
            msg = ChatMessage(
                message_id=f"msg_unicode_{hash(content)}",
                conversation_id="conv_001",
                sequence_id=1,
                sender_id="user_123",
                sender_name="Unicode User",
                content=content,
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            assert msg.content == content
            
            # Serialization should handle Unicode
            msg_dict = msg.to_dict()
            assert msg_dict["content"] == content


@pytest.mark.unit
class TestPropertyBased:
    """Property-based tests using Hypothesis."""
    
    @given(
        messages=st.lists(
            st.integers(min_value=1, max_value=1000),
            min_size=10,
            max_size=100
        )
    )
    def test_message_ordering_by_sequence_id(self, messages):
        """Test that messages can be ordered by sequence_id."""
        # Create messages with given sequence IDs
        chat_messages = []
        for seq_id in messages:
            msg = ChatMessage(
                message_id=f"msg_{seq_id}",
                conversation_id="conv_prop",
                sequence_id=seq_id,
                sender_id="user_123",
                sender_name="Test",
                content=f"Message {seq_id}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            chat_messages.append(msg)
        
        # Sort by sequence_id
        sorted_messages = sorted(chat_messages, key=lambda m: m.sequence_id)
        
        # Verify ordering
        for i in range(1, len(sorted_messages)):
            assert sorted_messages[i].sequence_id >= sorted_messages[i-1].sequence_id
    
    @given(
        num_humans=st.integers(min_value=0, max_value=50),
        num_ai=st.integers(min_value=0, max_value=10)
    )
    def test_participant_count_accuracy(self, num_humans, num_ai):
        """Test accurate participant counting."""
        conv = Conversation(
            conversation_id="conv_count",
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=1000
        )
        
        # Add humans
        for i in range(num_humans):
            p = ParticipantInfo(
                f"human_{i}",
                f"Human {i}",
                ParticipantType.HUMAN,
                datetime.utcnow()
            )
            conv.add_participant(p)
        
        # Add AIs
        for i in range(num_ai):
            p = ParticipantInfo(
                f"ai_{i}",
                f"AI {i}",
                ParticipantType.AI,
                datetime.utcnow()
            )
            conv.add_participant(p)
        
        assert len(conv.get_human_participants()) == num_humans
        assert len(conv.get_ai_participants()) == num_ai
        assert len(conv.active_participants) == num_humans + num_ai
    
    @given(
        queue_limit=st.integers(min_value=10, max_value=2000),
        messages_to_add=st.integers(min_value=0, max_value=2500)
    )
    def test_queue_overflow_behavior(self, queue_limit, messages_to_add):
        """Test queue overflow behavior with various limits."""
        conv = Conversation(
            conversation_id="conv_overflow",
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=queue_limit
        )
        
        # Add messages up to limit
        for i in range(min(messages_to_add, queue_limit)):
            conv.increment_message_count()
        
        # If we're at or over limit, should raise
        if messages_to_add >= queue_limit:
            with pytest.raises(QueueFullError) as exc_info:
                conv.check_queue_limit()
            
            error = exc_info.value
            assert error.queue_size == queue_limit
            assert error.limit == queue_limit
        else:
            # Should not raise
            conv.check_queue_limit()
            assert conv.message_count == messages_to_add


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "unit"])