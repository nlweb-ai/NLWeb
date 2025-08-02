"""
In-memory storage implementation for chat system.
Used for development and testing.
"""

from typing import Dict, List, Optional, Set
import asyncio
from datetime import datetime
from collections import defaultdict

from chat.schemas import ChatMessage, Conversation, QueueFullError
from chat.storage import ChatStorageInterface


class MemoryStorage(ChatStorageInterface):
    """
    In-memory implementation of chat storage.
    Thread-safe using asyncio locks.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize memory storage.
        
        Args:
            config: Storage configuration
        """
        self.config = config
        self.queue_size_limit = config.get("queue_size_limit", 1000)
        
        # Storage structures
        self._messages: Dict[str, List[ChatMessage]] = defaultdict(list)
        self._conversations: Dict[str, Conversation] = {}
        self._sequence_counters: Dict[str, int] = defaultdict(int)
        self._message_ids: Set[str] = set()  # For deduplication
        
        # Locks for thread safety
        self._sequence_lock = asyncio.Lock()
        self._storage_lock = asyncio.Lock()
    
    async def store_message(self, message: ChatMessage) -> None:
        """
        Store a message with deduplication and queue limit checking.
        
        Args:
            message: The message to store
            
        Raises:
            QueueFullError: If conversation queue is full
        """
        async with self._storage_lock:
            # Check for duplicate message ID
            if message.message_id in self._message_ids:
                return  # Already stored, skip
            
            # Check queue limit
            conv_id = message.conversation_id
            current_size = len(self._messages[conv_id])
            
            # Get conversation to check queue limit
            conversation = self._conversations.get(conv_id)
            if conversation:
                limit = conversation.queue_size_limit
            else:
                limit = self.queue_size_limit
            
            if current_size >= limit:
                raise QueueFullError(
                    conversation_id=conv_id,
                    queue_size=current_size,
                    limit=limit
                )
            
            # Store the message
            self._messages[conv_id].append(message)
            self._message_ids.add(message.message_id)
            
            # Update conversation message count
            if conversation:
                conversation.message_count = len(self._messages[conv_id])
                conversation.updated_at = datetime.utcnow()
    
    async def get_conversation_messages(
        self, 
        conversation_id: str, 
        limit: int = 100,
        after_sequence_id: Optional[int] = None
    ) -> List[ChatMessage]:
        """
        Get messages for a conversation.
        
        Args:
            conversation_id: The conversation ID
            limit: Maximum number of messages to return
            after_sequence_id: Only return messages after this sequence ID
            
        Returns:
            List of messages ordered by sequence_id
        """
        async with self._storage_lock:
            messages = self._messages.get(conversation_id, [])
            
            # Filter by sequence ID if specified
            if after_sequence_id is not None:
                messages = [m for m in messages if m.sequence_id > after_sequence_id]
            
            # Sort by sequence ID
            messages = sorted(messages, key=lambda m: m.sequence_id)
            
            # Apply limit
            if len(messages) > limit:
                messages = messages[-limit:]
            
            return messages
    
    async def get_next_sequence_id(self, conversation_id: str) -> int:
        """
        Get the next sequence ID for a conversation.
        Atomic operation to handle concurrent requests.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            The next sequence ID
        """
        async with self._sequence_lock:
            # Increment and return
            self._sequence_counters[conversation_id] += 1
            return self._sequence_counters[conversation_id]
    
    async def update_conversation(self, conversation: Conversation) -> None:
        """
        Update conversation metadata.
        
        Args:
            conversation: The conversation to update
        """
        async with self._storage_lock:
            self._conversations[conversation.conversation_id] = conversation
    
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        Get conversation metadata.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            The conversation or None if not found
        """
        async with self._storage_lock:
            return self._conversations.get(conversation_id)