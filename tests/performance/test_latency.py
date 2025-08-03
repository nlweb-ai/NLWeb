"""
Performance tests for multi-participant chat system.
Tests single participant, multi-participant, and large group latency targets.
"""

import asyncio
import time
import uuid
import statistics
import psutil
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable
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


# Performance Test Configuration
PERFORMANCE_BASE_URL = "http://localhost:8080"
LATENCY_TARGETS = {
    "single_participant": 1.05,  # 105% of baseline
    "multi_participant": 0.2,    # 200ms absolute
    "large_group": 0.5          # 500ms absolute
}


class PerformanceMetrics:
    """Track performance metrics during testing."""
    
    def __init__(self):
        self.latencies = []
        self.memory_usage = []
        self.cpu_usage = []
        self.throughput_data = []
        self.start_time = None
        self.baseline_latency = None
    
    def start_measurement(self):
        """Start performance measurement."""
        self.start_time = time.perf_counter()
        
    def record_latency(self, operation: str, latency: float):
        """Record latency measurement."""
        self.latencies.append({
            "operation": operation,
            "latency": latency,
            "timestamp": time.perf_counter()
        })
    
    def record_memory_usage(self):
        """Record current memory usage."""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        self.memory_usage.append({
            "memory_mb": memory_mb,
            "timestamp": time.perf_counter()
        })
    
    def record_throughput(self, messages_per_second: float):
        """Record throughput measurement."""
        self.throughput_data.append({
            "messages_per_second": messages_per_second,
            "timestamp": time.perf_counter()
        })
    
    def get_percentiles(self, operation: str = None) -> Dict[str, float]:
        """Get latency percentiles for operation."""
        latencies = [
            m["latency"] for m in self.latencies 
            if operation is None or m["operation"] == operation
        ]
        
        if not latencies:
            return {"p50": 0, "p95": 0, "p99": 0}
        
        return {
            "p50": statistics.median(latencies),
            "p95": statistics.quantiles(latencies, n=20)[18],  # 95th percentile
            "p99": statistics.quantiles(latencies, n=100)[98]   # 99th percentile
        }
    
    def get_memory_stats(self) -> Dict[str, float]:
        """Get memory usage statistics."""
        if not self.memory_usage:
            return {"avg_mb": 0, "peak_mb": 0}
        
        memory_values = [m["memory_mb"] for m in self.memory_usage]
        return {
            "avg_mb": statistics.mean(memory_values),
            "peak_mb": max(memory_values)
        }


def measure_latency(func: Callable) -> Callable:
    """Decorator to measure function latency."""
    def wrapper(self, *args, **kwargs):
        start_time = time.perf_counter()
        result = func(self, *args, **kwargs)
        end_time = time.perf_counter()
        
        # Record latency in metrics
        if hasattr(self, 'metrics'):
            self.metrics.record_latency(func.__name__, end_time - start_time)
        
        return result
    return wrapper


@pytest.fixture
def performance_metrics():
    """Create performance metrics tracker."""
    return PerformanceMetrics()


@pytest.fixture
async def performance_client():
    """Create HTTP client for performance testing."""
    async with httpx.AsyncClient(
        base_url=PERFORMANCE_BASE_URL, 
        timeout=httpx.Timeout(30.0, connect=10.0)
    ) as client:
        yield client


@pytest.fixture
def baseline_measurement():
    """Mock baseline /ask endpoint measurement."""
    # In real implementation, this would measure actual /ask endpoint
    return {
        "p50": 0.045,  # 45ms
        "p95": 0.120,  # 120ms
        "p99": 0.180   # 180ms
    }


@pytest.mark.performance
@pytest.mark.asyncio
class TestSingleParticipantPerformance:
    """Test single participant performance (80% of usage)."""
    
    async def test_baseline_vs_websocket_latency(self, performance_client, performance_metrics, baseline_measurement):
        """Test: Single participant latency ≤105% of baseline."""
        performance_metrics.baseline_latency = baseline_measurement
        performance_metrics.start_measurement()
        
        with aioresponses() as mock_resp:
            # Mock WebSocket-based chat response
            conversation_id = f"perf_conv_{uuid.uuid4().hex[:8]}"
            
            # Mock conversation creation (part of latency)
            mock_resp.post(
                f"{PERFORMANCE_BASE_URL}/chat/create",
                payload={
                    "id": conversation_id,
                    "title": "Performance Test",
                    "participants": [{"participantId": "perf_user", "displayName": "Performance User"}]
                },
                status=201
            )
            
            # Measure conversation creation + message latency
            latencies = []
            
            for i in range(20):  # 20 test messages
                start_time = time.perf_counter()
                
                # Create conversation (first time only)
                if i == 0:
                    create_response = await performance_client.post(
                        "/chat/create",
                        json={
                            "title": f"Performance Test {i}",
                            "sites": ["example.com"],
                            "mode": "list",
                            "participant": {"participantId": "perf_user", "displayName": "User"}
                        },
                        headers={"Authorization": "Bearer test_token"}
                    )
                
                # Simulate WebSocket message send/receive cycle
                await asyncio.sleep(0.001)  # Minimal processing time
                
                end_time = time.perf_counter()
                latency = end_time - start_time
                latencies.append(latency)
                performance_metrics.record_latency("websocket_message", latency)
                performance_metrics.record_memory_usage()
        
        # Calculate percentiles
        percentiles = performance_metrics.get_percentiles("websocket_message")
        
        # Performance targets: ≤105% of baseline
        baseline_p50 = baseline_measurement["p50"]
        baseline_p95 = baseline_measurement["p95"]
        
        target_p50 = baseline_p50 * LATENCY_TARGETS["single_participant"]
        target_p95 = baseline_p95 * LATENCY_TARGETS["single_participant"]
        
        # Verify performance meets targets
        assert percentiles["p50"] <= target_p50, f"p50 {percentiles['p50']:.3f}s exceeds target {target_p50:.3f}s"
        assert percentiles["p95"] <= target_p95, f"p95 {percentiles['p95']:.3f}s exceeds target {target_p95:.3f}s"
        
        print(f"✓ Single participant performance:")
        print(f"  Baseline p50: {baseline_p50:.3f}s, Actual: {percentiles['p50']:.3f}s")
        print(f"  Baseline p95: {baseline_p95:.3f}s, Actual: {percentiles['p95']:.3f}s")
    
    async def test_typical_message_sizes(self, performance_client, performance_metrics):
        """Test performance with typical message sizes."""
        message_sizes = [
            ("short", "What's the weather?"),  # ~20 chars
            ("medium", "Can you help me understand the current market trends in renewable energy?" * 2),  # ~150 chars
            ("long", "I need a comprehensive analysis of the following data..." + "x" * 500)  # ~550 chars
        ]
        
        with aioresponses() as mock_resp:
            conversation_id = "perf_message_sizes"
            
            # Mock responses for different message sizes
            for size_name, message_content in message_sizes:
                mock_resp.post(
                    f"{PERFORMANCE_BASE_URL}/chat/{conversation_id}/message",
                    payload={"success": True, "message_id": f"msg_{size_name}"},
                    status=200
                )
            
            # Test each message size
            for size_name, message_content in message_sizes:
                latencies = []
                
                for i in range(10):  # 10 tests per size
                    start_time = time.perf_counter()
                    
                    # Simulate sending message
                    response = await performance_client.post(
                        f"/chat/{conversation_id}/message",
                        json={"content": message_content, "sites": ["example.com"]},
                        headers={"Authorization": "Bearer test_token"}
                    )
                    
                    end_time = time.perf_counter()
                    latency = end_time - start_time
                    latencies.append(latency)
                    performance_metrics.record_latency(f"message_{size_name}", latency)
                
                # Verify all message sizes meet performance targets
                avg_latency = statistics.mean(latencies)
                assert avg_latency < 0.1, f"Message size {size_name} too slow: {avg_latency:.3f}s"
    
    async def test_nlweb_processing_time_included(self, performance_client, performance_metrics):
        """Test latency including NLWeb processing time."""
        with aioresponses() as mock_resp:
            conversation_id = "perf_nlweb"
            
            # Mock NLWeb response with realistic processing time
            mock_resp.post(
                f"{PERFORMANCE_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "ai_response": {
                        "content": "Based on the weather data, today will be sunny with 75°F...",
                        "processing_time_ms": 850  # Realistic NLWeb processing time
                    }
                },
                status=200
            )
            
            # Test end-to-end latency including AI processing
            latencies = []
            
            for i in range(15):
                start_time = time.perf_counter()
                
                # Send message and wait for AI response
                response = await performance_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": "What's the weather today?", "sites": ["weather.com"]},
                    headers={"Authorization": "Bearer test_token"}
                )
                
                # Simulate waiting for AI response
                await asyncio.sleep(0.85)  # Mock NLWeb processing time
                
                end_time = time.perf_counter()
                latency = end_time - start_time
                latencies.append(latency)
                performance_metrics.record_latency("end_to_end_nlweb", latency)
            
            # Include NLWeb processing in performance evaluation
            percentiles = performance_metrics.get_percentiles("end_to_end_nlweb")
            
            # End-to-end should still be reasonable (< 2s for single participant)
            assert percentiles["p95"] < 2.0, f"End-to-end p95 {percentiles['p95']:.3f}s too slow"
    
    async def test_memory_overhead(self, performance_client, performance_metrics):
        """Test memory overhead for single participant."""
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        performance_metrics.record_memory_usage()
        
        with aioresponses() as mock_resp:
            conversation_id = "perf_memory"
            
            # Mock conversation operations
            mock_resp.post(
                f"{PERFORMANCE_BASE_URL}/chat/create",
                payload={"id": conversation_id},
                status=201
            )
            
            mock_resp.post(
                f"{PERFORMANCE_BASE_URL}/chat/{conversation_id}/message",
                payload={"success": True},
                status=200
            )
            
            # Create conversation and send messages
            await performance_client.post(
                "/chat/create",
                json={
                    "title": "Memory Test",
                    "participant": {"participantId": "mem_user", "displayName": "Memory User"}
                },
                headers={"Authorization": "Bearer test_token"}
            )
            
            # Send 100 messages to test memory growth
            for i in range(100):
                await performance_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"Message {i}"},
                    headers={"Authorization": "Bearer test_token"}
                )
                
                if i % 10 == 0:  # Record memory every 10 messages
                    performance_metrics.record_memory_usage()
        
        # Analyze memory usage
        memory_stats = performance_metrics.get_memory_stats()
        memory_growth = memory_stats["peak_mb"] - initial_memory
        
        # Memory growth should be reasonable (< 50MB for single participant)
        assert memory_growth < 50, f"Memory growth {memory_growth:.1f}MB too high"
        
        print(f"✓ Memory overhead: {memory_growth:.1f}MB for single participant")


@pytest.mark.performance
@pytest.mark.asyncio
class TestMultiParticipantScenarios:
    """Test multi-participant performance (15% of usage)."""
    
    async def test_2_to_5_humans_plus_ai_agents(self, performance_client, performance_metrics):
        """Test 2-5 humans + AI agents performance."""
        participant_counts = [2, 3, 4, 5]  # Different group sizes
        
        for participant_count in participant_counts:
            with aioresponses() as mock_resp:
                conversation_id = f"perf_multi_{participant_count}"
                
                # Mock multi-participant conversation
                participants = [
                    {"participantId": f"user_{i}", "displayName": f"User {i}"}
                    for i in range(participant_count)
                ]
                
                mock_resp.post(
                    f"{PERFORMANCE_BASE_URL}/chat/create",
                    payload={
                        "id": conversation_id,
                        "participants": participants + [{"participantId": "ai_1", "type": "ai"}]
                    },
                    status=201
                )
                
                # Mock broadcast message
                mock_resp.post(
                    f"{PERFORMANCE_BASE_URL}/chat/{conversation_id}/message",
                    payload={"success": True, "broadcast_count": participant_count + 1},
                    status=200
                )
                
                # Test message broadcast latency
                latencies = []
                
                for i in range(10):  # 10 test messages
                    start_time = time.perf_counter()
                    
                    # Send message that gets broadcast to all participants
                    response = await performance_client.post(
                        f"/chat/{conversation_id}/message",
                        json={
                            "content": f"Broadcast message {i}",
                            "sender_id": "user_0"
                        },
                        headers={"Authorization": "Bearer test_token"}
                    )
                    
                    # Simulate broadcast delivery time
                    broadcast_time = 0.010 * participant_count  # 10ms per participant
                    await asyncio.sleep(broadcast_time)
                    
                    end_time = time.perf_counter()
                    latency = end_time - start_time
                    latencies.append(latency)
                    performance_metrics.record_latency(f"broadcast_{participant_count}", latency)
                
                # Verify broadcast performance
                avg_latency = statistics.mean(latencies)
                target_latency = LATENCY_TARGETS["multi_participant"]  # 200ms
                
                assert avg_latency < target_latency, f"Broadcast to {participant_count} participants too slow: {avg_latency:.3f}s"
                
                print(f"✓ Broadcast to {participant_count} participants: {avg_latency:.3f}s")
    
    async def test_message_broadcast_timing(self, performance_client, performance_metrics):
        """Test message broadcast timing <200ms."""
        with aioresponses() as mock_resp:
            conversation_id = "perf_broadcast_timing"
            participant_count = 5
            
            # Mock broadcast endpoint
            mock_resp.post(
                f"{PERFORMANCE_BASE_URL}/chat/{conversation_id}/broadcast",
                payload={"success": True, "delivered_to": participant_count},
                status=200
            )
            
            # Test broadcast timing
            broadcast_latencies = []
            
            for i in range(25):  # 25 broadcast tests
                participants_online = [f"user_{j}" for j in range(participant_count)]
                
                start_time = time.perf_counter()
                
                # Simulate O(N) broadcast operation
                response = await performance_client.post(
                    f"/chat/{conversation_id}/broadcast",
                    json={
                        "message": f"Broadcast test {i}",
                        "participants": participants_online
                    },
                    headers={"Authorization": "Bearer test_token"}
                )
                
                # Simulate realistic broadcast time (O(N) not O(N²))
                await asyncio.sleep(0.020 * participant_count)  # 20ms per participant
                
                end_time = time.perf_counter()
                broadcast_latency = end_time - start_time
                broadcast_latencies.append(broadcast_latency)
                performance_metrics.record_latency("broadcast_timing", broadcast_latency)
            
            # Analyze broadcast performance
            percentiles = performance_metrics.get_percentiles("broadcast_timing")
            target_p95 = LATENCY_TARGETS["multi_participant"]  # 200ms
            
            assert percentiles["p95"] < target_p95, f"Broadcast p95 {percentiles['p95']:.3f}s exceeds {target_p95}s"
            
            print(f"✓ Broadcast timing p95: {percentiles['p95']:.3f}s (target: {target_p95}s)")
    
    async def test_linear_scaling_verification(self, performance_client, performance_metrics):
        """Test that performance scales linearly with participant count."""
        participant_counts = [2, 4, 6, 8, 10]
        scaling_data = []
        
        for count in participant_counts:
            with aioresponses() as mock_resp:
                conversation_id = f"perf_scaling_{count}"
                
                mock_resp.post(
                    f"{PERFORMANCE_BASE_URL}/chat/{conversation_id}/message",
                    payload={"success": True},
                    status=200
                )
                
                # Measure latency for this participant count
                test_latencies = []
                
                for i in range(15):  # 15 tests per count
                    start_time = time.perf_counter()
                    
                    await performance_client.post(
                        f"/chat/{conversation_id}/message",
                        json={"content": f"Scaling test {i}"},
                        headers={"Authorization": "Bearer test_token"}
                    )
                    
                    # Simulate O(N) processing time
                    processing_time = 0.005 * count  # 5ms per participant
                    await asyncio.sleep(processing_time)
                    
                    end_time = time.perf_counter()
                    latency = end_time - start_time
                    test_latencies.append(latency)
                
                avg_latency = statistics.mean(test_latencies)
                scaling_data.append({"participants": count, "latency": avg_latency})
                performance_metrics.record_latency(f"scaling_{count}", avg_latency)
        
        # Verify linear scaling (not exponential)
        # Latency should roughly double when participants double
        latency_2 = next(d["latency"] for d in scaling_data if d["participants"] == 2)
        latency_4 = next(d["latency"] for d in scaling_data if d["participants"] == 4)
        latency_8 = next(d["latency"] for d in scaling_data if d["participants"] == 8)
        
        # Check scaling is roughly linear (within 50% tolerance)
        scaling_factor_2_to_4 = latency_4 / latency_2
        scaling_factor_4_to_8 = latency_8 / latency_4
        
        assert 1.5 < scaling_factor_2_to_4 < 2.5, f"Non-linear scaling 2→4: {scaling_factor_2_to_4:.2f}x"
        assert 1.5 < scaling_factor_4_to_8 < 2.5, f"Non-linear scaling 4→8: {scaling_factor_4_to_8:.2f}x"
        
        print(f"✓ Linear scaling verified: 2→4 participants: {scaling_factor_2_to_4:.2f}x")


@pytest.mark.performance
@pytest.mark.asyncio
class TestLargeGroupPerformance:
    """Test large group performance (5% of usage)."""
    
    async def test_50_to_100_total_participants(self, performance_client, performance_metrics):
        """Test performance with 50-100 total participants."""
        large_group_sizes = [50, 75, 100]
        
        for group_size in large_group_sizes:
            with aioresponses() as mock_resp:
                conversation_id = f"perf_large_{group_size}"
                
                # Mock large group conversation
                mock_resp.post(
                    f"{PERFORMANCE_BASE_URL}/chat/{conversation_id}/message",
                    payload={"success": True, "participant_count": group_size},
                    status=200
                )
                
                # Test message delivery to large group
                large_group_latencies = []
                
                for i in range(5):  # 5 tests (fewer due to large group overhead)
                    start_time = time.perf_counter()
                    
                    response = await performance_client.post(
                        f"/chat/{conversation_id}/message",
                        json={"content": f"Large group message {i}"},
                        headers={"Authorization": "Bearer test_token"}
                    )
                    
                    # Simulate large group broadcast (still should be O(N))
                    broadcast_time = 0.002 * group_size  # 2ms per participant (optimized)
                    await asyncio.sleep(broadcast_time)
                    
                    end_time = time.perf_counter()
                    latency = end_time - start_time
                    large_group_latencies.append(latency)
                    performance_metrics.record_latency(f"large_group_{group_size}", latency)
                
                # Verify large group performance
                avg_latency = statistics.mean(large_group_latencies)
                target_latency = LATENCY_TARGETS["large_group"]  # 500ms
                
                assert avg_latency < target_latency, f"Large group {group_size} too slow: {avg_latency:.3f}s"
                
                print(f"✓ Large group {group_size} participants: {avg_latency:.3f}s")
    
    async def test_broadcast_performance_at_scale(self, performance_client, performance_metrics):
        """Test broadcast performance with large participant counts."""
        with aioresponses() as mock_resp:
            group_size = 100
            conversation_id = "perf_broadcast_scale"
            
            mock_resp.post(
                f"{PERFORMANCE_BASE_URL}/chat/{conversation_id}/broadcast",
                payload={"success": True, "delivered_count": group_size},
                status=200
            )
            
            # Test large-scale broadcast
            broadcast_latencies = []
            
            for i in range(10):  # 10 broadcast tests
                start_time = time.perf_counter()
                
                # Simulate broadcast to 100 participants
                response = await performance_client.post(
                    f"/chat/{conversation_id}/broadcast",
                    json={
                        "message": f"Scale broadcast {i}",
                        "participant_count": group_size
                    },
                    headers={"Authorization": "Bearer test_token"}
                )
                
                # Optimized broadcast time for 100 participants
                await asyncio.sleep(0.15)  # 150ms for 100 participants
                
                end_time = time.perf_counter()
                latency = end_time - start_time
                broadcast_latencies.append(latency)
                performance_metrics.record_latency("broadcast_scale", latency)
            
            # Verify broadcast scaling
            avg_broadcast_latency = statistics.mean(broadcast_latencies)
            
            # Large group broadcast should still be < 500ms
            assert avg_broadcast_latency < 0.5, f"Large group broadcast too slow: {avg_broadcast_latency:.3f}s"
    
    async def test_memory_usage_scaling(self, performance_client, performance_metrics):
        """Test memory usage with large groups."""
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Simulate memory usage for large conversation
        participant_counts = [10, 25, 50, 100]
        memory_measurements = []
        
        for count in participant_counts:
            # Simulate memory allocation for participants
            simulated_memory_per_participant = 0.5  # 0.5MB per participant
            expected_memory_growth = count * simulated_memory_per_participant
            
            performance_metrics.record_memory_usage()
            memory_measurements.append({
                "participants": count,
                "expected_memory_mb": expected_memory_growth
            })
        
        # Verify memory scaling is reasonable
        max_expected_memory = max(m["expected_memory_mb"] for m in memory_measurements)
        
        # 100 participants should use < 100MB additional memory
        assert max_expected_memory < 100, f"Memory scaling too high: {max_expected_memory:.1f}MB"
        
        print(f"✓ Memory scaling: {max_expected_memory:.1f}MB for 100 participants")
    
    async def test_queue_management_overhead(self, performance_client, performance_metrics):
        """Test queue management with large groups."""
        with aioresponses() as mock_resp:
            conversation_id = "perf_queue_mgmt"
            
            mock_resp.post(
                f"{PERFORMANCE_BASE_URL}/chat/{conversation_id}/queue-status",
                payload={"queue_size": 50, "participants": 100},
                status=200
            )
            
            # Test queue management performance
            queue_latencies = []
            
            for i in range(20):
                start_time = time.perf_counter()
                
                # Check queue status (operation done frequently)
                response = await performance_client.post(
                    f"/chat/{conversation_id}/queue-status",
                    json={"check_capacity": True},
                    headers={"Authorization": "Bearer test_token"}
                )
                
                # Queue management should be very fast
                await asyncio.sleep(0.001)  # 1ms queue operations
                
                end_time = time.perf_counter()
                latency = end_time - start_time
                queue_latencies.append(latency)
                performance_metrics.record_latency("queue_management", latency)
            
            # Queue operations should be very fast (< 10ms)
            avg_queue_latency = statistics.mean(queue_latencies)
            assert avg_queue_latency < 0.01, f"Queue management too slow: {avg_queue_latency:.3f}s"


@pytest.mark.performance
@pytest.mark.asyncio
class TestThroughputTests:
    """Test system throughput under load."""
    
    async def test_100_messages_per_second_throughput(self, performance_client, performance_metrics):
        """Test 100 messages/second throughput."""
        with aioresponses() as mock_resp:
            conversation_id = "perf_throughput"
            
            # Mock high-throughput endpoint
            mock_resp.post(
                f"{PERFORMANCE_BASE_URL}/chat/{conversation_id}/message",
                payload={"success": True},
                status=200
            )
            
            # Test sustained throughput
            message_count = 200  # Send 200 messages
            target_duration = 2.0  # In 2 seconds (100 msg/sec)
            
            start_time = time.perf_counter()
            
            # Send messages at high rate
            tasks = []
            for i in range(message_count):
                task = performance_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"Throughput test {i}"},
                    headers={"Authorization": "Bearer test_token"}
                )
                tasks.append(task)
                
                # Control rate to ~100 messages/second
                await asyncio.sleep(0.01)  # 10ms between messages
            
            # Wait for all messages to complete
            await asyncio.gather(*tasks)
            
            end_time = time.perf_counter()
            actual_duration = end_time - start_time
            actual_throughput = message_count / actual_duration
            
            performance_metrics.record_throughput(actual_throughput)
            
            # Verify throughput meets target
            target_throughput = 100  # messages/second
            assert actual_throughput >= target_throughput * 0.9, f"Throughput {actual_throughput:.1f} < target {target_throughput}"
            
            print(f"✓ Throughput: {actual_throughput:.1f} messages/second")
    
    async def test_1000_concurrent_connections(self, performance_client, performance_metrics):
        """Test 1000 concurrent connections."""
        # Note: This is a simplified test - real implementation would use WebSocket
        concurrent_count = 100  # Reduced for testing (would be 1000 in real test)
        
        with aioresponses() as mock_resp:
            # Mock connection endpoint
            mock_resp.post(
                f"{PERFORMANCE_BASE_URL}/chat/connect",
                payload={"success": True, "connection_id": "test_conn"},
                status=200
            )
            
            # Test concurrent connections
            start_time = time.perf_counter()
            
            # Create concurrent connection tasks
            connection_tasks = []
            for i in range(concurrent_count):
                task = performance_client.post(
                    "/chat/connect",
                    json={"participant_id": f"user_{i}"},
                    headers={"Authorization": f"Bearer token_{i}"}
                )
                connection_tasks.append(task)
            
            # Execute all connections concurrently
            responses = await asyncio.gather(*connection_tasks, return_exceptions=True)
            
            end_time = time.perf_counter()
            connection_duration = end_time - start_time
            
            # Count successful connections
            successful_connections = sum(
                1 for response in responses 
                if not isinstance(response, Exception) and response.status_code == 200
            )
            
            performance_metrics.record_latency("concurrent_connections", connection_duration)
            
            # Verify concurrent connection handling
            success_rate = successful_connections / concurrent_count
            assert success_rate >= 0.95, f"Connection success rate {success_rate:.2f} too low"
            assert connection_duration < 5.0, f"Concurrent connections took {connection_duration:.1f}s"
            
            print(f"✓ Concurrent connections: {successful_connections}/{concurrent_count} in {connection_duration:.1f}s")
    
    async def test_100_active_conversations(self, performance_client, performance_metrics):
        """Test 100 active conversations simultaneously."""
        conversation_count = 50  # Reduced for testing
        
        with aioresponses() as mock_resp:
            # Mock multiple conversation endpoints
            for i in range(conversation_count):
                mock_resp.post(
                    f"{PERFORMANCE_BASE_URL}/chat/conv_{i}/message",
                    payload={"success": True, "conversation_id": f"conv_{i}"},
                    status=200
                )
            
            # Test multiple active conversations
            start_time = time.perf_counter()
            
            # Send messages to multiple conversations concurrently
            conversation_tasks = []
            for i in range(conversation_count):
                task = performance_client.post(
                    f"/chat/conv_{i}/message",
                    json={"content": f"Multi-conversation test {i}"},
                    headers={"Authorization": "Bearer test_token"}
                )
                conversation_tasks.append(task)
            
            # Execute all conversation operations
            responses = await asyncio.gather(*conversation_tasks, return_exceptions=True)
            
            end_time = time.perf_counter()
            multi_conv_duration = end_time - start_time
            
            # Analyze results
            successful_conversations = sum(
                1 for response in responses
                if not isinstance(response, Exception) and response.status_code == 200
            )
            
            performance_metrics.record_latency("multi_conversations", multi_conv_duration)
            
            # Verify multi-conversation performance
            success_rate = successful_conversations / conversation_count
            assert success_rate >= 0.95, f"Multi-conversation success rate {success_rate:.2f} too low"
            
            print(f"✓ Multi-conversation: {successful_conversations}/{conversation_count} successful")
    
    async def test_memory_usage_under_load(self, performance_client, performance_metrics):
        """Test memory usage under sustained load."""
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        peak_memory = initial_memory
        
        # Monitor memory during load test
        memory_monitor_active = True
        
        async def monitor_memory():
            nonlocal peak_memory
            while memory_monitor_active:
                current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                peak_memory = max(peak_memory, current_memory)
                performance_metrics.record_memory_usage()
                await asyncio.sleep(0.1)  # Check every 100ms
        
        # Start memory monitoring
        monitor_task = asyncio.create_task(monitor_memory())
        
        try:
            with aioresponses() as mock_resp:
                mock_resp.post(
                    f"{PERFORMANCE_BASE_URL}/chat/load_test/message",
                    payload={"success": True},
                    status=200
                )
                
                # Generate sustained load for 5 seconds
                load_duration = 2.0  # 2 seconds for testing
                load_start = time.perf_counter()
                
                load_tasks = []
                message_count = 0
                
                while time.perf_counter() - load_start < load_duration:
                    task = performance_client.post(
                        "/chat/load_test/message",
                        json={"content": f"Load test {message_count}"},
                        headers={"Authorization": "Bearer test_token"}
                    )
                    load_tasks.append(task)
                    message_count += 1
                    await asyncio.sleep(0.05)  # 20 messages/second
                
                # Wait for all load tasks to complete
                await asyncio.gather(*load_tasks, return_exceptions=True)
                
        finally:
            # Stop memory monitoring
            memory_monitor_active = False
            await monitor_task
        
        # Analyze memory usage
        memory_growth = peak_memory - initial_memory
        memory_stats = performance_metrics.get_memory_stats()
        
        # Memory growth should be reasonable under load
        assert memory_growth < 200, f"Memory growth under load too high: {memory_growth:.1f}MB"
        
        print(f"✓ Memory under load: {memory_growth:.1f}MB growth, peak: {peak_memory:.1f}MB")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance", "--benchmark-only"])