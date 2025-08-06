"""
Chat storage interface and client.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Set
import time
import importlib
from datetime import datetime

from chat.schemas import ChatMessage, Conversation, ParticipantInfo
from chat.metrics import ChatMetrics
from core.config import CONFIG


class SimpleChatStorageInterface(ABC):
    """Simple abstract interface for chat storage - just store and retrieve messages"""
    
    @abstractmethod
    async def store_message(self, message: ChatMessage) -> None:
        """
        Store a chat message.
        
        Args:
            message: The message to store
        """
        pass
    
    @abstractmethod
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
            after_sequence_id: Ignored in simple implementation
            
        Returns:
            List of messages in order they were added
        """
        pass


class OldChatStorageInterface(ABC):
    """Abstract interface for chat storage backends (OLD - DO NOT USE)"""
    
    @abstractmethod
    async def store_message(self, message: ChatMessage) -> None:
        """
        Store a chat message.
        Must handle deduplication by message_id.
        Must check queue limits before storing.
        
        Args:
            message: The message to store
            
        Raises:
            QueueFullError: If conversation queue is full
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def get_next_sequence_id(self, conversation_id: str) -> int:
        """
        Get the next sequence ID for a conversation.
        Must be atomic to handle concurrent requests from multiple humans.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            The next sequence ID
        """
        pass
    
    @abstractmethod
    async def update_conversation(self, conversation: Conversation) -> None:
        """
        Update conversation metadata.
        
        Args:
            conversation: The conversation to update
        """
        pass
    
    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        Get conversation metadata.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            The conversation or None if not found
        """
        pass
    
    @abstractmethod
    async def create_conversation(self, conversation: Conversation) -> None:
        """
        Create a new conversation.
        
        Args:
            conversation: The conversation to create
        """
        pass
    
    @abstractmethod
    async def is_participant(self, conversation_id: str, user_id: str) -> bool:
        """
        Check if user is participant in conversation.
        
        Args:
            conversation_id: The conversation ID
            user_id: The user ID to check
            
        Returns:
            True if user is a participant, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_participant_count(self, conversation_id: str) -> int:
        """
        Get current participant count for a conversation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            Number of active participants
        """
        pass
    
    @abstractmethod
    async def update_participants(
        self, 
        conversation_id: str, 
        participants: Set[ParticipantInfo]
    ) -> None:
        """
        Update participant list atomically.
        
        Args:
            conversation_id: The conversation ID
            participants: New set of participants
        """
        pass
    
    @abstractmethod
    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Conversation]:
        """
        Get conversations for a specific user.
        
        Args:
            user_id: The user ID
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            
        Returns:
            List of conversations where user is a participant
        """
        pass


class SimpleChatStorageClient:
    """
    Simple client for chat storage - just wraps the storage backend.
    """
    
    def __init__(self, backend: SimpleChatStorageInterface):
        """
        Initialize storage client.
        
        Args:
            backend: The storage backend to use
        """
        self.backend = backend
    
    async def store_message(self, message: ChatMessage) -> None:
        """Store a message"""
        await self.backend.store_message(message)
    
    async def get_conversation_messages(
        self, 
        conversation_id: str, 
        limit: int = 100,
        after_sequence_id: Optional[int] = None
    ) -> List[ChatMessage]:
        """Get messages for a conversation"""
        return await self.backend.get_conversation_messages(
            conversation_id, limit, after_sequence_id
        )


class ChatStorageClient:
    """
    Client that routes to appropriate storage backend based on configuration.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize storage client.
        
        Args:
            config: Optional config override for testing
        """
        if config is None:
            # Get config from CONFIG object
            config_dict = CONFIG.to_dict() if hasattr(CONFIG, 'to_dict') else CONFIG.__dict__
            config = config_dict
        
        # Get chat storage config
        chat_config = config.get("chat", {}) if isinstance(config, dict) else getattr(config, "chat", {})
        storage_config = chat_config.get("storage", {}) if isinstance(chat_config, dict) else getattr(chat_config, "storage", {})
        
        self.backend_type = storage_config.get("backend", "memory")
        self.metrics = ChatMetrics()
        
        # Initialize the backend
        self.backend = self._create_backend(storage_config)
    
    def _create_backend(self, storage_config: Dict[str, Any]) -> OldChatStorageInterface:
        """
        Create the appropriate storage backend.
        
        Args:
            storage_config: Storage configuration
            
        Returns:
            Storage backend instance
        """
        backend_type = storage_config.get("backend", "memory")
        
        # Map backend types to modules
        backend_map = {
            "memory": "chat_storage_providers.memory_storage.MemoryStorage",
            "azure": "chat_storage_providers.azure_storage.AzureStorage",
            "qdrant": "chat_storage_providers.qdrant_storage.QdrantStorage",
            "elastic": "chat_storage_providers.elastic_storage.ElasticStorage"
        }
        
        if backend_type not in backend_map:
            raise ValueError(f"Unknown storage backend: {backend_type}")
        
        # Import and instantiate the backend
        module_path, class_name = backend_map[backend_type].rsplit(".", 1)
        module = importlib.import_module(module_path)
        backend_class = getattr(module, class_name)
        
        # Pass backend-specific config
        backend_config = storage_config.get(backend_type, {})
        backend_config["queue_size_limit"] = storage_config.get("queue_size_limit", 1000)
        
        return backend_class(backend_config)
    
    async def store_message(self, message: ChatMessage) -> None:
        """Store a message with metrics tracking"""
        start_time = time.time()
        try:
            await self.backend.store_message(message)
            self.metrics.record_storage_operation("store_message", time.time() - start_time)
        except Exception as e:
            self.metrics.record_storage_operation("store_message", time.time() - start_time, success=False)
            raise
    
    async def get_conversation_messages(
        self, 
        conversation_id: str, 
        limit: int = 100,
        after_sequence_id: Optional[int] = None
    ) -> List[ChatMessage]:
        """Get messages with metrics tracking"""
        start_time = time.time()
        try:
            messages = await self.backend.get_conversation_messages(
                conversation_id, limit, after_sequence_id
            )
            self.metrics.record_storage_operation("get_messages", time.time() - start_time)
            return messages
        except Exception as e:
            self.metrics.record_storage_operation("get_messages", time.time() - start_time, success=False)
            raise
    
    async def get_next_sequence_id(self, conversation_id: str) -> int:
        """Get next sequence ID with metrics tracking"""
        start_time = time.time()
        try:
            seq_id = await self.backend.get_next_sequence_id(conversation_id)
            self.metrics.record_storage_operation("get_sequence_id", time.time() - start_time)
            return seq_id
        except Exception as e:
            self.metrics.record_storage_operation("get_sequence_id", time.time() - start_time, success=False)
            raise
    
    async def update_conversation(self, conversation: Conversation) -> None:
        """Update conversation with metrics tracking"""
        start_time = time.time()
        try:
            await self.backend.update_conversation(conversation)
            self.metrics.record_storage_operation("update_conversation", time.time() - start_time)
            
            # Track multi-human patterns
            human_count = len([p for p in conversation.active_participants if p.is_human()])
            self.metrics.track_conversation_pattern(conversation.conversation_id, human_count)
        except Exception as e:
            self.metrics.record_storage_operation("update_conversation", time.time() - start_time, success=False)
            raise
    
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation with metrics tracking"""
        start_time = time.time()
        try:
            conv = await self.backend.get_conversation(conversation_id)
            self.metrics.record_storage_operation("get_conversation", time.time() - start_time)
            return conv
        except Exception as e:
            self.metrics.record_storage_operation("get_conversation", time.time() - start_time, success=False)
            raise
    
    async def create_conversation(self, conversation: Conversation) -> None:
        """Create a conversation with metrics tracking"""
        start_time = time.time()
        try:
            await self.backend.create_conversation(conversation)
            self.metrics.record_storage_operation("create_conversation", time.time() - start_time)
        except Exception as e:
            self.metrics.record_storage_operation("create_conversation", time.time() - start_time, success=False)
            raise
    
    async def is_participant(self, conversation_id: str, user_id: str) -> bool:
        """Check if user is participant with metrics tracking"""
        start_time = time.time()
        try:
            result = await self.backend.is_participant(conversation_id, user_id)
            self.metrics.record_storage_operation("is_participant", time.time() - start_time)
            return result
        except Exception as e:
            self.metrics.record_storage_operation("is_participant", time.time() - start_time, success=False)
            raise
    
    async def get_participant_count(self, conversation_id: str) -> int:
        """Get participant count with metrics tracking"""
        start_time = time.time()
        try:
            count = await self.backend.get_participant_count(conversation_id)
            self.metrics.record_storage_operation("get_participant_count", time.time() - start_time)
            return count
        except Exception as e:
            self.metrics.record_storage_operation("get_participant_count", time.time() - start_time, success=False)
            raise
    
    async def update_participants(self, conversation_id: str, participants: Set[ParticipantInfo]) -> None:
        """Update participants with metrics tracking"""
        start_time = time.time()
        try:
            await self.backend.update_participants(conversation_id, participants)
            self.metrics.record_storage_operation("update_participants", time.time() - start_time)
            
            # Track participant count changes
            self.metrics.track_conversation_pattern(conversation_id, len(participants))
        except Exception as e:
            self.metrics.record_storage_operation("update_participants", time.time() - start_time, success=False)
            raise
    
    async def get_user_conversations(
        self, 
        user_id: str, 
        limit: int = 20, 
        offset: int = 0
    ) -> List[Conversation]:
        """Get user conversations with metrics tracking"""
        start_time = time.time()
        try:
            conversations = await self.backend.get_user_conversations(user_id, limit, offset)
            self.metrics.record_storage_operation("get_user_conversations", time.time() - start_time)
            return conversations
        except Exception as e:
            self.metrics.record_storage_operation("get_user_conversations", time.time() - start_time, success=False)
            raise


# Helper function for getting config (for testing)
def get_config():
    """Get configuration"""
    return CONFIG