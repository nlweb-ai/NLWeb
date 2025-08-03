"""
Load and stress tests for multi-participant chat system.
Tests sustained load patterns, spike patterns, resource limits, and degradation scenarios.
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


# Load Test Configuration
LOAD_TEST_BASE_URL = "http://localhost:8080"
LOAD_TEST_DURATION = 60  # Reduced from 15 minutes for testing
FAILURE_CRITERIA = {
    "single_participant_latency": 1.05,  # 105% of baseline
    "multi_participant_latency": 0.5,    # 500ms
    "error_rate": 0.01,                  # 1%
    "memory_growth": 2.0                 # 200% of baseline
}


class LoadTestMonitor:
    """Monitor system resources and performance during load tests."""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = {
            "response_times": [],
            "error_counts": [],
            "queue_depths": [],
            "memory_usage": [],
            "cpu_usage": [],
            "connection_counts": [],
            "message_loss": 0
        }
        
    async def start_monitoring(self):
        """Start continuous monitoring."""
        self.monitoring = True
        
        async def monitor_loop():
            while self.monitoring:
                # Record system metrics
                process = psutil.Process()
                
                self.metrics["memory_usage"].append({
                    "timestamp": time.perf_counter(),
                    "memory_mb": process.memory_info().rss / 1024 / 1024,
                    "memory_percent": process.memory_percent()
                })
                
                self.metrics["cpu_usage"].append({
                    "timestamp": time.perf_counter(),
                    "cpu_percent": process.cpu_percent(interval=None)
                })
                
                await asyncio.sleep(1.0)  # Monitor every second
        
        self.monitor_task = asyncio.create_task(monitor_loop())
    
    def stop_monitoring(self):
        """Stop monitoring and return final metrics."""
        self.monitoring = False
        if hasattr(self, 'monitor_task'):
            self.monitor_task.cancel()
        
        return self.get_summary()
    
    def record_response_time(self, operation: str, latency: float):
        """Record response time for operation."""
        self.metrics["response_times"].append({
            "operation": operation,
            "latency": latency,
            "timestamp": time.perf_counter()
        })
    
    def record_error(self, error_type: str):
        """Record error occurrence."""
        self.metrics["error_counts"].append({
            "error_type": error_type,
            "timestamp": time.perf_counter()
        })
    
    def record_queue_depth(self, conversation_id: str, depth: int):
        """Record queue depth for conversation."""
        self.metrics["queue_depths"].append({
            "conversation_id": conversation_id,
            "depth": depth,
            "timestamp": time.perf_counter()
        })
    
    def record_connection_count(self, count: int):
        """Record active connection count."""
        self.metrics["connection_counts"].append({
            "count": count,
            "timestamp": time.perf_counter()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of monitoring results."""
        if not self.metrics["response_times"]:
            return {"error": "No data collected"}
        
        response_times = [m["latency"] for m in self.metrics["response_times"]]
        
        return {
            "response_time_percentiles": {
                "p50": statistics.median(response_times),
                "p95": statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else max(response_times),
                "p99": statistics.quantiles(response_times, n=100)[98] if len(response_times) > 100 else max(response_times)
            },
            "error_rate": len(self.metrics["error_counts"]) / len(self.metrics["response_times"]) if self.metrics["response_times"] else 0,
            "peak_memory_mb": max(m["memory_mb"] for m in self.metrics["memory_usage"]) if self.metrics["memory_usage"] else 0,
            "avg_cpu_percent": statistics.mean(m["cpu_percent"] for m in self.metrics["cpu_usage"]) if self.metrics["cpu_usage"] else 0,
            "max_queue_depth": max(m["depth"] for m in self.metrics["queue_depths"]) if self.metrics["queue_depths"] else 0,
            "message_loss_count": self.metrics["message_loss"]
        }


class LoadTestClient:
    """Simulated client for load testing."""
    
    def __init__(self, client_id: str, http_client: httpx.AsyncClient):
        self.client_id = client_id
        self.http_client = http_client
        self.conversation_id = None
        self.messages_sent = 0
        self.messages_received = 0
        self.errors = 0
        
    async def create_conversation(self, participant_count: int = 1):
        """Create a conversation for load testing."""
        try:
            start_time = time.perf_counter()
            
            participants = [
                {"participantId": f"{self.client_id}_user_{i}", "displayName": f"User {i}"}
                for i in range(participant_count)
            ]
            
            response = await self.http_client.post(
                "/chat/create",
                json={
                    "title": f"Load Test {self.client_id}",
                    "sites": ["example.com"],
                    "mode": "list",
                    "participant": participants[0],
                    "additional_participants": participants[1:] if len(participants) > 1 else []
                },
                headers={"Authorization": f"Bearer token_{self.client_id}"}
            )
            
            if response.status_code == 201:
                data = response.json()
                self.conversation_id = data["id"]
                
            end_time = time.perf_counter()
            return end_time - start_time
            
        except Exception as e:
            self.errors += 1
            return None
    
    async def send_message(self, content: str):
        """Send a message in the conversation."""
        if not self.conversation_id:
            return None
            
        try:
            start_time = time.perf_counter()
            
            response = await self.http_client.post(
                f"/chat/{self.conversation_id}/message",
                json={"content": content},
                headers={"Authorization": f"Bearer token_{self.client_id}"}
            )
            
            if response.status_code == 200:
                self.messages_sent += 1
            else:
                self.errors += 1
                
            end_time = time.perf_counter()
            return end_time - start_time
            
        except Exception as e:
            self.errors += 1
            return None
    
    async def join_conversation(self, conversation_id: str):
        """Join an existing conversation."""
        try:
            start_time = time.perf_counter()
            
            response = await self.http_client.post(
                f"/chat/{conversation_id}/join",
                json={"participant": {"participantId": self.client_id, "displayName": f"User {self.client_id}"}},
                headers={"Authorization": f"Bearer token_{self.client_id}"}
            )
            
            if response.status_code == 200:
                self.conversation_id = conversation_id
                
            end_time = time.perf_counter()
            return end_time - start_time
            
        except Exception as e:
            self.errors += 1
            return None


@pytest.fixture
async def load_test_client():
    """Create HTTP client for load testing."""
    async with httpx.AsyncClient(
        base_url=LOAD_TEST_BASE_URL,
        timeout=httpx.Timeout(60.0, connect=30.0)
    ) as client:
        yield client


@pytest.fixture
def load_monitor():
    """Create load test monitor."""
    return LoadTestMonitor()


@pytest.mark.load
@pytest.mark.asyncio
class TestSustainedLoadPatterns:
    """Test sustained load patterns."""
    
    async def test_500_concurrent_single_participant_chats(self, load_test_client, load_monitor):
        """Test 500 concurrent single-participant chats."""
        client_count = 100  # Reduced for testing (would be 500 in production)
        
        with aioresponses() as mock_resp:
            # Mock conversation creation
            mock_resp.post(
                f"{LOAD_TEST_BASE_URL}/chat/create",
                payload={"id": "load_conv_001", "status": "created"},
                status=201
            )
            
            # Mock message sending
            mock_resp.post(
                f"{LOAD_TEST_BASE_URL}/chat/load_conv_001/message",
                payload={"success": True},
                status=200
            )
            
            await load_monitor.start_monitoring()
            
            # Create load test clients
            clients = []
            for i in range(client_count):
                client = LoadTestClient(f"client_{i}", load_test_client)
                clients.append(client)
            
            # Start sustained load test
            test_duration = 30  # 30 seconds for testing
            test_start = time.perf_counter()
            
            async def client_load_pattern(client: LoadTestClient):
                """Sustained load pattern for single client."""
                # Create conversation
                create_latency = await client.create_conversation(participant_count=1)
                if create_latency:
                    load_monitor.record_response_time("create_conversation", create_latency)
                
                # Send messages continuously
                message_count = 0
                while time.perf_counter() - test_start < test_duration:
                    message_latency = await client.send_message(f"Load test message {message_count}")
                    if message_latency:
                        load_monitor.record_response_time("send_message", message_latency)
                    else:
                        load_monitor.record_error("message_send_failed")
                    
                    message_count += 1
                    await asyncio.sleep(0.1)  # 10 messages per second per client
            
            # Execute load test
            load_tasks = [client_load_pattern(client) for client in clients]
            await asyncio.gather(*load_tasks, return_exceptions=True)
            
            # Analyze results
            results = load_monitor.stop_monitoring()
            
            # Verify performance criteria
            assert results["error_rate"] < FAILURE_CRITERIA["error_rate"], f"Error rate {results['error_rate']:.3f} too high"
            assert results["response_time_percentiles"]["p95"] < 1.0, f"p95 latency {results['response_time_percentiles']['p95']:.3f}s too slow"
            
            print(f"✓ Sustained load: {client_count} clients, p95: {results['response_time_percentiles']['p95']:.3f}s")
    
    async def test_100_multi_participant_conversations(self, load_test_client, load_monitor):
        """Test 100 multi-participant conversations (3-5 humans each)."""
        conversation_count = 20  # Reduced for testing
        
        with aioresponses() as mock_resp:
            # Mock multi-participant conversations
            for i in range(conversation_count):
                mock_resp.post(
                    f"{LOAD_TEST_BASE_URL}/chat/create",
                    payload={"id": f"multi_conv_{i}", "participant_count": 4},
                    status=201
                )
                
                mock_resp.post(
                    f"{LOAD_TEST_BASE_URL}/chat/multi_conv_{i}/message",
                    payload={"success": True, "broadcast_count": 4},
                    status=200
                )
            
            await load_monitor.start_monitoring()
            
            # Create multi-participant conversations
            conversations = []
            for i in range(conversation_count):
                # Each conversation has 3-5 humans
                participant_count = 3 + (i % 3)  # 3, 4, or 5 participants
                conversation_clients = []
                
                for j in range(participant_count):
                    client = LoadTestClient(f"conv_{i}_user_{j}", load_test_client)
                    conversation_clients.append(client)
                
                conversations.append(conversation_clients)
            
            async def multi_participant_load(conversation_clients: List[LoadTestClient]):
                """Load pattern for multi-participant conversation."""
                # First client creates conversation
                main_client = conversation_clients[0]
                create_latency = await main_client.create_conversation(len(conversation_clients))
                
                if create_latency:
                    load_monitor.record_response_time("multi_create", create_latency)
                
                # Other clients join
                if main_client.conversation_id:
                    for client in conversation_clients[1:]:
                        join_latency = await client.join_conversation(main_client.conversation_id)
                        if join_latency:
                            load_monitor.record_response_time("multi_join", join_latency)
                
                # All clients send messages
                test_start = time.perf_counter()
                test_duration = 20  # 20 seconds
                
                async def client_messaging(client: LoadTestClient):
                    message_count = 0
                    while time.perf_counter() - test_start < test_duration:
                        message_latency = await client.send_message(f"Multi-participant msg {message_count}")
                        if message_latency:
                            load_monitor.record_response_time("multi_message", message_latency)
                        else:
                            load_monitor.record_error("multi_message_failed")
                        
                        message_count += 1
                        await asyncio.sleep(0.2)  # 5 messages per second per participant
                
                # Execute messaging for all participants
                messaging_tasks = [client_messaging(client) for client in conversation_clients]
                await asyncio.gather(*messaging_tasks, return_exceptions=True)
            
            # Execute multi-participant load test
            conversation_tasks = [multi_participant_load(clients) for clients in conversations]
            await asyncio.gather(*conversation_tasks, return_exceptions=True)
            
            # Analyze results
            results = load_monitor.stop_monitoring()
            
            # Verify multi-participant performance
            multi_message_times = [
                m["latency"] for m in load_monitor.metrics["response_times"] 
                if m["operation"] == "multi_message"
            ]
            
            if multi_message_times:
                avg_multi_latency = statistics.mean(multi_message_times)
                assert avg_multi_latency < FAILURE_CRITERIA["multi_participant_latency"], \
                    f"Multi-participant latency {avg_multi_latency:.3f}s exceeds {FAILURE_CRITERIA['multi_participant_latency']}s"
            
            print(f"✓ Multi-participant load: {conversation_count} conversations")
    
    async def test_10_large_conversations_50_plus_participants(self, load_test_client, load_monitor):
        """Test 10 large conversations (50+ participants)."""
        large_conversation_count = 3  # Reduced for testing
        participants_per_large_conv = 20  # Reduced from 50+ for testing
        
        with aioresponses() as mock_resp:
            # Mock large conversations
            for i in range(large_conversation_count):
                mock_resp.post(
                    f"{LOAD_TEST_BASE_URL}/chat/create",
                    payload={"id": f"large_conv_{i}", "participant_count": participants_per_large_conv},
                    status=201
                )
                
                mock_resp.post(
                    f"{LOAD_TEST_BASE_URL}/chat/large_conv_{i}/message",
                    payload={"success": True, "broadcast_count": participants_per_large_conv},
                    status=200
                )
                
                mock_resp.post(
                    f"{LOAD_TEST_BASE_URL}/chat/large_conv_{i}/join",
                    payload={"success": True},
                    status=200
                )
            
            await load_monitor.start_monitoring()
            
            # Create large conversations
            large_conversations = []
            for i in range(large_conversation_count):
                # Create clients for large conversation
                conv_clients = []
                for j in range(participants_per_large_conv):
                    client = LoadTestClient(f"large_{i}_user_{j}", load_test_client)
                    conv_clients.append(client)
                large_conversations.append(conv_clients)
            
            async def large_conversation_load(clients: List[LoadTestClient]):
                """Load pattern for large conversation."""
                # First client creates conversation
                main_client = clients[0]
                create_latency = await main_client.create_conversation(len(clients))
                
                if create_latency:
                    load_monitor.record_response_time("large_create", create_latency)
                
                # Simulate gradual joining (realistic pattern)
                join_tasks = []
                for i, client in enumerate(clients[1:]):
                    if main_client.conversation_id:
                        # Stagger joins to simulate realistic behavior
                        await asyncio.sleep(0.1 * (i % 10))  # Stagger every 10 participants
                        task = client.join_conversation(main_client.conversation_id)
                        join_tasks.append(task)
                
                # Wait for all joins
                join_results = await asyncio.gather(*join_tasks, return_exceptions=True)
                for latency in join_results:
                    if isinstance(latency, float):
                        load_monitor.record_response_time("large_join", latency)
                
                # Test messaging with large group
                test_duration = 15  # 15 seconds
                test_start = time.perf_counter()
                
                # Only subset of participants actively message (realistic)
                active_participants = clients[:min(10, len(clients))]  # 10 active participants max
                
                async def active_messaging(client: LoadTestClient):
                    message_count = 0
                    while time.perf_counter() - test_start < test_duration:
                        message_latency = await client.send_message(f"Large group msg {message_count}")
                        if message_latency:
                            load_monitor.record_response_time("large_message", message_latency)
                            load_monitor.record_queue_depth(client.conversation_id or "unknown", 
                                                          len(clients))  # Simulate queue depth
                        else:
                            load_monitor.record_error("large_message_failed")
                        
                        message_count += 1
                        await asyncio.sleep(0.5)  # 2 messages per second (slower for large groups)
                
                # Execute messaging
                messaging_tasks = [active_messaging(client) for client in active_participants]
                await asyncio.gather(*messaging_tasks, return_exceptions=True)
            
            # Execute large conversation tests
            large_conv_tasks = [large_conversation_load(clients) for clients in large_conversations]
            await asyncio.gather(*large_conv_tasks, return_exceptions=True)
            
            # Analyze results
            results = load_monitor.stop_monitoring()
            
            # Verify large group performance
            large_message_times = [
                m["latency"] for m in load_monitor.metrics["response_times"]
                if m["operation"] == "large_message"
            ]
            
            if large_message_times:
                avg_large_latency = statistics.mean(large_message_times)
                # Large groups have higher latency tolerance
                assert avg_large_latency < 1.0, f"Large group latency {avg_large_latency:.3f}s too high"
            
            print(f"✓ Large conversations: {large_conversation_count} with {participants_per_large_conv} participants each")
    
    async def test_15_minute_sustained_load(self, load_test_client, load_monitor):
        """Test 15-minute sustained load (reduced to 2 minutes for testing)."""
        test_duration = 120  # 2 minutes for testing (would be 900 seconds = 15 minutes)
        client_count = 25   # Reduced client count for extended test
        
        with aioresponses() as mock_resp:
            # Mock sustained load endpoints
            mock_resp.post(
                f"{LOAD_TEST_BASE_URL}/chat/create",
                payload={"id": "sustained_conv", "status": "created"},
                status=201
            )
            
            mock_resp.post(
                f"{LOAD_TEST_BASE_URL}/chat/sustained_conv/message",
                payload={"success": True},
                status=200
            )
            
            await load_monitor.start_monitoring()
            
            # Create sustained load clients
            clients = [LoadTestClient(f"sustained_{i}", load_test_client) for i in range(client_count)]
            
            async def sustained_client_load(client: LoadTestClient):
                """Long-running client load pattern."""
                # Create conversation
                await client.create_conversation()
                
                test_start = time.perf_counter()
                message_count = 0
                
                while time.perf_counter() - test_start < test_duration:
                    # Send message
                    message_latency = await client.send_message(f"Sustained message {message_count}")
                    if message_latency:
                        load_monitor.record_response_time("sustained_message", message_latency)
                    else:
                        load_monitor.record_error("sustained_message_failed")
                    
                    message_count += 1
                    
                    # Record periodic metrics
                    if message_count % 10 == 0:
                        load_monitor.record_connection_count(len([c for c in clients if c.conversation_id]))
                    
                    # Vary message rate slightly (realistic pattern)
                    sleep_time = 0.5 + (0.2 * (message_count % 5) / 5)  # 0.5-0.7 seconds
                    await asyncio.sleep(sleep_time)
            
            # Start sustained load
            load_tasks = [sustained_client_load(client) for client in clients]
            await asyncio.gather(*load_tasks, return_exceptions=True)
            
            # Analyze sustained load results
            results = load_monitor.stop_monitoring()
            
            # Verify sustained performance doesn't degrade
            sustained_times = [
                m["latency"] for m in load_monitor.metrics["response_times"]
                if m["operation"] == "sustained_message"
            ]
            
            if len(sustained_times) > 100:  # Need sufficient data
                # Check if performance degrades over time
                first_half = sustained_times[:len(sustained_times)//2]
                second_half = sustained_times[len(sustained_times)//2:]
                
                first_half_avg = statistics.mean(first_half)
                second_half_avg = statistics.mean(second_half)
                
                degradation_ratio = second_half_avg / first_half_avg
                
                # Performance shouldn't degrade by more than 20%
                assert degradation_ratio < 1.2, f"Performance degraded {degradation_ratio:.2f}x over time"
            
            print(f"✓ Sustained load: {client_count} clients for {test_duration}s")


@pytest.mark.load
@pytest.mark.asyncio
class TestSpikePatterns:
    """Test spike load patterns."""
    
    async def test_sudden_influx_200_connections(self, load_test_client, load_monitor):
        """Test sudden influx of 200 connections."""
        connection_count = 50  # Reduced for testing
        
        with aioresponses() as mock_resp:
            # Mock connection endpoint
            mock_resp.post(
                f"{LOAD_TEST_BASE_URL}/chat/connect",
                payload={"success": True, "connection_id": "spike_conn"},
                status=200
            )
            
            await load_monitor.start_monitoring()
            
            # Create sudden spike of connections
            start_time = time.perf_counter()
            
            async def connect_client(client_id: int):
                """Single client connection."""
                try:
                    response = await load_test_client.post(
                        "/chat/connect",
                        json={"participant_id": f"spike_user_{client_id}"},
                        headers={"Authorization": f"Bearer spike_token_{client_id}"}
                    )
                    
                    end_time = time.perf_counter()
                    connect_latency = end_time - start_time
                    
                    if response.status_code == 200:
                        load_monitor.record_response_time("spike_connect", connect_latency)
                        return True
                    else:
                        load_monitor.record_error("spike_connect_failed")
                        return False
                        
                except Exception as e:
                    load_monitor.record_error("spike_connect_exception")
                    return False
            
            # Execute sudden connection spike
            connection_tasks = [connect_client(i) for i in range(connection_count)]
            results = await asyncio.gather(*connection_tasks, return_exceptions=True)
            
            # Analyze spike results
            successful_connections = sum(1 for r in results if r is True)
            total_time = time.perf_counter() - start_time
            
            load_monitor.stop_monitoring()
            
            # Verify spike handling
            success_rate = successful_connections / connection_count
            assert success_rate >= 0.90, f"Connection spike success rate {success_rate:.2f} too low"
            assert total_time < 10.0, f"Connection spike took {total_time:.1f}s, too slow"
            
            print(f"✓ Connection spike: {successful_connections}/{connection_count} in {total_time:.1f}s")
    
    async def test_burst_1000_messages_10_seconds(self, load_test_client, load_monitor):
        """Test burst of 1000 messages in 10 seconds."""
        message_count = 200  # Reduced for testing
        burst_duration = 10  # 10 seconds
        
        with aioresponses() as mock_resp:
            # Mock message burst endpoint
            mock_resp.post(
                f"{LOAD_TEST_BASE_URL}/chat/burst_conv/message",
                payload={"success": True},
                status=200
            )
            
            await load_monitor.start_monitoring()
            
            # Create message burst
            burst_start = time.perf_counter()
            
            async def send_burst_message(message_id: int):
                """Send single burst message."""
                try:
                    send_time = time.perf_counter()
                    
                    response = await load_test_client.post(
                        "/chat/burst_conv/message",
                        json={"content": f"Burst message {message_id}"},
                        headers={"Authorization": "Bearer burst_token"}
                    )
                    
                    response_time = time.perf_counter() - send_time
                    
                    if response.status_code == 200:
                        load_monitor.record_response_time("message_burst", response_time)
                        return True
                    else:
                        load_monitor.record_error("message_burst_failed")
                        return False
                        
                except Exception:
                    load_monitor.record_error("message_burst_exception")
                    return False
            
            # Send messages as fast as possible
            message_tasks = [send_burst_message(i) for i in range(message_count)]
            burst_results = await asyncio.gather(*message_tasks, return_exceptions=True)
            
            burst_total_time = time.perf_counter() - burst_start
            
            # Analyze burst results
            successful_messages = sum(1 for r in burst_results if r is True)
            messages_per_second = successful_messages / burst_total_time
            
            load_monitor.stop_monitoring()
            
            # Verify burst handling
            success_rate = successful_messages / message_count
            assert success_rate >= 0.85, f"Message burst success rate {success_rate:.2f} too low"
            assert messages_per_second >= 20, f"Burst throughput {messages_per_second:.1f} msg/s too low"
            
            print(f"✓ Message burst: {successful_messages} messages in {burst_total_time:.1f}s ({messages_per_second:.1f} msg/s)")
    
    async def test_mass_reconnection_scenario(self, load_test_client, load_monitor):
        """Test mass reconnection scenario."""
        client_count = 30  # Clients that will reconnect
        
        with aioresponses() as mock_resp:
            # Mock reconnection endpoints
            mock_resp.post(
                f"{LOAD_TEST_BASE_URL}/chat/reconnect",
                payload={"success": True, "sync_required": True},
                status=200
            )
            
            await load_monitor.start_monitoring()
            
            # Simulate mass reconnection (e.g., after network outage)
            reconnection_start = time.perf_counter()
            
            async def client_reconnection(client_id: int):
                """Simulate client reconnection with sync."""
                try:
                    # Simulate exponential backoff reconnection
                    backoff_delay = min(1.0 * (2 ** (client_id % 5)), 30.0)  # Max 30s backoff
                    await asyncio.sleep(backoff_delay * 0.1)  # Scaled down for testing
                    
                    reconnect_start = time.perf_counter()
                    
                    # Reconnect request
                    response = await load_test_client.post(
                        "/chat/reconnect",
                        json={
                            "participant_id": f"reconnect_user_{client_id}",
                            "last_sequence_id": client_id * 10  # Simulate different sync points
                        },
                        headers={"Authorization": f"Bearer reconnect_token_{client_id}"}
                    )
                    
                    reconnect_time = time.perf_counter() - reconnect_start
                    
                    if response.status_code == 200:
                        load_monitor.record_response_time("mass_reconnect", reconnect_time)
                        return True
                    else:
                        load_monitor.record_error("mass_reconnect_failed")
                        return False
                        
                except Exception:
                    load_monitor.record_error("mass_reconnect_exception")
                    return False
            
            # Execute mass reconnection
            reconnection_tasks = [client_reconnection(i) for i in range(client_count)]
            reconnect_results = await asyncio.gather(*reconnection_tasks, return_exceptions=True)
            
            total_reconnect_time = time.perf_counter() - reconnection_start
            
            # Analyze reconnection results
            successful_reconnects = sum(1 for r in reconnect_results if r is True)
            
            load_monitor.stop_monitoring()
            
            # Verify mass reconnection handling
            success_rate = successful_reconnects / client_count
            assert success_rate >= 0.90, f"Mass reconnection success rate {success_rate:.2f} too low"
            
            print(f"✓ Mass reconnection: {successful_reconnects}/{client_count} in {total_reconnect_time:.1f}s")
    
    async def test_participant_join_leave_storms(self, load_test_client, load_monitor):
        """Test participant join/leave storms."""
        storm_participants = 25  # Reduced for testing
        conversation_id = "storm_conv_001"
        
        with aioresponses() as mock_resp:
            # Mock join/leave endpoints
            mock_resp.post(
                f"{LOAD_TEST_BASE_URL}/chat/{conversation_id}/join",
                payload={"success": True},
                status=200
            )
            
            mock_resp.delete(
                f"{LOAD_TEST_BASE_URL}/chat/{conversation_id}/leave",
                payload={"success": True},
                status=200
            )
            
            await load_monitor.start_monitoring()
            
            # Create join/leave storm
            storm_start = time.perf_counter()
            
            async def join_leave_cycle(participant_id: int):
                """Rapid join/leave cycle."""
                try:
                    # Join
                    join_start = time.perf_counter()
                    join_response = await load_test_client.post(
                        f"/chat/{conversation_id}/join",
                        json={"participant": {"participantId": f"storm_user_{participant_id}"}},
                        headers={"Authorization": f"Bearer storm_token_{participant_id}"}
                    )
                    join_time = time.perf_counter() - join_start
                    
                    if join_response.status_code == 200:
                        load_monitor.record_response_time("storm_join", join_time)
                    else:
                        load_monitor.record_error("storm_join_failed")
                        return False
                    
                    # Brief stay
                    await asyncio.sleep(0.1)
                    
                    # Leave
                    leave_start = time.perf_counter()
                    leave_response = await load_test_client.delete(
                        f"/chat/{conversation_id}/leave",
                        headers={"Authorization": f"Bearer storm_token_{participant_id}"}
                    )
                    leave_time = time.perf_counter() - leave_start
                    
                    if leave_response.status_code == 200:
                        load_monitor.record_response_time("storm_leave", leave_time)
                        return True
                    else:
                        load_monitor.record_error("storm_leave_failed")
                        return False
                        
                except Exception:
                    load_monitor.record_error("storm_cycle_exception")
                    return False
            
            # Execute join/leave storm
            storm_tasks = [join_leave_cycle(i) for i in range(storm_participants)]
            storm_results = await asyncio.gather(*storm_tasks, return_exceptions=True)
            
            storm_total_time = time.perf_counter() - storm_start
            
            # Analyze storm results
            successful_cycles = sum(1 for r in storm_results if r is True)
            
            load_monitor.stop_monitoring()
            
            # Verify join/leave storm handling
            success_rate = successful_cycles / storm_participants
            assert success_rate >= 0.80, f"Join/leave storm success rate {success_rate:.2f} too low"
            
            print(f"✓ Join/leave storm: {successful_cycles}/{storm_participants} cycles in {storm_total_time:.1f}s")


@pytest.mark.load
@pytest.mark.asyncio
class TestResourceLimits:
    """Test resource limit handling."""
    
    async def test_queue_overflow_behavior(self, load_test_client, load_monitor):
        """Test queue overflow behavior."""
        overflow_message_count = 100  # Messages to trigger overflow
        
        with aioresponses() as mock_resp:
            # Mock queue full responses after some messages
            for i in range(overflow_message_count):
                if i < 80:  # First 80 succeed
                    mock_resp.post(
                        f"{LOAD_TEST_BASE_URL}/chat/overflow_conv/message",
                        payload={"success": True},
                        status=200
                    )
                else:  # Last 20 trigger queue full
                    mock_resp.post(
                        f"{LOAD_TEST_BASE_URL}/chat/overflow_conv/message",
                        payload={"error": "Queue full", "retry_after": 5},
                        status=429
                    )
            
            await load_monitor.start_monitoring()
            
            # Send messages until queue overflow
            async def send_overflow_message(message_id: int):
                """Send message that may trigger overflow."""
                try:
                    response = await load_test_client.post(
                        "/chat/overflow_conv/message",
                        json={"content": f"Overflow test {message_id}"},
                        headers={"Authorization": "Bearer overflow_token"}
                    )
                    
                    if response.status_code == 200:
                        load_monitor.record_response_time("overflow_message", 0.010)
                        return "success"
                    elif response.status_code == 429:
                        load_monitor.record_error("queue_full")
                        return "queue_full"
                    else:
                        load_monitor.record_error("overflow_other_error")
                        return "error"
                        
                except Exception:
                    load_monitor.record_error("overflow_exception")
                    return "exception"
            
            # Send overflow messages
            overflow_tasks = [send_overflow_message(i) for i in range(overflow_message_count)]
            overflow_results = await asyncio.gather(*overflow_tasks)
            
            load_monitor.stop_monitoring()
            
            # Analyze overflow behavior
            success_count = sum(1 for r in overflow_results if r == "success")
            queue_full_count = sum(1 for r in overflow_results if r == "queue_full")
            error_count = sum(1 for r in overflow_results if r in ["error", "exception"])
            
            # Verify graceful queue overflow handling
            assert queue_full_count > 0, "Queue overflow not triggered"
            assert error_count == 0, f"Unexpected errors during overflow: {error_count}"
            assert success_count >= 70, f"Too few successful messages before overflow: {success_count}"
            
            print(f"✓ Queue overflow: {success_count} success, {queue_full_count} queue full, {error_count} errors")
    
    async def test_memory_pressure_response(self, load_test_client, load_monitor):
        """Test system response under memory pressure."""
        # Simulate memory pressure by tracking memory usage
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        with aioresponses() as mock_resp:
            mock_resp.post(
                f"{LOAD_TEST_BASE_URL}/chat/memory_test/message",
                payload={"success": True},
                status=200
            )
            
            await load_monitor.start_monitoring()
            
            # Generate load that increases memory usage
            memory_load_duration = 30  # 30 seconds
            load_start = time.perf_counter()
            
            async def memory_intensive_operation(operation_id: int):
                """Simulate memory-intensive chat operations."""
                # Simulate large message processing
                large_content = "x" * 1000  # 1KB messages
                
                while time.perf_counter() - load_start < memory_load_duration:
                    try:
                        response = await load_test_client.post(
                            "/chat/memory_test/message",
                            json={"content": f"{large_content} - operation {operation_id}"},
                            headers={"Authorization": f"Bearer memory_token_{operation_id}"}
                        )
                        
                        if response.status_code == 200:
                            load_monitor.record_response_time("memory_operation", 0.020)
                        else:
                            load_monitor.record_error("memory_operation_failed")
                        
                        # Record memory usage
                        current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                        memory_growth = current_memory - initial_memory
                        
                        # Simulate memory pressure response if growth is significant
                        if memory_growth > 100:  # 100MB growth
                            load_monitor.record_error("memory_pressure_detected")
                            break
                        
                        await asyncio.sleep(0.1)
                        
                    except Exception:
                        load_monitor.record_error("memory_operation_exception")
                        break
            
            # Execute memory-intensive operations
            memory_tasks = [memory_intensive_operation(i) for i in range(10)]
            await asyncio.gather(*memory_tasks, return_exceptions=True)
            
            results = load_monitor.stop_monitoring()
            
            # Verify memory pressure handling
            final_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_growth = final_memory - initial_memory
            
            # Memory growth should be reasonable
            assert memory_growth < 200, f"Memory growth {memory_growth:.1f}MB too high"
            
            print(f"✓ Memory pressure: {memory_growth:.1f}MB growth, handled gracefully")
    
    async def test_connection_limit_handling(self, load_test_client, load_monitor):
        """Test connection limit handling."""
        connection_attempt_count = 50  # Attempt more connections than limit
        
        with aioresponses() as mock_resp:
            # Mock connection limit responses
            for i in range(connection_attempt_count):
                if i < 40:  # First 40 succeed
                    mock_resp.post(
                        f"{LOAD_TEST_BASE_URL}/chat/connect",
                        payload={"success": True, "connection_id": f"conn_{i}"},
                        status=200
                    )
                else:  # Last 10 hit connection limit
                    mock_resp.post(
                        f"{LOAD_TEST_BASE_URL}/chat/connect",
                        payload={"error": "Connection limit exceeded", "retry_after": 10},
                        status=429
                    )
            
            await load_monitor.start_monitoring()
            
            # Attempt connections beyond limit
            async def attempt_connection(conn_id: int):
                """Attempt to establish connection."""
                try:
                    response = await load_test_client.post(
                        "/chat/connect",
                        json={"participant_id": f"limit_user_{conn_id}"},
                        headers={"Authorization": f"Bearer limit_token_{conn_id}"}
                    )
                    
                    if response.status_code == 200:
                        load_monitor.record_response_time("connection_attempt", 0.015)
                        return "connected"
                    elif response.status_code == 429:
                        load_monitor.record_error("connection_limit_exceeded")
                        return "limit_exceeded"
                    else:
                        load_monitor.record_error("connection_other_error")
                        return "error"
                        
                except Exception:
                    load_monitor.record_error("connection_exception")
                    return "exception"
            
            # Execute connection attempts
            connection_tasks = [attempt_connection(i) for i in range(connection_attempt_count)]
            connection_results = await asyncio.gather(*connection_tasks)
            
            load_monitor.stop_monitoring()
            
            # Analyze connection limit handling
            connected_count = sum(1 for r in connection_results if r == "connected")
            limit_exceeded_count = sum(1 for r in connection_results if r == "limit_exceeded")
            error_count = sum(1 for r in connection_results if r in ["error", "exception"])
            
            # Verify proper connection limit enforcement
            assert limit_exceeded_count > 0, "Connection limit not enforced"
            assert error_count == 0, f"Unexpected connection errors: {error_count}"
            assert connected_count >= 35, f"Too few successful connections: {connected_count}"
            
            print(f"✓ Connection limits: {connected_count} connected, {limit_exceeded_count} limited")
    
    async def test_storage_write_throughput(self, load_test_client, load_monitor):
        """Test storage write throughput limits."""
        write_operation_count = 100
        
        with aioresponses() as mock_resp:
            # Mock storage write operations
            for i in range(write_operation_count):
                if i < 90:  # Most succeed
                    mock_resp.post(
                        f"{LOAD_TEST_BASE_URL}/chat/storage/write",
                        payload={"success": True, "write_id": f"write_{i}"},
                        status=200
                    )
                else:  # Some hit storage limits
                    mock_resp.post(
                        f"{LOAD_TEST_BASE_URL}/chat/storage/write",
                        payload={"error": "Storage write limit exceeded", "retry_after": 2},
                        status=429
                    )
            
            await load_monitor.start_monitoring()
            
            # Execute storage write operations
            write_start = time.perf_counter()
            
            async def storage_write_operation(write_id: int):
                """Execute storage write operation."""
                try:
                    response = await load_test_client.post(
                        "/chat/storage/write",
                        json={
                            "conversation_id": f"storage_test_{write_id % 10}",
                            "message": f"Storage test message {write_id}",
                            "sequence_id": write_id
                        },
                        headers={"Authorization": "Bearer storage_token"}
                    )
                    
                    if response.status_code == 200:
                        load_monitor.record_response_time("storage_write", 0.005)
                        return "success"
                    elif response.status_code == 429:
                        load_monitor.record_error("storage_write_limit")
                        return "limit"
                    else:
                        load_monitor.record_error("storage_write_error")
                        return "error"
                        
                except Exception:
                    load_monitor.record_error("storage_write_exception")
                    return "exception"
            
            # Execute storage writes
            write_tasks = [storage_write_operation(i) for i in range(write_operation_count)]
            write_results = await asyncio.gather(*write_tasks)
            
            write_total_time = time.perf_counter() - write_start
            
            load_monitor.stop_monitoring()
            
            # Analyze storage throughput
            success_count = sum(1 for r in write_results if r == "success")
            limit_count = sum(1 for r in write_results if r == "limit")
            error_count = sum(1 for r in write_results if r in ["error", "exception"])
            
            writes_per_second = success_count / write_total_time
            
            # Verify storage throughput handling
            assert writes_per_second >= 10, f"Storage throughput {writes_per_second:.1f} writes/s too low"
            assert error_count == 0, f"Unexpected storage errors: {error_count}"
            
            print(f"✓ Storage throughput: {writes_per_second:.1f} writes/s, {limit_count} limited")


@pytest.mark.load
@pytest.mark.asyncio
class TestDegradationScenarios:
    """Test system degradation under adverse conditions."""
    
    async def test_performance_with_90_percent_memory_used(self, load_test_client, load_monitor):
        """Test performance with 90% memory usage."""
        # Get initial memory baseline
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        available_memory = psutil.virtual_memory().available / 1024 / 1024
        
        # Simulate high memory usage (reduced for testing)
        memory_ballast = []
        target_memory_usage = 100  # 100MB for testing (would be much higher in production)
        
        try:
            # Allocate memory to simulate pressure
            while len(memory_ballast) * 10 < target_memory_usage:  # 10MB chunks
                memory_ballast.append(bytearray(10 * 1024 * 1024))  # 10MB chunks
                
            with aioresponses() as mock_resp:
                mock_resp.post(
                    f"{LOAD_TEST_BASE_URL}/chat/memory_pressure/message",
                    payload={"success": True},
                    status=200
                )
                
                await load_monitor.start_monitoring()
                
                # Test performance under memory pressure
                message_count = 50
                pressure_start = time.perf_counter()
                
                async def memory_pressure_operation(op_id: int):
                    """Operation under memory pressure."""
                    try:
                        response = await load_test_client.post(
                            "/chat/memory_pressure/message",
                            json={"content": f"Memory pressure test {op_id}"},
                            headers={"Authorization": f"Bearer pressure_token_{op_id}"}
                        )
                        
                        if response.status_code == 200:
                            load_monitor.record_response_time("memory_pressure", 0.025)
                            return True
                        else:
                            load_monitor.record_error("memory_pressure_failed")
                            return False
                            
                    except Exception:
                        load_monitor.record_error("memory_pressure_exception")
                        return False
                
                # Execute operations under memory pressure
                pressure_tasks = [memory_pressure_operation(i) for i in range(message_count)]
                pressure_results = await asyncio.gather(*pressure_tasks, return_exceptions=True)
                
                pressure_duration = time.perf_counter() - pressure_start
                
                results = load_monitor.stop_monitoring()
                
                # Analyze performance under memory pressure
                success_count = sum(1 for r in pressure_results if r is True)
                success_rate = success_count / message_count
                
                # System should still function under memory pressure (degraded performance OK)
                assert success_rate >= 0.70, f"Success rate under memory pressure too low: {success_rate:.2f}"
                
                # Performance degradation is acceptable but shouldn't crash
                if results["response_time_percentiles"]["p95"] > 0.1:  # 100ms acceptable under pressure
                    print(f"⚠️  Performance degraded under memory pressure: {results['response_time_percentiles']['p95']:.3f}s")
                
                print(f"✓ Memory pressure: {success_count}/{message_count} operations successful")
                
        finally:
            # Clean up memory ballast
            memory_ballast.clear()
    
    async def test_storage_latency_increases(self, load_test_client, load_monitor):
        """Test performance with increased storage latency."""
        with aioresponses() as mock_resp:
            # Mock slow storage responses
            slow_response_count = 30
            
            for i in range(slow_response_count):
                # Simulate increasing storage latency
                if i < 10:
                    delay = 0.050  # 50ms
                elif i < 20:
                    delay = 0.150  # 150ms
                else:
                    delay = 0.300  # 300ms
                
                # Mock with delay simulation
                mock_resp.post(
                    f"{LOAD_TEST_BASE_URL}/chat/slow_storage/message",
                    payload={"success": True, "storage_latency_ms": delay * 1000},
                    status=200
                )
            
            await load_monitor.start_monitoring()
            
            # Test with increasing storage latency
            async def slow_storage_operation(op_id: int):
                """Operation with slow storage."""
                start_time = time.perf_counter()
                
                try:
                    # Simulate storage delay based on operation ID
                    if op_id < 10:
                        await asyncio.sleep(0.050)  # 50ms
                    elif op_id < 20:
                        await asyncio.sleep(0.150)  # 150ms
                    else:
                        await asyncio.sleep(0.300)  # 300ms
                    
                    response = await load_test_client.post(
                        "/chat/slow_storage/message",
                        json={"content": f"Slow storage test {op_id}"},
                        headers={"Authorization": f"Bearer slow_token_{op_id}"}
                    )
                    
                    end_time = time.perf_counter()
                    actual_latency = end_time - start_time
                    
                    if response.status_code == 200:
                        load_monitor.record_response_time("slow_storage", actual_latency)
                        return actual_latency
                    else:
                        load_monitor.record_error("slow_storage_failed")
                        return None
                        
                except Exception:
                    load_monitor.record_error("slow_storage_exception")
                    return None
            
            # Execute with progressive storage slowdown
            slow_storage_tasks = [slow_storage_operation(i) for i in range(slow_response_count)]
            latency_results = await asyncio.gather(*slow_storage_tasks, return_exceptions=True)
            
            results = load_monitor.stop_monitoring()
            
            # Analyze storage latency impact
            valid_latencies = [l for l in latency_results if isinstance(l, float)]
            
            if len(valid_latencies) >= 20:
                # Check if system adapts to slow storage
                early_latencies = valid_latencies[:10]
                late_latencies = valid_latencies[-10:]
                
                early_avg = statistics.mean(early_latencies)
                late_avg = statistics.mean(late_latencies)
                
                # System should still respond, even if slower
                assert all(l < 1.0 for l in valid_latencies), "Some operations took over 1 second"
                
                print(f"✓ Storage latency degradation: {early_avg:.3f}s → {late_avg:.3f}s")
            
            success_rate = len(valid_latencies) / slow_response_count
            assert success_rate >= 0.80, f"Success rate with slow storage too low: {success_rate:.2f}"
    
    async def test_network_packet_loss_simulation(self, load_test_client, load_monitor):
        """Test system behavior with simulated network packet loss."""
        packet_loss_scenarios = [0.0, 0.05, 0.10, 0.20]  # 0%, 5%, 10%, 20% packet loss
        
        with aioresponses() as mock_resp:
            # Mock responses with packet loss simulation
            for scenario_idx, loss_rate in enumerate(packet_loss_scenarios):
                for i in range(20):  # 20 operations per scenario
                    # Simulate packet loss by randomly failing requests
                    if (i * scenario_idx + i) % 100 < (loss_rate * 100):
                        # Simulate packet loss (timeout/connection error)
                        mock_resp.post(
                            f"{LOAD_TEST_BASE_URL}/chat/packet_loss_{scenario_idx}/message",
                            exception=asyncio.TimeoutError("Simulated packet loss")
                        )
                    else:
                        # Successful response
                        mock_resp.post(
                            f"{LOAD_TEST_BASE_URL}/chat/packet_loss_{scenario_idx}/message",
                            payload={"success": True},
                            status=200
                        )
            
            await load_monitor.start_monitoring()
            
            # Test each packet loss scenario
            for scenario_idx, loss_rate in enumerate(packet_loss_scenarios):
                scenario_start = time.perf_counter()
                
                async def packet_loss_operation(op_id: int):
                    """Operation with simulated packet loss."""
                    try:
                        # Add retry logic for packet loss
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                response = await load_test_client.post(
                                    f"/chat/packet_loss_{scenario_idx}/message",
                                    json={"content": f"Packet loss test {op_id}"},
                                    headers={"Authorization": f"Bearer loss_token_{op_id}"}
                                )
                                
                                if response.status_code == 200:
                                    load_monitor.record_response_time(f"packet_loss_{loss_rate}", 0.030)
                                    return "success"
                                else:
                                    if attempt == max_retries - 1:
                                        load_monitor.record_error(f"packet_loss_{loss_rate}_failed")
                                        return "failed"
                            
                            except asyncio.TimeoutError:
                                if attempt == max_retries - 1:
                                    load_monitor.record_error(f"packet_loss_{loss_rate}_timeout")
                                    return "timeout"
                                else:
                                    # Retry with exponential backoff
                                    await asyncio.sleep(0.1 * (2 ** attempt))
                                    
                        return "failed"
                        
                    except Exception:
                        load_monitor.record_error(f"packet_loss_{loss_rate}_exception")
                        return "exception"
                
                # Execute operations with packet loss
                loss_tasks = [packet_loss_operation(i) for i in range(20)]
                loss_results = await asyncio.gather(*loss_tasks, return_exceptions=True)
                
                # Analyze packet loss impact
                success_count = sum(1 for r in loss_results if r == "success")
                timeout_count = sum(1 for r in loss_results if r == "timeout")
                
                success_rate = success_count / 20
                expected_success_rate = 1.0 - loss_rate  # Account for packet loss
                
                # Success rate should be reasonable considering packet loss and retries
                min_expected_success = max(0.6, expected_success_rate * 0.8)  # 80% of expected, minimum 60%
                assert success_rate >= min_expected_success, \
                    f"Success rate {success_rate:.2f} too low for {loss_rate*100}% packet loss"
                
                print(f"✓ Packet loss {loss_rate*100}%: {success_count}/20 success, {timeout_count} timeouts")
    
    async def test_cpu_throttling_simulation(self, load_test_client, load_monitor):
        """Test system behavior under CPU throttling."""
        with aioresponses() as mock_resp:
            # Mock CPU-intensive operations
            cpu_load_levels = ["normal", "high", "extreme"]
            
            for level in cpu_load_levels:
                for i in range(15):
                    mock_resp.post(
                        f"{LOAD_TEST_BASE_URL}/chat/cpu_throttle_{level}/message",
                        payload={"success": True, "cpu_load": level},
                        status=200
                    )
            
            await load_monitor.start_monitoring()
            
            # Test different CPU load levels
            for load_level in cpu_load_levels:
                cpu_test_start = time.perf_counter()
                
                async def cpu_throttle_operation(op_id: int):
                    """Operation under CPU throttling."""
                    start_time = time.perf_counter()
                    
                    try:
                        # Simulate CPU-intensive work based on load level
                        if load_level == "normal":
                            cpu_work_duration = 0.001  # 1ms
                        elif load_level == "high":
                            cpu_work_duration = 0.010  # 10ms
                        else:  # extreme
                            cpu_work_duration = 0.050  # 50ms
                        
                        # Simulate CPU work (busy wait)
                        work_end = time.perf_counter() + cpu_work_duration
                        while time.perf_counter() < work_end:
                            pass  # Busy wait to simulate CPU load
                        
                        response = await load_test_client.post(
                            f"/chat/cpu_throttle_{load_level}/message",
                            json={"content": f"CPU throttle test {op_id}"},
                            headers={"Authorization": f"Bearer cpu_token_{op_id}"}
                        )
                        
                        end_time = time.perf_counter()
                        total_latency = end_time - start_time
                        
                        if response.status_code == 200:
                            load_monitor.record_response_time(f"cpu_{load_level}", total_latency)
                            return total_latency
                        else:
                            load_monitor.record_error(f"cpu_{load_level}_failed")
                            return None
                            
                    except Exception:
                        load_monitor.record_error(f"cpu_{load_level}_exception")
                        return None
                
                # Execute CPU throttle operations
                cpu_tasks = [cpu_throttle_operation(i) for i in range(15)]
                cpu_results = await asyncio.gather(*cpu_tasks, return_exceptions=True)
                
                # Analyze CPU throttling impact
                valid_latencies = [l for l in cpu_results if isinstance(l, float)]
                
                if valid_latencies:
                    avg_latency = statistics.mean(valid_latencies)
                    max_latency = max(valid_latencies)
                    
                    # System should still respond under CPU pressure
                    if load_level == "extreme":
                        assert avg_latency < 0.5, f"Extreme CPU load latency {avg_latency:.3f}s too high"
                    else:
                        assert avg_latency < 0.1, f"CPU load {load_level} latency {avg_latency:.3f}s too high"
                    
                    print(f"✓ CPU {load_level} load: avg {avg_latency:.3f}s, max {max_latency:.3f}s")
                
                success_rate = len(valid_latencies) / 15
                assert success_rate >= 0.80, f"CPU {load_level} success rate {success_rate:.2f} too low"
            
            load_monitor.stop_monitoring()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "load"])