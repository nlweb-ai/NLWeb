"""
Tests for chat system data models and schemas.
"""

import pytest
from datetime import datetime
from typing import Set
import json

# These imports will fail until we create the schemas module
from chat.schemas import (
    Conversation,
    ParticipantInfo,
    ParticipantType,
    QueueFullError
)
from core.schemas import (
    Message,
    MessageType,
    MessageStatus
)


class TestMessage:
    """Test Message dataclass"""
    
    def test_create_text_message(self):
        """Test creating a basic text message"""
        msg = Message(
            message_id="msg_123",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="user_123",
            sender_name="Alice",
            content="Hello, world!",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        assert msg.message_id == "msg_123"
        assert msg.conversation_id == "conv_abc"
        assert msg.sequence_id == 1
        assert msg.sender_id == "user_123"
        assert msg.sender_name == "Alice"
        assert msg.content == "Hello, world!"
        assert msg.message_type == MessageType.TEXT
        assert msg.status == MessageStatus.DELIVERED  # Default
        
    def test_message_immutability(self):
        """Test that Message is frozen (immutable)"""
        msg = Message(
            message_id="msg_123",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="user_123",
            sender_name="Alice",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Should raise error when trying to modify
        with pytest.raises(AttributeError):
            msg.content = "Modified content"
            
    def test_nlweb_response_message(self):
        """Test creating an NLWeb AI response message"""
        msg = Message(
            message_id="msg_124",
            conversation_id="conv_abc",
            sequence_id=2,
            sender_id="nlweb_1",
            sender_name="NLWeb Assistant",
            content="I can help you with that.",
            message_type=MessageType.NLWEB_RESPONSE,
            timestamp=datetime.utcnow(),
            metadata={"model": "gpt-4", "tokens": 15}
        )
        
        assert msg.message_type == MessageType.NLWEB_RESPONSE
        assert msg.metadata["model"] == "gpt-4"
        
    def test_system_message(self):
        """Test creating a system message"""
        msg = Message(
            message_id="msg_125",
            conversation_id="conv_abc",
            sequence_id=3,
            sender_id="system",
            sender_name="System",
            content="Bob has joined the conversation",
            message_type=MessageType.SYSTEM,
            timestamp=datetime.utcnow()
        )
        
        assert msg.message_type == MessageType.SYSTEM
        assert msg.sender_id == "system"
        
    def test_message_ordering_by_sequence_id(self):
        """Test that messages can be ordered by sequence_id"""
        msg1 = Message(
            message_id="msg_1",
            conversation_id="conv_abc",
            sequence_id=3,
            sender_id="user_123",
            sender_name="Alice",
            content="Third",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        msg2 = Message(
            message_id="msg_2",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="user_456",
            sender_name="Bob",
            content="First",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        msg3 = Message(
            message_id="msg_3",
            conversation_id="conv_abc",
            sequence_id=2,
            sender_id="nlweb_1",
            sender_name="NLWeb",
            content="Second",
            message_type=MessageType.NLWEB_RESPONSE,
            timestamp=datetime.utcnow()
        )
        
        messages = sorted([msg1, msg2, msg3], key=lambda m: m.sequence_id)
        assert messages[0].content == "First"
        assert messages[1].content == "Second"
        assert messages[2].content == "Third"
        
    def test_message_serialization(self):
        """Test message can be serialized to dict"""
        msg = Message(
            message_id="msg_123",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="user_123",
            sender_name="Alice",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        msg_dict = msg.to_dict()
        assert msg_dict["message_id"] == "msg_123"
        assert msg_dict["sequence_id"] == 1
        assert msg_dict["message_type"] == "text"
        
        # Should be JSON serializable
        json_str = json.dumps(msg_dict)
        assert json_str is not None


class TestParticipantInfo:
    """Test ParticipantInfo dataclass"""
    
    def test_human_participant(self):
        """Test creating a human participant"""
        participant = ParticipantInfo(
            participant_id="user_123",
            name="Alice",
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        assert participant.participant_id == "user_123"
        assert participant.name == "Alice"
        assert participant.participant_type == ParticipantType.HUMAN
        assert participant.is_human() is True
        assert participant.is_ai() is False
        
    def test_ai_participant(self):
        """Test creating an AI participant"""
        participant = ParticipantInfo(
            participant_id="nlweb_1",
            name="NLWeb Assistant",
            participant_type=ParticipantType.AI,
            joined_at=datetime.utcnow()
        )
        
        assert participant.participant_type == ParticipantType.AI
        assert participant.is_human() is False
        assert participant.is_ai() is True
        
    def test_participant_equality(self):
        """Test participant equality based on ID"""
        p1 = ParticipantInfo(
            participant_id="user_123",
            name="Alice",
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        p2 = ParticipantInfo(
            participant_id="user_123",
            name="Alice Updated",  # Different name
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        # Should be equal based on participant_id
        assert p1 == p2


class TestConversation:
    """Test Conversation dataclass"""
    
    def test_create_conversation(self):
        """Test creating a conversation with participants"""
        alice = ParticipantInfo(
            participant_id="user_123",
            name="Alice",
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        nlweb = ParticipantInfo(
            participant_id="nlweb_1",
            name="NLWeb Assistant",
            participant_type=ParticipantType.AI,
            joined_at=datetime.utcnow()
        )
        
        conv = Conversation(
            conversation_id="conv_abc",
            created_at=datetime.utcnow(),
            active_participants={alice, nlweb},
            queue_size_limit=1000
        )
        
        assert conv.conversation_id == "conv_abc"
        assert len(conv.active_participants) == 2
        assert alice in conv.active_participants
        assert nlweb in conv.active_participants
        assert conv.queue_size_limit == 1000
        assert conv.message_count == 0
        
    def test_multi_human_conversation(self):
        """Test conversation with multiple humans"""
        alice = ParticipantInfo("user_123", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        bob = ParticipantInfo("user_456", "Bob", ParticipantType.HUMAN, datetime.utcnow())
        charlie = ParticipantInfo("user_789", "Charlie", ParticipantType.HUMAN, datetime.utcnow())
        nlweb = ParticipantInfo("nlweb_1", "NLWeb", ParticipantType.AI, datetime.utcnow())
        
        conv = Conversation(
            conversation_id="conv_multi",
            created_at=datetime.utcnow(),
            active_participants={alice, bob, charlie, nlweb},
            queue_size_limit=1000
        )
        
        humans = conv.get_human_participants()
        assert len(humans) == 3
        assert all(p.is_human() for p in humans)
        
        ai_participants = conv.get_ai_participants()
        assert len(ai_participants) == 1
        assert ai_participants[0].participant_id == "nlweb_1"
        
    def test_add_participant(self):
        """Test adding a participant to conversation"""
        alice = ParticipantInfo("user_123", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        nlweb = ParticipantInfo("nlweb_1", "NLWeb", ParticipantType.AI, datetime.utcnow())
        
        conv = Conversation(
            conversation_id="conv_abc",
            created_at=datetime.utcnow(),
            active_participants={alice, nlweb},
            queue_size_limit=1000
        )
        
        # Add Bob
        bob = ParticipantInfo("user_456", "Bob", ParticipantType.HUMAN, datetime.utcnow())
        conv.add_participant(bob)
        
        assert len(conv.active_participants) == 3
        assert bob in conv.active_participants
        
    def test_remove_participant(self):
        """Test removing a participant from conversation"""
        alice = ParticipantInfo("user_123", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        bob = ParticipantInfo("user_456", "Bob", ParticipantType.HUMAN, datetime.utcnow())
        nlweb = ParticipantInfo("nlweb_1", "NLWeb", ParticipantType.AI, datetime.utcnow())
        
        conv = Conversation(
            conversation_id="conv_abc",
            created_at=datetime.utcnow(),
            active_participants={alice, bob, nlweb},
            queue_size_limit=1000
        )
        
        # Remove Bob
        conv.remove_participant("user_456")
        
        assert len(conv.active_participants) == 2
        assert bob not in conv.active_participants
        assert alice in conv.active_participants
        
    def test_queue_overflow(self):
        """Test queue overflow behavior"""
        alice = ParticipantInfo("user_123", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        nlweb = ParticipantInfo("nlweb_1", "NLWeb", ParticipantType.AI, datetime.utcnow())
        
        # Small queue for testing
        conv = Conversation(
            conversation_id="conv_abc",
            created_at=datetime.utcnow(),
            active_participants={alice, nlweb},
            queue_size_limit=3
        )
        
        # Add messages up to limit
        conv.increment_message_count()
        conv.increment_message_count()
        conv.increment_message_count()
        
        # Should raise QueueFullError
        with pytest.raises(QueueFullError) as exc_info:
            conv.check_queue_limit()
            
        assert "Queue full" in str(exc_info.value)
        assert exc_info.value.conversation_id == "conv_abc"
        assert exc_info.value.queue_size == 3
        assert exc_info.value.limit == 3
        
    def test_participant_events(self):
        """Test generating participant join/leave events"""
        alice = ParticipantInfo("user_123", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        nlweb = ParticipantInfo("nlweb_1", "NLWeb", ParticipantType.AI, datetime.utcnow())
        
        conv = Conversation(
            conversation_id="conv_abc",
            created_at=datetime.utcnow(),
            active_participants={alice, nlweb},
            queue_size_limit=1000
        )
        
        # Test join event
        bob = ParticipantInfo("user_456", "Bob", ParticipantType.HUMAN, datetime.utcnow())
        join_msg = conv.create_participant_event(bob, "join")
        
        assert join_msg.message_type == MessageType.SYSTEM
        assert join_msg.sender_id == "system"
        assert "Bob has joined" in join_msg.content
        assert join_msg.metadata["event_type"] == "participant_join"
        assert join_msg.metadata["participant_id"] == "user_456"
        
        # Test leave event
        leave_msg = conv.create_participant_event(alice, "leave")
        
        assert leave_msg.message_type == MessageType.SYSTEM
        assert "Alice has left" in leave_msg.content
        assert leave_msg.metadata["event_type"] == "participant_leave"
        
    def test_conversation_serialization(self):
        """Test conversation can be serialized"""
        alice = ParticipantInfo("user_123", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        nlweb = ParticipantInfo("nlweb_1", "NLWeb", ParticipantType.AI, datetime.utcnow())
        
        conv = Conversation(
            conversation_id="conv_abc",
            created_at=datetime.utcnow(),
            active_participants={alice, nlweb},
            queue_size_limit=1000
        )
        
        conv_dict = conv.to_dict()
        assert conv_dict["conversation_id"] == "conv_abc"
        assert conv_dict["participant_count"] == 2
        assert len(conv_dict["participants"]) == 2
        
        # Check participant data
        participant_ids = [p["participant_id"] for p in conv_dict["participants"]]
        assert "user_123" in participant_ids
        assert "nlweb_1" in participant_ids


class TestMessageTypes:
    """Test MessageType enum"""
    
    def test_message_type_values(self):
        """Test all message type values exist"""
        assert MessageType.TEXT.value == "text"
        assert MessageType.SYSTEM.value == "system"
        assert MessageType.NLWEB_RESPONSE.value == "nlweb_response"
        assert MessageType.ERROR.value == "error"
        
    def test_message_type_from_string(self):
        """Test creating MessageType from string"""
        assert MessageType("text") == MessageType.TEXT
        assert MessageType("system") == MessageType.SYSTEM
        assert MessageType("nlweb_response") == MessageType.NLWEB_RESPONSE


class TestMessageStatus:
    """Test MessageStatus enum"""
    
    def test_message_status_values(self):
        """Test all message status values exist"""
        assert MessageStatus.PENDING.value == "pending"
        assert MessageStatus.DELIVERED.value == "delivered"
        assert MessageStatus.FAILED.value == "failed"
        assert MessageStatus.PROCESSING.value == "processing"


class TestQueueFullError:
    """Test QueueFullError exception"""
    
    def test_queue_full_error(self):
        """Test QueueFullError creation and attributes"""
        error = QueueFullError(
            conversation_id="conv_abc",
            queue_size=1000,
            limit=1000
        )
        
        assert error.conversation_id == "conv_abc"
        assert error.queue_size == 1000
        assert error.limit == 1000
        assert "Queue full for conversation conv_abc" in str(error)
        assert "1000/1000" in str(error)