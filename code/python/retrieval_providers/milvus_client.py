# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Milvus Vector Database Client - Interface for Milvus operations.
"""

import os
import sys
import threading
import asyncio
import json
from typing import List, Dict, Union, Optional, Any, Tuple

from pymilvus import MilvusClient
import numpy as np

from core.config import CONFIG
from core.embedding import get_embedding
from core.retriever import RetrievalClientBase
from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

logger = get_configured_logger("milvus_client")

class MilvusVectorClient(RetrievalClientBase):
    """
    Client for Milvus vector database operations, providing a unified interface for 
    indexing, storing, and retrieving vector-based search results.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Milvus vector database client.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        super().__init__()  # Initialize the base class with caching
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        logger.info(f"Initialized MilvusVectorClient for endpoint: {self.endpoint_name}")

        self._client_lock = threading.Lock()
        self._milvus_clients = {}  # Cache for Milvus clients
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        
        self.uri = self.endpoint_config.api_endpoint
        self.token = self.endpoint_config.api_key

        if not self.uri:
            error_msg = f"Milvus URI is empty. Please check if you have set MILVUS_ENDPOINT env var or milvus.api_endpoint_env in config_retrieval.yaml properly."
            logger.error(error_msg)
            raise ValueError(error_msg)
        logger.info(f"Using Milvus deployed at : {self.uri}")
            
        self.default_collection_name = self.endpoint_config.index_name or "prod_collection"
        logger.info(f"Default collection name: {self.default_collection_name}")
    
    def _get_endpoint_config(self):
        """Get the Milvus endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Verify this is a Milvus endpoint
        if endpoint_config.db_type != "milvus":
            error_msg = f"Endpoint {self.endpoint_name} is not a Milvus endpoint (type: {endpoint_config.db_type})"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _get_milvus_client(self, embedding_size: str = "small") -> MilvusClient:
        """
        Get or create a Milvus client.
        
        Args:
            embedding_size: Size of the embeddings ("small"=1536 or "large"=3072)
            
        Returns:
            MilvusClient instance
        """
        client_key = f"{self.endpoint_name}_{embedding_size}"
        
        with self._client_lock:
            if client_key not in self._milvus_clients:
                logger.debug(f"Creating Milvus client for {client_key}")
                
                # Initialize the client
                self._milvus_clients[client_key] = MilvusClient(self.uri, self.token)
                logger.info(f"Created Milvus client for {client_key} at {self.uri}")
                
                # Test client connection with a simple search
                try:
                    logger.debug("Testing connection to Milvus")
                    self._milvus_clients[client_key].list_collections()
                    logger.info(f"Connection verified for {client_key}")
                except Exception as e:
                    logger.error(f"Failed to connect to Milvus at {self.uri}: {str(e)}")
                    raise
                    
        return self._milvus_clients[client_key]
    
    def collection_exists(self, collection_name: Optional[str] = None, 
                         embedding_size: str = "small") -> bool:
        """
        Check if a collection exists in Milvus.
        
        Args:
            collection_name: Name of the collection to check
            embedding_size: Size of the embeddings ("small"=1536 or "large"=3072)
            
        Returns:
            bool: True if the collection exists, False otherwise
        """
        collection_name = collection_name or self.default_collection_name
        client = self._get_milvus_client(embedding_size)
        
        try:
            return client.has_collection(collection_name)
        except Exception as e:
            logger.error(f"Error checking if collection '{collection_name}' exists: {str(e)}")
            return False
    
    def create_collection(self, collection_name: Optional[str] = None, 
                         embedding_size: str = "small", 
                         drop_existing: bool = False) -> bool:
        """
        Create a Milvus collection with the specified settings.
        
        Args:
            collection_name: Name of the collection (defaults to configured name)
            embedding_size: Size of embeddings ("small"=1536 or "large"=3072)
            drop_existing: Whether to drop the collection if it exists
            
        Returns:
            bool: True if the collection was created, False if it already existed
        """
        collection_name = collection_name or self.default_collection_name
        client = self._get_milvus_client(embedding_size)
        
        # Determine vector size based on embedding size
        vector_size = 1536 if embedding_size == "small" else 3072
        
        # Drop collection if requested and it exists
        if drop_existing and client.has_collection(collection_name):
            logger.info(f"Dropping existing collection '{collection_name}'")
            client.drop_collection(collection_name)
        
        # Create collection if it doesn't exist
        if not client.has_collection(collection_name):
            logger.info(f"Creating collection '{collection_name}' with dimension {vector_size}")
            client.create_collection(
                collection_name=collection_name,
                dimension=vector_size
            )
            logger.info(f"Created collection '{collection_name}' with dimension {vector_size}")
            return True
        else:
            logger.info(f"Collection '{collection_name}' already exists")
            return False
    
    def ensure_collection_exists(self, collection_name: Optional[str] = None, 
                               embedding_size: str = "small") -> bool:
        """
        Ensure that a collection exists, creating it if necessary.
        
        Args:
            collection_name: Name of the collection (defaults to configured name)
            embedding_size: Size of embeddings ("small"=1536 or "large"=3072)
            
        Returns:
            bool: True if the collection already existed, False if it was created
        """
        collection_name = collection_name or self.default_collection_name
        
        if self.collection_exists(collection_name, embedding_size):
            logger.info(f"Collection '{collection_name}' already exists")
            return True
        else:
            logger.info(f"Collection '{collection_name}' does not exist, creating it")
            self.create_collection(collection_name, embedding_size)
            return False
    
    async def delete_documents_by_site(self, site: str, 
                                     collection_name: Optional[str] = None,
                                     embedding_size: str = "small") -> int:
        """
        Delete all documents from the collection that match a specific site value.
        
        Args:
            site: The site value to filter by
            collection_name: Optional collection name (defaults to configured name)
            embedding_size: Size of embeddings ("small"=1536 or "large"=3072)
            
        Returns:
            int: Number of documents deleted
        """
        collection_name = collection_name or self.default_collection_name
        client = self._get_milvus_client(embedding_size)
        
        if not client.has_collection(collection_name):
            logger.warning(f"Collection '{collection_name}' does not exist")
            return 0
        
        try:
            # Run the delete operation asynchronously
            return await asyncio.get_event_loop().run_in_executor(
                None, self._delete_documents_by_site_sync, site, collection_name, client
            )
        except Exception as e:
            logger.error(f"Error deleting documents for site {site}: {str(e)}")
            return 0
    
    def _delete_documents_by_site_sync(self, site: str, collection_name: str, 
                                      client: MilvusClient) -> int:
        """Synchronous implementation of delete_documents_by_site for thread execution"""
        try:
            # Query to find entities with the specified site
            expr = f'site == "{site}"'
            result = client.query(
                collection_name=collection_name,
                filter=expr,
                output_fields=["id"]
            )
            
            total_entities = len(result)
            
            if total_entities > 0:
                logger.info(f"Found {total_entities} entities with site = '{site}'")
                
                # Extract entity IDs
                ids = [entity["id"] for entity in result]
                
                # Delete entities
                client.delete(
                    collection_name=collection_name,
                    ids=ids
                )
                
                logger.info(f"Successfully deleted {total_entities} entities with site = '{site}'")
                return total_entities
            else:
                logger.info(f"No entities found with site = '{site}'")
                return 0
        except Exception as e:
            logger.error(f"Error in _delete_documents_by_site_sync for site {site}: {str(e)}")
            raise
    
    async def upload_documents(self, documents: List[Dict[str, Any]], 
                             collection_name: Optional[str] = None,
                             embedding_size: str = "small") -> int:
        """
        Upload a batch of documents to Milvus.
        
        Args:
            documents: List of document objects with embedding, schema_json, etc.
            collection_name: Optional collection name (defaults to configured name)
            embedding_size: Size of embeddings ("small"=1536 or "large"=3072)
            
        Returns:
            int: Number of documents uploaded
        """
        if not documents:
            return 0
            
        collection_name = collection_name or self.default_collection_name
        
        # Ensure collection exists
        self.ensure_collection_exists(collection_name, embedding_size)
        
        # Run the upload operation asynchronously
        return await asyncio.get_event_loop().run_in_executor(
            None, self._upload_documents_sync, documents, collection_name, embedding_size
        )
    
    def _upload_documents_sync(self, documents: List[Dict[str, Any]], 
                             collection_name: str, embedding_size: str) -> int:
        """Synchronous implementation of upload_documents for thread execution"""
        client = self._get_milvus_client(embedding_size)
        
        # Convert documents to Milvus format
        milvus_docs = []
        for doc in documents:
            # Skip documents without embeddings
            if "embedding" not in doc or not doc["embedding"]:
                continue
                
            milvus_docs.append({
                "id": int(doc["id"]) if isinstance(doc["id"], (int, str)) else doc["id"],
                "vector": doc["embedding"],
                "text": doc["schema_json"],
                "url": doc["url"],
                "name": doc["name"],
                "site": doc["site"]
            })
        
        if milvus_docs:
            client.insert(collection_name=collection_name, data=milvus_docs)
            logger.info(f"Uploaded {len(milvus_docs)} entities to Milvus collection '{collection_name}'")
            return len(milvus_docs)
        
        return 0
    
    async def search(self, query: str, site: Union[str, List[str]], 
                   num_results: int = 50, collection_name: Optional[str] = None,
                   query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search the Milvus collection for records filtered by site and ranked by vector similarity.
        
        Args:
            query: The search query to embed and search with
            site: Site to filter by (string or list of strings)
            num_results: Maximum number of results to return
            collection_name: Optional collection name (defaults to configured name)
            query_params: Additional query parameters
            
        Returns:
            List[List[str]]: List of search results in format [url, text_json, name, site]
        """
        collection_name = collection_name or self.default_collection_name
        logger.info(f"Starting Milvus search - collection: {collection_name}, site: {site}, num_results: {num_results}")
        logger.debug(f"Query: {query}")
        
        try:
            # Generate embedding for the query
            embedding = await get_embedding(query, query_params=query_params)
            logger.debug(f"Generated embedding with dimension: {len(embedding)}")
            
            # Run the search operation asynchronously
            results = await asyncio.get_event_loop().run_in_executor(
                None, self._search_sync, query, site, num_results, embedding, collection_name, query_params
            )
            
            logger.info(f"Milvus search completed successfully, found {len(results)} results")
            return results
        
        except Exception as e:
            logger.exception(f"Error in Milvus search")
            logger.log_with_context(
                LogLevel.ERROR,
                "Milvus search failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "collection": collection_name,
                    "site": site,
                    "query_length": len(query)
                }
            )
            raise
    
    def _search_sync(self, query: str, site: Union[str, List[str]], num_results: int, 
                   embedding: List[float], collection_name: str, 
                   query_params: Optional[Dict[str, Any]]) -> List[List[str]]:
        """Synchronous implementation of search for thread execution"""
        logger.debug(f"Executing synchronous search - site: {site}, num_results: {num_results}")
        
        try:
            client = self._get_milvus_client()
            
            # Perform the search based on the site parameter
            if site == "all":
                logger.debug(f"Searching all sites in collection: {collection_name}")
                res = client.search(
                    collection_name=collection_name,
                    data=[embedding],
                    limit=num_results,
                    output_fields=["url", "text", "name", "site"],
                )
            elif isinstance(site, list):
                site_filter = " || ".join([f"site == '{s}'" for s in site])
                logger.debug(f"Searching sites: {site} with filter: {site_filter}")
                res = client.search(
                    collection_name=collection_name, 
                    data=[embedding],
                    filter=site_filter,
                    limit=num_results,
                    output_fields=["url", "text", "name", "site"],
                )
            else:
                logger.debug(f"Searching site: {site} in collection: {collection_name}")
                res = client.search(
                    collection_name=collection_name,
                    data=[embedding],
                    filter=f"site == '{site}'",
                    limit=num_results,
                    output_fields=["url", "text", "name", "site"],
                )

            # Format the results
            retval = []
            if res and len(res) > 0:
                for item in res[0]:
                    ent = item["entity"]
                    try:
                        # Parse text field as JSON
                        schema_json = json.loads(ent["text"])
                        retval.append([ent["url"], schema_json, ent["name"], ent["site"]])
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse text field as JSON: {str(e)}")
                        continue
            
            logger.info(f"Retrieved {len(retval)} items from Milvus")
            logger.debug(f"First result URL: {retval[0][0] if retval else 'No results'}")
            return retval
        
        except Exception as e:
            logger.exception(f"Error in _search_sync")
            raise
    
    async def search_by_url(self, url: str, collection_name: Optional[str] = None) -> Optional[List[str]]:
        """
        Retrieve a record by its exact URL.
        
        Args:
            url: URL to search for
            collection_name: Optional collection name (defaults to configured name)
            
        Returns:
            Optional[List[str]]: Search result or None if not found
        """
        collection_name = collection_name or self.default_collection_name
        logger.info(f"Retrieving item by URL: {url} from collection: {collection_name}")
        
        try:
            # Run the search by URL operation asynchronously
            return await asyncio.get_event_loop().run_in_executor(
                None, self._search_by_url_sync, url, collection_name
            )
        except Exception as e:
            logger.exception(f"Error retrieving item with URL: {url}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Milvus item retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "url": url,
                    "collection": collection_name
                }
            )
            raise
    
    def _search_by_url_sync(self, url: str, collection_name: str) -> Optional[List[str]]:
        """Synchronous implementation of search_by_url for thread execution"""
        client = self._get_milvus_client()
        
        logger.debug(f"Querying collection: {collection_name} for URL: {url}")
        res = client.query(
            collection_name=collection_name,
            filter=f"url == '{url}'",
            limit=1,
            output_fields=["url", "text", "name", "site"],
        )
        
        if len(res) == 0:
            logger.warning(f"No item found for URL: {url}")
            return None
        
        item = res[0]
        try:
            # Parse text field as JSON
            schema_json = json.loads(item["text"])
            logger.info(f"Successfully retrieved item for URL: {url}")
            return [item["url"], schema_json, item["name"], item["site"]]
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse text field as JSON: {str(e)}")
            return None
    
    async def search_all_sites(self, query: str, num_results: int = 50, 
                             collection_name: Optional[str] = None,
                             query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search across all sites using vector similarity.
        
        Args:
            query: The search query to embed and search with
            num_results: Maximum number of results to return
            collection_name: Optional collection name (defaults to configured name)
            query_params: Additional query parameters
            
        Returns:
            List[List[str]]: List of search results
        """
        # This is just a convenience wrapper around the regular search method with site="all"
        return await self.search(query, "all", num_results, collection_name, query_params)
    
    async def get_sites(self, collection_name: Optional[str] = None,
                       embedding_size: str = "small") -> List[str]:
        """
        Get a list of unique site names from the Milvus collection.
        
        Args:
            collection_name: Optional collection name (defaults to configured name)
            embedding_size: Size of embeddings ("small"=1536 or "large"=3072)
            
        Returns:
            List[str]: Sorted list of unique site names
        """
        collection_name = collection_name or self.default_collection_name
        logger.info(f"Retrieving unique sites from collection: {collection_name}")
        
        try:
            # Run the get_sites operation asynchronously
            return await asyncio.get_event_loop().run_in_executor(
                None, self._get_sites_sync, collection_name, embedding_size
            )
        except Exception as e:
            logger.exception(f"Error retrieving sites from collection '{collection_name}': {str(e)}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Milvus get_sites failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "collection": collection_name,
                }
            )
            raise
    
    def _get_sites_sync(self, collection_name: str, embedding_size: str) -> List[str]:
        """Synchronous implementation of get_sites for thread execution"""
        client = self._get_milvus_client(embedding_size)
        
        try:
            # Check if collection exists
            if not client.has_collection(collection_name):
                logger.warning(f"Collection '{collection_name}' does not exist")
                return []
            
            # Query all distinct site values
            # Note: Milvus doesn't have a direct "SELECT DISTINCT" equivalent,
            # so we need to query all records and extract unique sites
            sites = set()
            
            # Query in batches to handle large collections
            batch_size = 10000
            offset = 0
            
            while True:
                try:
                    # Query a batch of records, only getting the site field
                    results = client.query(
                        collection_name=collection_name,
                        filter="",  # Empty filter to get all records
                        output_fields=["site"],
                        limit=batch_size,
                        offset=offset
                    )
                    
                    if not results:
                        break
                    
                    # Extract unique site values from this batch
                    for result in results:
                        site = result.get("site")
                        if site:
                            sites.add(site)
                    
                    # If we got fewer results than batch_size, we've reached the end
                    if len(results) < batch_size:
                        break
                    
                    offset += batch_size
                    
                except Exception as e:
                    logger.error(f"Error querying batch at offset {offset}: {str(e)}")
                    break
            
            # Convert to sorted list
            site_list = sorted(list(sites))
            logger.info(f"Found {len(site_list)} unique sites in collection '{collection_name}'")
            return site_list
            
        except Exception as e:
            logger.error(f"Error in _get_sites_sync for collection '{collection_name}': {str(e)}")
            raise