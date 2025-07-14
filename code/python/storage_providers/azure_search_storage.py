# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Azure AI Search storage provider for conversation history.
"""

import os
import uuid
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchAlgorithmConfiguration,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    VectorSearchAlgorithmKind,
    SearchableField,
    SearchField
)
from azure.search.documents.models import VectorizedQuery

from core.storage import StorageProvider, ConversationEntry
from core.embedding import get_embedding
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("azure_search_storage")

class AzureSearchStorageProvider(StorageProvider):
    """Azure AI Search-based storage for conversation history."""
    
    def __init__(self, config):
        """
        Initialize Azure Search storage provider.
        
        Args:
            config: ConversationStorageConfig instance
        """
        self.config = config
        self.index_name = config.collection_name or 'nlweb_conversations'
        self.vector_size = config.vector_size
        
        # Azure Search connection settings
        self.endpoint = config.endpoint or config.url
        self.api_key = config.api_key
        
        if not self.endpoint or not self.api_key:
            raise ValueError("Azure Search endpoint and API key are required")
            
        # Strip quotes if present
        self.endpoint = self.endpoint.strip('"')
        self.api_key = self.api_key.strip('"')
        
        self.credential = AzureKeyCredential(self.api_key)
        self.index_client = None
        self.search_client = None
        
    async def initialize(self):
        """Initialize the Azure Search client and create index if needed."""
        try:
            # Create index client
            self.index_client = SearchIndexClient(
                endpoint=self.endpoint,
                credential=self.credential
            )
            
            # Check if index exists
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.index_client.get_index, self.index_name
                )
                logger.info(f"Index '{self.index_name}' already exists")
            except Exception:
                # Index doesn't exist, create it
                logger.info(f"Creating index '{self.index_name}'")
                await self._create_index()
            
            # Create search client
            self.search_client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=self.credential
            )
            
            logger.info("Azure Search storage provider initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure Search storage: {e}")
            raise
    
    async def _create_index(self):
        """Create the conversation index with appropriate fields."""
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="conversation_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="user_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="site", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SimpleField(name="thread_id", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="user_prompt", type=SearchFieldDataType.String),
            SearchableField(name="response", type=SearchFieldDataType.String),
            SimpleField(name="time_of_creation", type=SearchFieldDataType.DateTimeOffset, 
                       filterable=True, sortable=True),
            SearchField(
                name="embedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.vector_size,
                vector_search_profile_name="conversation-vector-profile"
            )
        ]
        
        # Configure vector search
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="conversation-hnsw",
                    kind=VectorSearchAlgorithmKind.HNSW,
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine"
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="conversation-vector-profile",
                    algorithm_configuration_name="conversation-hnsw"
                )
            ]
        )
        
        # Create index
        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search
        )
        
        await asyncio.get_event_loop().run_in_executor(
            None, self.index_client.create_or_update_index, index
        )
        logger.info(f"Created index '{self.index_name}'")
    
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
            
            # Create document for Azure Search
            document = {
                "id": str(uuid.uuid4()),  # Azure Search requires a unique document ID
                "conversation_id": entry.conversation_id,
                "user_id": entry.user_id,
                "site": entry.site,
                "thread_id": entry.thread_id,
                "user_prompt": entry.user_prompt,
                "response": entry.response,
                "time_of_creation": entry.time_of_creation,
                "embedding": entry.embedding
            }
            
            # Upload document
            await asyncio.get_event_loop().run_in_executor(
                None, self.search_client.upload_documents, [document]
            )
            
            logger.debug(f"Stored conversation {entry.conversation_id} in thread {entry.thread_id}")
            return entry
            
        except Exception as e:
            logger.error(f"Failed to add conversation: {e}")
            raise
    
    async def get_recent_conversations(self, user_id: str, site: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve the N most recent conversations for a user and site, grouped by thread.
        Returns thread objects with conversations sorted by date (oldest first within each thread).
        """
        try:
            # Build filter
            if site == 'all':
                filter_str = f"user_id eq '{user_id}'"
            else:
                filter_str = f"user_id eq '{user_id}' and site eq '{site}'"
            
            # Search for conversations
            def search_sync():
                return list(self.search_client.search(
                    search_text="*",
                    filter=filter_str,
                    select=["conversation_id", "thread_id", "user_prompt", "response", "time_of_creation", "site"],
                    order_by=["time_of_creation desc"],
                    top=limit
                ))
            
            results = await asyncio.get_event_loop().run_in_executor(None, search_sync)
            
            # Group conversations by thread_id
            threads_dict = {}
            for result in results:
                thread_id = result["thread_id"]
                
                if thread_id not in threads_dict:
                    threads_dict[thread_id] = {
                        "id": thread_id,
                        "site": result.get("site", site),  # Use actual site from the conversation
                        "conversations": []
                    }
                
                # Add conversation to thread
                threads_dict[thread_id]["conversations"].append({
                    "id": result["conversation_id"],
                    "user_prompt": result["user_prompt"],
                    "response": result["response"],
                    "time": result["time_of_creation"].isoformat() if hasattr(result["time_of_creation"], 'isoformat') else str(result["time_of_creation"])
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
            # Build filter to find the document
            filter_str = f"conversation_id eq '{conversation_id}'"
            if user_id:
                filter_str += f" and user_id eq '{user_id}'"
            
            # Find the document
            def search_sync():
                return list(self.search_client.search(
                    search_text="*",
                    filter=filter_str,
                    select=["id"],
                    top=1
                ))
            
            results = await asyncio.get_event_loop().run_in_executor(None, search_sync)
            
            if results:
                # Delete the document
                doc_id = results[0]["id"]
                await asyncio.get_event_loop().run_in_executor(
                    None, self.search_client.delete_documents, [{"id": doc_id}]
                )
                logger.debug(f"Deleted conversation {conversation_id}")
                return True
            else:
                logger.warning(f"Conversation {conversation_id} not found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False
    
    async def search_conversations(self, query: str, user_id: Optional[str] = None, 
                                 site: Optional[str] = None, limit: int = 10) -> List[ConversationEntry]:
        """Search conversations using vector similarity and/or text search."""
        try:
            # Get embedding for the query
            query_embedding = await get_embedding(query)
            
            # Build filter
            filters = []
            if user_id:
                filters.append(f"user_id eq '{user_id}'")
            if site:
                filters.append(f"site eq '{site}'")
            filter_str = " and ".join(filters) if filters else None
            
            # Create vectorized query
            vector_query = VectorizedQuery(
                vector=query_embedding,
                k_nearest_neighbors=limit,
                fields="embedding"
            )
            
            # Search with both text and vector
            def search_sync():
                return list(self.search_client.search(
                    search_text=query,
                    vector_queries=[vector_query],
                    filter=filter_str,
                    select=["conversation_id", "user_id", "site", "thread_id", 
                           "user_prompt", "response", "time_of_creation"],
                    top=limit
                ))
            
            results = await asyncio.get_event_loop().run_in_executor(None, search_sync)
            
            # Convert to ConversationEntry objects
            conversations = []
            for result in results:
                conversations.append(ConversationEntry(
                    conversation_id=result["conversation_id"],
                    user_id=result["user_id"],
                    site=result["site"],
                    thread_id=result["thread_id"],
                    user_prompt=result["user_prompt"],
                    response=result["response"],
                    time_of_creation=datetime.fromisoformat(result["time_of_creation"]) 
                        if isinstance(result["time_of_creation"], str) 
                        else result["time_of_creation"],
                    embedding=None  # We don't return embeddings in search results
                ))
            
            return conversations
            
        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            return []