"""
Chat system metrics collection.
"""

from typing import Dict, Any, Optional
from collections import defaultdict
import time
import threading
from datetime import datetime


class ChatMetrics:
    """
    Collects metrics for chat system operations.
    Thread-safe implementation.
    """
    
    def __init__(self):
        """Initialize metrics collection"""
        self._lock = threading.RLock()
        
        # Storage operation metrics
        self._storage_operations = defaultdict(lambda: {
            "count": 0,
            "total_latency": 0.0,
            "failures": 0
        })
        
        # Connection metrics per human
        self._connections_per_human = defaultdict(int)
        self._total_connections = 0
        
        # Queue depth metrics
        self._queue_depths = {}
        
        # Conversation pattern metrics
        self._conversation_patterns = {
            "single_human": 0,
            "multi_human": 0,
            "human_counts": []
        }
    
    def record_storage_operation(
        self, 
        operation: str, 
        latency: float, 
        success: bool = True
    ) -> None:
        """
        Record a storage operation metric.
        
        Args:
            operation: Operation name (e.g., "store_message")
            latency: Operation latency in seconds
            success: Whether the operation succeeded
        """
        with self._lock:
            stats = self._storage_operations[operation]
            stats["count"] += 1
            stats["total_latency"] += latency
            if not success:
                stats["failures"] += 1
    
    def get_storage_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get storage operation statistics.
        
        Returns:
            Dictionary of operation stats
        """
        with self._lock:
            result = {}
            for operation, stats in self._storage_operations.items():
                count = stats["count"]
                avg_latency = stats["total_latency"] / count if count > 0 else 0
                result[operation] = {
                    "count": count,
                    "avg_latency": avg_latency,
                    "total_latency": stats["total_latency"],
                    "failures": stats["failures"],
                    "success_rate": (count - stats["failures"]) / count if count > 0 else 0
                }
            return result
    
    def track_connection(self, human_id: str, event: str) -> None:
        """
        Track connection events per human.
        
        Args:
            human_id: Unique identifier for the human
            event: "connect" or "disconnect"
        """
        with self._lock:
            if event == "connect":
                self._connections_per_human[human_id] += 1
                self._total_connections += 1
            elif event == "disconnect" and self._connections_per_human[human_id] > 0:
                self._connections_per_human[human_id] -= 1
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.
        
        Returns:
            Dictionary of connection stats
        """
        with self._lock:
            active_connections = sum(1 for count in self._connections_per_human.values() if count > 0)
            return {
                **dict(self._connections_per_human),
                "total_connections": self._total_connections,
                "active_connections": active_connections,
                "unique_humans": len(self._connections_per_human)
            }
    
    def update_queue_depth(self, conversation_id: str, depth: int) -> None:
        """
        Update queue depth for a conversation.
        
        Args:
            conversation_id: The conversation ID
            depth: Current queue depth
        """
        with self._lock:
            self._queue_depths[conversation_id] = depth
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue depth statistics.
        
        Returns:
            Dictionary of queue stats
        """
        with self._lock:
            if not self._queue_depths:
                return {
                    "max_queue_depth": 0,
                    "avg_queue_depth": 0,
                    "conversations_with_queues": 0
                }
            
            depths = list(self._queue_depths.values())
            return {
                **self._queue_depths,
                "max_queue_depth": max(depths),
                "avg_queue_depth": sum(depths) / len(depths),
                "conversations_with_queues": len(depths),
                "queues_near_limit": sum(1 for d in depths if d > 900)  # Assuming 1000 limit
            }
    
    def track_conversation_pattern(self, conversation_id: str, human_count: int) -> None:
        """
        Track multi-human conversation patterns.
        
        Args:
            conversation_id: The conversation ID
            human_count: Number of humans in the conversation
        """
        with self._lock:
            if human_count == 1:
                self._conversation_patterns["single_human"] += 1
            else:
                self._conversation_patterns["multi_human"] += 1
            
            self._conversation_patterns["human_counts"].append(human_count)
    
    def get_conversation_patterns(self) -> Dict[str, Any]:
        """
        Get conversation pattern statistics.
        
        Returns:
            Dictionary of conversation patterns
        """
        with self._lock:
            human_counts = self._conversation_patterns["human_counts"]
            if not human_counts:
                return {
                    "single_human": 0,
                    "multi_human": 0,
                    "max_humans_in_conversation": 0,
                    "avg_humans_per_conversation": 0
                }
            
            return {
                "single_human": self._conversation_patterns["single_human"],
                "multi_human": self._conversation_patterns["multi_human"],
                "max_humans_in_conversation": max(human_counts),
                "avg_humans_per_conversation": sum(human_counts) / len(human_counts),
                "total_conversations": len(human_counts)
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics in a single call.
        
        Returns:
            Dictionary containing all metrics
        """
        return {
            "storage": self.get_storage_stats(),
            "connections": self.get_connection_stats(),
            "queues": self.get_queue_stats(),
            "conversation_patterns": self.get_conversation_patterns(),
            "timestamp": datetime.utcnow().isoformat()
        }