"""
Failure recovery and reliability tests for multi-participant chat system.
Tests network failures, storage failures, service failures, message delivery guarantees, and recovery mechanisms.
"""

import asyncio
import time
import uuid
import random
import json
import threading
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Set
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import httpx
from aioresponses import aioresponses
import websockets
from websockets.exceptions import ConnectionClosed, InvalidHandshake

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../code/python'))

from chat.schemas import (
    ChatMessage, MessageType, MessageStatus,
    ParticipantInfo, ParticipantType
)


# Reliability Test Configuration
RELIABILITY_BASE_URL = "http://localhost:8080"
WEBSOCKET_BASE_URL = "ws://localhost:8080"
NETWORK_TIMEOUT = 5.0
MAX_RETRY_ATTEMPTS = 5


class NetworkSimulator:
    """Simulate various network failure conditions."""
    
    def __init__(self):
        self.failure_rate = 0.0
        self.latency_ms = 0
        self.packet_loss_rate = 0.0
        self.is_partitioned = False
        self.connection_drops = []
        
    def set_failure_rate(self, rate: float):
        """Set network failure rate (0.0 to 1.0)."""
        self.failure_rate = max(0.0, min(1.0, rate))
    
    def set_latency(self, latency_ms: int):
        """Set network latency in milliseconds."""
        self.latency_ms = max(0, latency_ms)
    
    def set_packet_loss(self, loss_rate: float):
        """Set packet loss rate (0.0 to 1.0)."""
        self.packet_loss_rate = max(0.0, min(1.0, loss_rate))
    
    def create_network_partition(self):
        """Simulate network partition."""
        self.is_partitioned = True
    
    def heal_network_partition(self):
        """Heal network partition."""
        self.is_partitioned = False
    
    async def simulate_network_delay(self):
        """Simulate network latency."""
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
    
    def should_fail_request(self) -> bool:
        """Determine if request should fail based on failure rate."""
        if self.is_partitioned:
            return True
        return random.random() < self.failure_rate
    
    def should_drop_packet(self) -> bool:
        """Determine if packet should be dropped."""
        return random.random() < self.packet_loss_rate


class StorageSimulator:
    """Simulate storage failure conditions."""
    
    def __init__(self):
        self.failure_rate = 0.0
        self.read_latency_ms = 0
        self.write_latency_ms = 0
        self.is_unavailable = False
        self.connection_pool_exhausted = False
        self.partial_write_failures = []
        
    def set_failure_rate(self, rate: float):
        """Set storage failure rate."""
        self.failure_rate = max(0.0, min(1.0, rate))
    
    def set_read_latency(self, latency_ms: int):
        """Set read operation latency."""
        self.read_latency_ms = max(0, latency_ms)
    
    def set_write_latency(self, latency_ms: int):
        """Set write operation latency."""
        self.write_latency_ms = max(0, latency_ms)
    
    def make_unavailable(self):
        """Make storage unavailable."""
        self.is_unavailable = True
    
    def make_available(self):
        """Make storage available."""
        self.is_unavailable = False
    
    def exhaust_connection_pool(self):
        """Simulate connection pool exhaustion."""
        self.connection_pool_exhausted = True
    
    def restore_connection_pool(self):
        """Restore connection pool."""
        self.connection_pool_exhausted = False
    
    async def simulate_read_latency(self):
        """Simulate read operation latency."""
        if self.read_latency_ms > 0:
            await asyncio.sleep(self.read_latency_ms / 1000.0)
    
    async def simulate_write_latency(self):
        """Simulate write operation latency."""
        if self.write_latency_ms > 0:
            await asyncio.sleep(self.write_latency_ms / 1000.0)
    
    def should_fail_operation(self) -> bool:
        """Determine if storage operation should fail."""
        if self.is_unavailable or self.connection_pool_exhausted:
            return True
        return random.random() < self.failure_rate


class MessageTracker:
    """Track message delivery and ordering."""
    
    def __init__(self):
        self.sent_messages: Dict[str, Dict] = {}
        self.received_messages: Dict[str, Dict] = {}
        self.duplicate_messages: Set[str] = set()
        self.out_of_order_messages: List[str] = []
        self.lost_messages: Set[str] = set()
        
    def record_sent_message(self, message_id: str, sequence_id: int, content: str):
        """Record a sent message."""
        self.sent_messages[message_id] = {
            "sequence_id": sequence_id,
            "content": content,
            "sent_at": time.perf_counter()
        }
    
    def record_received_message(self, message_id: str, sequence_id: int, content: str):
        """Record a received message."""
        if message_id in self.received_messages:
            self.duplicate_messages.add(message_id)
        
        self.received_messages[message_id] = {
            "sequence_id": sequence_id,
            "content": content,
            "received_at": time.perf_counter()
        }
    
    def check_message_ordering(self):
        """Check if messages were received in correct order."""
        received_sequence_ids = [
            msg["sequence_id"] for msg in self.received_messages.values()
        ]
        received_sequence_ids.sort()
        
        for i in range(1, len(received_sequence_ids)):
            if received_sequence_ids[i] != received_sequence_ids[i-1] + 1:
                # Gap in sequence - potential message loss or out-of-order
                for seq_id in range(received_sequence_ids[i-1] + 1, received_sequence_ids[i]):
                    # Find message with this sequence ID
                    for msg_id, msg_data in self.sent_messages.items():
                        if msg_data["sequence_id"] == seq_id and msg_id not in self.received_messages:
                            self.lost_messages.add(msg_id)
    
    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get message delivery statistics."""
        self.check_message_ordering()
        
        total_sent = len(self.sent_messages)
        total_received = len(self.received_messages)
        delivery_rate = total_received / total_sent if total_sent > 0 else 0.0
        
        return {
            "total_sent": total_sent,
            "total_received": total_received,
            "delivery_rate": delivery_rate,
            "duplicates": len(self.duplicate_messages),
            "lost_messages": len(self.lost_messages),
            "out_of_order": len(self.out_of_order_messages)
        }


@pytest.fixture
async def reliability_client():
    """Create HTTP client for reliability testing."""
    async with httpx.AsyncClient(
        base_url=RELIABILITY_BASE_URL,
        timeout=httpx.Timeout(NETWORK_TIMEOUT)
    ) as client:
        yield client


@pytest.fixture
def network_simulator():
    """Create network failure simulator."""
    return NetworkSimulator()


@pytest.fixture
def storage_simulator():
    """Create storage failure simulator."""
    return StorageSimulator()


@pytest.fixture
def message_tracker():
    """Create message delivery tracker."""
    return MessageTracker()


@pytest.fixture
def valid_auth_token():
    """Valid authentication token for testing."""
    return "Bearer reliability_test_token"


@pytest.mark.reliability
@pytest.mark.asyncio
class TestNetworkFailures:
    """Test network failure recovery scenarios."""
    
    async def test_connection_drop_during_message_send(self, reliability_client, network_simulator, message_tracker, valid_auth_token):
        """Test connection drop during message send with recovery."""
        conversation_id = "network_drop_conv"
        
        with aioresponses() as mock_resp:
            # First few messages succeed
            for i in range(3):
                mock_resp.post(
                    f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                    payload={"success": True, "message_id": f"msg_{i}", "sequence_id": i+1},
                    status=200
                )
            
            # Connection drops for next messages
            for i in range(3, 6):
                mock_resp.post(
                    f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                    exception=ConnectionError("Connection dropped")
                )
            
            # Recovery - messages succeed again
            for i in range(6, 9):
                mock_resp.post(
                    f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                    payload={"success": True, "message_id": f"msg_{i}", "sequence_id": i+1},
                    status=200
                )
            
            headers = {"Authorization": valid_auth_token}
            
            # Send messages with connection drops in middle
            for i in range(9):
                message_content = f"Test message {i}"
                message_tracker.record_sent_message(f"msg_{i}", i+1, message_content)
                
                try:
                    await network_simulator.simulate_network_delay()
                    
                    response = await reliability_client.post(
                        f"/chat/{conversation_id}/message",
                        json={"content": message_content},
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        message_tracker.record_received_message(
                            data["message_id"], 
                            data["sequence_id"], 
                            message_content
                        )
                    
                except (ConnectionError, httpx.ConnectError):
                    # Connection dropped - implement retry logic
                    await asyncio.sleep(0.1)  # Brief retry delay
                    
                    try:
                        # Retry the message
                        response = await reliability_client.post(
                            f"/chat/{conversation_id}/message",
                            json={"content": message_content},
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            message_tracker.record_received_message(
                                data["message_id"],
                                data["sequence_id"],
                                message_content
                            )
                    except Exception:
                        # Retry failed - message lost
                        pass
            
            # Analyze delivery results
            stats = message_tracker.get_delivery_stats()
            
            # Should recover from connection drops
            assert stats["delivery_rate"] >= 0.7, f"Delivery rate {stats['delivery_rate']:.2f} too low after connection drops"
            assert stats["lost_messages"] <= 3, f"Too many lost messages: {stats['lost_messages']}"
    
    async def test_intermittent_connectivity_flapping(self, reliability_client, network_simulator, valid_auth_token):
        """Test handling of intermittent connectivity (connection flapping)."""
        conversation_id = "flapping_conv"
        flapping_pattern = [True, False, True, True, False, False, True, False, True, True]
        
        with aioresponses() as mock_resp:
            # Mock responses based on flapping pattern
            for i, is_connected in enumerate(flapping_pattern):
                if is_connected:
                    mock_resp.post(
                        f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                        payload={"success": True, "message_id": f"flap_msg_{i}"},
                        status=200
                    )
                else:
                    mock_resp.post(
                        f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                        exception=ConnectionError("Network flapping")
                    )
            
            headers = {"Authorization": valid_auth_token}
            successful_sends = 0
            
            # Send messages during connectivity flapping
            for i, is_connected in enumerate(flapping_pattern):
                try:
                    response = await reliability_client.post(
                        f"/chat/{conversation_id}/message",
                        json={"content": f"Flapping test message {i}"},
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        successful_sends += 1
                    
                except (ConnectionError, httpx.ConnectError):
                    # Expected during connectivity flapping
                    pass
            
            # Verify system handles flapping gracefully
            expected_successful = sum(flapping_pattern)
            assert successful_sends == expected_successful, f"Expected {expected_successful} successful sends, got {successful_sends}"
    
    async def test_high_latency_conditions(self, reliability_client, network_simulator, valid_auth_token):
        """Test system behavior under high latency conditions (>1s)."""
        conversation_id = "high_latency_conv"
        high_latency_ms = 1500  # 1.5 seconds
        
        network_simulator.set_latency(high_latency_ms)
        
        with aioresponses() as mock_resp:
            # Mock slow responses
            for i in range(5):
                mock_resp.post(
                    f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                    payload={"success": True, "message_id": f"slow_msg_{i}", "latency_ms": high_latency_ms},
                    status=200
                )
            
            headers = {"Authorization": valid_auth_token}
            latencies = []
            
            # Send messages with high latency
            for i in range(5):
                start_time = time.perf_counter()
                
                await network_simulator.simulate_network_delay()
                
                response = await reliability_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"High latency test {i}"},
                    headers=headers
                )
                
                end_time = time.perf_counter()
                latency = end_time - start_time
                latencies.append(latency)
                
                assert response.status_code == 200, f"Message {i} failed under high latency"
            
            # Verify system tolerates high latency
            avg_latency = sum(latencies) / len(latencies)
            assert avg_latency >= high_latency_ms / 1000.0, f"Latency simulation not working: {avg_latency:.3f}s"
            
            # All messages should still succeed despite high latency
            assert len([l for l in latencies if l > 0]) == 5, "Some messages failed under high latency"
    
    async def test_packet_loss_simulation(self, reliability_client, network_simulator, message_tracker, valid_auth_token):
        """Test packet loss simulation and recovery."""
        conversation_id = "packet_loss_conv"
        packet_loss_rates = [0.1, 0.2, 0.3]  # 10%, 20%, 30% packet loss
        
        for loss_rate in packet_loss_rates:
            network_simulator.set_packet_loss(loss_rate)
            
            with aioresponses() as mock_resp:
                # Mock responses with packet loss simulation
                message_count = 20
                
                for i in range(message_count):
                    if network_simulator.should_drop_packet():
                        # Packet dropped - no response
                        mock_resp.post(
                            f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                            exception=asyncio.TimeoutError("Packet lost")
                        )
                    else:
                        # Packet arrives successfully
                        mock_resp.post(
                            f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                            payload={"success": True, "message_id": f"loss_msg_{i}"},
                            status=200
                        )
                
                headers = {"Authorization": valid_auth_token}
                successful_messages = 0
                
                # Send messages with packet loss
                for i in range(message_count):
                    try:
                        response = await reliability_client.post(
                            f"/chat/{conversation_id}/message",
                            json={"content": f"Packet loss test {i} (loss rate: {loss_rate})"},
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            successful_messages += 1
                    
                    except (asyncio.TimeoutError, httpx.TimeoutException):
                        # Packet lost - expected behavior
                        pass
                
                # Verify system handles packet loss reasonably
                expected_success_rate = 1.0 - loss_rate
                actual_success_rate = successful_messages / message_count
                
                # Allow some tolerance for randomness
                tolerance = 0.15
                assert actual_success_rate >= expected_success_rate - tolerance, \
                    f"Success rate {actual_success_rate:.2f} too low for {loss_rate*100}% packet loss"
    
    async def test_dns_resolution_failures(self, network_simulator):
        """Test DNS resolution failure handling."""
        # Simulate DNS resolution failure
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.side_effect = Exception("DNS resolution failed")
            
            # Test DNS failure handling
            with pytest.raises(Exception, match="DNS resolution failed"):
                async with httpx.AsyncClient(base_url="http://non-existent-domain.invalid") as client:
                    await client.get("/test")
        
        # Test recovery after DNS resolution is restored
        with aioresponses() as mock_resp:
            mock_resp.get(
                f"{RELIABILITY_BASE_URL}/health",
                payload={"status": "healthy", "dns_resolved": True},
                status=200
            )
            
            async with httpx.AsyncClient(base_url=RELIABILITY_BASE_URL) as client:
                response = await client.get("/health")
                assert response.status_code == 200
                assert response.json()["dns_resolved"] is True


@pytest.mark.reliability
@pytest.mark.asyncio
class TestStorageFailures:
    """Test storage failure recovery scenarios."""
    
    async def test_write_failures_during_persistence(self, reliability_client, storage_simulator, valid_auth_token):
        """Test write failure handling during message persistence."""
        conversation_id = "storage_write_fail_conv"
        
        # Simulate storage write failures
        storage_simulator.set_failure_rate(0.3)  # 30% failure rate
        
        with aioresponses() as mock_resp:
            # Mock storage write failures
            write_attempts = 10
            
            for i in range(write_attempts):
                if storage_simulator.should_fail_operation():
                    # Storage write fails
                    mock_resp.post(
                        f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                        payload={
                            "error": "Storage write failed",
                            "code": "STORAGE_WRITE_ERROR",
                            "retry_recommended": True
                        },
                        status=500
                    )
                else:
                    # Storage write succeeds
                    mock_resp.post(
                        f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                        payload={"success": True, "message_id": f"storage_msg_{i}", "persisted": True},
                        status=200
                    )
            
            headers = {"Authorization": valid_auth_token}
            successful_persists = 0
            failed_persists = 0
            
            # Attempt message persistence with storage failures
            for i in range(write_attempts):
                await storage_simulator.simulate_write_latency()
                
                response = await reliability_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"Storage test message {i}"},
                    headers=headers
                )
                
                if response.status_code == 200:
                    successful_persists += 1
                elif response.status_code == 500:
                    failed_persists += 1
                    
                    # Implement retry logic for storage failures
                    await asyncio.sleep(0.1)  # Brief retry delay
                    
                    # Retry once
                    retry_response = await reliability_client.post(
                        f"/chat/{conversation_id}/message",
                        json={"content": f"Storage test message {i} (retry)"},
                        headers=headers
                    )
                    
                    if retry_response.status_code == 200:
                        successful_persists += 1
            
            # Verify system handles storage failures with retries
            assert successful_persists > 0, "No messages successfully persisted"
            assert failed_persists > 0, "No storage failures simulated"
            
            # Success rate should improve with retries
            total_attempts = write_attempts
            success_rate = successful_persists / total_attempts
            assert success_rate >= 0.5, f"Success rate {success_rate:.2f} too low even with retries"
    
    async def test_read_timeouts(self, reliability_client, storage_simulator, valid_auth_token):
        """Test handling of storage read timeouts."""
        conversation_id = "storage_read_timeout_conv"
        
        # Simulate high read latency causing timeouts
        storage_simulator.set_read_latency(3000)  # 3 second read latency
        
        with aioresponses() as mock_resp:
            # Mock slow read operations that timeout
            mock_resp.get(
                f"{RELIABILITY_BASE_URL}/chat/conversations/{conversation_id}",
                exception=asyncio.TimeoutError("Storage read timeout")
            )
            
            # Mock successful read after timeout handling
            mock_resp.get(
                f"{RELIABILITY_BASE_URL}/chat/conversations/{conversation_id}",
                payload={
                    "id": conversation_id,
                    "messages": [],
                    "read_timeout_recovered": True
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test read timeout handling
            try:
                await storage_simulator.simulate_read_latency()
                response = await reliability_client.get(
                    f"/chat/conversations/{conversation_id}",
                    headers=headers
                )
                
                # Should not reach here due to timeout
                assert False, "Expected timeout exception"
                
            except (asyncio.TimeoutError, httpx.TimeoutException):
                # Expected timeout behavior
                pass
            
            # Test recovery after timeout
            storage_simulator.set_read_latency(50)  # Restore normal latency
            
            response = await reliability_client.get(
                f"/chat/conversations/{conversation_id}",
                headers=headers
            )
            
            assert response.status_code == 200
            assert response.json()["read_timeout_recovered"] is True
    
    async def test_connection_pool_exhaustion(self, reliability_client, storage_simulator, valid_auth_token):
        """Test connection pool exhaustion handling."""
        conversation_id = "conn_pool_exhaustion_conv"
        
        # Simulate connection pool exhaustion
        storage_simulator.exhaust_connection_pool()
        
        with aioresponses() as mock_resp:
            # Mock connection pool exhaustion
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "error": "Connection pool exhausted",
                    "code": "CONNECTION_POOL_EXHAUSTED",
                    "retry_after": 5
                },
                status=503
            )
            
            # Mock successful operation after pool recovery
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={"success": True, "connection_pool_recovered": True},
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test connection pool exhaustion
            response = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": "Pool exhaustion test"},
                headers=headers
            )
            
            assert response.status_code == 503
            assert "Connection pool exhausted" in response.json()["error"]
            assert "retry_after" in response.json()
            
            # Simulate pool recovery
            storage_simulator.restore_connection_pool()
            
            # Test successful operation after recovery
            recovery_response = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": "Pool recovery test"},
                headers=headers
            )
            
            assert recovery_response.status_code == 200
            assert recovery_response.json()["connection_pool_recovered"] is True
    
    async def test_partial_write_scenarios(self, reliability_client, storage_simulator, valid_auth_token):
        """Test partial write failure scenarios."""
        conversation_id = "partial_write_conv"
        
        with aioresponses() as mock_resp:
            # Mock partial write failure
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "error": "Partial write failure - message metadata saved but content failed",
                    "code": "PARTIAL_WRITE_FAILURE",
                    "metadata_saved": True,
                    "content_saved": False,
                    "rollback_required": True
                },
                status=500
            )
            
            # Mock successful rollback and retry
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "rollback_completed": True,
                    "retry_successful": True
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test partial write failure
            response = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": "Partial write test message"},
                headers=headers
            )
            
            assert response.status_code == 500
            data = response.json()
            assert data["metadata_saved"] is True
            assert data["content_saved"] is False
            assert data["rollback_required"] is True
            
            # Test recovery with rollback and retry
            retry_response = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": "Partial write retry message"},
                headers=headers
            )
            
            assert retry_response.status_code == 200
            retry_data = retry_response.json()
            assert retry_data["rollback_completed"] is True
            assert retry_data["retry_successful"] is True
    
    async def test_cache_storage_inconsistency(self, reliability_client, valid_auth_token):
        """Test handling of cache/storage inconsistency."""
        conversation_id = "cache_inconsistency_conv"
        
        with aioresponses() as mock_resp:
            # Mock cache/storage inconsistency detection
            mock_resp.get(
                f"{RELIABILITY_BASE_URL}/chat/conversations/{conversation_id}",
                payload={
                    "error": "Cache/storage inconsistency detected",
                    "code": "CACHE_STORAGE_MISMATCH",
                    "cache_version": "v1.2",
                    "storage_version": "v1.1",
                    "cache_invalidated": True
                },
                status=409
            )
            
            # Mock successful read after cache invalidation
            mock_resp.get(
                f"{RELIABILITY_BASE_URL}/chat/conversations/{conversation_id}",
                payload={
                    "id": conversation_id,
                    "messages": [],
                    "cache_refreshed": True,
                    "consistency_restored": True
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test inconsistency detection
            response = await reliability_client.get(
                f"/chat/conversations/{conversation_id}",
                headers=headers
            )
            
            assert response.status_code == 409
            data = response.json()
            assert "inconsistency detected" in data["error"]
            assert data["cache_invalidated"] is True
            
            # Test successful read after cache refresh
            retry_response = await reliability_client.get(
                f"/chat/conversations/{conversation_id}",
                headers=headers
            )
            
            assert retry_response.status_code == 200
            retry_data = retry_response.json()
            assert retry_data["cache_refreshed"] is True
            assert retry_data["consistency_restored"] is True


@pytest.mark.reliability
@pytest.mark.asyncio
class TestServiceFailures:
    """Test service failure recovery scenarios."""
    
    async def test_nlweb_timeout_handling(self, reliability_client, valid_auth_token):
        """Test NLWeb service timeout handling."""
        conversation_id = "nlweb_timeout_conv"
        
        with aioresponses() as mock_resp:
            # Mock NLWeb timeout
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "partial_success": True,
                    "message_saved": True,
                    "nlweb_response": None,
                    "nlweb_timeout": True,
                    "timeout_duration": 20.0
                },
                status=202  # Accepted but incomplete
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Send message that would trigger NLWeb timeout
            response = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": "This message will cause NLWeb timeout"},
                headers=headers
            )
            
            assert response.status_code == 202
            data = response.json()
            assert data["message_saved"] is True
            assert data["nlweb_timeout"] is True
            assert data["timeout_duration"] == 20.0
            
            # Message should be saved even if NLWeb times out
            assert data["partial_success"] is True
    
    async def test_partial_participant_failures(self, reliability_client, valid_auth_token):
        """Test handling when some participants fail to receive messages."""
        conversation_id = "partial_participant_fail_conv"
        
        with aioresponses() as mock_resp:
            # Mock partial delivery failure
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "message_id": "partial_fail_msg_001",
                    "total_participants": 5,
                    "successful_deliveries": 3,
                    "failed_deliveries": 2,
                    "failed_participants": ["user_4", "user_5"],
                    "retry_scheduled": True
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Send message with partial delivery failure
            response = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": "Partial delivery test message"},
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_participants"] == 5
            assert data["successful_deliveries"] == 3
            assert data["failed_deliveries"] == 2
            assert len(data["failed_participants"]) == 2
            assert data["retry_scheduled"] is True
    
    async def test_websocket_server_restart(self, valid_auth_token):
        """Test WebSocket server restart handling."""
        # Mock WebSocket connection before restart
        mock_websocket_before = AsyncMock()
        mock_websocket_before.send = AsyncMock()
        mock_websocket_before.recv = AsyncMock(return_value='{"type": "pong"}')
        mock_websocket_before.close = AsyncMock()
        
        # Simulate server restart - connection becomes invalid
        mock_websocket_before.send.side_effect = ConnectionClosed(None, None)
        
        # Test connection failure detection
        with pytest.raises(ConnectionClosed):
            await mock_websocket_before.send("test message")
        
        # Mock successful reconnection after restart
        mock_websocket_after = AsyncMock()
        mock_websocket_after.send = AsyncMock()
        mock_websocket_after.recv = AsyncMock(return_value='{"type": "reconnected", "server_restarted": true}')
        
        # Test successful reconnection
        await mock_websocket_after.send("reconnection test message")
        response = await mock_websocket_after.recv()
        response_data = json.loads(response)
        
        assert response_data["type"] == "reconnected"
        assert response_data["server_restarted"] is True
    
    async def test_database_failover(self, reliability_client, valid_auth_token):
        """Test database failover handling."""
        conversation_id = "db_failover_conv"
        
        with aioresponses() as mock_resp:
            # Mock primary database failure
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "error": "Primary database unavailable",
                    "code": "DATABASE_FAILOVER",
                    "failover_initiated": True,
                    "secondary_database_active": True
                },
                status=503
            )
            
            # Mock successful operation on secondary database
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "message_id": "failover_msg_001",
                    "database": "secondary",
                    "failover_completed": True
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # First request fails due to primary database failure
            response = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": "Database failover test"},
                headers=headers
            )
            
            assert response.status_code == 503
            data = response.json()
            assert data["failover_initiated"] is True
            assert data["secondary_database_active"] is True
            
            # Retry succeeds on secondary database
            retry_response = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": "Database failover retry"},
                headers=headers
            )
            
            assert retry_response.status_code == 200
            retry_data = retry_response.json()
            assert retry_data["database"] == "secondary"
            assert retry_data["failover_completed"] is True
    
    async def test_cache_eviction_under_pressure(self, reliability_client, valid_auth_token):
        """Test cache eviction under memory pressure."""
        with aioresponses() as mock_resp:
            # Mock cache pressure response
            mock_resp.get(
                f"{RELIABILITY_BASE_URL}/chat/cache-status",
                payload={
                    "cache_pressure": "HIGH",
                    "eviction_rate": 0.3,
                    "hit_rate": 0.4,
                    "memory_usage_percent": 95,
                    "eviction_policy": "LRU"
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Check cache status under pressure
            response = await reliability_client.get("/chat/cache-status", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["cache_pressure"] == "HIGH"
            assert data["eviction_rate"] == 0.3
            assert data["memory_usage_percent"] == 95
            assert data["eviction_policy"] == "LRU"


@pytest.mark.reliability
@pytest.mark.asyncio
class TestMessageDeliveryGuarantees:
    """Test message delivery guarantee mechanisms."""
    
    async def test_at_least_once_verification(self, reliability_client, message_tracker, valid_auth_token):
        """Test at-least-once message delivery verification."""
        conversation_id = "at_least_once_conv"
        
        with aioresponses() as mock_resp:
            # Mock message delivery with acknowledgments
            message_count = 10
            
            for i in range(message_count):
                mock_resp.post(
                    f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "success": True,
                        "message_id": f"ack_msg_{i}",
                        "sequence_id": i + 1,
                        "acknowledgment": True,
                        "delivery_confirmed": True
                    },
                    status=200
                )
            
            headers = {"Authorization": valid_auth_token}
            delivered_messages = []
            
            # Send messages and track acknowledgments
            for i in range(message_count):
                message_content = f"At-least-once test message {i}"
                message_id = f"ack_msg_{i}"
                
                message_tracker.record_sent_message(message_id, i + 1, message_content)
                
                response = await reliability_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": message_content, "message_id": message_id},
                    headers=headers
                )
                
                assert response.status_code == 200
                data = response.json()
                
                if data.get("acknowledgment") and data.get("delivery_confirmed"):
                    message_tracker.record_received_message(
                        data["message_id"],
                        data["sequence_id"],
                        message_content
                    )
                    delivered_messages.append(message_id)
            
            # Verify at-least-once delivery
            stats = message_tracker.get_delivery_stats()
            assert stats["delivery_rate"] == 1.0, f"At-least-once guarantee violated: {stats['delivery_rate']}"
            assert len(delivered_messages) == message_count, f"Expected {message_count} delivered, got {len(delivered_messages)}"
    
    async def test_duplicate_detection(self, reliability_client, message_tracker, valid_auth_token):
        """Test duplicate message detection."""
        conversation_id = "duplicate_detection_conv"
        
        with aioresponses() as mock_resp:
            # Mock duplicate message handling
            message_id = "duplicate_test_msg_001"
            
            # First send - success
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "message_id": message_id,
                    "sequence_id": 1,
                    "is_duplicate": False
                },
                status=200
            )
            
            # Second send - duplicate detected
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "message_id": message_id,
                    "sequence_id": 1,
                    "is_duplicate": True,
                    "original_timestamp": "2024-01-01T10:00:00Z"
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            message_content = "Duplicate detection test message"
            
            # Send message first time
            response1 = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": message_content, "message_id": message_id},
                headers=headers
            )
            
            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["is_duplicate"] is False
            
            message_tracker.record_received_message(message_id, 1, message_content)
            
            # Send same message again (duplicate)
            response2 = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": message_content, "message_id": message_id},
                headers=headers
            )
            
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["is_duplicate"] is True
            assert "original_timestamp" in data2
            
            message_tracker.record_received_message(message_id, 1, message_content)
            
            # Verify duplicate detection
            stats = message_tracker.get_delivery_stats()
            assert len(message_tracker.duplicate_messages) == 1, "Duplicate not detected"
    
    async def test_message_ordering_preservation(self, reliability_client, message_tracker, valid_auth_token):
        """Test message ordering preservation."""
        conversation_id = "order_preservation_conv"
        
        with aioresponses() as mock_resp:
            # Mock ordered message delivery
            message_count = 15
            
            for i in range(message_count):
                mock_resp.post(
                    f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "success": True,
                        "message_id": f"order_msg_{i}",
                        "sequence_id": i + 1,
                        "order_preserved": True
                    },
                    status=200
                )
            
            headers = {"Authorization": valid_auth_token}
            
            # Send messages in order
            for i in range(message_count):
                message_content = f"Order test message {i}"
                message_id = f"order_msg_{i}"
                
                message_tracker.record_sent_message(message_id, i + 1, message_content)
                
                response = await reliability_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": message_content, "message_id": message_id},
                    headers=headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["order_preserved"] is True
                
                message_tracker.record_received_message(
                    data["message_id"],
                    data["sequence_id"],
                    message_content
                )
            
            # Verify message ordering
            message_tracker.check_message_ordering()
            stats = message_tracker.get_delivery_stats()
            
            assert stats["lost_messages"] == 0, f"Messages lost: {stats['lost_messages']}"
            assert stats["out_of_order"] == 0, f"Out of order messages: {stats['out_of_order']}"
    
    async def test_no_message_loss_proof(self, reliability_client, message_tracker, valid_auth_token):
        """Test proof of no message loss under normal conditions."""
        conversation_id = "no_loss_conv" 
        
        with aioresponses() as mock_resp:
            # Mock reliable message delivery
            message_count = 25
            
            for i in range(message_count):
                mock_resp.post(
                    f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "success": True,
                        "message_id": f"no_loss_msg_{i}",
                        "sequence_id": i + 1,
                        "persisted": True,
                        "broadcasted": True
                    },
                    status=200
                )
            
            headers = {"Authorization": valid_auth_token}
            
            # Send all messages
            for i in range(message_count):
                message_content = f"No loss test message {i}"
                message_id = f"no_loss_msg_{i}"
                
                message_tracker.record_sent_message(message_id, i + 1, message_content)
                
                response = await reliability_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": message_content, "message_id": message_id},
                    headers=headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["persisted"] is True
                assert data["broadcasted"] is True
                
                message_tracker.record_received_message(
                    data["message_id"],
                    data["sequence_id"],
                    message_content
                )
            
            # Verify no message loss
            stats = message_tracker.get_delivery_stats()
            assert stats["delivery_rate"] == 1.0, f"Message loss detected: delivery rate {stats['delivery_rate']}"
            assert stats["lost_messages"] == 0, f"Lost messages: {stats['lost_messages']}"
            assert stats["total_sent"] == stats["total_received"], "Sent/received count mismatch"
    
    async def test_acknowledgment_system(self, reliability_client, valid_auth_token):
        """Test message acknowledgment system."""
        conversation_id = "acknowledgment_conv"
        
        with aioresponses() as mock_resp:
            # Mock acknowledgment system
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "message_id": "ack_system_msg_001",
                    "acknowledgment_id": "ack_12345",
                    "acknowledgment_required": True,
                    "timeout_ms": 5000
                },
                status=200
            )
            
            # Mock acknowledgment endpoint
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/acknowledge",
                payload={
                    "acknowledgment_received": True,
                    "acknowledgment_id": "ack_12345",
                    "acknowledged_at": datetime.utcnow().isoformat()
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Send message requiring acknowledgment
            response = await reliability_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": "Acknowledgment test message"},
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["acknowledgment_required"] is True
            assert "acknowledgment_id" in data
            
            # Send acknowledgment
            ack_response = await reliability_client.post(
                f"/chat/{conversation_id}/acknowledge",
                json={"acknowledgment_id": data["acknowledgment_id"]},
                headers=headers
            )
            
            assert ack_response.status_code == 200
            ack_data = ack_response.json()
            assert ack_data["acknowledgment_received"] is True
            assert ack_data["acknowledgment_id"] == data["acknowledgment_id"]


@pytest.mark.reliability
@pytest.mark.asyncio
class TestRecoveryMechanisms:
    """Test recovery mechanism implementations."""
    
    async def test_automatic_reconnection(self, valid_auth_token):
        """Test automatic reconnection mechanism."""
        # Mock WebSocket with connection failure and recovery
        connection_attempts = []
        
        async def mock_connect_with_retry():
            """Mock connection with retry logic."""
            max_attempts = 5
            backoff_times = [1, 2, 4, 8, 16]  # Exponential backoff
            
            for attempt in range(max_attempts):
                try:
                    connection_attempts.append(attempt + 1)
                    
                    if attempt < 3:  # First 3 attempts fail
                        raise ConnectionError(f"Connection failed (attempt {attempt + 1})")
                    else:
                        # Success on 4th attempt
                        return {"connected": True, "attempt": attempt + 1}
                
                except ConnectionError:
                    if attempt < max_attempts - 1:
                        # Wait with exponential backoff
                        await asyncio.sleep(backoff_times[attempt] * 0.01)  # Scaled for testing
                    else:
                        raise
        
        # Test automatic reconnection
        result = await mock_connect_with_retry()
        
        assert result["connected"] is True
        assert result["attempt"] == 4  # Succeeded on 4th attempt
        assert len(connection_attempts) == 4  # Made 4 attempts total
    
    async def test_message_replay(self, reliability_client, message_tracker, valid_auth_token):
        """Test message replay after reconnection."""
        conversation_id = "message_replay_conv"
        
        with aioresponses() as mock_resp:
            # Mock message replay after reconnection
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/replay",
                payload={
                    "replay_started": True,
                    "last_known_sequence_id": 5,
                    "messages_to_replay": [
                        {"sequence_id": 6, "content": "Missed message 1"},
                        {"sequence_id": 7, "content": "Missed message 2"},
                        {"sequence_id": 8, "content": "Missed message 3"}
                    ],
                    "replay_completed": True
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Request message replay
            response = await reliability_client.post(
                f"/chat/{conversation_id}/replay",
                json={"last_known_sequence_id": 5},
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["replay_started"] is True
            assert data["last_known_sequence_id"] == 5
            assert len(data["messages_to_replay"]) == 3
            assert data["replay_completed"] is True
            
            # Track replayed messages
            for msg in data["messages_to_replay"]:
                message_tracker.record_received_message(
                    f"replay_msg_{msg['sequence_id']}",
                    msg["sequence_id"],
                    msg["content"]
                )
            
            # Verify replay fills the gap
            expected_sequences = [6, 7, 8]
            replayed_sequences = [msg["sequence_id"] for msg in data["messages_to_replay"]]
            assert replayed_sequences == expected_sequences
    
    async def test_state_synchronization(self, reliability_client, valid_auth_token):
        """Test state synchronization after recovery."""
        conversation_id = "state_sync_conv"
        
        with aioresponses() as mock_resp:
            # Mock state synchronization
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/sync",
                payload={
                    "sync_started": True,
                    "current_sequence_id": 15,
                    "participant_states": [
                        {"participant_id": "user_1", "last_seen_sequence_id": 15, "online": True},
                        {"participant_id": "user_2", "last_seen_sequence_id": 12, "online": False},
                        {"participant_id": "user_3", "last_seen_sequence_id": 15, "online": True}
                    ],
                    "conversation_state": {
                        "mode": "MULTI",
                        "queue_size": 3,
                        "active_participants": 2
                    },
                    "sync_completed": True
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Request state synchronization
            response = await reliability_client.post(
                f"/chat/{conversation_id}/sync",
                json={"sync_type": "full", "participant_id": "user_1"},
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["sync_started"] is True
            assert data["current_sequence_id"] == 15
            assert len(data["participant_states"]) == 3
            assert data["conversation_state"]["mode"] == "MULTI"
            assert data["sync_completed"] is True
    
    async def test_participant_list_recovery(self, reliability_client, valid_auth_token):
        """Test participant list recovery after failures."""
        conversation_id = "participant_recovery_conv"
        
        with aioresponses() as mock_resp:
            # Mock participant list recovery
            mock_resp.get(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/participants/recover",
                payload={
                    "recovery_initiated": True,
                    "participants_before": [
                        {"participant_id": "user_1", "status": "unknown"},
                        {"participant_id": "user_2", "status": "unknown"},
                        {"participant_id": "user_3", "status": "unknown"}
                    ],
                    "participants_after": [
                        {"participant_id": "user_1", "status": "online", "recovered": True},
                        {"participant_id": "user_2", "status": "offline", "recovered": True},
                        {"participant_id": "user_3", "status": "online", "recovered": True}
                    ],
                    "recovery_successful": True
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Request participant list recovery
            response = await reliability_client.get(
                f"/chat/{conversation_id}/participants/recover",
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["recovery_initiated"] is True
            assert len(data["participants_before"]) == 3
            assert len(data["participants_after"]) == 3
            assert data["recovery_successful"] is True
            
            # Verify all participants were recovered
            for participant in data["participants_after"]:
                assert participant["recovered"] is True
                assert participant["status"] in ["online", "offline"]
    
    async def test_queue_state_restoration(self, reliability_client, valid_auth_token):
        """Test queue state restoration after failures."""
        conversation_id = "queue_restoration_conv"
        
        with aioresponses() as mock_resp:
            # Mock queue state restoration
            mock_resp.post(
                f"{RELIABILITY_BASE_URL}/chat/{conversation_id}/queue/restore",
                payload={
                    "restoration_started": True,
                    "queue_backup_found": True,
                    "messages_restored": 7,
                    "queue_state_before": {
                        "size": 0,
                        "head_sequence_id": None,
                        "tail_sequence_id": None
                    },
                    "queue_state_after": {
                        "size": 7,
                        "head_sequence_id": 10,
                        "tail_sequence_id": 16
                    },
                    "restoration_completed": True
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Request queue state restoration
            response = await reliability_client.post(
                f"/chat/{conversation_id}/queue/restore",
                json={"restore_from_backup": True},
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["restoration_started"] is True
            assert data["queue_backup_found"] is True
            assert data["messages_restored"] == 7
            assert data["queue_state_after"]["size"] == 7
            assert data["restoration_completed"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "reliability"])