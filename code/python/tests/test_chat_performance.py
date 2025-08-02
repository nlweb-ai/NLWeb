"""
Performance tests for chat system.
Compare against /ask endpoint baseline and verify multi-human scenarios.
"""

import pytest
import asyncio
import time
import psutil
import aiohttp
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import json
import statistics

from chat.websocket import WebSocketManager, WebSocketConnection
from chat.conversation import ConversationManager
from chat.participants import HumanParticipant, NLWebParticipant, ParticipantConfig
from chat.storage import ChatStorageClient
from chat.schemas import ChatMessage, MessageType, ParticipantType
from chat_storage_providers.memory_storage import MemoryStorageProvider


class PerformanceMetrics:
    """Track performance metrics during tests"""
    
    def __init__(self):
        self.latencies = []
        self.memory_usage = []
        self.start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
    
    def record_latency(self, latency_ms: float):
        self.latencies.append(latency_ms)
    
    def record_memory(self):
        current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        self.memory_usage.append(current_memory - self.start_memory)
    
    def get_stats(self):
        return {
            'avg_latency_ms': statistics.mean(self.latencies) if self.latencies else 0,
            'p95_latency_ms': statistics.quantiles(self.latencies, n=20)[18] if len(self.latencies) > 1 else 0,
            'max_latency_ms': max(self.latencies) if self.latencies else 0,
            'memory_delta_mb': max(self.memory_usage) if self.memory_usage else 0,
            'total_messages': len(self.latencies)
        }


class TestChatPerformance:
    """Performance tests for chat system"""
    
    @pytest.fixture
    async def chat_system(self):
        """Create a complete chat system for testing"""
        # Storage
        storage_providers = {'memory': MemoryStorageProvider()}
        storage_config = {
            'default_provider': 'memory',
            'cache_enabled': True,
            'cache_ttl': 300,
            'cache_max_size': 1000
        }
        storage = ChatStorageClient(providers=storage_providers, config=storage_config)
        
        # Conversation manager
        conv_config = {
            'single_mode_timeout': 100,
            'multi_mode_timeout': 2000,
            'queue_size_limit': 1000,
            'max_participants': 100
        }
        conv_manager = ConversationManager(conv_config)
        conv_manager.storage = storage
        
        # WebSocket manager
        ws_manager = WebSocketManager(max_connections_per_participant=1)
        
        # Set up broadcast callback
        async def broadcast_callback(conv_id: str, msg: dict):
            await ws_manager.broadcast_to_conversation(conv_id, msg)
        
        conv_manager.broadcast_callback = broadcast_callback
        
        yield {
            'storage': storage,
            'conv_manager': conv_manager,
            'ws_manager': ws_manager
        }
        
        # Cleanup
        await conv_manager.shutdown()
        await ws_manager.shutdown()
    
    @pytest.fixture
    async def ask_endpoint_baseline(self):
        """Get baseline performance from /ask endpoint"""
        # Mock /ask endpoint behavior
        async def mock_ask_handler(query: str) -> tuple[str, float]:
            start_time = time.time()
            
            # Simulate NLWeb processing
            await asyncio.sleep(0.1)  # 100ms simulated processing
            
            response = f"Response to: {query}"
            latency_ms = (time.time() - start_time) * 1000
            
            return response, latency_ms
        
        return mock_ask_handler
    
    @pytest.mark.asyncio
    async def test_single_user_chat_latency(self, chat_system, ask_endpoint_baseline):
        """Test: Single user chat latency vs /ask endpoint latency"""
        metrics = PerformanceMetrics()
        
        # Create conversation with 1 human + 1 NLWeb
        conv_id = "conv_single_test"
        
        # Add human participant
        human = HumanParticipant("user_123", "Test User")
        chat_system['conv_manager'].add_participant(conv_id, human)
        
        # Add NLWeb participant with mock handler
        async def mock_nlweb_handler(query_params, chunk_capture):
            # Simulate NLWeb processing delay
            await asyncio.sleep(0.1)
            await chunk_capture.write_stream("Test response", end_response=True)
        
        config = ParticipantConfig(timeout=20)
        nlweb = NLWebParticipant(mock_nlweb_handler, config)
        chat_system['conv_manager'].add_participant(conv_id, nlweb)
        
        # Test 100 messages
        for i in range(100):
            start_time = time.time()
            
            message = ChatMessage(
                message_id=f"msg_{i}",
                conversation_id=conv_id,
                sequence_id=0,
                sender_id="user_123",
                sender_name="Test User",
                content=f"Test message {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            
            # Process message
            await chat_system['conv_manager'].process_message(message)
            
            # Record latency
            latency_ms = (time.time() - start_time) * 1000
            metrics.record_latency(latency_ms)
            
            # Record memory periodically
            if i % 10 == 0:
                metrics.record_memory()
        
        # Get baseline performance
        baseline_latencies = []
        for i in range(100):
            _, latency = await ask_endpoint_baseline(f"Test query {i}")
            baseline_latencies.append(latency)
        
        # Compare results
        chat_stats = metrics.get_stats()
        baseline_avg = statistics.mean(baseline_latencies)
        
        print(f"\nSingle User Performance:")
        print(f"Chat avg latency: {chat_stats['avg_latency_ms']:.2f}ms")
        print(f"Baseline avg latency: {baseline_avg:.2f}ms")
        print(f"Performance ratio: {chat_stats['avg_latency_ms'] / baseline_avg:.2%}")
        print(f"Memory usage: {chat_stats['memory_delta_mb']:.2f}MB")
        
        # Assert performance is within 105% of baseline
        assert chat_stats['avg_latency_ms'] <= baseline_avg * 1.05, \
            f"Chat latency {chat_stats['avg_latency_ms']:.2f}ms exceeds 105% of baseline {baseline_avg:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_multi_human_performance(self, chat_system):
        """Test: Multi-human scenarios: 2-5 humans + NLWeb performance"""
        
        for num_humans in [2, 3, 5]:
            metrics = PerformanceMetrics()
            conv_id = f"conv_multi_{num_humans}"
            
            # Add human participants
            humans = []
            for i in range(num_humans):
                human = HumanParticipant(f"user_{i}", f"User {i}")
                chat_system['conv_manager'].add_participant(conv_id, human)
                humans.append(human)
            
            # Add NLWeb
            async def mock_nlweb_handler(query_params, chunk_capture):
                await asyncio.sleep(0.05)  # Faster response for multi-human
                await chunk_capture.write_stream("Multi response", end_response=True)
            
            config = ParticipantConfig(timeout=20)
            nlweb = NLWebParticipant(mock_nlweb_handler, config)
            chat_system['conv_manager'].add_participant(conv_id, nlweb)
            
            # Simulate conversation with messages from different humans
            for round in range(20):
                for i, human in enumerate(humans):
                    start_time = time.time()
                    
                    message = ChatMessage(
                        message_id=f"msg_{round}_{i}",
                        conversation_id=conv_id,
                        sequence_id=0,
                        sender_id=f"user_{i}",
                        sender_name=f"User {i}",
                        content=f"Message from user {i} in round {round}",
                        message_type=MessageType.TEXT,
                        timestamp=datetime.utcnow()
                    )
                    
                    await chat_system['conv_manager'].process_message(message)
                    
                    latency_ms = (time.time() - start_time) * 1000
                    metrics.record_latency(latency_ms)
                
                metrics.record_memory()
            
            stats = metrics.get_stats()
            print(f"\n{num_humans} Humans Performance:")
            print(f"Avg latency: {stats['avg_latency_ms']:.2f}ms")
            print(f"P95 latency: {stats['p95_latency_ms']:.2f}ms")
            print(f"Memory usage: {stats['memory_delta_mb']:.2f}MB")
            
            # Multi-human can be slightly slower but must feel real-time (<200ms avg)
            assert stats['avg_latency_ms'] < 200, \
                f"Multi-human latency {stats['avg_latency_ms']:.2f}ms exceeds real-time threshold"
    
    @pytest.mark.asyncio
    async def test_websocket_overhead(self, chat_system):
        """Test: WebSocket overhead measurement"""
        metrics = PerformanceMetrics()
        conv_id = "conv_ws_overhead"
        
        # Create mock WebSocket connections
        mock_websockets = []
        for i in range(5):
            mock_ws = AsyncMock()
            mock_ws.send_json = AsyncMock()
            mock_ws.close = AsyncMock()
            
            conn = WebSocketConnection(
                websocket=mock_ws,
                participant_id=f"user_{i}",
                conversation_id=conv_id
            )
            
            await chat_system['ws_manager'].add_connection(conv_id, conn)
            mock_websockets.append(mock_ws)
        
        # Measure broadcast overhead
        for i in range(100):
            start_time = time.time()
            
            message = {
                'type': 'message',
                'message': {
                    'message_id': f'msg_{i}',
                    'content': f'Broadcast message {i}',
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
            
            await chat_system['ws_manager'].broadcast_to_conversation(conv_id, message)
            
            # Wait for all sends to complete
            await asyncio.sleep(0.001)
            
            latency_ms = (time.time() - start_time) * 1000
            metrics.record_latency(latency_ms)
        
        stats = metrics.get_stats()
        print(f"\nWebSocket Overhead:")
        print(f"Avg broadcast time (5 connections): {stats['avg_latency_ms']:.2f}ms")
        print(f"Per-connection overhead: {stats['avg_latency_ms'] / 5:.2f}ms")
        
        # WebSocket overhead should be minimal (<5ms per connection)
        assert stats['avg_latency_ms'] / 5 < 5, \
            "WebSocket overhead exceeds 5ms per connection"
    
    @pytest.mark.asyncio
    async def test_queue_limit_behavior(self, chat_system):
        """Test: Queue limit behavior under load"""
        conv_id = "conv_queue_test"
        chat_system['conv_manager'].queue_size_limit = 10  # Small limit for testing
        
        # Add participants
        human = HumanParticipant("user_123", "Test User")
        chat_system['conv_manager'].add_participant(conv_id, human)
        
        # Slow NLWeb to cause queue buildup
        async def slow_nlweb_handler(query_params, chunk_capture):
            await asyncio.sleep(1.0)  # Very slow
            await chunk_capture.write_stream("Slow response", end_response=True)
        
        config = ParticipantConfig(timeout=20)
        nlweb = NLWebParticipant(slow_nlweb_handler, config)
        chat_system['conv_manager'].add_participant(conv_id, nlweb)
        
        # Send messages rapidly
        queue_full_count = 0
        successful_count = 0
        
        for i in range(15):
            message = ChatMessage(
                message_id=f"msg_{i}",
                conversation_id=conv_id,
                sequence_id=0,
                sender_id="user_123",
                sender_name="Test User",
                content=f"Rapid message {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            
            try:
                await chat_system['conv_manager'].process_message(message)
                successful_count += 1
            except Exception as e:
                if "QueueFullError" in str(type(e)):
                    queue_full_count += 1
        
        print(f"\nQueue Limit Behavior:")
        print(f"Successful messages: {successful_count}")
        print(f"Queue full errors: {queue_full_count}")
        
        # Should have some queue full errors
        assert queue_full_count > 0, "No queue full errors raised despite rapid sending"
        assert successful_count <= 10, "More messages processed than queue limit"
    
    @pytest.mark.asyncio
    async def test_broadcast_timing_many_participants(self, chat_system):
        """Test: Message broadcast timing with 10+ participants"""
        metrics = PerformanceMetrics()
        conv_id = "conv_broadcast_test"
        
        # Add 15 participants (12 humans + 3 NLWeb)
        for i in range(12):
            human = HumanParticipant(f"user_{i}", f"User {i}")
            chat_system['conv_manager'].add_participant(conv_id, human)
        
        for i in range(3):
            async def mock_handler(query_params, chunk_capture):
                await asyncio.sleep(0.01)
                await chunk_capture.write_stream(f"AI response {i}", end_response=True)
            
            config = ParticipantConfig(timeout=20)
            nlweb = NLWebParticipant(mock_handler, config)
            chat_system['conv_manager'].add_participant(conv_id, nlweb)
        
        # Measure broadcast timing
        for i in range(50):
            start_time = time.time()
            
            message = ChatMessage(
                message_id=f"msg_{i}",
                conversation_id=conv_id,
                sequence_id=0,
                sender_id="user_0",
                sender_name="User 0",
                content=f"Broadcast test {i}",
                message_type=MessageType.TEXT,
                timestamp=datetime.utcnow()
            )
            
            # This should broadcast to 14 other participants
            await chat_system['conv_manager'].process_message(message)
            
            latency_ms = (time.time() - start_time) * 1000
            metrics.record_latency(latency_ms)
        
        stats = metrics.get_stats()
        print(f"\nBroadcast Timing (15 participants):")
        print(f"Avg broadcast time: {stats['avg_latency_ms']:.2f}ms")
        print(f"P95 broadcast time: {stats['p95_latency_ms']:.2f}ms")
        
        # Even with 15 participants, broadcast should be fast (<100ms avg)
        assert stats['avg_latency_ms'] < 100, \
            f"Broadcast to 15 participants too slow: {stats['avg_latency_ms']:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_memory_usage_comparison(self, chat_system):
        """Test: Memory usage comparison between chat and baseline"""
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Create 10 conversations with varying participants
        for i in range(10):
            conv_id = f"conv_mem_{i}"
            
            # Add 2-5 humans per conversation
            for j in range(2 + i % 4):
                human = HumanParticipant(f"user_{i}_{j}", f"User {i}-{j}")
                chat_system['conv_manager'].add_participant(conv_id, human)
            
            # Add NLWeb
            async def mock_handler(query_params, chunk_capture):
                await chunk_capture.write_stream("Response", end_response=True)
            
            config = ParticipantConfig(timeout=20)
            nlweb = NLWebParticipant(mock_handler, config)
            chat_system['conv_manager'].add_participant(conv_id, nlweb)
            
            # Send 100 messages per conversation
            for k in range(100):
                message = ChatMessage(
                    message_id=f"msg_{i}_{k}",
                    conversation_id=conv_id,
                    sequence_id=0,
                    sender_id=f"user_{i}_0",
                    sender_name=f"User {i}-0",
                    content=f"Message {k} in conversation {i}",
                    message_type=MessageType.TEXT,
                    timestamp=datetime.utcnow()
                )
                await chat_system['conv_manager'].process_message(message)
        
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_used = final_memory - initial_memory
        
        print(f"\nMemory Usage:")
        print(f"Initial: {initial_memory:.2f}MB")
        print(f"Final: {final_memory:.2f}MB")
        print(f"Used: {memory_used:.2f}MB")
        print(f"Per conversation: {memory_used / 10:.2f}MB")
        print(f"Per message: {memory_used / 1000:.3f}MB")
        
        # Memory usage should be reasonable (<100MB for 1000 messages)
        assert memory_used < 100, f"Excessive memory usage: {memory_used:.2f}MB for 1000 messages"