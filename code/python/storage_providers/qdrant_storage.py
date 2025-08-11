# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Qdrant storage provider for conversation history.
"""

import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from core.storage import StorageProvider, ConversationEntry
from core.embedding import get_embedding
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("qdrant_storage")

class QdrantStorageProvider(StorageProvider):
    """Qdrant-based storage for conversation history."""
    
    def __init__(self, config):
        """
        Initialize Qdrant storage provider.
        
        Args:
            config: ConversationStorageConfig instance
        """
        self.config = config
        self.collection_name = config.collection_name or 'nlweb_conversations'
        self.vector_size = config.vector_size
        
        # Qdrant connection settings
        self.url = config.url
        self.api_key = config.api_key
        self.path = config.database_path
        
        self.client = None
        
    async def initialize(self):
        """Initialize the Qdrant client and create collection if needed."""
        try:
            # Create client based on configuration
            if self.url:
                logger.info(f"Connecting to Qdrant at {self.url}")
                self.client = AsyncQdrantClient(url=self.url, api_key=self.api_key)
            else:
                # Local file-based storage
                logger.info(f"Using local Qdrant storage at {self.path}")
                self.client = AsyncQdrantClient(path=self.path)
            
            # Check if collection exists
            collections = await self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Creating collection '{self.collection_name}'")
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE
                    )
                )
                
                # Create payload indexes for efficient filtering
                # Note: These have no effect in local mode but are important for server mode
                try:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", message="Payload indexes have no effect in the local Qdrant")
                        await self.client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name="user_id",
                            field_schema=models.PayloadSchemaType.KEYWORD
                        )
                        await self.client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name="thread_id",
                            field_schema=models.PayloadSchemaType.KEYWORD
                        )
                        await self.client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name="site",
                            field_schema=models.PayloadSchemaType.KEYWORD
                        )
                        await self.client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name="time_of_creation",
                            field_schema=models.PayloadSchemaType.DATETIME
                        )
                except Exception as e:
                    # Silently ignore index creation errors in local mode
                    pass
                
            logger.info("Qdrant storage provider initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant storage: {e}")
            raise
    
    async def add_conversation(self, user_id: str, site: str, thread_id: Optional[str], 
                             user_prompt: str, response: str) -> ConversationEntry:
        """
        Add a conversation to storage.
        
        If thread_id is None, creates a new thread_id.
        Creates conversation_id and computes embedding from user_prompt + response.
        """
        try:
            # Generate thread_id if not provided
            if thread_id is None:
                thread_id = str(uuid.uuid4())
                logger.info(f"Created new thread_id: {thread_id}")
            
            # Generate conversation_id
            conversation_id = str(uuid.uuid4())
            
            # Generate embedding for the conversation
            # Combine user prompt and response for better context
            conversation_text = f"User: {user_prompt}\nAssistant: {response}"
            embedding = await get_embedding(conversation_text)
            
            # Create conversation entry
            entry = ConversationEntry(
                user_id=user_id,
                site=site,
                thread_id=thread_id,
                user_prompt=user_prompt,
                response=response,
                time_of_creation=datetime.utcnow(),
                conversation_id=conversation_id,
                embedding=embedding
            )
            
            # Convert to point format
            point = models.PointStruct(
                id=str(uuid.uuid4()),  # Generate unique point ID
                vector=entry.embedding,
                payload={
                    "conversation_id": entry.conversation_id,
                    "user_id": entry.user_id,
                    "site": entry.site,
                    "thread_id": entry.thread_id,
                    "user_prompt": entry.user_prompt,
                    "response": entry.response,
                    "time_of_creation": entry.time_of_creation.isoformat()
                }
            )
            
            # Store in Qdrant
            await self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug(f"Stored conversation {entry.conversation_id} in thread {entry.thread_id}")
            return entry
            
        except Exception as e:
            logger.error(f"Failed to add conversation: {e}")
            raise
    
    async def get_conversation_thread(self, thread_id: str, user_id: Optional[str] = None) -> List[ConversationEntry]:
        """Retrieve all conversations in a thread."""
        try:
            # Build filter
            must_conditions = [
                models.FieldCondition(
                    key="thread_id",
                    match=models.MatchValue(value=thread_id)
                )
            ]
            
            if user_id:
                must_conditions.append(
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id)
                    )
                )
            
            # Search without vector (just filter)
            results = await self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(must=must_conditions),
                limit=1000,  # Reasonable limit for a thread
                with_payload=True,
                with_vectors=True
            )
            
            # Convert to ConversationEntry objects
            conversations = []
            for point in results[0]:
                payload = point.payload
                conversations.append(ConversationEntry(
                    conversation_id=payload["conversation_id"],
                    user_id=payload["user_id"],
                    site=payload["site"],
                    thread_id=payload["thread_id"],
                    user_prompt=payload["user_prompt"],
                    response=payload["response"],
                    time_of_creation=datetime.fromisoformat(payload["time_of_creation"]),
                    embedding=point.vector
                ))
            
            # Sort by time
            conversations.sort(key=lambda x: x.time_of_creation)
            return conversations
            
        except Exception as e:
            logger.error(f"Failed to get conversation thread: {e}")
            return []
    
    async def get_recent_conversations(self, user_id: str, site: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve the N most recent conversations for a user and site, grouped by thread.
        Returns thread objects with conversations sorted by date (oldest first within each thread).
        """
        try:
            # Build filter conditions
            must_conditions = [
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id)
                )
            ]
            
            # Only filter by site if it's not 'all'
            if site != 'all':
                must_conditions.append(
                    models.FieldCondition(
                        key="site",
                        match=models.MatchValue(value=site)
                    )
                )
            
            filter_condition = models.Filter(must=must_conditions)
            
            # Get conversations
            results = await self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=filter_condition,
                limit=limit,
                with_payload=True,
                with_vectors=False  # Don't need vectors for this operation
            )
            
            # Group conversations by thread_id
            threads_dict = {}
            for point in results[0]:
                payload = point.payload
                thread_id = payload["thread_id"]
                
                if thread_id not in threads_dict:
                    threads_dict[thread_id] = {
                        "id": thread_id,
                        "site": payload["site"],  # Use actual site from the conversation
                        "conversations": []
                    }
                
                # Add conversation to thread
                threads_dict[thread_id]["conversations"].append({
                    "id": payload["conversation_id"],
                    "user_prompt": payload["user_prompt"],
                    "response": payload["response"],
                    "time": payload["time_of_creation"]
                })
            
            # Sort conversations within each thread by time (oldest first)
            for thread in threads_dict.values():
                thread["conversations"].sort(key=lambda x: x["time"])
            
            # Convert to list and sort threads by most recent conversation
            threads_list = list(threads_dict.values())
            threads_list.sort(
                key=lambda t: t["conversations"][-1]["time"] if t["conversations"] else "",
                reverse=True
            )
            
            return threads_list
            
        except Exception as e:
            logger.error(f"Failed to get recent conversations: {e}")
            return []
    
    
    async def delete_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> bool:
        """Delete a specific conversation entry."""
        try:
            # Build filter
            must_conditions = [
                models.FieldCondition(
                    key="conversation_id",
                    match=models.MatchValue(value=conversation_id)
                )
            ]
            
            if user_id:
                must_conditions.append(
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id)
                    )
                )
            
            # Delete by filter
            result = await self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(must=must_conditions)
                )
            )
            
            logger.debug(f"Deleted conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False
    
    async def search_conversations(self, query: str, user_id: Optional[str] = None, 
        site: Optional[str] = None, limit: int = 10) -> List[ConversationEntry]:
        """
        To be implemented: Search conversations using a text query.
        This will likely involve using the vector search capabilities of Qdrant.
        """
        # TODO: implement this method
        raise NotImplementedError("search_conversations() not implemented yet")