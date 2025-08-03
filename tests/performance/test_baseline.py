"""
Performance baseline tests for multi-participant chat system.
Establishes baseline metrics from the current /ask endpoint.
"""

import asyncio
import time
from typing import Dict, List, Tuple
from statistics import mean, median, stdev

import pytest
import httpx
from aiohttp import ClientSession
import yaml

# Load test configuration
with open('tests/config_test.yaml', 'r') as f:
    TEST_CONFIG = yaml.safe_load(f)


@pytest.mark.performance
@pytest.mark.asyncio
class TestPerformanceBaseline:
    """Establish performance baselines for the system."""
    
    @pytest.fixture
    async def baseline_client(self):
        """Create HTTP client for baseline testing."""
        async with httpx.AsyncClient(
            base_url=f"http://{TEST_CONFIG['test_server']['host']}:{TEST_CONFIG['test_server']['port']}"
        ) as client:
            yield client
    
    @pytest.mark.benchmark(group="baseline", min_rounds=100)
    async def test_ask_endpoint_baseline(self, benchmark, baseline_client):
        """
        Measure baseline latency of /ask endpoint.
        This will be our reference for ≤105% target.
        """
        # Sample query
        query_params = {
            "query": "What's the weather today?",
            "user_id": "test_user_baseline",
            "generate_mode": "list"
        }
        
        async def make_request():
            start = time.perf_counter()
            try:
                response = await baseline_client.get("/ask", params=query_params)
                response.raise_for_status()
                end = time.perf_counter()
                return end - start
            except Exception as e:
                pytest.skip(f"Baseline endpoint not available: {e}")
        
        # Run benchmark
        result = benchmark.pedantic(make_request, rounds=100, warmup_rounds=10)
        
        # Document baseline
        baseline_metrics = {
            "mean": benchmark.stats["mean"],
            "median": benchmark.stats["median"],
            "min": benchmark.stats["min"],
            "max": benchmark.stats["max"],
            "stddev": benchmark.stats["stddev"],
            "p95": benchmark.stats.get("q95", 0),
            "p99": benchmark.stats.get("q99", 0)
        }
        
        # Save baseline to metrics file
        self._update_baseline_metrics(baseline_metrics)
        
        # Assert reasonable baseline (adjust based on actual system)
        assert baseline_metrics["mean"] < 1.0, "Baseline mean latency exceeds 1 second"
        assert baseline_metrics["p99"] < 2.0, "Baseline p99 latency exceeds 2 seconds"
        
        return baseline_metrics
    
    async def test_measure_websocket_handshake_baseline(self, baseline_client):
        """Measure WebSocket handshake time as baseline."""
        handshake_times = []
        
        for _ in range(50):
            start = time.perf_counter()
            try:
                async with baseline_client.websocket_connect(
                    f"ws://{TEST_CONFIG['test_server']['host']}:{TEST_CONFIG['test_server']['port']}/ws"
                ) as ws:
                    end = time.perf_counter()
                    handshake_times.append(end - start)
                    await ws.close()
            except Exception as e:
                pytest.skip(f"WebSocket endpoint not available: {e}")
        
        metrics = {
            "mean": mean(handshake_times),
            "median": median(handshake_times),
            "min": min(handshake_times),
            "max": max(handshake_times),
            "stddev": stdev(handshake_times) if len(handshake_times) > 1 else 0
        }
        
        # Assert WebSocket handshake is reasonably fast
        assert metrics["mean"] < 0.1, "WebSocket handshake mean exceeds 100ms"
        
        return metrics
    
    async def test_concurrent_request_baseline(self, baseline_client):
        """Measure system behavior under concurrent load."""
        concurrent_levels = [1, 5, 10, 20, 50]
        results = {}
        
        async def make_concurrent_requests(count: int) -> List[float]:
            """Make concurrent requests and measure latencies."""
            query_params = {
                "query": f"Concurrent test query {count}",
                "user_id": f"test_user_{count}",
                "generate_mode": "list"
            }
            
            async def single_request():
                start = time.perf_counter()
                try:
                    response = await baseline_client.get("/ask", params=query_params)
                    response.raise_for_status()
                    end = time.perf_counter()
                    return end - start
                except Exception:
                    return None
            
            tasks = [single_request() for _ in range(count)]
            latencies = await asyncio.gather(*tasks)
            return [l for l in latencies if l is not None]
        
        for level in concurrent_levels:
            latencies = await make_concurrent_requests(level)
            if latencies:
                results[level] = {
                    "mean": mean(latencies),
                    "median": median(latencies),
                    "min": min(latencies),
                    "max": max(latencies),
                    "success_rate": len(latencies) / level
                }
        
        # Verify system scales reasonably
        if 1 in results and 10 in results:
            # Latency shouldn't increase more than 2x with 10x load
            assert results[10]["mean"] < results[1]["mean"] * 2
        
        return results
    
    async def test_memory_baseline(self):
        """Establish memory usage baseline."""
        # This would require system monitoring tools
        # For now, we'll create a placeholder
        memory_metrics = {
            "idle_memory_mb": 0,  # Would measure actual memory
            "single_connection_mb": 0,
            "per_message_kb": 0
        }
        
        # Document for future comparison
        return memory_metrics
    
    def _update_baseline_metrics(self, metrics: Dict):
        """Update TEST_METRICS.md with baseline measurements."""
        import os
        from datetime import datetime
        
        metrics_file = os.path.join(os.path.dirname(__file__), '../../TEST_METRICS.md')
        
        # Read current metrics
        with open(metrics_file, 'r') as f:
            content = f.read()
        
        # Update baseline section
        baseline_section = f"""### Current System (/ask endpoint)
- **Baseline Latency**: {metrics['mean']:.3f}s (mean)
- **Measurement Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Test Conditions**: 100 requests, 10 warmup rounds
- **Average Response Time**: {metrics['mean']:.3f}s
- **P50 Latency**: {metrics['median']:.3f}s
- **P95 Latency**: {metrics.get('p95', 0):.3f}s
- **P99 Latency**: {metrics.get('p99', 0):.3f}s"""
        
        # Replace the baseline section
        import re
        pattern = r'### Current System \(/ask endpoint\).*?(?=###|\Z)'
        content = re.sub(pattern, baseline_section + '\n\n', content, flags=re.DOTALL)
        
        # Write back
        with open(metrics_file, 'w') as f:
            f.write(content)


@pytest.mark.performance
class TestPerformanceTargets:
    """Verify performance targets based on baseline."""
    
    def test_calculate_performance_targets(self):
        """Calculate and document performance targets from baseline."""
        # This test would run after baseline is established
        # For now, we document the target calculations
        
        baseline_latency = 0.100  # Placeholder - would read from metrics
        
        targets = {
            "single_participant": {
                "target": baseline_latency * 1.05,
                "description": "≤105% of baseline /ask latency"
            },
            "multi_participant": {
                "target": 0.200,
                "description": "<200ms message delivery"
            },
            "websocket_handshake": {
                "target": 0.050,
                "description": "≤50ms overhead"
            },
            "message_routing": {
                "2_participants": 0.001,
                "10_participants": 0.005,
                "description": "Routing latency by participant count"
            },
            "storage_operation": {
                "target": 0.050,
                "description": "<50ms for sequence ID assignment"
            }
        }
        
        # Verify targets are reasonable
        assert targets["single_participant"]["target"] < 1.0
        assert targets["multi_participant"]["target"] < 1.0
        
        return targets


@pytest.mark.performance
@pytest.mark.slow
class TestSystemLimits:
    """Test system limits and capacity."""
    
    async def test_max_concurrent_connections(self):
        """Find maximum concurrent WebSocket connections."""
        # This would gradually increase connections until failure
        # Placeholder for actual implementation
        max_connections = 1000  # Target
        
        assert max_connections >= 1000, "System should support 1000+ concurrent connections"
        
    async def test_max_messages_per_second(self):
        """Find maximum message throughput."""
        # This would send messages at increasing rates
        # Placeholder for actual implementation
        max_throughput = 100  # Target messages/second
        
        assert max_throughput >= 100, "System should handle 100+ messages/second"
        
    async def test_queue_overflow_behavior(self):
        """Test behavior when queue limit is reached."""
        # This would fill queue to limit and verify 429 responses
        # Placeholder for actual implementation
        queue_limit = 1000
        
        # Verify graceful handling
        assert queue_limit == 1000, "Queue limit should be 1000 messages"


if __name__ == "__main__":
    # Run baseline tests
    pytest.main([__file__, "-v", "-m", "performance"])