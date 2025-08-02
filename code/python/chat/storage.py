"""
Chat storage interface and client.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import time
import importlib
from datetime import datetime

from chat.schemas import ChatMessage, Conversation
from chat.metrics import ChatMetrics
from core.config import CONFIG


class ChatStorageInterface(ABC):
    """Abstract interface for chat storage backends"""
    
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
    
    def _create_backend(self, storage_config: Dict[str, Any]) -> ChatStorageInterface:
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


# Helper function for getting config (for testing)
def get_config():
    """Get configuration"""
    return CONFIG