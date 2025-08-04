"""
Unit tests for chat participants.
Tests BaseParticipant, HumanParticipant, NLWebParticipant, and NLWebContextBuilder.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../code/python'))

from chat.schemas import (
    ChatMessage, MessageType, MessageStatus,
    ParticipantInfo, ParticipantType, QueueFullError
)
from chat.participants import (
    BaseParticipant, HumanParticipant, NLWebParticipant,
    NLWebContextBuilder, ParticipantConfig
)


@pytest.mark.unit
class TestBaseParticipant:
    """Test the BaseParticipant abstract interface."""
    
    def test_abstract_method_enforcement(self):
        """Test that abstract methods must be implemented."""
        # Cannot instantiate abstract class
        with pytest.raises(TypeError):
            BaseParticipant()
        
        # Must implement all abstract methods
        class IncompleteParticipant(BaseParticipant):
            def get_participant_info(self):
                return ParticipantInfo("test", "Test", ParticipantType.HUMAN, datetime.utcnow())
        
        with pytest.raises(TypeError):
            IncompleteParticipant()
    
    def test_participant_info_correctness(self):
        """Test participant info is correctly structured."""
        # Create a concrete implementation
        class TestParticipant(BaseParticipant):
            async def process_message(self, message, context, stream_callback=None):
                return None
            
            def get_participant_info(self):
                return ParticipantInfo(
                    participant_id="test_123",
                    name="Test Participant",
                    participant_type=ParticipantType.HUMAN,
                    joined_at=datetime.utcnow()
                )
        
        participant = TestParticipant()
        info = participant.get_participant_info()
        
        assert info.participant_id == "test_123"
        assert info.name == "Test Participant"
        assert info.participant_type == ParticipantType.HUMAN
        assert isinstance(info.joined_at, datetime)
    
    @pytest.mark.asyncio
    async def test_message_delivery_mechanism(self):
        """Test the message delivery mechanism interface."""
        delivered_messages = []
        
        class DeliveryTestParticipant(BaseParticipant):
            async def process_message(self, message, context, stream_callback=None):
                delivered_messages.append(message)
                return None
            
            def get_participant_info(self):
                return ParticipantInfo("delivery_test", "Delivery Test", ParticipantType.HUMAN, datetime.utcnow())
        
        participant = DeliveryTestParticipant()
        
        test_message = ChatMessage(
            message_id="msg_001",
            conversation_id="conv_001",
            sequence_id=1,
            sender_id="sender_001",
            sender_name="Sender",
            content="Test delivery",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        await participant.process_message(test_message, [])
        
        assert len(delivered_messages) == 1
        assert delivered_messages[0] == test_message


@pytest.mark.unit
class TestHumanParticipant:
    """Test HumanParticipant implementation."""
    
    def test_human_participant_creation(self):
        """Test creating a human participant."""
        human = HumanParticipant(user_id="user_123", user_name="Alice")
        
        assert human.user_id == "user_123"
        assert human.user_name == "Alice"
        
        info = human.get_participant_info()
        assert info.participant_id == "user_123"
        assert info.name == "Alice"
        assert info.participant_type == ParticipantType.HUMAN
    
    @pytest.mark.asyncio
    async def test_human_does_not_process_messages(self):
        """Test that humans don't process messages (they only send)."""
        human = HumanParticipant(user_id="user_456", user_name="Bob")
        
        test_message = ChatMessage(
            message_id="msg_002",
            conversation_id="conv_001",
            sequence_id=2,
            sender_id="other_user",
            sender_name="Other",
            content="Hello Bob",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        result = await human.process_message(test_message, [])
        assert result is None  # Humans don't generate responses


@pytest.mark.unit
@pytest.mark.asyncio
class TestNLWebParticipant:
    """Test NLWebParticipant implementation."""
    
    @pytest.fixture
    def mock_nlweb_handler(self):
        """Create a mock NLWebHandler."""
        # Create a class that mimics NLWebHandler behavior
        class MockNLWebHandler:
            def __init__(self, query_params, chunk_capture):
                self.query_params = query_params
                self.chunk_capture = chunk_capture
            
            async def runQuery(self):
                # Simulate NLWeb response
                await self.chunk_capture.write_stream(
                    {"type": "nlws", "content": "Test NLWeb response"}
                )
        
        return MockNLWebHandler
    
    @pytest.fixture
    def participant_config(self):
        """Create test participant configuration."""
        return ParticipantConfig(
            timeout=20,
            human_messages_context=5,
            nlweb_messages_context=1
        )
    
    async def test_nlweb_handler_wrapping_without_modification(self, mock_nlweb_handler, participant_config):
        """Test that NLWebHandler is wrapped without modification."""
        nlweb_participant = NLWebParticipant(mock_nlweb_handler, participant_config)
        
        # Verify handler is stored unmodified
        assert nlweb_participant.nlweb_handler == mock_nlweb_handler
        
        # Verify participant info
        info = nlweb_participant.get_participant_info()
        assert info.participant_id == "nlweb_1"
        assert info.name == "NLWeb Assistant"
        assert info.participant_type == ParticipantType.AI
    
    async def test_context_building_with_multi_human_messages(self, mock_nlweb_handler, participant_config):
        """Test context building includes messages from multiple humans."""
        nlweb_participant = NLWebParticipant(mock_nlweb_handler, participant_config)
        
        # Create messages from multiple humans
        context_messages = [
            ChatMessage("msg_1", "conv_1", 1, "human_1", "Alice", "Hello from Alice", 
                       MessageType.TEXT, datetime.utcnow(), MessageStatus.DELIVERED),
            ChatMessage("msg_2", "conv_1", 2, "human_2", "Bob", "Hi from Bob", 
                       MessageType.TEXT, datetime.utcnow(), MessageStatus.DELIVERED),
            ChatMessage("msg_3", "conv_1", 3, "nlweb_1", "AI", "Hello Alice and Bob", 
                       MessageType.NLWEB_RESPONSE, datetime.utcnow(), MessageStatus.DELIVERED),
            ChatMessage("msg_4", "conv_1", 4, "human_3", "Charlie", "Greetings from Charlie", 
                       MessageType.TEXT, datetime.utcnow(), MessageStatus.DELIVERED),
        ]
        
        current_message = ChatMessage("msg_5", "conv_1", 5, "human_1", "Alice", 
                                    "What about this?", MessageType.TEXT, 
                                    datetime.utcnow(), MessageStatus.DELIVERED)
        
        # Test context building
        context = nlweb_participant.context_builder.build_context(context_messages, current_message)
        
        # Verify all human messages are included
        assert len(context["prev_queries"]) == 3  # 3 human messages
        assert context["prev_queries"][0]["user_id"] == "human_1"
        assert context["prev_queries"][1]["user_id"] == "human_2"
        assert context["prev_queries"][2]["user_id"] == "human_3"
        
        # Verify AI response is included
        assert len(context["last_answers"]) == 1
        assert "Hello Alice and Bob" in context["last_answers"][0]["content"]
    
    async def test_timeout_handling(self, participant_config):
        """Test timeout handling (20s default)."""
        # Create a handler that takes too long
        async def slow_handler(query_params, chunk_capture):
            await asyncio.sleep(25)  # Longer than timeout
            await chunk_capture.write_stream({"content": "Too late"})
        
        nlweb_participant = NLWebParticipant(slow_handler, participant_config)
        
        test_message = ChatMessage(
            "msg_timeout", "conv_1", 1, "human_1", "Human",
            "Test timeout", MessageType.TEXT, datetime.utcnow()
        )
        
        # Should timeout
        with pytest.raises(asyncio.TimeoutError):
            await nlweb_participant.process_message(test_message, [])
    
    async def test_stream_callback_functionality(self, mock_nlweb_handler, participant_config):
        """Test stream callback receives chunks."""
        nlweb_participant = NLWebParticipant(mock_nlweb_handler, participant_config)
        
        received_chunks = []
        
        async def stream_callback(chunk):
            received_chunks.append(chunk)
        
        test_message = ChatMessage(
            "msg_stream", "conv_1", 1, "human_1", "Human",
            "Test streaming", MessageType.TEXT, datetime.utcnow()
        )
        
        result = await nlweb_participant.process_message(test_message, [], stream_callback)
        
        # Verify callback received chunks
        assert len(received_chunks) > 0
        assert '{"type": "nlws", "content": "Test NLWeb response"}' in received_chunks[0]
        
        # Verify response message
        assert result is not None
        assert result.message_type == MessageType.NLWEB_RESPONSE
        assert "Test NLWeb response" in result.content
    
    async def test_response_filtering_nlweb_chooses_not_to_respond(self, participant_config):
        """Test when NLWeb chooses not to respond."""
        # Handler that produces no output
        async def silent_handler(query_params, chunk_capture):
            # NLWeb decides not to respond
            pass
        
        nlweb_participant = NLWebParticipant(silent_handler, participant_config)
        
        test_message = ChatMessage(
            "msg_silent", "conv_1", 1, "human_1", "Human",
            "Irrelevant message", MessageType.TEXT, datetime.utcnow()
        )
        
        result = await nlweb_participant.process_message(test_message, [])
        
        # Should return None when NLWeb doesn't respond
        assert result is None
    
    async def test_queue_full_handling(self, mock_nlweb_handler, participant_config):
        """Test that NLWebParticipant generates response regardless of queue state."""
        # Create handler that would normally respond
        nlweb_participant = NLWebParticipant(mock_nlweb_handler, participant_config)
        
        test_message = ChatMessage(
            "msg_queue_full", "conv_1", 1, "human_1", "Human",
            "Message when queue is full", MessageType.TEXT, datetime.utcnow()
        )
        
        # NLWebParticipant should still generate a response
        # Queue handling is done by ConversationManager, not the participant
        result = await nlweb_participant.process_message(test_message, [])
        assert result is not None
        assert result.message_type == MessageType.NLWEB_RESPONSE
        assert "Test NLWeb response" in result.content


@pytest.mark.unit
class TestNLWebContextBuilder:
    """Test NLWebContextBuilder functionality."""
    
    @pytest.fixture
    def context_builder(self):
        """Create a context builder with test config."""
        config = {
            "human_messages": 5,
            "nlweb_messages": 1
        }
        return NLWebContextBuilder(config)
    
    def test_correct_number_of_human_messages_included(self, context_builder):
        """Test configurable number of human messages."""
        # Create 10 human messages
        messages = []
        for i in range(10):
            msg = ChatMessage(
                f"msg_{i}", "conv_1", i, f"human_{i}", f"Human {i}",
                f"Message {i}", MessageType.TEXT, datetime.utcnow()
            )
            messages.append(msg)
        
        context = context_builder.build_context(messages)
        
        # Should only include last 5 (configured limit)
        assert len(context["prev_queries"]) == 5
        assert context["prev_queries"][0]["query"] == "Message 5"
        assert context["prev_queries"][4]["query"] == "Message 9"
    
    def test_messages_from_all_humans_included(self, context_builder):
        """Test that messages from ALL humans are included."""
        messages = [
            ChatMessage("msg_1", "conv_1", 1, "alice", "Alice", "Hello from Alice", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_2", "conv_1", 2, "bob", "Bob", "Hi from Bob", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_3", "conv_1", 3, "charlie", "Charlie", "Hey from Charlie", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_4", "conv_1", 4, "alice", "Alice", "Another from Alice", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_5", "conv_1", 5, "david", "David", "David here", 
                       MessageType.TEXT, datetime.utcnow()),
        ]
        
        context = context_builder.build_context(messages)
        
        # All 5 messages should be included (within limit)
        assert len(context["prev_queries"]) == 5
        
        # Verify all different humans are represented
        user_ids = [q["user_id"] for q in context["prev_queries"]]
        assert "alice" in user_ids
        assert "bob" in user_ids
        assert "charlie" in user_ids
        assert "david" in user_ids
    
    def test_sender_identification_preserved(self, context_builder):
        """Test that sender identity is preserved in context."""
        messages = [
            ChatMessage("msg_1", "conv_1", 1, "user_123", "Alice Smith", 
                       "First message", MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_2", "conv_1", 2, "user_456", "Bob Jones", 
                       "Second message", MessageType.TEXT, datetime.utcnow()),
        ]
        
        context = context_builder.build_context(messages)
        
        assert context["prev_queries"][0]["user_id"] == "user_123"
        assert context["prev_queries"][0]["query"] == "First message"
        assert context["prev_queries"][1]["user_id"] == "user_456"
        assert context["prev_queries"][1]["query"] == "Second message"
    
    def test_prev_queries_format_correctness(self, context_builder):
        """Test prev_queries format matches expected structure."""
        timestamp = datetime.utcnow()
        messages = [
            ChatMessage("msg_1", "conv_1", 1, "user_1", "User 1", 
                       "Test query", MessageType.TEXT, timestamp)
        ]
        
        context = context_builder.build_context(messages)
        
        assert "prev_queries" in context
        assert isinstance(context["prev_queries"], list)
        
        query = context["prev_queries"][0]
        assert "query" in query
        assert "user_id" in query
        assert "timestamp" in query
        assert query["query"] == "Test query"
        assert query["user_id"] == "user_1"
        assert query["timestamp"] == timestamp.isoformat()
    
    def test_last_answers_format_with_only_ai_responses(self, context_builder):
        """Test last_answers contains only AI responses."""
        messages = [
            ChatMessage("msg_1", "conv_1", 1, "user_1", "User", "Human message", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_2", "conv_1", 2, "nlweb_1", "AI", "AI response 1", 
                       MessageType.NLWEB_RESPONSE, datetime.utcnow(), 
                       metadata={"confidence": 0.9}),
            ChatMessage("msg_3", "conv_1", 3, "user_2", "User 2", "Another human", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_4", "conv_1", 4, "nlweb_1", "AI", "AI response 2", 
                       MessageType.NLWEB_RESPONSE, datetime.utcnow()),
        ]
        
        context = context_builder.build_context(messages)
        
        # Should only have AI responses
        assert len(context["last_answers"]) == 1  # Limited to 1 by config
        assert context["last_answers"][0]["content"] == "AI response 2"  # Most recent
        
        # Test with higher limit
        context_builder.nlweb_messages_limit = 2
        context = context_builder.build_context(messages)
        assert len(context["last_answers"]) == 2
    
    def test_current_message_handling(self, context_builder):
        """Test handling of current message in context."""
        past_messages = [
            ChatMessage("msg_1", "conv_1", 1, "user_1", "User", "Past message", 
                       MessageType.TEXT, datetime.utcnow())
        ]
        
        current_message = ChatMessage("msg_2", "conv_1", 2, "user_2", "Current User", 
                                    "Current query", MessageType.TEXT, datetime.utcnow())
        
        context = context_builder.build_context(past_messages, current_message)
        
        # Current message should not be in prev_queries
        assert len(context["prev_queries"]) == 1
        assert context["prev_queries"][0]["query"] == "Past message"
        
        # But should be in special fields
        assert context["current_query"] == "Current query"
        assert context["current_user_id"] == "user_2"


@pytest.mark.unit
@pytest.mark.asyncio
class TestMockNLWebHandlerBehaviors:
    """Test various NLWebHandler mock behaviors."""
    
    async def test_successful_response(self):
        """Test successful NLWeb response."""
        async def success_handler(query_params, chunk_capture):
            # Verify query params
            assert "query" in query_params
            assert query_params["query"][0] == "Test question"
            
            # Send response
            await chunk_capture.write_stream({
                "type": "nlws",
                "content": "Here's the answer to your question"
            })
        
        config = ParticipantConfig()
        participant = NLWebParticipant(success_handler, config)
        
        message = ChatMessage("msg_1", "conv_1", 1, "user_1", "User",
                            "Test question", MessageType.TEXT, datetime.utcnow())
        
        response = await participant.process_message(message, [])
        
        assert response is not None
        assert response.content == '{"type": "nlws", "content": "Here\'s the answer to your question"}'
        assert response.message_type == MessageType.NLWEB_RESPONSE
    
    async def test_timeout_scenario(self):
        """Test timeout scenario handling."""
        async def timeout_handler(query_params, chunk_capture):
            # Simulate long processing
            await asyncio.sleep(30)
        
        config = ParticipantConfig(timeout=1)  # 1 second timeout
        participant = NLWebParticipant(timeout_handler, config)
        
        message = ChatMessage("msg_1", "conv_1", 1, "user_1", "User",
                            "Timeout test", MessageType.TEXT, datetime.utcnow())
        
        with pytest.raises(asyncio.TimeoutError):
            await participant.process_message(message, [])
    
    async def test_no_response_decision(self):
        """Test when NLWeb decides not to respond."""
        async def no_response_handler(query_params, chunk_capture):
            # Analyze query and decide not to respond
            query = query_params["query"][0]
            if "irrelevant" in query.lower():
                # Don't write any chunks
                return
            await chunk_capture.write_stream({"content": "Response"})
        
        config = ParticipantConfig()
        participant = NLWebParticipant(no_response_handler, config)
        
        # Irrelevant message
        message = ChatMessage("msg_1", "conv_1", 1, "user_1", "User",
                            "This is irrelevant chatter", MessageType.TEXT, datetime.utcnow())
        
        response = await participant.process_message(message, [])
        assert response is None
    
    async def test_streaming_response_chunks(self):
        """Test streaming response in chunks."""
        async def streaming_handler(query_params, chunk_capture):
            # Send multiple chunks
            chunks = [
                {"type": "chunk", "content": "First "},
                {"type": "chunk", "content": "part of "},
                {"type": "chunk", "content": "the response"}
            ]
            
            for chunk in chunks:
                await chunk_capture.write_stream(chunk)
                await asyncio.sleep(0.1)  # Simulate streaming delay
        
        config = ParticipantConfig()
        participant = NLWebParticipant(streaming_handler, config)
        
        received_chunks = []
        
        async def capture_chunks(chunk):
            received_chunks.append(chunk)
        
        message = ChatMessage("msg_1", "conv_1", 1, "user_1", "User",
                            "Stream test", MessageType.TEXT, datetime.utcnow())
        
        response = await participant.process_message(message, [], capture_chunks)
        
        # Verify all chunks received
        assert len(received_chunks) == 3
        assert response is not None
        
        # Combined response
        expected = '{"type": "chunk", "content": "First "}{"type": "chunk", "content": "part of "}{"type": "chunk", "content": "the response"}'
        assert response.content == expected
    
    async def test_error_during_processing(self):
        """Test error handling during processing."""
        async def error_handler(query_params, chunk_capture):
            # Start processing
            await chunk_capture.write_stream({"content": "Starting..."})
            # Then error occurs
            raise ValueError("Processing error")
        
        config = ParticipantConfig()
        participant = NLWebParticipant(error_handler, config)
        
        message = ChatMessage("msg_1", "conv_1", 1, "user_1", "User",
                            "Error test", MessageType.TEXT, datetime.utcnow())
        
        # Should handle error gracefully
        response = await participant.process_message(message, [])
        assert response is None  # Returns None on error


@pytest.mark.unit
@pytest.mark.asyncio
class TestMultiParticipantScenarios:
    """Test multi-participant scenarios."""
    
    async def test_nlweb_sees_messages_from_three_humans(self):
        """Test NLWeb sees messages from 3 different humans."""
        # Track what NLWeb sees
        seen_queries = []
        
        async def tracking_handler(query_params, chunk_capture):
            # Record what we see
            if "prev_queries" in query_params:
                prev = json.loads(query_params["prev_queries"][0])
                seen_queries.extend(prev)
            
            await chunk_capture.write_stream({
                "content": f"I see {len(seen_queries)} previous messages"
            })
        
        config = ParticipantConfig(human_messages_context=10)
        participant = NLWebParticipant(tracking_handler, config)
        
        # Create conversation history with 3 humans
        context = [
            ChatMessage("msg_1", "conv_1", 1, "alice", "Alice", "Hello from Alice", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_2", "conv_1", 2, "bob", "Bob", "Hi from Bob", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_3", "conv_1", 3, "charlie", "Charlie", "Hey from Charlie", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_4", "conv_1", 4, "nlweb_1", "AI", "Hello everyone", 
                       MessageType.NLWEB_RESPONSE, datetime.utcnow()),
            ChatMessage("msg_5", "conv_1", 5, "alice", "Alice", "Thanks AI", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_6", "conv_1", 6, "bob", "Bob", "Good response", 
                       MessageType.TEXT, datetime.utcnow()),
        ]
        
        current = ChatMessage("msg_7", "conv_1", 7, "charlie", "Charlie",
                            "What do you think?", MessageType.TEXT, datetime.utcnow())
        
        response = await participant.process_message(current, context)
        
        # Verify NLWeb saw all human messages
        assert len(seen_queries) == 5  # 5 human messages in context
        user_ids = {q["user_id"] for q in seen_queries}
        assert user_ids == {"alice", "bob", "charlie"}
    
    async def test_context_includes_appropriate_history_from_all(self):
        """Test context includes appropriate history from all participants."""
        config = ParticipantConfig(
            human_messages_context=3,
            nlweb_messages_context=2
        )
        
        # Create mixed conversation history
        context = [
            ChatMessage("msg_1", "conv_1", 1, "user_1", "User 1", "First message", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_2", "conv_1", 2, "nlweb_1", "AI", "First AI response", 
                       MessageType.NLWEB_RESPONSE, datetime.utcnow()),
            ChatMessage("msg_3", "conv_1", 3, "user_2", "User 2", "Second user joins", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_4", "conv_1", 4, "user_3", "User 3", "Third user message", 
                       MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_5", "conv_1", 5, "nlweb_1", "AI", "Second AI response", 
                       MessageType.NLWEB_RESPONSE, datetime.utcnow()),
            ChatMessage("msg_6", "conv_1", 6, "user_1", "User 1", "User 1 again", 
                       MessageType.TEXT, datetime.utcnow()),
        ]
        
        context_builder = NLWebContextBuilder({
            "human_messages": config.human_messages_context,
            "nlweb_messages": config.nlweb_messages_context
        })
        
        built_context = context_builder.build_context(context)
        
        # Should have last 3 human messages in chronological order
        assert len(built_context["prev_queries"]) == 3
        # Messages are in chronological order: user_3, user_1 (from msg_6)
        # We get messages 3, 4, 6 (the last 3 human messages)
        assert built_context["prev_queries"][0]["user_id"] == "user_2"  # msg_3
        assert built_context["prev_queries"][1]["user_id"] == "user_3"  # msg_4
        assert built_context["prev_queries"][2]["user_id"] == "user_1"  # msg_6
        
        # Should have last 2 AI responses in chronological order
        assert len(built_context["last_answers"]) == 2
        assert "First AI response" in built_context["last_answers"][0]["content"]
        assert "Second AI response" in built_context["last_answers"][1]["content"]
    
    async def test_each_humans_identity_preserved_in_context(self):
        """Test each human's identity is preserved in context."""
        received_context = None
        
        async def context_capture_handler(query_params, chunk_capture):
            nonlocal received_context
            if "prev_queries" in query_params:
                received_context = json.loads(query_params["prev_queries"][0])
            await chunk_capture.write_stream({"content": "Captured context"})
        
        config = ParticipantConfig()
        participant = NLWebParticipant(context_capture_handler, config)
        
        # Create messages with distinct identities
        context = [
            ChatMessage("msg_1", "conv_1", 1, "alice_123", "Alice Smith", 
                       "Alice's perspective", MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_2", "conv_1", 2, "bob_456", "Bob Jones", 
                       "Bob's viewpoint", MessageType.TEXT, datetime.utcnow()),
            ChatMessage("msg_3", "conv_1", 3, "charlie_789", "Charlie Brown", 
                       "Charlie's opinion", MessageType.TEXT, datetime.utcnow()),
        ]
        
        current = ChatMessage("msg_4", "conv_1", 4, "alice_123", "Alice Smith",
                            "What about this?", MessageType.TEXT, datetime.utcnow())
        
        await participant.process_message(current, context)
        
        # Verify each identity preserved
        assert received_context is not None
        assert len(received_context) == 3
        
        # Check identity preservation
        identities = {(q["user_id"], q["query"]) for q in received_context}
        expected = {
            ("alice_123", "Alice's perspective"),
            ("bob_456", "Bob's viewpoint"),
            ("charlie_789", "Charlie's opinion")
        }
        assert identities == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "unit"])