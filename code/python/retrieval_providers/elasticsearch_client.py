# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Elasticsearch Client - Interface for Elasticsearch operations.
"""

import time
import uuid
import threading
from typing import List, Dict, Union, Optional, Any

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from core.config import CONFIG
from core.retriever import RetrievalClientBasefrom core.embedding import get_embedding
from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

logger = get_configured_logger("elasticsearch_client")

class ElasticsearchClient(RetrievalClientBase):
    """
    Client for Elasticsearch operations, providing a unified interface for 
    vector-based search results using the Elasticsearch Python client.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Elasticsearch client.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        super().__init__()  # Initialize the base class with caching
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        self._client_lock = threading.Lock()
        self._es_clients = {}  # Cache for Elasticsearch clients

        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        # Handle None values from configuration
        self.api_endpoint = self.endpoint_config.api_endpoint
        self.api_key = self.endpoint_config.api_key
        self.default_index_name = self.endpoint_config.index_name or "embeddings"
        
        if self.api_endpoint is None:
            raise ValueError(f"API endpoint not configured for {self.endpoint_name}. Check environment variable configuration.")
        if self.api_key is None:
            raise ValueError(f"API key not configured for {self.endpoint_name}. Check environment variable configuration.")
            
        logger.info(f"Initialized Elasticsearch for endpoint: {self.endpoint_name}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def close(self):
        """Close the Elasticsearch client connections"""
        if self._es_clients:
            try:
                for each_client in self._es_clients.values():
                    logger.debug(f"Closing Elasticsearch client for endpoint: {self.endpoint_name}")
                    await each_client.close()
                logger.debug("Elasticsearch client connections closed")
            except Exception as e:
                logger.warning(f"Error closing Elasticsearch client: {str(e)}")
            finally:
                self._es_clients = {}
    
    def _get_endpoint_config(self):
        """Get the Elasticsearch endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)

        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Verify this is an Elasticsearch endpoint
        if endpoint_config.db_type != "elasticsearch":
            error_msg = f"Endpoint {self.endpoint_name} is not an Elasticsearch endpoint (type: {endpoint_config.db_type})"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _create_client_params(self):
        """Extract client parameters from endpoint config."""
        params = {}
        logger.debug(f"Creating client parameters for endpoint: {self.endpoint_name}")

        # Check for URL-based connection
        params["hosts"] = self.api_endpoint
        params["api_key"] = self.api_key

        logger.debug(f"Final client parameters: {params}")
        return params
    
    def _create_vector_properties(self):
        """Extract embedding properties from endpoint config."""
        params = {}
        logger.debug(f"Creating client parameters for endpoint: {self.endpoint_name}")
        
        params = self.endpoint_config.vector_type
        if params is None:
            # Set the default as dense_vector
            return {
                'type': 'dense_vector'
            }
        
        return params
    
    async def _get_es_client(self) -> AsyncElasticsearch:
        """
        Get or initialize Elasticsearch client.
        
        Returns:
            AsyncElasticsearch: Elasticsearch async client instance
        """
        client_key = self.endpoint_name
        
        # First check if we already have a client
        with self._client_lock:
            if client_key in self._es_clients:
                return self._es_clients[client_key]
        
        # If not, create a new client (outside the lock to avoid deadlocks during async init)
        try:
            logger.info(f"Initializing Elasticsearch client for endpoint: {self.endpoint_name}")
            
            params = self._create_client_params()
            # Create client with the determined parameters
            client = AsyncElasticsearch(**params)
            
            # Test connection by getting information
            await client.info()
            logger.info(f"Successfully initialized Elasticsearch client for {self.endpoint_name}")
            
            # Store in cache with lock
            with self._client_lock:
                self._es_clients[client_key] = client
            
            return client
            
        except Exception as e:
            logger.exception(f"Failed to initialize Elasticsearch client: {str(e)}")
            raise
            
    async def create_index_if_not_exists(self, index_name: Optional[str] = None) -> bool:
        """
        Create the Elasticsearch index with proper vector mapping if it doesn't exist.
        
        Args:
            index_name: Optional index name (defaults to configured index name)
            
        Returns:
            bool: True if index was created, False if it already existed
        """
        index_name = index_name or self.default_index_name
        client = await self._get_es_client()
        
        # Check if index already exists
        if await client.indices.exists(index = index_name):
            logger.info(f"Index {index_name} already exists")
            return False
        
        # Define index mapping based on k-NN availability
        properties = {
            "url": {
                "type": "text"
            },
            "site": {
                "type": "keyword"
            },
            "name": {
                "type": "text"
            },
            "schema_json": {
                "type": "text"
            },
            "embedding": self._create_vector_properties()
        }
        
        try:
            await client.indices.create(index=index_name, mappings={'properties' : properties})           
            logger.info(f"Successfully created index {index_name} with vector mapping")
            return True
                
        except Exception as e:
            error_details = str(e)           
            logger.exception(f"Error creating index {index_name}: {error_details}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Elasticsearch index creation failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": error_details,
                    "index_name": index_name,
                    "mapping": properties
                }
            )
            raise
    
    async def delete_index(self, index_name: Optional[str] = None) -> bool:
        """
        Delete the Elasticsearch index.
        
        Args:
            index_name: Optional index name (defaults to configured index name)
            
        Returns:
            bool: True if index was deleted, False if it didn't exist
        """
        index_name = index_name or self.default_index_name
        client = await self._get_es_client()
        
        try:
            await client.indices.delete(index=index_name)
            return True
                
        except Exception as e:
            logger.exception(f"Error deleting index {index_name}: {e}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Elasticsearch index deletion failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "index_name": index_name
                }
            )
            return False
       
    async def delete_documents_by_site(self, site: str, **kwargs) -> int:
        """
        Delete all documents matching the specified site.
        
        Args:
            site: Site identifier
            **kwargs: Additional parameters
            
        Returns:
            Number of documents deleted
        """
        index_name = kwargs.get('index_name', self.default_index_name)
        client = await self._get_es_client()

        logger.info(f"Deleting documents for site: {site} from index: {index_name}")

        try:
            response = await client.delete_by_query(index=index_name, query={
                "match": {
                    "site": site
                }
            })
            deleted_count = response['deleted']
                
            logger.info(f"Successfully deleted {deleted_count} documents for site: {site}")
            return deleted_count
                
        except Exception as e:
            logger.exception(f"Error deleting documents for site {site}: {e}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Elasticsearch document deletion failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "site": site,
                    "index_name": index_name
                }
            )
            raise
        
    async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs) -> int:
        """
        Upload documents to Elasticsearch using bulk API.
        
        Args:
            documents: List of document objects with keys: url, site, schema_json, name, embedding
            **kwargs: Additional parameters
            
        Returns:
            Number of documents uploaded
        """
        if not documents:
            logger.warning("No documents provided for upload")
            return 0
            
        index_name = kwargs.get('index_name', self.default_index_name)
        client = await self._get_es_client()
        num_documents = len(documents)

        logger.info(f"Uploading {num_documents} documents to index: {index_name}")
        
        # Ensure index exists with proper mapping
        await self.create_index_if_not_exists(index_name)
        
        # Prepare bulk operations
        actions = []
        for doc in documents:
            url = doc.get('url', '')
            if url == '':
                raise ValueError('The url cannot be empty')
        
            # Convert the URL in a deterministic unique ID
            id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
            
            action = {
                "_op_type": "index",
                "_index": index_name,
                "_id": id,
                "url": url,
                "site": doc.get('site', ''),
                "name": doc.get('name', ''),
                "schema_json": str(doc.get('schema_json', '{}')),
                "embedding": doc.get('embedding', [])
            }
            actions.append(action)
        
        try:
            successful_count, error_count = await async_bulk(
                client=client,
                actions=actions,
                timeout='300s',
                refresh=True,
                raise_on_error=True,
                stats_only=True
            )
            if error_count > 0:
                logger.warning(f"{error_count} out of {num_documents} documents failed to upload")
            
            logger.info(f"Successfully uploaded {successful_count} documents to index: {index_name}")
            
            return successful_count

        except Exception as e:
            logger.exception(f"Error uploading documents: {e}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Elasticsearch document upload failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "document_count": num_documents,
                    "index_name": index_name
                }
            )
            raise
    
    async def _format_es_response(self, response: Dict[str, Any]) -> List[List[str]]:
        """ 
        Converts the Elasticsearch response in a list of values [url, schema_json, name, site_name]

        Args:
            response (List[Dict[str, Any]]): the Elasticsearch response

        Returns:
            List[List[str]]: the list of values [url, schema_json, name, site_name]
        """
        processed_results = []
        for hit in response['hits']['hits']:
            source = hit.get('_source', {})
            url = source.get('url', '')
            schema_json = source.get('schema_json', '{}')
            name = source.get('name', '')
            site_name = source.get('site', '')
            processed_results.append([url, schema_json, name, site_name])
            
        return processed_results
    
    async def _search_knn_filter(self, index_name: str, embedding: List[float], 
                                 k: int, source: List[str], filter: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Search in Elasticsearch using kNN and filter
        
        Args:
            index_name: The index name
            embedding: The vector embedding to search
            k: The maximum number of documents to be returned
            source: The list of fields to be returned
            filter: Optional filter in kNN (e.g. {'terms': {'site' : '...'}})
        Returns:
            Dict[str, Any]: Elasticsearch response
        """
        client = await self._get_es_client()
        
        search_query = {
            "knn": {
                "field": "embedding",
                "query_vector": embedding,
                "k": k
            }
        }
        if filter:
            search_query['knn']['filter'] = filter

        try:
            return await client.search(index=index_name, query=search_query, source=source, size=k)
        except Exception as e:
            logger.exception(f"Error in Elasticsearch")
            logger.log_with_context(
                LogLevel.ERROR,
                "Elasticsearch retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "filter": filter,
                    "num_results": k
                }
            )
            raise
        
    async def search(self, query: str, site: Union[str, List[str]], 
                    num_results: int = 50, query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search for documents matching the query and site using vector similarity.
        
        Args:
            query: Search query string
            site: Site identifier or list of sites
            num_results: Maximum number of results to return
            query_params: Query parameters for embedding generation
            **kwargs: Additional parameters
            
        Returns:
            List[List[str]]: List of search results [url, schema_json, name, site]
        """
        index_name = kwargs.get('index_name', self.default_index_name)
        logger.info(f"Starting Elasticsearch - query: '{query[:50]}...', site: {site}, index: {index_name}")
        
        start_embed = time.time()
        embedding = await get_embedding(query, query_params=query_params)
        embed_time = time.time() - start_embed
        logger.debug(f"Embedding generated in {embed_time:.2f}s, dimension: {len(embedding)}")
        
        # Handle both single site and multiple sites
        if isinstance(site, str):
            sites = [site]
        else:
            sites = site
        
        # Build site filter
        if len(sites) == 1:
            filter = {"term": {"site": sites[0]}}
        else:
            filter = {"terms": {"site": sites}}
                
        source = ["url", "site", "schema_json", "name"]
        start_retrieve = time.time()
        # Execute Elasticsearch query with kNN vector search and filter
        response = await self._search_knn_filter(
            index_name=index_name,
            embedding=embedding,
            k=num_results,
            source=source,
            filter=filter
        )
        retrieve_time = time.time() - start_retrieve
        
        results = await self._format_es_response(response)
        logger.log_with_context(
            LogLevel.INFO,
            "Elasticsearch search completed",
            {
                "embedding_time": f"{embed_time:.2f}s",
                "retrieval_time": f"{retrieve_time:.2f}s",
                "total_time": f"{embed_time + retrieve_time:.2f}s",
                "results_count": len(results)
            }
        )
        return results
    
    
    async def search_by_url(self, url: str, **kwargs) -> Optional[List[str]]:
        """
        Retrieve records by exact URL match
        
        Args:
            url: URL to search for
            **kwargs: Additional parameters
            
        Returns:
            Optional[List[str]]: Search result or None if not found
        """
        index_name = kwargs.get('index_name', self.default_index_name)
        client = await self._get_es_client()

        logger.info(f"Retrieving item by URL: {url} from index: {index_name}")
        
        source = ["url", "site", "schema_json", "name"];
        try:
            # Convert the URL in a deterministic unique ID
            id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
        
            response = await client.get(index = index_name, id = id, source = source)
            source = response.get('_source', {})
            if source:
                url = source.get('url', '')
                schema_json = source.get('schema_json', '{}')
                name = source.get('name', '')
                site_name = source.get('site', '')
                return [url, schema_json, name, site_name]
            
            logger.warning(f"No item found for URL: {url}")
            return None
            
        except Exception as e:
            logger.exception(f"Error retrieving item with URL: {url}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Elasticsearch item retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "url": url
                }
            )
            raise
    
    async def search_all_sites(self, query: str, num_results: int = 50, query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search across all sites using vector similarity
        
        Args:
            query: The search query to embed and search with
            num_results: Maximum number of results to return (default 50)
            query_params: Optional parameters for embedding generation
            **kwargs: Additional parameters
            
        Returns:
            List[List[str]]: List of search results [url, schema_json, name, site]
        """
        index_name = kwargs.get('index_name', self.default_index_name)
        logger.info(f"Starting global Elasticsearch (all sites) - index: {index_name}, num_results: {num_results}")
        logger.debug(f"Query: {query}")
        
        try:
            start_embed = time.time()
            embedding = await get_embedding(query, query_params=query_params)
            embed_time = time.time() - start_embed
            logger.debug(f"Embedding generated in {embed_time:.2f}s, dimension: {len(embedding)}")
            
            source = ["url", "site", "schema_json", "name"]
            start_retrieve = time.time()
            # Execute Elasticsearch query with kNN vector search and filter
            response = await self._search_knn_filter(
                index_name=index_name, 
                embedding=embedding,
                k=num_results,
                source=source
            ) 
            retrieve_time = time.time() - start_retrieve
            
            results = await self._format_es_response(response)
            logger.log_with_context(
                LogLevel.INFO,
                "Elasticsearch search_all_sites completed",
                {
                    "embedding_time": f"{embed_time:.2f}s",
                    "retrieval_time": f"{retrieve_time:.2f}s",
                    "total_time": f"{embed_time + retrieve_time:.2f}s",
                    "results_count": len(results)
                }
            )
            return results
            
        except Exception as e:
            logger.exception(f"Error in search_all_sites")
            logger.log_with_context(
                LogLevel.ERROR,
                "Elasticsearch search all failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "query": query[:50] + "..." if len(query) > 50 else query
                }
            )
            raise
    
    async def get_sites(self, **kwargs) -> List[str]:
        """
        Get list of all unique sites in the database.

        Args:
            **kwargs: Additional parameters

        Returns:
            List[str]: List of unique site names
        """
        index_name = kwargs.get('index_name', self.default_index_name)
        size = int(kwargs.get('size', 100))
        client = await self._get_es_client()

        logger.info(f"Retrieving list of sites from index: {index_name}")
        
        # Use aggregation to get unique site values
        aggs = {
            "unique_sites": {
                "terms": {
                    "field": "site",
                    "size": size
                }
            }
        }
        
        try:
            response = await client.search(index=index_name, aggs=aggs, size=0)
            buckets = response.get('aggregations', {}).get('unique_sites', {}).get('buckets', [])
                
            sites = [bucket['key'] for bucket in buckets]
            logger.info(f"Retrieved {len(sites)} unique sites")
            return sorted(sites)
        
        except Exception as e:
            logger.exception(f"Error retrieving sites from index: {index_name}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Elasticsearch sites retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "index_name": index_name
                }
            )
            raise
