# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Storage module for conversation history.
Provides a unified interface for storing and retrieving conversation history,
similar to how retriever.py handles vector database operations.
"""

import os
import sys
import json
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod

from core.config import CONFIG
from core.embedding import get_embedding
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("storage")

@dataclass
class ConversationEntry:
    """
    Represents a single conversation entry (one exchange between user and assistant).
    """
    user_id: str                    # User ID (if logged in) or anonymous ID
    site: str                       # Site context for the conversation
    thread_id: str                  # Thread ID to group related conversations
    user_prompt: str                # The user's question/prompt
    response: str                   # The assistant's response
    time_of_creation: datetime      # Timestamp of creation
    conversation_id: str            # Unique ID for this conversation entry
    embedding: Optional[List[float]] = None  # Embedding vector for the conversation
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "user_id": self.user_id,
            "site": self.site,
            "thread_id": self.thread_id,
            "user_prompt": self.user_prompt,
            "response": self.response,
            "time_of_creation": self.time_of_creation.isoformat(),
            "conversation_id": self.conversation_id,
            "embedding": self.embedding
        }
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON format for API responses."""
        return {
            "id": self.conversation_id,
            "user_prompt": self.user_prompt,
            "response": self.response,
            "time": self.time_of_creation.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationEntry':
        """Create from dictionary."""
        data["time_of_creation"] = datetime.fromisoformat(data["time_of_creation"])
        return cls(**data)

class StorageProvider(ABC):
    """Abstract base class for storage providers."""
    
    @abstractmethod
    async def add_conversation(self, user_id: str, site: str, thread_id: Optional[str], 
                             user_prompt: str, response: str) -> ConversationEntry:
        """
        Add a conversation to storage.
        
        Args:
            user_id: User ID (if logged in) or anonymous ID
            site: Site context for the conversation
            thread_id: Thread ID for grouping. If None, create a new thread_id
            user_prompt: The user's question/prompt
            response: The assistant's response
            
        Returns:
            ConversationEntry: The created conversation entry with generated conversation_id and embedding
        """
        pass
    
    @abstractmethod
    async def get_recent_conversations(self, user_id: str, site: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve the N most recent conversations for a user and site, grouped by thread.
        
        Args:
            user_id: User ID to retrieve conversations for
            site: Site to filter by
            limit: Maximum number of conversations to retrieve
            
        Returns:
            List of thread objects, each containing:
            {
                "id": thread_id,
                "site": site,
                "conversations": [
                    {
                        "id": conversation_id,
                        "user_prompt": prompt,
                        "response": response,
                        "time": timestamp
                    },
                    ...
                ]  # sorted by date, oldest first
            }
        """
        pass
    
    @abstractmethod
    async def delete_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a specific conversation.
        
        Args:
            conversation_id: ID of the conversation to delete
            user_id: Optional user ID for access control
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        pass

    @abstractmethod
    async def search_conversations(self, query: str, user_id: Optional[str] = None, 
                                 site: Optional[str] = None, limit: int = 10) -> List[ConversationEntry]:
        """
        Search conversations using a query string.

        Args:
            query: The search query string
            user_id: Optional user ID to filter results
            site: Optional site to filter results
            limit: Maximum number of results to return

        Returns:
            List[ConversationEntry]: The search results
        """
        pass

# Global storage client instance
_storage_client = None
_storage_lock = asyncio.Lock()

async def get_storage_client() -> StorageProvider:
    """
    Get or create the storage client instance.
    
    Returns:
        StorageProvider: The storage provider instance
    """
    global _storage_client
    
    if _storage_client is not None:
        return _storage_client
    
    async with _storage_lock:
        # Double-check after acquiring lock
        if _storage_client is not None:
            return _storage_client
        
        # Get storage configuration from CONFIG
        storage_config = CONFIG.conversation_storage
        storage_type = storage_config.type
        
        logger.info(f"Initializing storage client with type: {storage_type}")
        
        if storage_type == 'qdrant':
            from storage_providers.qdrant_storage import QdrantStorageProvider
            _storage_client = QdrantStorageProvider(storage_config)
        elif storage_type == 'azure_ai_search':
            from storage_providers.azure_search_storage import AzureSearchStorageProvider
            _storage_client = AzureSearchStorageProvider(storage_config)
        elif storage_type == 'azure_cosmos':
            from storage_providers.cosmos_storage import CosmosStorageProvider
            _storage_client = CosmosStorageProvider(storage_config)
        elif storage_type == 'postgres':
            from storage_providers.postgres_storage import PostgresStorageProvider
            _storage_client = PostgresStorageProvider(storage_config)
        elif storage_type == 'memory':
            from storage_providers.memory_storage import MemoryStorageProvider
            _storage_client = MemoryStorageProvider(storage_config)
        else:
            # Default to Qdrant for now
            from storage_providers.qdrant_storage import QdrantStorageProvider
            logger.warning(f"Unknown storage type '{storage_type}', defaulting to Qdrant")
            _storage_client = QdrantStorageProvider(storage_config)
        
        # Initialize the storage provider
        await _storage_client.initialize()
        
        logger.info(f"Storage client initialized successfully")
        return _storage_client

async def add_conversation(user_id: str, site: str, thread_id: Optional[str], 
                         user_prompt: str, response: str) -> ConversationEntry:
    """
    Add a conversation to storage.
    
    Args:
        user_id: User ID (can be anonymous ID)
        site: Site context
        thread_id: Thread ID for grouping. If None, create a new thread_id
        user_prompt: User's question
        response: Assistant's response
        
    Returns:
        ConversationEntry: The stored conversation entry
    """
    client = await get_storage_client()
    return await client.add_conversation(user_id, site, thread_id, user_prompt, response)

async def get_recent_conversations(user_id: str, site: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent conversations for a user and site, grouped by thread.
    
    Args:
        user_id: User ID
        site: Site to filter by
        limit: Maximum number of conversations to return
        
    Returns:
        List of thread objects with conversations
    """
    client = await get_storage_client()
    return await client.get_recent_conversations(user_id, site, limit)

async def delete_conversation(conversation_id: str, user_id: Optional[str] = None) -> bool:
    """
    Delete a specific conversation.
    
    Args:
        conversation_id: Conversation ID to delete
        user_id: Optional user ID for access control
        
    Returns:
        bool: Success status
    """
    client = await get_storage_client()
    return await client.delete_conversation(conversation_id, user_id)

# Convenience function for migration from localStorage
async def migrate_from_localstorage(user_id: str, conversations_data: List[Dict[str, Any]]) -> int:
    """
    Migrate conversations from browser localStorage to server storage.
    
    Args:
        user_id: User ID to assign to migrated conversations
        conversations_data: List of conversation data from localStorage
        
    Returns:
        int: Number of conversations migrated
    """
    migrated_count = 0
    
    for conv_data in conversations_data:
        try:
            # Handle converted format from client
            thread_id = conv_data.get('thread_id', str(uuid.uuid4()))
            site = conv_data.get('site', 'all')
            user_prompt = conv_data.get('user_prompt', '')
            response = conv_data.get('response', '')
            
            if user_prompt and response:
                await add_conversation(
                    user_id=user_id,
                    site=site,
                    thread_id=thread_id,
                    user_prompt=user_prompt,
                    response=response
                )
                migrated_count += 1
                        
        except Exception as e:
            logger.error(f"Error migrating conversation: {e}")
            continue
    
    return migrated_count