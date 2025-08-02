"""
Tests for chat participants, especially NLWeb integration.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import json
from typing import List, Dict, Any

from chat.schemas import (
    ChatMessage,
    MessageType,
    MessageStatus,
    QueueFullError
)

# These imports will fail until we create the module
from chat.participants import (
    BaseParticipant,
    HumanParticipant,
    NLWebParticipant,
    NLWebContextBuilder,
    ParticipantConfig
)


class TestNLWebContextBuilder:
    """Test context building for NLWeb"""
    
    @pytest.fixture
    def config(self):
        """Create test configuration"""
        return {
            "human_messages": 5,
            "nlweb_messages": 1
        }
    
    @pytest.fixture
    def builder(self, config):
        """Create context builder"""
        return NLWebContextBuilder(config)
    
    def test_empty_context(self, builder):
        """Test building context with no messages"""
        context = builder.build_context([])
        
        assert context["prev_queries"] == []
        assert context["last_answers"] == []
        assert "user_id" not in context
    
    def test_single_human_message(self, builder):
        """Test context with single human message"""
        messages = [
            ChatMessage(
                message_id="msg_1",
                conversation_id="conv_abc",
                sequence_id=1,
                sender_id="alice_123",
                sender_name="Alice",
                content="What's the weather?",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
        ]
        
        context = builder.build_context(messages)
        
        assert len(context["prev_queries"]) == 1
        assert context["prev_queries"][0]["query"] == "What's the weather?"
        assert context["prev_queries"][0]["user_id"] == "alice_123"
        assert context["last_answers"] == []
    
    def test_multi_human_messages(self, builder):
        """Test context with messages from multiple humans"""
        messages = [
            ChatMessage(
                message_id="msg_1",
                conversation_id="conv_abc",
                sequence_id=1,
                sender_id="alice_123",
                sender_name="Alice",
                content="Hello everyone",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            ),
            ChatMessage(
                message_id="msg_2",
                conversation_id="conv_abc",
                sequence_id=2,
                sender_id="bob_456",
                sender_name="Bob",
                content="Hi Alice, how are you?",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            ),
            ChatMessage(
                message_id="msg_3",
                conversation_id="conv_abc",
                sequence_id=3,
                sender_id="charlie_789",
                sender_name="Charlie",
                content="What should we discuss today?",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
        ]
        
        context = builder.build_context(messages)
        
        assert len(context["prev_queries"]) == 3
        # Check all human messages are included with user_id
        assert context["prev_queries"][0]["user_id"] == "alice_123"
        assert context["prev_queries"][1]["user_id"] == "bob_456"
        assert context["prev_queries"][2]["user_id"] == "charlie_789"
    
    def test_human_message_limit(self, builder):
        """Test that only last N human messages are included"""
        # Create 10 human messages
        messages = []
        for i in range(10):
            messages.append(ChatMessage(
                message_id=f"msg_{i}",
                conversation_id="conv_abc",
                sequence_id=i+1,
                sender_id=f"user_{i % 3}",  # 3 different users
                sender_name=f"User{i % 3}",
                content=f"Message {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            ))
        
        context = builder.build_context(messages)
        
        # Should only include last 5 human messages
        assert len(context["prev_queries"]) == 5
        assert context["prev_queries"][0]["query"] == "Message 5"
        assert context["prev_queries"][-1]["query"] == "Message 9"
    
    def test_mixed_messages_with_nlweb(self, builder):
        """Test context with mixed human and NLWeb messages"""
        messages = [
            ChatMessage(
                message_id="msg_1",
                conversation_id="conv_abc",
                sequence_id=1,
                sender_id="alice_123",
                sender_name="Alice",
                content="What's the weather?",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            ),
            ChatMessage(
                message_id="msg_2",
                conversation_id="conv_abc",
                sequence_id=2,
                sender_id="nlweb_1",
                sender_name="NLWeb Assistant",
                content="The weather is sunny and 72°F.",
                message_type=MessageType.NLWEB_RESPONSE,
                timestamp=datetime.utcnow(),
                metadata={"sources": ["weather.com"]}
            ),
            ChatMessage(
                message_id="msg_3",
                conversation_id="conv_abc",
                sequence_id=3,
                sender_id="bob_456",
                sender_name="Bob",
                content="Thanks! What about tomorrow?",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
        ]
        
        context = builder.build_context(messages)
        
        # Should have 2 human messages
        assert len(context["prev_queries"]) == 2
        assert context["prev_queries"][0]["query"] == "What's the weather?"
        assert context["prev_queries"][1]["query"] == "Thanks! What about tomorrow?"
        
        # Should have 1 NLWeb answer
        assert len(context["last_answers"]) == 1
        assert context["last_answers"][0]["content"] == "The weather is sunny and 72°F."
        assert context["last_answers"][0]["metadata"]["sources"] == ["weather.com"]
    
    def test_current_query_extraction(self, builder):
        """Test extracting current query from latest human message"""
        messages = [
            ChatMessage(
                message_id="msg_1",
                conversation_id="conv_abc",
                sequence_id=1,
                sender_id="alice_123",
                sender_name="Alice",
                content="Previous question",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            ),
            ChatMessage(
                message_id="msg_2",
                conversation_id="conv_abc",
                sequence_id=2,
                sender_id="bob_456",
                sender_name="Bob",
                content="Current question?",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
        ]
        
        context = builder.build_context(messages, current_message=messages[-1])
        
        assert context["current_query"] == "Current question?"
        assert context["current_user_id"] == "bob_456"
        # Previous queries should not include current
        assert len(context["prev_queries"]) == 1
        assert context["prev_queries"][0]["query"] == "Previous question"


class TestNLWebParticipant:
    """Test NLWeb participant wrapper"""
    
    @pytest.fixture
    def mock_nlweb_handler(self):
        """Create mock NLWebHandler"""
        handler = AsyncMock()
        handler.runQuery = AsyncMock()
        return handler
    
    @pytest.fixture
    def participant_config(self):
        """Create participant configuration"""
        return ParticipantConfig(
            timeout=20,
            human_messages_context=5,
            nlweb_messages_context=1
        )
    
    @pytest.fixture
    async def nlweb_participant(self, mock_nlweb_handler, participant_config):
        """Create NLWeb participant"""
        participant = NLWebParticipant(
            nlweb_handler=mock_nlweb_handler,
            config=participant_config
        )
        return participant
    
    @pytest.mark.asyncio
    async def test_process_human_message(self, nlweb_participant, mock_nlweb_handler):
        """Test processing a message from a human"""
        message = ChatMessage(
            message_id="msg_1",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="alice_123",
            sender_name="Alice",
            content="What's the weather?",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Mock response capture
        captured_response = []
        
        class MockChunkCapture:
            async def write_stream(self, data, end_response=False):
                captured_response.append(data)
        
        # Mock handler function
        async def mock_handler(query_params, chunk_handler):
            # Simulate NLWeb response
            await chunk_handler.write_stream(
                {"answer": "The weather is sunny."}, 
                end_response=True
            )
        
        nlweb_participant.nlweb_handler = mock_handler
        
        # Process message
        response = await nlweb_participant.process_message(message, context=[])
        
        # Should have returned a response
        assert response is not None
        assert response.message_type == MessageType.NLWEB_RESPONSE
        assert response.sender_id == "nlweb_1"
    
    @pytest.mark.asyncio
    async def test_process_with_context(self, nlweb_participant, mock_nlweb_handler):
        """Test processing with conversation context"""
        # Previous messages
        context = [
            ChatMessage(
                message_id="msg_1",
                conversation_id="conv_abc",
                sequence_id=1,
                sender_id="alice_123",
                sender_name="Alice",
                content="Hello",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            ),
            ChatMessage(
                message_id="msg_2",
                conversation_id="conv_abc",
                sequence_id=2,
                sender_id="nlweb_1",
                sender_name="NLWeb",
                content="Hello Alice!",
                message_type=MessageType.NLWEB_RESPONSE,
                timestamp=datetime.utcnow()
            )
        ]
        
        # Current message
        message = ChatMessage(
            message_id="msg_3",
            conversation_id="conv_abc",
            sequence_id=3,
            sender_id="alice_123",
            sender_name="Alice",
            content="What's the weather?",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Track calls to handler
        called_params = []
        
        async def tracking_handler(query_params, chunk_handler):
            called_params.append(query_params)
            await chunk_handler.write_stream("Response with context", end_response=True)
        
        nlweb_participant.nlweb_handler = tracking_handler
        
        # Process with context
        await nlweb_participant.process_message(message, context)
        
        # Check context was passed
        assert len(called_params) == 1
        query_params = called_params[0]
        
        # Should have previous queries
        assert "prev_queries" in query_params
        prev_queries = json.loads(query_params["prev_queries"][0])
        assert len(prev_queries) == 1
        assert prev_queries[0]["query"] == "Hello"
        assert prev_queries[0]["user_id"] == "alice_123"
        
        # Should have last answers
        assert "last_answers" in query_params
        last_answers = json.loads(query_params["last_answers"][0])
        assert len(last_answers) == 1
        assert last_answers[0]["content"] == "Hello Alice!"
    
    @pytest.mark.asyncio
    async def test_multi_human_context(self, nlweb_participant, mock_nlweb_handler):
        """Test NLWeb sees messages from multiple humans"""
        context = [
            ChatMessage(
                message_id="msg_1",
                conversation_id="conv_abc",
                sequence_id=1,
                sender_id="alice_123",
                sender_name="Alice",
                content="I think we should go to the park",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            ),
            ChatMessage(
                message_id="msg_2",
                conversation_id="conv_abc",
                sequence_id=2,
                sender_id="bob_456",
                sender_name="Bob",
                content="I prefer the beach",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            ),
            ChatMessage(
                message_id="msg_3",
                conversation_id="conv_abc",
                sequence_id=3,
                sender_id="charlie_789",
                sender_name="Charlie",
                content="What's the weather forecast?",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
        ]
        
        # Current message from Alice
        message = ChatMessage(
            message_id="msg_4",
            conversation_id="conv_abc",
            sequence_id=4,
            sender_id="alice_123",
            sender_name="Alice",
            content="Yes, weather is important. Can you check?",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Track calls
        called_params = []
        
        async def tracking_handler(query_params, chunk_handler):
            called_params.append(query_params)
            await chunk_handler.write_stream("Multi-human response", end_response=True)
        
        nlweb_participant.nlweb_handler = tracking_handler
        
        # Process with multi-human context
        await nlweb_participant.process_message(message, context)
        
        # Check all human messages are in context
        assert len(called_params) == 1
        query_params = called_params[0]
        
        prev_queries = json.loads(query_params["prev_queries"][0])
        assert len(prev_queries) == 3
        
        # Verify each human's message is preserved with their ID
        assert prev_queries[0]["user_id"] == "alice_123"
        assert prev_queries[1]["user_id"] == "bob_456"
        assert prev_queries[2]["user_id"] == "charlie_789"
    
    @pytest.mark.asyncio
    async def test_streaming_response(self, nlweb_participant, mock_nlweb_handler):
        """Test streaming response handling"""
        message = ChatMessage(
            message_id="msg_1",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="alice_123",
            sender_name="Alice",
            content="Tell me a story",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Track streamed chunks
        streamed_chunks = []
        
        async def mock_stream_callback(chunk):
            streamed_chunks.append(chunk)
        
        # Mock streaming response
        async def simulate_streaming(query_params, chunk_handler):
            # Simulate multiple chunks
            await chunk_handler.write_stream("Once upon a time", end_response=False)
            await chunk_handler.write_stream(", there was a", end_response=False)
            await chunk_handler.write_stream(" happy chat system.", end_response=True)
        
        # Replace the mock handler with our streaming function
        nlweb_participant.nlweb_handler = simulate_streaming
        
        # Process with streaming callback
        response = await nlweb_participant.process_message(
            message, 
            context=[], 
            stream_callback=mock_stream_callback
        )
        
        # Should have received all chunks
        assert len(streamed_chunks) == 3
        assert "Once upon a time" in str(streamed_chunks[0])
        assert "happy chat system" in str(streamed_chunks[2])
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, nlweb_participant, mock_nlweb_handler):
        """Test timeout handling"""
        message = ChatMessage(
            message_id="msg_1",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="alice_123",
            sender_name="Alice",
            content="Complex query",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Mock slow response
        async def slow_response(query_params, chunk_handler):
            await asyncio.sleep(30)  # Longer than timeout
        
        nlweb_participant.nlweb_handler = slow_response
        
        # Should timeout
        with pytest.raises(asyncio.TimeoutError):
            # Use short timeout for test
            nlweb_participant.config.timeout = 0.1
            await nlweb_participant.process_message(message, context=[])
    
    @pytest.mark.asyncio
    async def test_nlweb_decides_not_to_respond(self, nlweb_participant, mock_nlweb_handler):
        """Test when NLWeb decides not to respond"""
        message = ChatMessage(
            message_id="msg_1",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="alice_123",
            sender_name="Alice",
            content="[System message or greeting]",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Mock NLWeb returning empty response
        async def no_response(query_params, chunk_handler):
            # NLWeb decides not to respond
            pass
        
        nlweb_participant.nlweb_handler = no_response
        
        # Process message
        response = await nlweb_participant.process_message(message, context=[])
        
        # Should return None when NLWeb doesn't respond
        assert response is None
    
    @pytest.mark.asyncio
    async def test_queue_full_handling(self, nlweb_participant, mock_nlweb_handler):
        """Test handling queue full errors"""
        message = ChatMessage(
            message_id="msg_1",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="alice_123",
            sender_name="Alice",
            content="Another query",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Mock queue full error
        async def queue_full_handler(query_params, chunk_handler):
            raise QueueFullError(
                conversation_id="conv_abc",
                queue_size=1000,
                limit=1000
            )
        
        nlweb_participant.nlweb_handler = queue_full_handler
        
        # Should handle gracefully
        response = await nlweb_participant.process_message(message, context=[])
        assert response is None


class TestBaseParticipant:
    """Test base participant interface"""
    
    def test_base_participant_interface(self):
        """Test that base participant defines required methods"""
        assert hasattr(BaseParticipant, 'process_message')
        assert hasattr(BaseParticipant, 'get_participant_info')


class TestHumanParticipant:
    """Test human participant"""
    
    @pytest.mark.asyncio
    async def test_human_participant(self):
        """Test human participant creation"""
        participant = HumanParticipant(
            user_id="alice_123",
            user_name="Alice"
        )
        
        info = participant.get_participant_info()
        assert info.participant_id == "alice_123"
        assert info.name == "Alice"
        assert info.is_human() is True
        assert info.is_ai() is False
        
        # Humans don't process messages (they send them)
        result = await participant.process_message(None, [])
        assert result is None