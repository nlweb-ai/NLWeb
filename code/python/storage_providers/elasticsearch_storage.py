# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Elasticsearch storage provider for conversation history.
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from elasticsearch import AsyncElasticsearch
from core.storage import StorageProvider, ConversationEntry
from core.embedding import get_embedding
from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

logger = get_configured_logger("elasticsearch_storage")

class ElasticsearchStorageProvider(StorageProvider):
    """Elasticsearch-based storage for conversation history."""

    def __init__(self, config):
        """
        Initialize Elasticsearch storage provider.

        Args:
            config: ConversationStorageConfig instance
        """
        self.config = config
        self.index_name = config.collection_name or 'nlweb_conversations'
        
        # Check Elasticsearch settings
        if self.config.type != 'elasticsearch':
            error_msg = f"Invalid storage type: {self.config.type}. Expected 'elasticsearch'."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if self.config.url is None:
            error_msg = f"The ELASTICSEARCH_URL env is empty for Elasticsearch storage"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if self.config.api_key is None:
            error_msg = f"The ELASTICSEARCH_API_KEY env is empty for Elasticsearch storage"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.es_client = None

    async def _get_es_client(self) -> AsyncElasticsearch:
        """
        Get or initialize Elasticsearch client.
        
        Returns:
            AsyncElasticsearch: Elasticsearch async client instance
        """
        if self.es_client:
            return self.es_client
       
        try:
            logger.info(f"Initializing Elasticsearch client for storage provider on index '{self.index_name}'")
            
            # Create client with the determined parameters
            client = AsyncElasticsearch(hosts=self.config.url, api_key=self.config.api_key)

            await self._create_index_if_not_exists(client)
            logger.info(f"Successfully initialized Elasticsearch client for storage provider on index '{self.index_name}'")
            self.es_client = client

            return self.es_client

        except Exception as e:
            logger.exception(f"Failed to initialize Elasticsearch client: {str(e)}")
            raise

    async def _create_index_if_not_exists(self, client: AsyncElasticsearch) -> bool:
        """
        Create the Elasticsearch index with proper vector mapping if it doesn't exist.
        
        Args:
            index_name: Optional index name (defaults to configured index name)
            
        Returns:
            bool: True if index was created, False if it already existed
        """
        # Check if index already exists
        if await client.indices.exists(index = self.index_name):
            logger.info(f"Index {self.index_name} already exists")
            return False
        
        vector_type = self.config.vector_type or {
            "type": "dense_vector"
        }
        # Define index mapping for conversation entries
        properties = {
            "user_id": {
                "type": "keyword"
            },
            "site": {
                "type": "keyword"
            },
            "thread_id": {
                "type": "keyword"
            },
            "user_prompt": {
                "type": "text"
            },
            "response": {
                "type": "text"
            },
            "time_of_creation": {
                "type": "date"
            },
            "conversation_id": {
                "type": "keyword"
            },
            "embedding": vector_type
        }
        
        try:
            await client.indices.create(index=self.index_name, mappings={'properties' : properties})           
            logger.info(f"Successfully created index {self.index_name} with vector mapping")
            return True
                
        except Exception as e:
            error_details = str(e)           
            logger.exception(f"Error creating index {self.index_name}: {error_details}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Elasticsearch index creation failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": error_details,
                    "index_name": self.index_name,
                    "mapping": properties
                }
            )
            raise

    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def close(self):
        """Close the Elasticsearch client connections"""
        if self.es_client:
            try:
                await self.es_client.close()
                logger.debug("Elasticsearch client connection closed")
            except Exception as e:
                logger.warning(f"Error closing Elasticsearch client: {str(e)}")
            finally:
                self.es_client = None
    
    async def add_conversation(self, user_id: str, site: str, thread_id: Optional[str], 
                             user_prompt: str, response: str) -> ConversationEntry:
        """
        Add a conversation to storage.
        
        If thread_id is None, creates a new thread_id.
        Creates conversation_id and computes embedding from user_prompt + response.

        Args:
            user_id: The user ID associated with the conversation
            site: The site where the conversation took place
            thread_id: The thread ID of the conversation (optional)
            user_prompt: The user's prompt in the conversation
            response: The assistant's response in the conversation

        Returns:
            ConversationEntry: The conversation entry created
        """
        try:
            client = await self._get_es_client()

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
                time_of_creation=datetime.now(timezone.utc),
                conversation_id=conversation_id,
                embedding=embedding
            )
            
            # Store in Elasticsearch
            await client.index(
                index=self.index_name,
                document={
                    "conversation_id": entry.conversation_id,
                    "user_id": entry.user_id,
                    "site": entry.site,
                    "thread_id": entry.thread_id,
                    "user_prompt": entry.user_prompt,
                    "response": entry.response,
                    "time_of_creation": entry.time_of_creation.isoformat(),
                    "embedding": entry.embedding
                }
            )
            
            logger.debug(f"Stored conversation {entry.conversation_id} in thread {entry.thread_id}")
            return entry
            
        except Exception as e:
            logger.error(f"Failed to add conversation: {e}")
            raise
    
    async def get_conversation_thread(self, thread_id: str, user_id: Optional[str] = None) -> List[ConversationEntry]:
        """
        Retrieve all conversations in a thread.

        Args:
            thread_id: The thread ID of the conversation
            user_id: The user ID associated with the conversation (optional)

        Returns:
            List[ConversationEntry]: A list of conversation entries in the thread
        """
        try:
            client = await self._get_es_client()

            query = {
                "bool": {
                    "filter": [
                        {"term": {"thread_id": thread_id}}
                    ]
                }
            }
            sort = [{"time_of_creation": {"order": "asc"}}]
            if user_id:
                query["bool"]["filter"].append(
                    {"term": {"user_id": user_id}}
                )

            # Search using filter and sort
            response = await client.search(
                index=self.index_name,
                query=query,
                sort=sort
            )

            # Convert to ConversationEntry objects
            conversations = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                conversations.append(ConversationEntry(
                    conversation_id=source.get("conversation_id", ""),
                    user_id=source.get("user_id", ""),
                    site=source.get("site", ""),
                    thread_id=source.get("thread_id", ""),
                    user_prompt=source.get("user_prompt", ""),
                    response=source.get("response", ""),
                    time_of_creation=datetime.fromisoformat(source.get("time_of_creation", "")),
                    embedding=source.get("embedding", [])
                ))

            return conversations
            
        except Exception as e:
            logger.error(f"Failed to get conversation thread: {e}")
            return []
    
    async def get_recent_conversations(self, user_id: str, site: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve the N most recent conversations for a user and site, grouped by thread.
        Returns thread objects with conversations sorted by date (oldest first within each thread).

        Args:
            user_id: User ID to retrieve conversations for
            site: Site to filter by
            limit: Maximum number of conversations to retrieve (default 50)

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
        try:
            client = await self._get_es_client()

            query = {
                "bool": {
                    "filter": [
                        {"term": {"user_id": user_id}}
                    ]
                }
            }
            
            # Only filter by site if it's not 'all'
            if site != 'all':
                query["bool"]["filter"].append(
                    {"term": {"site": site}}
                )
            sort = [{"time_of_creation": {"order": "desc"}}]
            # Get conversations
            response = await client.search(
                index=self.index_name,
                query=query,
                source_includes=["conversation_id", "user_prompt", "thread_id", "site", "response", "time_of_creation"],
                sort=sort
            )
            conversations = response['hits']['hits']
            if not conversations:
                logger.info(f"No conversations found for user {user_id} on site {site}")
                return []

            # Prepare the list of threads with conversations
            threads = {}
            for conv in conversations:
                thread_id = conv["_source"]["thread_id"]
                if not thread_id in threads:
                    threads[thread_id] = {
                        "id": thread_id,
                        "site": conv["_source"]["site"],
                        "conversations": []
                    }

                # Add conversation entry to thread
                threads[thread_id]["conversations"].append({
                    "id": conv["_source"]["conversation_id"],
                    "user_prompt": conv["_source"]["user_prompt"],
                    "response": conv["_source"]["response"],
                    "time": conv["_source"]["time_of_creation"]
                })

            # Sort conversations in each thread by time (oldest first)
            for thread in threads.values():
                thread["conversations"].sort(key=lambda x: x["time"])

            return list(threads.values())

        except Exception as e:
            logger.error(f"Failed to get recent conversations: {e}")
            return []
    
    
    async def delete_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a specific conversation entry.

        Args:
            conversation_id: The ID of the conversation to delete
            user_id: User ID for access control (optional)

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            client = await self._get_es_client()

            query = {
                "bool": {
                    "must": [
                        {"match": {"conversation_id": conversation_id}}
                    ]
                }
            }
            
            if user_id:
                query["bool"]["must"].append(
                    {"match": {"user_id": user_id}}
                )

            # Delete by filter
            result = await client.delete_by_query(
                index=self.index_name,
                query=query
            )
            if result['deleted'] == 0:
                logger.warning(f"No conversation found with ID {conversation_id} for user {user_id}")
                return False
            else:
                logger.debug(f"Deleted conversation {conversation_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False
        
    async def search_conversations(self, query: str, user_id: Optional[str] = None, 
        site: Optional[str] = None, limit: int = 10) -> List[ConversationEntry]:
        """
        Search conversations using vector similarity and text search (hybrid search).
        It uses Reciprocal Rank Fusion (RRF) to combine results from both text and vector search.
        See https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion.

        Args:
            query: The search query string
            user_id: User ID to filter results (optional)
            site: Site to filter results (optional)
            limit: Maximum number of results to return (default 10)
        """
        client = await self._get_es_client()

        embedding = await get_embedding(query)
        try:
            standard_query = {
                "standard": {
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": ["user_prompt", "response"]
                        }
                    }
                }
            }
            if user_id:
                standard_query["standard"]["filter"] = [{"term": {"user_id": user_id}}]
            if site:
                filter_site = {"term": {"site": site}}
                if "filter" not in standard_query["standard"]:
                    standard_query["standard"]["filter"] = []
                standard_query["standard"]["filter"].append(filter_site)

            rank_options = self.config.rrf or {
                "rank_window_size": limit
            }
            knn_options = self.config.knn or {
                "num_candidates": 100
            }
            if "filter" in standard_query["standard"]:
                knn_filter = {"filter": standard_query["standard"]["filter"]}
            else:  
                knn_filter = {}

            retriever = {
                "rrf": {
                    "retrievers": [
                        standard_query,
                        {
                            "knn": {
                                "field": "embedding",
                                "query_vector": embedding,
                                "k": limit
                            }
                        }
                    ]
                }
            }
            retriever["rrf"].update(rank_options)
            retriever["rrf"]["retrievers"][1]["knn"].update(knn_options)
            if knn_filter:
                retriever["rrf"]["retrievers"][1]["knn"].update(knn_filter)

            # Hybrid search using Elasticsearch retrievers
            response = await client.search(
                index=self.index_name,
                retriever=retriever,
                size=limit,
                source_excludes=["embedding"]
            )

            conversations = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                conversations.append(ConversationEntry(
                    conversation_id=source.get("conversation_id", ""),
                    user_id=source.get("user_id", ""),
                    site=source.get("site", ""),
                    thread_id=source.get("thread_id", ""),
                    user_prompt=source.get("user_prompt", ""),
                    response=source.get("response", ""),
                    time_of_creation=datetime.fromisoformat(source.get("time_of_creation", "")),
                    embedding=None # We don't return embeddings in search results
                ))

            return conversations

        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            return []
        