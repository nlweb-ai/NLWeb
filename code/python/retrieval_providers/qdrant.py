# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Qdrant Vector Database Client - Interface for Qdrant operations.
"""

import os
import sys
import threading
import time
import uuid
import json
from typing import List, Dict, Union, Optional, Any, Tuple, Set

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from core.config import CONFIG
from core.embedding import get_embedding
from core.retriever import RetrievalClientBase
from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

logger = get_configured_logger("qdrant_client")

class QdrantVectorClient(RetrievalClientBase):
    """
    Client for Qdrant vector database operations, providing a unified interface for 
    indexing, storing, and retrieving vector-based search results.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Qdrant vector database client.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        super().__init__()  # Initialize the base class with caching
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        self._client_lock = threading.Lock()
        self._qdrant_clients = {}  # Cache for Qdrant clients
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        self.api_endpoint = self.endpoint_config.api_endpoint
        self.api_key = self.endpoint_config.api_key
        self.database_path = self.endpoint_config.database_path
        self.default_collection_name = self.endpoint_config.index_name or "nlweb_collection"
        
        logger.info(f"Initialized QdrantVectorClient for endpoint: {self.endpoint_name}")
        if self.api_endpoint:
            logger.info(f"Using Qdrant server URL: {self.api_endpoint}")
        elif self.database_path:
            logger.info(f"Using local Qdrant database path: {self.database_path}")
        logger.info(f"Default collection name: {self.default_collection_name}")
    
    def _get_endpoint_config(self):
        """Get the Qdrant endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Verify this is a Qdrant endpoint
        if endpoint_config.db_type != "qdrant":
            error_msg = f"Endpoint {self.endpoint_name} is not a Qdrant endpoint (type: {endpoint_config.db_type})"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _resolve_path(self, path: str) -> str:
        """
        Resolve relative paths to absolute paths.
        
        Args:
            path: The path to resolve
            
        Returns:
            str: Absolute path
        """
        if os.path.isabs(path):
            return path
            
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up to the project root directory (assuming this file is in a subdirectory)
        project_root = os.path.dirname(current_dir)
        
        # Handle different relative path formats
        if path.startswith('./'):
            resolved_path = os.path.join(project_root, path[2:])
        elif path.startswith('../'):
            resolved_path = os.path.join(os.path.dirname(project_root), path[3:])
        else:
            resolved_path = os.path.join(project_root, path)
        
        # Ensure directory exists
        directory = os.path.dirname(resolved_path)
        os.makedirs(directory, exist_ok=True)
        
        logger.debug(f"Resolved path: {resolved_path}")
        return resolved_path
    
    def _create_client_params(self):
        """Extract client parameters from endpoint config."""
        params = {}
        logger.debug(f"Creating client parameters for endpoint: {self.endpoint_name}")

        # Check for URL-based connection
        url = self.api_endpoint
        api_key = self.api_key
        path = self.database_path

        # Decide whether to use URL or path-based connection
        if url and url.startswith(("http://", "https://")):
            logger.debug(f"Using Qdrant server URL: {url}")
            params["url"] = url
            if api_key:
                params["api_key"] = api_key
        elif path:
            # Resolve relative paths for local file-based storage
            resolved_path = self._resolve_path(path)
            logger.debug(f"Using local Qdrant database path: {resolved_path}")
            params["path"] = resolved_path
        else:
            # Default to a local path if neither URL nor path is specified
            default_path = self._resolve_path("../data/db")
            logger.debug(f"Using default local Qdrant database path: {default_path}")
            params["path"] = default_path
        
        logger.debug(f"Final client parameters: {params}")
        return params
    
    async def _get_qdrant_client(self) -> AsyncQdrantClient:
        """
        Get or initialize Qdrant client.
        
        Returns:
            AsyncQdrantClient: Qdrant client instance
        """
        client_key = self.endpoint_name
        
        # First check if we already have a client
        with self._client_lock:
            if client_key in self._qdrant_clients:
                return self._qdrant_clients[client_key]
        
        # If not, create a new client (outside the lock to avoid deadlocks during async init)
        try:
            logger.info(f"Initializing Qdrant client for endpoint: {self.endpoint_name}")
            
            params = self._create_client_params()
            logger.debug(f"Qdrant client params: {params}")
            
            # Create client with the determined parameters
            client = AsyncQdrantClient(**params)
            
            # Test connection by getting collections
            collections = await client.get_collections()
            logger.debug(f"Available collections: {collections.collections}")
            logger.info(f"Successfully initialized Qdrant client for {self.endpoint_name}")
            
            # Store in cache with lock
            with self._client_lock:
                self._qdrant_clients[client_key] = client
            
            return client
            
        except Exception as e:
            logger.exception(f"Failed to initialize Qdrant client: {str(e)}")
            
            # If we failed with the URL endpoint, try a fallback to local file-based storage
            if self.api_endpoint and "Connection refused" in str(e):
                logger.info("Connection to Qdrant server failed, trying local file-based storage")
                
                # Create a default local client as fallback
                logger.info("Creating default local client")
                default_path = self._resolve_path("../data/db")
                logger.info(f"Using default local path: {default_path}")
                
                fallback_client = AsyncQdrantClient(path=default_path)
                
                # Test connection
                await fallback_client.get_collections()
                
                # Store in cache with lock
                with self._client_lock:
                    self._qdrant_clients[client_key] = fallback_client
                
                logger.info("Successfully created fallback local client")
                return fallback_client
            else:
                raise
    
    async def collection_exists(self, collection_name: Optional[str] = None) -> bool:
        """
        Check if a collection exists in Qdrant.
        
        Args:
            collection_name: Name of the collection to check
            
        Returns:
            bool: True if the collection exists, False otherwise
        """
        collection_name = collection_name or self.default_collection_name
        client = await self._get_qdrant_client()
        
        try:
            return await client.collection_exists(collection_name)
        except Exception as e:
            logger.error(f"Error checking if collection '{collection_name}' exists: {str(e)}")
            return False
    
    async def create_collection(self, collection_name: Optional[str] = None, 
                              vector_size: int = 1536) -> bool:
        """
        Create a collection in Qdrant if it doesn't exist.
        
        Args:
            collection_name: Name of the collection to create
            vector_size: Size of the embedding vectors
        
        Returns:
            bool: True if created, False if already exists
        """
        collection_name = collection_name or self.default_collection_name
        client = await self._get_qdrant_client()
        
        try:
            # Check if collection exists
            if await client.collection_exists(collection_name):
                logger.info(f"Collection '{collection_name}' already exists")
                return False
            
            # Create collection
            logger.info(f"Creating collection '{collection_name}' with vector size {vector_size}")
            await client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )
            logger.info(f"Successfully created collection '{collection_name}'")
            return True
        
        except Exception as e:
            logger.error(f"Error creating collection '{collection_name}': {str(e)}")
            # Try again if collection doesn't exist
            if "Collection not found" in str(e):
                try:
                    await client.create_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
                    )
                    logger.info(f"Successfully created collection '{collection_name}' on second attempt")
                    return True
                except Exception as e2:
                    logger.error(f"Error creating collection on second attempt: {str(e2)}")
                    raise
            raise
    
    async def recreate_collection(self, collection_name: Optional[str] = None, 
                                vector_size: int = 1536) -> bool:
        """
        Recreate a collection in Qdrant (drop and create).
        
        Args:
            collection_name: Name of the collection to recreate
            vector_size: Size of the embedding vectors
        
        Returns:
            bool: True if successfully recreated
        """
        collection_name = collection_name or self.default_collection_name
        client = await self._get_qdrant_client()
        
        try:
            # Delete collection if it exists
            if await client.collection_exists(collection_name):
                logger.info(f"Dropping existing collection '{collection_name}'")
                await client.delete_collection(collection_name)

            # Create new collection
            logger.info(f"Creating collection '{collection_name}' with vector size {vector_size}")
            await client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )
            
            logger.info(f"Successfully recreated collection '{collection_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error recreating collection '{collection_name}': {str(e)}")
            # Try again if collection doesn't exist
            if "Collection not found" in str(e):
                try:
                    await client.create_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
                    )
                    logger.info(f"Successfully created collection '{collection_name}' on second attempt")
                    return True
                except Exception as e2:
                    logger.error(f"Error creating collection on second attempt: {str(e2)}")
                    raise
            raise
    
    async def ensure_collection_exists(self, collection_name: Optional[str] = None, 
                                     vector_size: int = 1536) -> bool:
        """
        Ensure that a collection exists, creating it if necessary.
        
        Args:
            collection_name: Name of the collection to check/create
            vector_size: Size of the embedding vectors (used if creating)
            
        Returns:
            bool: True if the collection already existed, False if it was created
        """
        collection_name = collection_name or self.default_collection_name
        
        if await self.collection_exists(collection_name):
            logger.info(f"Collection '{collection_name}' already exists")
            return True
        else:
            logger.info(f"Collection '{collection_name}' does not exist. Creating it...")
            await self.create_collection(collection_name, vector_size)
            return False
    
    async def delete_documents_by_site(
        self, site: str, collection_name: Optional[str] = None
    ) -> int:
        """
        Delete all documents from a collection that match a specific site value.

        Args:
            site: The site value to filter by
            collection_name: Optional collection name (defaults to configured name)

        Returns:
            int: Number of documents deleted
        """
        collection_name = collection_name or self.default_collection_name
        client = await self._get_qdrant_client()

        if not await client.collection_exists(collection_name):
            logger.warning(
                f"Collection '{collection_name}' does not exist. No points to delete."
            )
            return 0

        filter_condition = models.Filter(
            must=[
                models.FieldCondition(key="site", match=models.MatchValue(value=site))
            ]
        )
        count = (
            await client.count(
                collection_name=collection_name, count_filter=filter_condition
            )
        ).count
        await client.delete(
            collection_name=collection_name, points_selector=filter_condition
        )
        logger.info(f"Deleted {count} points")

        return count

    async def upload_documents(self, documents: List[Dict[str, Any]], 
                             collection_name: Optional[str] = None) -> int:
        """
        Upload a batch of documents to Qdrant.
        
        Args:
            documents: List of document objects with embedding, schema_json, etc.
            collection_name: Optional collection name (defaults to configured name)
            
        Returns:
            int: Number of documents uploaded
        """
        if not documents:
            logger.info("No documents to upload")
            return 0
            
        collection_name = collection_name or self.default_collection_name
        client = await self._get_qdrant_client()
        
        # Calculate vector size from the first document with an embedding
        vector_size = None
        for doc in documents:
            if "embedding" in doc and doc["embedding"]:
                vector_size = len(doc["embedding"])
                break
        
        if vector_size is None:
            logger.warning("No documents with embeddings found")
            return 0
        
        # Ensure collection exists
        await self.ensure_collection_exists(collection_name, vector_size)
        
        try:
            # Convert documents to Qdrant point format
            points = []
            for doc in documents:
                # Skip documents without embeddings
                if "embedding" not in doc or not doc["embedding"]:
                    continue
                    
                # Generate a deterministic UUID from the document ID or URL
                doc_id = doc.get("id", doc.get("url", str(uuid.uuid4())))
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(doc_id)))
                
                points.append(models.PointStruct(
                    id=point_id,
                    vector=doc["embedding"],
                    payload={
                        "url": doc.get("url"),
                        "name": doc.get("name"),
                        "site": doc.get("site"),
                        "schema_json": doc.get("schema_json")
                    }
                ))
            
            if points:
                # Upload in batches
                batch_size = 100  # Smaller batch size for stability
                total_uploaded = 0
                
                for i in range(0, len(points), batch_size):
                    batch = points[i:i+batch_size]
                    try:
                        await client.upsert(collection_name=collection_name, points=batch)
                        total_uploaded += len(batch)
                        logger.info(f"Uploaded batch of {len(batch)} points (total: {total_uploaded})")
                    except Exception as e:
                        logger.error(f"Error uploading batch: {str(e)}")
                        # Try to create the collection if it doesn't exist
                        if "Collection not found" in str(e):
                            logger.info(f"Collection '{collection_name}' not found during upload. Creating it...")
                            await client.create_collection(
                                collection_name=collection_name,
                                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
                            )
                            # Try upload again
                            await client.upsert(collection_name=collection_name, points=batch)
                            total_uploaded += len(batch)
                            logger.info(f"Uploaded batch of {len(batch)} points after creating collection")
                        else:
                            raise
                
                logger.info(f"Successfully uploaded {total_uploaded} points to collection '{collection_name}'")
                return total_uploaded
            
            return 0
            
        except Exception as e:
            logger.exception(f"Error uploading documents to collection '{collection_name}': {str(e)}")
            raise
    
    def _create_site_filter(self, site: Union[str, List[str]]):
        """
        Create a Qdrant filter for site filtering.
        
        Args:
            site: Site or list of sites to filter by
            
        Returns:
            Optional[models.Filter]: Qdrant filter object or None for all sites
        """
        if site == "all":
            return None

        if isinstance(site, list):
            sites = site
        elif isinstance(site, str):
            sites = [site]
        else:
            sites = []

        return models.Filter(
            must=[models.FieldCondition(key="site", match=models.MatchAny(any=sites))]
        )
    
    def _format_results(self, search_result: List[models.ScoredPoint]) -> List[List[str]]:
        """
        Format Qdrant search results to match expected API: [url, text_json, name, site].
        
        Args:
            search_result: Qdrant search results
            
        Returns:
            List[List[str]]: Formatted results
        """
        results = []
        for item in search_result:
            payload = item.payload
            url = payload.get("url", "")
            schema = payload.get("schema_json", "")
            name = payload.get("name", "")
            site_name = payload.get("site", "")

            results.append([url, schema, name, site_name])

        return results
    
    async def search(self, query: str, site: Union[str, List[str]], 
                   num_results: int = 50, collection_name: Optional[str] = None,
                   query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search the Qdrant collection for records filtered by site and ranked by vector similarity.
        
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
        logger.info(f"Starting Qdrant search - collection: {collection_name}, site: {site}, num_results: {num_results}")
        logger.debug(f"Query: {query}")
        
        try:
            start_embed = time.time()
            embedding = await get_embedding(query, query_params=query_params)
            embed_time = time.time() - start_embed
            logger.debug(f"Generated embedding with dimension: {len(embedding)} in {embed_time:.2f}s")
            
            start_retrieve = time.time()
            
            # Get client and prepare filter
            client = await self._get_qdrant_client()
            filter_condition = self._create_site_filter(site)
            
            # Ensure collection exists before searching
            collection_created = not await self.ensure_collection_exists(collection_name, len(embedding))
            if collection_created:
                logger.info(f"Collection '{collection_name}' was just created. Returning empty results.")
                results = []
            else:
                # Perform the search
                search_result = (
                    await client.search(
                        collection_name=collection_name,
                        query_vector=embedding,
                        limit=num_results,
                        query_filter=filter_condition,
                        with_payload=True,
                    )
                )
                
                # Format the results
                results = self._format_results(search_result)
            
            retrieve_time = time.time() - start_retrieve
            
            logger.log_with_context(
                LogLevel.INFO,
                "Qdrant search completed",
                {
                    "embedding_time": f"{embed_time:.2f}s",
                    "retrieval_time": f"{retrieve_time:.2f}s",
                    "total_time": f"{embed_time + retrieve_time:.2f}s",
                    "results_count": len(results),
                    "embedding_dim": len(embedding),
                }
            )
            
            return results
            
        except Exception as e:
            logger.exception(f"Error in Qdrant search: {str(e)}")
            
            # Try fallback if we're using a URL endpoint and it fails
            if self.api_endpoint and "Connection refused" in str(e):
                logger.info("Connection to Qdrant server failed, trying fallback")
                # Create a new client with local path as fallback
                self.api_endpoint = None  # Disable URL for fallback
                
                # Clear client cache to force recreation
                with self._client_lock:
                    self._qdrant_clients = {}
                    
                # Try search again with new local client
                return await self.search(query, site, num_results, collection_name, query_params)
            
            logger.log_with_context(
                LogLevel.ERROR,
                "Qdrant search failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "collection": collection_name,
                    "site": site,
                }
            )
            raise
    
    async def search_by_url(self, url: str, collection_name: Optional[str] = None) -> Optional[List[str]]:
        """
        Retrieve a specific item by URL from Qdrant database.
        
        Args:
            url: URL to search for
            collection_name: Optional collection name (defaults to configured name)
            
        Returns:
            Optional[List[str]]: Search result or None if not found
        """
        collection_name = collection_name or self.default_collection_name
        logger.info(f"Retrieving item by URL: {url} from collection: {collection_name}")
        
        try:
            client = await self._get_qdrant_client()
            
            filter_condition = models.Filter(
                must=[models.FieldCondition(key="url", match=models.MatchValue(value=url))]
            )
            
            try:
                # Use scroll to find the item by URL
                points, _offset = await client.scroll(
                    collection_name=collection_name,
                    scroll_filter=filter_condition,
                    limit=1,
                    with_payload=True,
                )
                
                if not points:
                    logger.warning(f"No item found for URL: {url}")
                    return None
                
                # Format the result
                item = points[0]
                payload = item.payload
                formatted_result = [
                    payload.get("url", ""),
                    payload.get("schema_json", ""),
                    payload.get("name", ""),
                    payload.get("site", ""),
                ]
                
                logger.info(f"Successfully retrieved item for URL: {url}")
                return formatted_result
                
            except Exception as e:
                if "Collection not found" in str(e):
                    logger.warning(f"Collection '{collection_name}' not found.")
                    return None
                raise
            
        except Exception as e:
            logger.exception(f"Error retrieving item with URL: {url}")
            
            # Try fallback if we're using a URL endpoint and it fails
            if self.api_endpoint and "Connection refused" in str(e):
                logger.info("Connection to Qdrant server failed, trying fallback")
                # Create a new client with local path as fallback
                self.api_endpoint = None  # Disable URL for fallback
                
                # Clear client cache to force recreation
                with self._client_lock:
                    self._qdrant_clients = {}
                    
                # Try search again with new local client
                return await self.search_by_url(url, collection_name)
            
            logger.log_with_context(
                LogLevel.ERROR,
                "Qdrant item retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "url": url,
                    "collection": collection_name,
                }
            )
            raise
    
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
    
    async def get_sites(self, collection_name: Optional[str] = None) -> List[str]:
        """
        Get a list of unique site names from the Qdrant collection.
        
        Args:
            collection_name: Optional collection name (defaults to configured name)
            
        Returns:
            List[str]: Sorted list of unique site names
        """
        collection_name = collection_name or self.default_collection_name
        logger.info(f"Retrieving unique sites from collection: {collection_name}")
        
        try:
            client = await self._get_qdrant_client()
            
            # Check if collection exists
            if not await client.collection_exists(collection_name):
                logger.warning(f"Collection '{collection_name}' does not exist")
                return []
            
            # Use scroll to get all points with site field
            sites = set()
            offset = None
            batch_size = 1000
            
            while True:
                points, next_offset = await client.scroll(
                    collection_name=collection_name,
                    limit=batch_size,
                    offset=offset,
                    with_payload=["site"]
                )
                
                if not points:
                    break
                
                # Extract site values
                for point in points:
                    site = point.payload.get("site")
                    if site:
                        sites.add(site)
                
                offset = next_offset
                if offset is None:
                    break
            
            # Convert to sorted list
            site_list = sorted(list(sites))
            logger.info(f"Found {len(site_list)} unique sites in collection '{collection_name}'")
            return site_list
            
        except Exception as e:
            logger.exception(f"Error retrieving sites from collection '{collection_name}': {str(e)}")
            
            # Try fallback if we're using a URL endpoint and it fails
            if self.api_endpoint and "Connection refused" in str(e):
                logger.info("Connection to Qdrant server failed, trying fallback")
                # Create a new client with local path as fallback
                self.api_endpoint = None  # Disable URL for fallback
                
                # Clear client cache to force recreation
                with self._client_lock:
                    self._qdrant_clients = {}
                    
                # Try get_sites again with new local client
                return await self.get_sites(collection_name)
            
            logger.log_with_context(
                LogLevel.ERROR,
                "Qdrant get_sites failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "collection": collection_name,
                }
            )
            raise