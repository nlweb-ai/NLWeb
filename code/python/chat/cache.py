"""
Thread-safe in-memory cache for active conversations.
"""

from typing import Dict, List, Optional, Set
from collections import OrderedDict, deque
import threading
from datetime import datetime

from chat.schemas import ChatMessage, ParticipantInfo


class ConversationCache:
    """
    Thread-safe cache for active conversations.
    Uses LRU eviction for conversations and keeps only recent messages.
    """
    
    def __init__(self, max_conversations: int = 1000, max_messages_per_conversation: int = 100):
        """
        Initialize the cache.
        
        Args:
            max_conversations: Maximum number of conversations to cache
            max_messages_per_conversation: Maximum messages per conversation
        """
        self.max_conversations = max_conversations
        self.max_messages_per_conversation = max_messages_per_conversation
        
        # Thread-safe data structures
        self._lock = threading.RLock()
        self._conversations = OrderedDict()  # conversation_id -> deque of messages
        self._participants = {}  # conversation_id -> set of participants
        self._queue_sizes = {}  # conversation_id -> current queue size
        
        # Metrics
        self._cache_hits = 0
        self._cache_misses = 0
    
    def add_message(self, conversation_id: str, message: ChatMessage) -> None:
        """
        Add a message to the cache.
        Thread-safe operation.
        
        Args:
            conversation_id: The conversation ID
            message: The message to add
        """
        with self._lock:
            # Create conversation if it doesn't exist
            if conversation_id not in self._conversations:
                self._ensure_capacity()
                self._conversations[conversation_id] = deque(maxlen=self.max_messages_per_conversation)
                self._queue_sizes[conversation_id] = 0
            
            # Move to end (most recently used)
            self._conversations.move_to_end(conversation_id)
            
            # Add message
            self._conversations[conversation_id].append(message)
            
            # Update queue size
            self._queue_sizes[conversation_id] = self._queue_sizes.get(conversation_id, 0) + 1
    
    def get_messages(self, conversation_id: str, limit: Optional[int] = None) -> Optional[List[ChatMessage]]:
        """
        Get messages for a conversation.
        Thread-safe operation.
        
        Args:
            conversation_id: The conversation ID
            limit: Optional limit on number of messages
            
        Returns:
            List of messages or None if not cached
        """
        with self._lock:
            if conversation_id in self._conversations:
                self._cache_hits += 1
                # Move to end (most recently used)
                self._conversations.move_to_end(conversation_id)
                
                messages = list(self._conversations[conversation_id])
                if limit and limit < len(messages):
                    return messages[-limit:]
                return messages
            else:
                self._cache_misses += 1
                return None
    
    def has_conversation(self, conversation_id: str) -> bool:
        """
        Check if a conversation is cached.
        Thread-safe operation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            True if cached, False otherwise
        """
        with self._lock:
            return conversation_id in self._conversations
    
    def update_participants(self, conversation_id: str, participants: Set[ParticipantInfo]) -> None:
        """
        Update participants for a conversation.
        Thread-safe operation.
        
        Args:
            conversation_id: The conversation ID
            participants: Set of active participants
        """
        with self._lock:
            self._participants[conversation_id] = participants.copy()
    
    def get_participants(self, conversation_id: str) -> Optional[Set[ParticipantInfo]]:
        """
        Get participants for a conversation.
        Thread-safe operation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            Set of participants or None if not cached
        """
        with self._lock:
            if conversation_id in self._participants:
                return self._participants[conversation_id].copy()
            return None
    
    def get_queue_size(self, conversation_id: str) -> int:
        """
        Get current queue size for a conversation.
        Thread-safe operation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            Current queue size
        """
        with self._lock:
            return self._queue_sizes.get(conversation_id, 0)
    
    def update_queue_size(self, conversation_id: str, size: int) -> None:
        """
        Update queue size for a conversation.
        Thread-safe operation.
        
        Args:
            conversation_id: The conversation ID
            size: New queue size
        """
        with self._lock:
            self._queue_sizes[conversation_id] = size
    
    def evict_conversation(self, conversation_id: str) -> None:
        """
        Evict a conversation from cache.
        Thread-safe operation.
        
        Args:
            conversation_id: The conversation ID
        """
        with self._lock:
            if conversation_id in self._conversations:
                del self._conversations[conversation_id]
            if conversation_id in self._participants:
                del self._participants[conversation_id]
            if conversation_id in self._queue_sizes:
                del self._queue_sizes[conversation_id]
    
    def clear(self) -> None:
        """
        Clear the entire cache.
        Thread-safe operation.
        """
        with self._lock:
            self._conversations.clear()
            self._participants.clear()
            self._queue_sizes.clear()
            self._cache_hits = 0
            self._cache_misses = 0
    
    def get_metrics(self) -> Dict[str, any]:
        """
        Get cache metrics.
        Thread-safe operation.
        
        Returns:
            Dictionary of metrics
        """
        with self._lock:
            total_requests = self._cache_hits + self._cache_misses
            hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0
            
            return {
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "hit_rate": hit_rate,
                "total_requests": total_requests,
                "cached_conversations": len(self._conversations),
                "total_cached_messages": sum(len(msgs) for msgs in self._conversations.values())
            }
    
    def _ensure_capacity(self) -> None:
        """
        Ensure there's capacity for a new conversation.
        Evicts least recently used conversation if at capacity.
        Must be called with lock held.
        """
        if len(self._conversations) >= self.max_conversations:
            # Evict least recently used (first item)
            lru_conv_id = next(iter(self._conversations))
            self.evict_conversation(lru_conv_id)