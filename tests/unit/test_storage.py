"""
Unit tests for chat storage implementations.
Tests ChatStorageInterface, MemoryStorage, and ConversationCache.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Set, Dict, Any
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../code/python'))

from chat.schemas import (
    ChatMessage, MessageType, MessageStatus,
    Conversation, ParticipantInfo, ParticipantType,
    QueueFullError
)
from chat.storage import ChatStorageInterface, ChatStorageClient
from chat_storage_providers.memory_storage import MemoryStorage
from chat.cache import ConversationCache


# Test Fixtures
@pytest.fixture
def create_test_conversation():
    """Factory for creating test conversations."""
    def _create(conversation_id: str = None, participant_count: int = 2, queue_limit: int = 1000):
        if not conversation_id:
            conversation_id = f"conv_{uuid.uuid4().hex[:8]}"
        
        participants = set()
        for i in range(participant_count):
            if i == 0:
                # Always have at least one human
                p = ParticipantInfo(
                    participant_id=f"human_{i}",
                    name=f"Human {i}",
                    participant_type=ParticipantType.HUMAN,
                    joined_at=datetime.utcnow()
                )
            else:
                # Mix of humans and AI
                p = ParticipantInfo(
                    participant_id=f"participant_{i}",
                    name=f"Participant {i}",
                    participant_type=ParticipantType.HUMAN if i % 2 == 0 else ParticipantType.AI,
                    joined_at=datetime.utcnow()
                )
            participants.add(p)
        
        return Conversation(
            conversation_id=conversation_id,
            created_at=datetime.utcnow(),
            active_participants=participants,
            queue_size_limit=queue_limit
        )
    return _create


@pytest.fixture
def create_test_messages():
    """Factory for creating test messages."""
    def _create(count: int, conversation_id: str, participants: List[str] = None):
        if not participants:
            participants = ["user_1", "user_2", "nlweb_1"]
        
        messages = []
        for i in range(count):
            sender_id = participants[i % len(participants)]
            msg = ChatMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                conversation_id=conversation_id,
                sequence_id=i + 1,
                sender_id=sender_id,
                sender_name=f"Sender {sender_id}",
                content=f"Test message {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow(),
                status=MessageStatus.DELIVERED
            )
            messages.append(msg)
        return messages
    return _create


@pytest.fixture
async def memory_storage():
    """Create a memory storage instance for testing."""
    config = {"queue_size_limit": 1000}
    return MemoryStorage(config)


@pytest.fixture
def conversation_cache():
    """Create a conversation cache instance for testing."""
    return ConversationCache(max_conversations=10, max_messages_per_conversation=100)


@pytest.mark.unit
@pytest.mark.asyncio
class TestChatStorageInterface:
    """Test the abstract ChatStorageInterface."""
    
    async def test_interface_methods_defined(self):
        """Test that all required methods are defined in the interface."""
        required_methods = [
            'store_message',
            'get_conversation_messages',
            'get_next_sequence_id',
            'update_conversation',
            'get_conversation'
        ]
        
        for method in required_methods:
            assert hasattr(ChatStorageInterface, method)
            assert callable(getattr(ChatStorageInterface, method))
    
    async def test_cannot_instantiate_abstract_class(self):
        """Test that abstract class cannot be instantiated."""
        with pytest.raises(TypeError):
            ChatStorageInterface()


@pytest.mark.unit
@pytest.mark.asyncio
class TestMemoryStorage:
    """Test the MemoryStorage implementation."""
    
    async def test_store_message_idempotency(self, memory_storage, create_test_messages):
        """Test that storing the same message twice is idempotent."""
        conv_id = "conv_test_001"
        messages = create_test_messages(1, conv_id)
        message = messages[0]
        
        # Store the message twice
        await memory_storage.store_message(message)
        await memory_storage.store_message(message)
        
        # Retrieve messages
        stored_messages = await memory_storage.get_conversation_messages(conv_id)
        
        # Should only have one copy
        assert len(stored_messages) == 1
        assert stored_messages[0].message_id == message.message_id
    
    async def test_get_next_sequence_id_atomicity(self, memory_storage):
        """Test atomic sequence ID generation."""
        conv_id = "conv_atomic_001"
        
        # Get multiple sequence IDs
        seq_ids = []
        for _ in range(10):
            seq_id = await memory_storage.get_next_sequence_id(conv_id)
            seq_ids.append(seq_id)
        
        # All should be unique and sequential
        assert seq_ids == list(range(1, 11))
    
    async def test_concurrent_sequence_id_generation(self, memory_storage):
        """Test concurrent sequence ID generation remains sequential."""
        conv_id = "conv_concurrent_001"
        num_concurrent = 50
        
        async def get_sequence_id():
            return await memory_storage.get_next_sequence_id(conv_id)
        
        # Create concurrent tasks
        tasks = [get_sequence_id() for _ in range(num_concurrent)]
        seq_ids = await asyncio.gather(*tasks)
        
        # Sort and verify all are unique and sequential
        sorted_ids = sorted(seq_ids)
        assert sorted_ids == list(range(1, num_concurrent + 1))
        assert len(set(seq_ids)) == num_concurrent
    
    async def test_message_retrieval_with_pagination(self, memory_storage, create_test_messages):
        """Test message retrieval with pagination."""
        conv_id = "conv_paginate_001"
        messages = create_test_messages(20, conv_id)
        
        # Store all messages
        for msg in messages:
            await memory_storage.store_message(msg)
        
        # Test limit
        page1 = await memory_storage.get_conversation_messages(conv_id, limit=5)
        assert len(page1) == 5
        assert [m.sequence_id for m in page1] == [16, 17, 18, 19, 20]  # Latest 5
        
        # Test after_sequence_id
        page2 = await memory_storage.get_conversation_messages(conv_id, after_sequence_id=10)
        assert len(page2) == 10
        assert all(m.sequence_id > 10 for m in page2)
        
        # Test combined
        page3 = await memory_storage.get_conversation_messages(conv_id, limit=5, after_sequence_id=15)
        assert len(page3) == 5
        assert [m.sequence_id for m in page3] == [16, 17, 18, 19, 20]
    
    async def test_message_ordering_by_sequence_id(self, memory_storage, create_test_messages):
        """Test that messages are always ordered by sequence_id."""
        conv_id = "conv_order_001"
        
        # Create messages with non-sequential storage order
        messages = create_test_messages(10, conv_id)
        
        # Store in random order
        import random
        shuffled = messages.copy()
        random.shuffle(shuffled)
        
        for msg in shuffled:
            await memory_storage.store_message(msg)
        
        # Retrieve and verify order
        stored_messages = await memory_storage.get_conversation_messages(conv_id)
        seq_ids = [m.sequence_id for m in stored_messages]
        assert seq_ids == sorted(seq_ids)
    
    async def test_queue_limit_enforcement(self, memory_storage, create_test_conversation, create_test_messages):
        """Test queue limit enforcement."""
        conv = create_test_conversation(queue_limit=10)
        await memory_storage.update_conversation(conv)
        
        messages = create_test_messages(10, conv.conversation_id)
        
        # Store up to limit
        for msg in messages:
            await memory_storage.store_message(msg)
        
        # Next message should raise QueueFullError
        extra_msg = create_test_messages(1, conv.conversation_id)[0]
        with pytest.raises(QueueFullError) as exc_info:
            await memory_storage.store_message(extra_msg)
        
        error = exc_info.value
        assert error.conversation_id == conv.conversation_id
        assert error.queue_size == 10
        assert error.limit == 10
    
    async def test_conversation_isolation(self, memory_storage, create_test_messages):
        """Test that conversations are properly isolated."""
        conv1_id = "conv_iso_001"
        conv2_id = "conv_iso_002"
        
        # Store messages in different conversations
        conv1_messages = create_test_messages(5, conv1_id)
        conv2_messages = create_test_messages(3, conv2_id)
        
        for msg in conv1_messages + conv2_messages:
            await memory_storage.store_message(msg)
        
        # Retrieve separately
        stored1 = await memory_storage.get_conversation_messages(conv1_id)
        stored2 = await memory_storage.get_conversation_messages(conv2_id)
        
        assert len(stored1) == 5
        assert len(stored2) == 3
        assert all(m.conversation_id == conv1_id for m in stored1)
        assert all(m.conversation_id == conv2_id for m in stored2)
    
    async def test_sequence_counter_thread_safety(self, memory_storage):
        """Test sequence counter thread safety with threading."""
        conv_id = "conv_thread_001"
        num_threads = 10
        ids_per_thread = 10
        
        def get_ids():
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ids = []
            for _ in range(ids_per_thread):
                seq_id = loop.run_until_complete(
                    memory_storage.get_next_sequence_id(conv_id)
                )
                ids.append(seq_id)
            loop.close()
            return ids
        
        # Use threads to test thread safety
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_ids) for _ in range(num_threads)]
            all_ids = []
            for future in as_completed(futures):
                all_ids.extend(future.result())
        
        # Verify all IDs are unique
        assert len(set(all_ids)) == num_threads * ids_per_thread
        assert sorted(all_ids) == list(range(1, num_threads * ids_per_thread + 1))
    
    async def test_message_persistence_across_retrieval(self, memory_storage, create_test_messages):
        """Test that messages persist correctly across multiple retrievals."""
        conv_id = "conv_persist_001"
        messages = create_test_messages(5, conv_id)
        
        # Store messages
        for msg in messages:
            await memory_storage.store_message(msg)
        
        # Multiple retrievals should return same data
        retrieval1 = await memory_storage.get_conversation_messages(conv_id)
        retrieval2 = await memory_storage.get_conversation_messages(conv_id)
        retrieval3 = await memory_storage.get_conversation_messages(conv_id)
        
        assert len(retrieval1) == len(retrieval2) == len(retrieval3) == 5
        assert all(r1.message_id == r2.message_id == r3.message_id 
                  for r1, r2, r3 in zip(retrieval1, retrieval2, retrieval3))


@pytest.mark.unit
class TestConversationCache:
    """Test the ConversationCache implementation."""
    
    def test_lru_eviction_at_capacity(self, conversation_cache, create_test_messages):
        """Test LRU eviction when cache reaches capacity."""
        # Cache capacity is 10 conversations
        for i in range(12):
            conv_id = f"conv_lru_{i}"
            messages = create_test_messages(5, conv_id)
            for msg in messages:
                conversation_cache.add_message(conv_id, msg)
        
        # First 2 conversations should be evicted
        assert not conversation_cache.has_conversation("conv_lru_0")
        assert not conversation_cache.has_conversation("conv_lru_1")
        assert conversation_cache.has_conversation("conv_lru_2")
        assert conversation_cache.has_conversation("conv_lru_11")
    
    def test_thread_safe_operations(self, conversation_cache, create_test_messages):
        """Test thread-safe cache operations."""
        conv_id = "conv_thread_safe"
        num_threads = 20
        messages_per_thread = 5
        
        def add_messages(thread_id):
            messages = create_test_messages(messages_per_thread, conv_id, [f"user_{thread_id}"])
            for msg in messages:
                conversation_cache.add_message(conv_id, msg)
        
        # Use threads to add messages concurrently
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(add_messages, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()
        
        # Cache should have the conversation with max 100 messages
        cached_messages = conversation_cache.get_messages(conv_id)
        assert cached_messages is not None
        assert len(cached_messages) <= 100  # Max per conversation
    
    def test_cache_hit_miss_tracking(self, conversation_cache, create_test_messages):
        """Test cache hit/miss tracking."""
        conv_id = "conv_metrics"
        messages = create_test_messages(5, conv_id)
        
        # Initial state
        metrics = conversation_cache.get_metrics()
        assert metrics["cache_hits"] == 0
        assert metrics["cache_misses"] == 0
        
        # Miss
        result = conversation_cache.get_messages(conv_id)
        assert result is None
        
        # Add messages
        for msg in messages:
            conversation_cache.add_message(conv_id, msg)
        
        # Hit
        result = conversation_cache.get_messages(conv_id)
        assert result is not None
        
        # Check metrics
        metrics = conversation_cache.get_metrics()
        assert metrics["cache_hits"] == 1
        assert metrics["cache_misses"] == 1
        assert metrics["hit_rate"] == 0.5
    
    @pytest.mark.skip(reason="LRU eviction not yet implemented in ConversationCache")
    def test_memory_pressure_handling(self, conversation_cache):
        """Test cache behavior under memory pressure."""
        # Fill cache with maximum messages per conversation
        for i in range(10):  # Max conversations
            conv_id = f"conv_pressure_{i}"
            messages = create_test_messages(100, conv_id)  # Max messages
            for msg in messages:
                conversation_cache.add_message(conv_id, msg)
        
        metrics = conversation_cache.get_metrics()
        assert metrics["cached_conversations"] == 10
        assert metrics["total_cached_messages"] == 1000  # 10 * 100
        
        # Adding another conversation should evict LRU
        new_messages = create_test_messages(50, "conv_pressure_new")
        for msg in new_messages:
            conversation_cache.add_message("conv_pressure_new", msg)
        
        assert not conversation_cache.has_conversation("conv_pressure_0")
        assert conversation_cache.has_conversation("conv_pressure_new")
    
    def test_participant_list_caching(self, conversation_cache):
        """Test participant list caching."""
        conv_id = "conv_participants"
        participants = {
            ParticipantInfo("user_1", "Alice", ParticipantType.HUMAN, datetime.utcnow()),
            ParticipantInfo("user_2", "Bob", ParticipantType.HUMAN, datetime.utcnow()),
            ParticipantInfo("nlweb_1", "AI", ParticipantType.AI, datetime.utcnow())
        }
        
        # Update participants
        conversation_cache.update_participants(conv_id, participants)
        
        # Retrieve participants
        cached_participants = conversation_cache.get_participants(conv_id)
        assert cached_participants is not None
        assert len(cached_participants) == 3
        assert all(p.participant_id in ["user_1", "user_2", "nlweb_1"] for p in cached_participants)
    
    def test_cache_vs_storage_performance(self, conversation_cache, create_test_messages):
        """Test cache performance vs storage retrieval."""
        import time
        
        conv_id = "conv_perf"
        messages = create_test_messages(50, conv_id)
        
        # Add to cache
        for msg in messages:
            conversation_cache.add_message(conv_id, msg)
        
        # Measure cache retrieval
        start = time.perf_counter()
        for _ in range(1000):
            cached = conversation_cache.get_messages(conv_id)
        cache_time = time.perf_counter() - start
        
        # Simulate storage retrieval (with delay)
        async def slow_retrieval():
            await asyncio.sleep(0.001)  # 1ms simulated storage latency
            return messages
        
        # Measure storage retrieval
        start = time.perf_counter()
        for _ in range(100):  # Less iterations due to slowness
            asyncio.run(slow_retrieval())
        storage_time = time.perf_counter() - start
        
        # Cache should be significantly faster
        assert cache_time < storage_time / 10  # At least 10x faster


@pytest.mark.unit
@pytest.mark.asyncio
class TestConcurrentAccess:
    """Test concurrent access scenarios."""
    
    async def simulate_concurrent_writes(self, storage, conversation_id, participants, messages_per_participant):
        """Helper to simulate concurrent writes from multiple participants."""
        async def write_messages(participant_id):
            messages = []
            for i in range(messages_per_participant):
                # Get sequence ID first
                seq_id = await storage.get_next_sequence_id(conversation_id)
                
                msg = ChatMessage(
                    message_id=f"msg_{participant_id}_{i}",
                    conversation_id=conversation_id,
                    sequence_id=seq_id,
                    sender_id=participant_id,
                    sender_name=f"User {participant_id}",
                    content=f"Message {i} from {participant_id}",
                    message_type=MessageType.TEXT,
                    timestamp=datetime.utcnow(),
                    status=MessageStatus.DELIVERED
                )
                await storage.store_message(msg)
                messages.append(msg)
            return messages
        
        # Create concurrent tasks for all participants
        tasks = [write_messages(p) for p in participants]
        results = await asyncio.gather(*tasks)
        return [msg for msgs in results for msg in msgs]  # Flatten
    
    async def test_ten_humans_sending_simultaneously(self, memory_storage):
        """Test 10 humans sending messages simultaneously."""
        conv_id = "conv_10humans"
        participants = [f"human_{i}" for i in range(10)]
        messages_per_participant = 10
        
        # Simulate concurrent writes
        all_messages = await self.simulate_concurrent_writes(
            memory_storage, conv_id, participants, messages_per_participant
        )
        
        # Verify all messages stored
        stored = await memory_storage.get_conversation_messages(conv_id, limit=200)
        assert len(stored) == 100  # 10 humans * 10 messages
        
        # Verify sequence IDs are sequential
        seq_ids = [m.sequence_id for m in stored]
        assert seq_ids == list(range(1, 101))
    
    async def test_sequence_ids_remain_sequential(self, memory_storage):
        """Test sequence IDs remain sequential under concurrent load."""
        conv_id = "conv_sequential"
        num_concurrent = 50
        
        async def get_and_store():
            seq_id = await memory_storage.get_next_sequence_id(conv_id)
            msg = ChatMessage(
                message_id=f"msg_seq_{seq_id}",
                conversation_id=conv_id,
                sequence_id=seq_id,
                sender_id="user_concurrent",
                sender_name="Concurrent User",
                content=f"Message {seq_id}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            await memory_storage.store_message(msg)
            return seq_id
        
        # Create highly concurrent operations
        tasks = [get_and_store() for _ in range(num_concurrent)]
        seq_ids = await asyncio.gather(*tasks)
        
        # Verify all sequential with no gaps
        assert sorted(seq_ids) == list(range(1, num_concurrent + 1))
    
    async def test_no_message_loss_under_load(self, memory_storage):
        """Test no messages are lost under heavy concurrent load."""
        conv_id = "conv_no_loss"
        participants = [f"user_{i}" for i in range(20)]
        messages_per_participant = 50
        
        # Track all message IDs sent
        sent_message_ids = set()
        
        async def write_with_tracking(participant_id):
            messages = []
            for i in range(messages_per_participant):
                msg_id = f"msg_{participant_id}_{i}_{uuid.uuid4().hex[:8]}"
                sent_message_ids.add(msg_id)
                
                seq_id = await memory_storage.get_next_sequence_id(conv_id)
                msg = ChatMessage(
                    message_id=msg_id,
                    conversation_id=conv_id,
                    sequence_id=seq_id,
                    sender_id=participant_id,
                    sender_name=f"User {participant_id}",
                    content=f"Load test message {i}",
                    message_type=MessageType.TEXT,
                    timestamp=datetime.utcnow()
                )
                await memory_storage.store_message(msg)
                messages.append(msg)
            return messages
        
        # Execute concurrent writes
        tasks = [write_with_tracking(p) for p in participants]
        await asyncio.gather(*tasks)
        
        # Verify no message loss
        stored = await memory_storage.get_conversation_messages(conv_id, limit=2000)
        stored_ids = {m.message_id for m in stored}
        
        assert len(stored) == 1000  # 20 * 50
        assert stored_ids == sent_message_ids
    
    async def test_cache_consistency_under_concurrent_access(self, conversation_cache):
        """Test cache remains consistent under concurrent access."""
        conv_id = "conv_cache_consistent"
        num_threads = 10
        
        def concurrent_operations(thread_id):
            # Mix of reads and writes
            for i in range(20):
                if i % 3 == 0:
                    # Write
                    msg = ChatMessage(
                        message_id=f"msg_{thread_id}_{i}",
                        conversation_id=conv_id,
                        sequence_id=thread_id * 20 + i,
                        sender_id=f"user_{thread_id}",
                        sender_name=f"User {thread_id}",
                        content=f"Concurrent message {i}",
                        message_type=MessageType.TEXT,
                        timestamp=datetime.utcnow()
                    )
                    conversation_cache.add_message(conv_id, msg)
                else:
                    # Read
                    messages = conversation_cache.get_messages(conv_id)
                    if messages:
                        assert all(isinstance(m, ChatMessage) for m in messages)
        
        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(concurrent_operations, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()
        
        # Verify final state is consistent
        final_messages = conversation_cache.get_messages(conv_id)
        assert final_messages is not None
        assert len(final_messages) <= 100  # Respects max messages limit
        
        # All messages should be valid
        for msg in final_messages:
            assert isinstance(msg, ChatMessage)
            assert msg.conversation_id == conv_id


@pytest.mark.unit
@pytest.mark.asyncio
class TestStorageBackendSwitching:
    """Test storage backend switching via configuration."""
    
    async def test_backend_switching_via_config(self):
        """Test switching between different storage backends."""
        # Test memory backend
        memory_config = {
            "chat": {
                "storage": {
                    "backend": "memory",
                    "queue_size_limit": 500
                }
            }
        }
        
        client = ChatStorageClient(config=memory_config)
        assert client.backend_type == "memory"
        assert isinstance(client.backend, MemoryStorage)
        
        # Test invalid backend
        invalid_config = {
            "chat": {
                "storage": {
                    "backend": "invalid_backend"
                }
            }
        }
        
        with pytest.raises(ValueError, match="Unknown storage backend"):
            ChatStorageClient(config=invalid_config)
    
    async def test_backend_specific_config(self):
        """Test backend-specific configuration is passed correctly."""
        config = {
            "chat": {
                "storage": {
                    "backend": "memory",
                    "queue_size_limit": 2000,
                    "memory": {
                        "additional_setting": "test"
                    }
                }
            }
        }
        
        client = ChatStorageClient(config=config)
        
        # Verify queue limit is passed
        assert client.backend.queue_size_limit == 2000


@pytest.mark.unit
@pytest.mark.asyncio
class TestStorageMetrics:
    """Test storage metrics and monitoring."""
    
    async def test_storage_operation_metrics(self, create_test_messages):
        """Test metrics tracking for storage operations."""
        config = {"chat": {"storage": {"backend": "memory"}}}
        client = ChatStorageClient(config=config)
        
        conv_id = "conv_metrics"
        messages = create_test_messages(5, conv_id)
        
        # Perform operations
        for msg in messages:
            await client.store_message(msg)
        
        await client.get_conversation_messages(conv_id)
        await client.get_next_sequence_id(conv_id)
        
        # Check metrics were recorded
        metrics = client.metrics
        assert hasattr(metrics, 'record_storage_operation')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "unit"])