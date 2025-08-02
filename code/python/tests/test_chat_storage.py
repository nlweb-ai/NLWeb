"""
Tests for chat storage system.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import time

from chat.schemas import (
    ChatMessage,
    Conversation,
    ParticipantInfo,
    ParticipantType,
    MessageType,
    MessageStatus,
    QueueFullError
)

# These imports will fail until we create the modules
from chat.storage import ChatStorageInterface, ChatStorageClient
from chat.cache import ConversationCache
from chat_storage_providers.memory_storage import MemoryStorage
from chat.metrics import ChatMetrics


class TestChatStorageInterface:
    """Test the abstract storage interface"""
    
    @pytest.mark.asyncio
    async def test_interface_methods(self):
        """Test that interface defines required methods"""
        # This test will ensure the interface has the right methods
        assert hasattr(ChatStorageInterface, 'store_message')
        assert hasattr(ChatStorageInterface, 'get_conversation_messages')
        assert hasattr(ChatStorageInterface, 'get_next_sequence_id')
        assert hasattr(ChatStorageInterface, 'update_conversation')
        assert hasattr(ChatStorageInterface, 'get_conversation')


class TestMemoryStorage:
    """Test the in-memory storage implementation"""
    
    @pytest.fixture
    async def storage(self):
        """Create a memory storage instance"""
        config = {
            "queue_size_limit": 1000
        }
        return MemoryStorage(config)
    
    @pytest.mark.asyncio
    async def test_store_message(self, storage):
        """Test storing a message"""
        message = ChatMessage(
            message_id="msg_123",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="user_123",
            sender_name="Alice",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Store the message
        await storage.store_message(message)
        
        # Retrieve it
        messages = await storage.get_conversation_messages("conv_abc", limit=10)
        assert len(messages) == 1
        assert messages[0].message_id == "msg_123"
        assert messages[0].sender_id == "user_123"
    
    @pytest.mark.asyncio
    async def test_atomic_sequence_id(self, storage):
        """Test atomic sequence ID generation"""
        conv_id = "conv_abc"
        
        # Get initial sequence ID
        seq1 = await storage.get_next_sequence_id(conv_id)
        assert seq1 == 1
        
        # Get next sequence ID
        seq2 = await storage.get_next_sequence_id(conv_id)
        assert seq2 == 2
        
        # Different conversation should have its own sequence
        seq_other = await storage.get_next_sequence_id("conv_xyz")
        assert seq_other == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_sequence_ids(self, storage):
        """Test concurrent sequence ID generation from multiple humans"""
        conv_id = "conv_multi"
        tasks = []
        
        # Simulate 10 humans requesting sequence IDs concurrently
        async def get_sequence():
            return await storage.get_next_sequence_id(conv_id)
        
        for _ in range(10):
            tasks.append(asyncio.create_task(get_sequence()))
        
        # Wait for all tasks
        sequence_ids = await asyncio.gather(*tasks)
        
        # All sequence IDs should be unique
        assert len(set(sequence_ids)) == 10
        # Should be sequential
        assert sorted(sequence_ids) == list(range(1, 11))
    
    @pytest.mark.asyncio
    async def test_message_deduplication(self, storage):
        """Test message deduplication by message_id"""
        message = ChatMessage(
            message_id="msg_dup",
            conversation_id="conv_abc",
            sequence_id=1,
            sender_id="user_123",
            sender_name="Alice",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Store the message twice
        await storage.store_message(message)
        await storage.store_message(message)
        
        # Should only have one message
        messages = await storage.get_conversation_messages("conv_abc")
        assert len(messages) == 1
    
    @pytest.mark.asyncio
    async def test_queue_limit_enforcement(self, storage):
        """Test queue limit enforcement"""
        # Create storage with small queue limit
        storage = MemoryStorage({"queue_size_limit": 3})
        conv_id = "conv_limited"
        
        # Create conversation
        conversation = Conversation(
            conversation_id=conv_id,
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=3
        )
        await storage.update_conversation(conversation)
        
        # Add 3 messages (up to limit)
        for i in range(3):
            message = ChatMessage(
                message_id=f"msg_{i}",
                conversation_id=conv_id,
                sequence_id=i+1,
                sender_id=f"user_{i}",
                sender_name=f"User{i}",
                content=f"Message {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            await storage.store_message(message)
        
        # Fourth message should fail
        with pytest.raises(QueueFullError) as exc_info:
            message = ChatMessage(
                message_id="msg_4",
                conversation_id=conv_id,
                sequence_id=4,
                sender_id="user_4",
                sender_name="User4",
                content="This should fail",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            await storage.store_message(message)
        
        assert exc_info.value.conversation_id == conv_id
        assert exc_info.value.queue_size == 3
        assert exc_info.value.limit == 3
    
    @pytest.mark.asyncio
    async def test_multiple_human_messages(self, storage):
        """Test storing messages from multiple humans"""
        conv_id = "conv_multi_human"
        
        # Store messages from different humans
        humans = ["alice_123", "bob_456", "charlie_789"]
        for i, human_id in enumerate(humans):
            message = ChatMessage(
                message_id=f"msg_{human_id}",
                conversation_id=conv_id,
                sequence_id=await storage.get_next_sequence_id(conv_id),
                sender_id=human_id,
                sender_name=human_id.split('_')[0].title(),
                content=f"Hello from {human_id}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            await storage.store_message(message)
        
        # Retrieve messages
        messages = await storage.get_conversation_messages(conv_id)
        assert len(messages) == 3
        
        # Check all sender_ids are preserved
        sender_ids = [msg.sender_id for msg in messages]
        assert set(sender_ids) == set(humans)
        
        # Messages should be ordered by sequence_id
        assert messages[0].sequence_id < messages[1].sequence_id < messages[2].sequence_id
    
    @pytest.mark.asyncio
    async def test_conversation_update(self, storage):
        """Test updating conversation metadata"""
        alice = ParticipantInfo("alice_123", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        bob = ParticipantInfo("bob_456", "Bob", ParticipantType.HUMAN, datetime.utcnow())
        nlweb = ParticipantInfo("nlweb_1", "NLWeb", ParticipantType.AI, datetime.utcnow())
        
        conversation = Conversation(
            conversation_id="conv_update",
            created_at=datetime.utcnow(),
            active_participants={alice, nlweb},
            queue_size_limit=1000
        )
        
        # Store conversation
        await storage.update_conversation(conversation)
        
        # Retrieve it
        retrieved = await storage.get_conversation("conv_update")
        assert retrieved is not None
        assert len(retrieved.active_participants) == 2
        
        # Add Bob
        conversation.add_participant(bob)
        await storage.update_conversation(conversation)
        
        # Retrieve again
        retrieved = await storage.get_conversation("conv_update")
        assert len(retrieved.active_participants) == 3
        assert bob in retrieved.active_participants


class TestChatStorageClient:
    """Test the storage client that routes to backends"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        return {
            "chat": {
                "storage": {
                    "backend": "memory",
                    "queue_size_limit": 1000
                }
            }
        }
    
    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_config):
        """Test client initialization with config"""
        with patch('chat.storage.get_config', return_value=mock_config):
            client = ChatStorageClient()
            assert client.backend_type == "memory"
            assert isinstance(client.backend, MemoryStorage)
    
    @pytest.mark.asyncio
    async def test_client_delegates_to_backend(self, mock_config):
        """Test that client delegates all calls to backend"""
        with patch('chat.storage.get_config', return_value=mock_config):
            client = ChatStorageClient()
            
            # Mock the backend
            mock_backend = AsyncMock(spec=ChatStorageInterface)
            client.backend = mock_backend
            
            # Test store_message delegation
            message = Mock()
            await client.store_message(message)
            mock_backend.store_message.assert_called_once_with(message)
            
            # Test get_conversation_messages delegation
            await client.get_conversation_messages("conv_123", limit=50)
            mock_backend.get_conversation_messages.assert_called_once_with("conv_123", 50, None)
            
            # Test get_next_sequence_id delegation
            await client.get_next_sequence_id("conv_123")
            mock_backend.get_next_sequence_id.assert_called_once_with("conv_123")
    
    @pytest.mark.asyncio
    async def test_client_metrics_collection(self, mock_config):
        """Test that client collects metrics"""
        with patch('chat.storage.get_config', return_value=mock_config):
            with patch('chat.storage.ChatMetrics') as mock_metrics_class:
                mock_metrics = Mock()
                mock_metrics_class.return_value = mock_metrics
                
                client = ChatStorageClient()
                
                # Store a message
                message = ChatMessage(
                    message_id="msg_123",
                    conversation_id="conv_abc",
                    sequence_id=1,
                    sender_id="user_123",
                    sender_name="Alice",
                    content="Hello",
                    message_type=MessageType.TEXT,
                    timestamp=datetime.utcnow()
                )
                
                await client.store_message(message)
                
                # Check metrics were recorded
                mock_metrics.record_storage_operation.assert_called()


class TestConversationCache:
    """Test the conversation cache"""
    
    @pytest.fixture
    def cache(self):
        """Create a cache instance"""
        return ConversationCache(max_conversations=10, max_messages_per_conversation=100)
    
    def test_cache_basic_operations(self, cache):
        """Test basic cache operations"""
        conv_id = "conv_abc"
        message = ChatMessage(
            message_id="msg_123",
            conversation_id=conv_id,
            sequence_id=1,
            sender_id="user_123",
            sender_name="Alice",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        
        # Add message
        cache.add_message(conv_id, message)
        
        # Retrieve messages
        messages = cache.get_messages(conv_id)
        assert len(messages) == 1
        assert messages[0].message_id == "msg_123"
        
        # Check if conversation is cached
        assert cache.has_conversation(conv_id)
    
    def test_cache_message_limit(self, cache):
        """Test cache enforces message limit per conversation"""
        conv_id = "conv_abc"
        
        # Add 150 messages (more than limit of 100)
        for i in range(150):
            message = ChatMessage(
                message_id=f"msg_{i}",
                conversation_id=conv_id,
                sequence_id=i+1,
                sender_id="user_123",
                sender_name="Alice",
                content=f"Message {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            cache.add_message(conv_id, message)
        
        # Should only have last 100 messages
        messages = cache.get_messages(conv_id)
        assert len(messages) == 100
        # Should be the last 100 messages
        assert messages[0].message_id == "msg_50"
        assert messages[-1].message_id == "msg_149"
    
    def test_cache_conversation_limit(self, cache):
        """Test cache enforces conversation limit"""
        # Add 15 conversations (more than limit of 10)
        for i in range(15):
            conv_id = f"conv_{i}"
            message = ChatMessage(
                message_id=f"msg_{i}",
                conversation_id=conv_id,
                sequence_id=1,
                sender_id="user_123",
                sender_name="Alice",
                content=f"Message {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            cache.add_message(conv_id, message)
        
        # First 5 conversations should be evicted
        for i in range(5):
            assert not cache.has_conversation(f"conv_{i}")
        
        # Last 10 should still be there
        for i in range(5, 15):
            assert cache.has_conversation(f"conv_{i}")
    
    def test_cache_thread_safety(self, cache):
        """Test cache is thread-safe for concurrent access"""
        conv_id = "conv_concurrent"
        results = []
        
        def add_messages(start_id):
            for i in range(10):
                message = ChatMessage(
                    message_id=f"msg_{start_id}_{i}",
                    conversation_id=conv_id,
                    sequence_id=start_id + i,
                    sender_id=f"user_{start_id}",
                    sender_name=f"User{start_id}",
                    content=f"Message {i}",
                    message_type=MessageType.TEXT,
                    timestamp=datetime.utcnow()
                )
                cache.add_message(conv_id, message)
        
        # Run multiple threads
        import threading
        threads = []
        for i in range(5):
            thread = threading.Thread(target=add_messages, args=(i*10,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Should have all 50 messages
        messages = cache.get_messages(conv_id)
        assert len(messages) == 50
    
    def test_cache_metrics(self, cache):
        """Test cache metrics tracking"""
        conv_id = "conv_metrics"
        
        # Miss
        messages = cache.get_messages(conv_id)
        assert messages is None
        assert cache.get_metrics()["cache_misses"] == 1
        assert cache.get_metrics()["cache_hits"] == 0
        
        # Add message
        message = ChatMessage(
            message_id="msg_123",
            conversation_id=conv_id,
            sequence_id=1,
            sender_id="user_123",
            sender_name="Alice",
            content="Hello",
            message_type=MessageType.TEXT,
            timestamp=datetime.utcnow()
        )
        cache.add_message(conv_id, message)
        
        # Hit
        messages = cache.get_messages(conv_id)
        assert messages is not None
        assert cache.get_metrics()["cache_hits"] == 1
        assert cache.get_metrics()["hit_rate"] == 0.5  # 1 hit / 2 total
    
    def test_cache_participant_tracking(self, cache):
        """Test cache tracks participants correctly"""
        conv_id = "conv_participants"
        alice = ParticipantInfo("alice_123", "Alice", ParticipantType.HUMAN, datetime.utcnow())
        bob = ParticipantInfo("bob_456", "Bob", ParticipantType.HUMAN, datetime.utcnow())
        nlweb = ParticipantInfo("nlweb_1", "NLWeb", ParticipantType.AI, datetime.utcnow())
        
        # Update participants
        cache.update_participants(conv_id, {alice, bob, nlweb})
        
        # Get participants
        participants = cache.get_participants(conv_id)
        assert len(participants) == 3
        assert alice in participants
        assert bob in participants
        assert nlweb in participants
        
        # Remove Bob
        cache.update_participants(conv_id, {alice, nlweb})
        participants = cache.get_participants(conv_id)
        assert len(participants) == 2
        assert bob not in participants


class TestChatMetrics:
    """Test chat metrics collection"""
    
    @pytest.fixture
    def metrics(self):
        """Create metrics instance"""
        return ChatMetrics()
    
    def test_storage_operation_metrics(self, metrics):
        """Test storage operation metrics"""
        # Record some operations
        metrics.record_storage_operation("store_message", 0.01)
        metrics.record_storage_operation("store_message", 0.02)
        metrics.record_storage_operation("get_messages", 0.005)
        
        stats = metrics.get_storage_stats()
        assert stats["store_message"]["count"] == 2
        assert stats["store_message"]["avg_latency"] == 0.015
        assert stats["get_messages"]["count"] == 1
        assert stats["get_messages"]["avg_latency"] == 0.005
    
    def test_connection_metrics(self, metrics):
        """Test connection tracking per human"""
        # Track connections
        metrics.track_connection("alice_123", "connect")
        metrics.track_connection("bob_456", "connect")
        metrics.track_connection("alice_123", "connect")  # Alice's second connection
        
        stats = metrics.get_connection_stats()
        assert stats["alice_123"] == 2
        assert stats["bob_456"] == 1
        assert stats["total_connections"] == 3
    
    def test_queue_depth_metrics(self, metrics):
        """Test queue depth tracking"""
        # Track queue depths
        metrics.update_queue_depth("conv_abc", 10)
        metrics.update_queue_depth("conv_xyz", 50)
        metrics.update_queue_depth("conv_abc", 15)  # Update
        
        stats = metrics.get_queue_stats()
        assert stats["conv_abc"] == 15
        assert stats["conv_xyz"] == 50
        assert stats["max_queue_depth"] == 50
    
    def test_multi_human_pattern_metrics(self, metrics):
        """Test tracking multi-human conversation patterns"""
        # Track conversation with 1 human
        metrics.track_conversation_pattern("conv_single", 1)
        
        # Track conversations with multiple humans
        metrics.track_conversation_pattern("conv_multi1", 3)
        metrics.track_conversation_pattern("conv_multi2", 5)
        
        stats = metrics.get_conversation_patterns()
        assert stats["single_human"] == 1
        assert stats["multi_human"] == 2
        assert stats["max_humans_in_conversation"] == 5
        assert stats["avg_humans_per_conversation"] == 3.0  # (1+3+5)/3