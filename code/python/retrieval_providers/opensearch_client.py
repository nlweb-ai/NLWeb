# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
OpenSearch Client - Interface for OpenSearch operations.
"""

import time
import threading
import base64
import json
from typing import List, Dict, Union, Optional, Any
import httpx

from core.config import CONFIG
from core.retriever import RetrievalClientBasefrom core.embedding import get_embedding
from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

logger = get_configured_logger("opensearch_client")


class OpenSearchClient(RetrievalClientBase):
    """
    Client for OpenSearch operations, providing a unified interface for 
    vector-based search results using OpenSearch REST API.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the OpenSearch client.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        self._client_lock = threading.Lock()
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        
        # Handle None values from configuration
        api_endpoint_raw = self.endpoint_config.api_endpoint
        credentials_raw = self.endpoint_config.api_key
        
        if api_endpoint_raw is None:
            raise ValueError(f"API endpoint not configured for {self.endpoint_name}. Check environment variable configuration.")
        if credentials_raw is None:
            raise ValueError(f"API credentials not configured for {self.endpoint_name}. Check environment variable configuration.")
            
        self.api_endpoint = api_endpoint_raw.strip('"').rstrip('/')
        self.credentials = credentials_raw.strip('"')
        self.default_index_name = self.endpoint_config.index_name or "embeddings"
        # Handle use_knn configuration - default based on endpoint name
        use_knn_config = getattr(self.endpoint_config, 'use_knn', None)
        if use_knn_config is not None:
            self.use_knn = use_knn_config
        else:
            # Default based on endpoint name for backward compatibility
            self.use_knn = 'script' not in self.endpoint_name.lower()
        
        logger.info(f"Initialized OpenSearchClient for endpoint: {self.endpoint_name}, use_knn: {self.use_knn}")
    
    def _get_endpoint_config(self):
        """Get the OpenSearch endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Verify this is an OpenSearch endpoint
        if endpoint_config.db_type != "opensearch":
            error_msg = f"Endpoint {self.endpoint_name} is not an OpenSearch endpoint (type: {endpoint_config.db_type})"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for OpenSearch requests.
        Supports both basic auth (username:password) and API key authentication.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if ':' in self.credentials:
            # Basic authentication (username:password)
            encoded_credentials = base64.b64encode(self.credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded_credentials}"
        else:
            # API key authentication
            headers["Authorization"] = f"Bearer {self.credentials}"
        
        return headers
    
    async def create_index_if_not_exists(self, index_name: Optional[str] = None, 
                                       vector_dimension: int = 1536) -> bool:
        """
        Create the OpenSearch index with proper kNN vector mapping if it doesn't exist.
        
        Args:
            index_name: Optional index name (defaults to configured index name)
            vector_dimension: Dimension of the embedding vectors (default 1536)
            
        Returns:
            bool: True if index was created, False if it already existed
        """
        index_name = index_name or self.default_index_name
        
        # Check if index already exists
        try:
            async with httpx.AsyncClient() as client:
                response = await client.head(
                    f"{self.api_endpoint}/{index_name}",
                    headers=self._get_auth_headers(),
                    timeout=30
                )
                if response.status_code == 200:
                    logger.info(f"Index {index_name} already exists")
                    return False
        except Exception:
            pass  # Index doesn't exist, proceed to create
        
        # Define index mapping based on k-NN availability
        base_properties = {
            "url": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 2048
                    }
                }
            },
            "site": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "name": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 512
                    }
                }
            },
            "schema_json": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            }
        }
        
        if self.use_knn:
            # k-NN mapping with vector field
            index_mapping = {
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 100
                    }
                },
                "mappings": {
                    "properties": {
                        **base_properties,
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": vector_dimension,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "lucene",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 24
                                }
                            }
                        }
                    }
                }
            }
        else:
            # Standard mapping with float array for script_score (compatible with basic OpenSearch)
            index_mapping = {
                "mappings": {
                    "properties": {
                        **base_properties,
                        "embedding": {
                            "type": "float"
                        }
                    }
                }
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.api_endpoint}/{index_name}",
                    json=index_mapping,
                    headers=self._get_auth_headers(),
                    timeout=60
                )
                response.raise_for_status()
                
                logger.info(f"Successfully created index {index_name} with kNN vector mapping")
                return True
                
        except Exception as e:
            error_details = str(e)
            # Try to get more details from the response if it's an HTTP error
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                error_details = f"{str(e)} - Response: {e.response.text}"
            
            logger.exception(f"Error creating index {index_name}: {error_details}")
            logger.log_with_context(
                LogLevel.ERROR,
                "OpenSearch index creation failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": error_details,
                    "index_name": index_name,
                    "vector_dimension": vector_dimension,
                    "mapping": index_mapping
                }
            )
            raise
    
    async def delete_index(self, index_name: Optional[str] = None) -> bool:
        """
        Delete the OpenSearch index.
        
        Args:
            index_name: Optional index name (defaults to configured index name)
            
        Returns:
            bool: True if index was deleted, False if it didn't exist
        """
        index_name = index_name or self.default_index_name
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.api_endpoint}/{index_name}",
                    headers=self._get_auth_headers(),
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully deleted index {index_name}")
                    return True
                elif response.status_code == 404:
                    logger.info(f"Index {index_name} does not exist")
                    return False
                else:
                    response.raise_for_status()
                    
        except Exception as e:
            logger.exception(f"Error deleting index {index_name}: {e}")
            logger.log_with_context(
                LogLevel.ERROR,
                "OpenSearch index deletion failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "index_name": index_name
                }
            )
            raise
    
    async def recreate_index(self, index_name: Optional[str] = None, 
                           vector_dimension: int = 1536) -> bool:
        """
        Delete and recreate the OpenSearch index with proper kNN mapping.
        
        Args:
            index_name: Optional index name (defaults to configured index name)
            vector_dimension: Dimension of the embedding vectors (default 1536)
            
        Returns:
            bool: True if index was recreated successfully
        """
        index_name = index_name or self.default_index_name
        
        logger.info(f"Recreating index {index_name} with kNN vector mapping")
        
        # Delete existing index
        await self.delete_index(index_name)
        
        # Create new index with proper mapping
        return await self.create_index_if_not_exists(index_name, vector_dimension)
    
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
        logger.info(f"Deleting documents for site: {site} from index: {index_name}")
        
        delete_query = {
            "query": {
                "term": {
                    "site": site
                }
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_endpoint}/{index_name}/_delete_by_query",
                    json=delete_query,
                    headers=self._get_auth_headers(),
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                deleted_count = result.get('deleted', 0)
                
                logger.info(f"Successfully deleted {deleted_count} documents for site: {site}")
                return deleted_count
                
        except Exception as e:
            logger.exception(f"Error deleting documents for site {site}: {e}")
            logger.log_with_context(
                LogLevel.ERROR,
                "OpenSearch document deletion failed",
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
        Upload documents to OpenSearch using bulk API.
        
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
        logger.info(f"Uploading {len(documents)} documents to index: {index_name}")
        
        # Ensure index exists with proper kNN mapping
        await self.create_index_if_not_exists(index_name)
        
        # Prepare bulk request body
        bulk_body = []
        for doc in documents:
            # Index action metadata
            action = {
                "index": {
                    "_index": index_name,
                    "_id": doc.get('url', '')  # Use URL as document ID
                }
            }
            bulk_body.append(action)
            
            # Document source
            doc_source = {
                "url": doc.get('url', ''),
                "site": doc.get('site', ''),
                "schema_json": doc.get('schema_json', '{}'),
                "name": doc.get('name', ''),
                "embedding": doc.get('embedding', [])
            }
            bulk_body.append(doc_source)
        
        try:
            # Use proper JSON serialization for bulk API
            bulk_lines = []
            for item in bulk_body:
                bulk_lines.append(json.dumps(item))
            bulk_data = '\n'.join(bulk_lines) + '\n'
            
            headers = self._get_auth_headers()
            headers["Content-Type"] = "application/x-ndjson"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_endpoint}/_bulk",
                    content=bulk_data,
                    headers=headers,
                    timeout=120  # Longer timeout for bulk operations
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Count successful uploads
                successful_count = 0
                errors = []
                
                if 'items' in result:
                    for item in result['items']:
                        if 'index' in item:
                            if item['index'].get('status') in [200, 201]:
                                successful_count += 1
                            else:
                                errors.append(item['index'].get('error', 'Unknown error'))
                
                if errors:
                    logger.warning(f"Some documents failed to upload. Errors: {errors[:5]}...")  # Show first 5 errors
                
                logger.info(f"Successfully uploaded {successful_count} documents to index: {index_name}")
                return successful_count
                
        except Exception as e:
            logger.exception(f"Error uploading documents: {e}")
            logger.log_with_context(
                LogLevel.ERROR,
                "OpenSearch document upload failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "document_count": len(documents),
                    "index_name": index_name
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
            **kwargs: Additional parameters
            
        Returns:
            List[List[str]]: List of search results [url, schema_json, name, site]
        """
        index_name = kwargs.get('index_name', self.default_index_name)
        logger.info(f"Starting OpenSearch - query: '{query[:50]}...', site: {site}, index: {index_name}")
        
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
            site_filter = {"term": {"site": sites[0]}}
        else:
            site_filter = {"terms": {"site": sites}}
        
        # Build OpenSearch query with kNN vector search and site filtering
        search_query = {
            "size": num_results,
            "_source": ["url", "site", "schema_json", "name"],
            "query": {
                "bool": {
                    "must": [
                        {
                            "knn": {
                                "embedding": {
                                    "vector": embedding,
                                    "k": num_results
                                }
                            }
                        }
                    ],
                    "filter": [site_filter]
                }
            }
        }
        
        start_retrieve = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_endpoint}/{index_name}/_search",
                    json=search_query,
                    headers=self._get_auth_headers(),
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                hits = result.get('hits', {}).get('hits', [])
                
                # Process results into the expected format
                processed_results = []
                for hit in hits:
                    source = hit.get('_source', {})
                    url = source.get('url', '')
                    schema_json = source.get('schema_json', '{}')
                    name = source.get('name', '')
                    site_name = source.get('site', '')
                    
                    processed_result = [url, schema_json, name, site_name]
                    processed_results.append(processed_result)
                
                retrieve_time = time.time() - start_retrieve
                
                logger.log_with_context(
                    LogLevel.INFO,
                    "OpenSearch completed",
                    {
                        "embedding_time": f"{embed_time:.2f}s",
                        "retrieval_time": f"{retrieve_time:.2f}s",
                        "total_time": f"{embed_time + retrieve_time:.2f}s",
                        "results_count": len(processed_results)
                    }
                )
                return processed_results
        
        except Exception as e:
            logger.exception(f"Error in OpenSearch")
            logger.log_with_context(
                LogLevel.ERROR,
                "OpenSearch retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "sites": sites,
                    "num_results": num_results
                }
            )
            raise
    
    async def _search_by_site_and_vector(self, sites: Union[str, List[str]], 
                                       vector_embedding: List[float], 
                                       top_n: int = 10, 
                                       index_name: Optional[str] = None) -> List[List[str]]:
        """
        Internal method to retrieve top n records filtered by site and ranked by vector similarity
        
        Args:
            sites: Site or list of sites to filter by
            vector_embedding: The embedding vector to search with
            top_n: Maximum number of results to return
            index_name: Optional index name (defaults to configured index name)
            
        Returns:
            List[List[str]]: List of search results
        """
        index_name = index_name or self.default_index_name
        logger.debug(f"Retrieving by site and vector - sites: {sites}, top_n: {top_n}")
        
        # Handle both single site and multiple sites
        if isinstance(sites, str):
            sites = [sites]
        
        # Build site filter
        if len(sites) == 1:
            site_filter = {"term": {"site": sites[0]}}
        else:
            site_filter = {"terms": {"site": sites}}
        
        # Build OpenSearch query based on k-NN availability
        if self.use_knn:
            # Use k-NN plugin query
            search_query = {
                "size": top_n,
                "_source": ["url", "site", "schema_json", "name"],
                "query": {
                    "bool": {
                        "must": [
                            {
                                "knn": {
                                    "embedding": {
                                        "vector": vector_embedding,
                                        "k": top_n
                                    }
                                }
                            }
                        ],
                        "filter": [site_filter]
                    }
                }
            }
        else:
            # Use script_score for vector similarity
            search_query = {
                "size": top_n,
                "_source": ["url", "site", "schema_json", "name"],
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": [site_filter]
                            }
                        },
                        "script": {
                            "source": """
        super().__init__()  # Initialize the base class with caching
                                double dotProduct = 0.0;
                                double normA = 0.0;
                                double normB = 0.0;
                                for (int i = 0; i < params.query_vector.length; i++) {
                                    dotProduct += params.query_vector[i] * doc['embedding'][i];
                                    normA += params.query_vector[i] * params.query_vector[i];
                                    normB += doc['embedding'][i] * doc['embedding'][i];
                                }
                                return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB)) + 1.0;
                            """,
                            "params": {
                                "query_vector": vector_embedding
                            }
                        }
                    }
                }
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_endpoint}/{index_name}/_search",
                    json=search_query,
                    headers=self._get_auth_headers(),
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                hits = result.get('hits', {}).get('hits', [])
                
                # Process results into the expected format
                processed_results = []
                for hit in hits:
                    source = hit.get('_source', {})
                    url = source.get('url', '')
                    schema_json = source.get('schema_json', '{}')
                    name = source.get('name', '')
                    site = source.get('site', '')
                    
                    processed_result = [url, schema_json, name, site]
                    processed_results.append(processed_result)
                
                logger.debug(f"Retrieved {len(processed_results)} results")
                return processed_results
        
        except Exception as e:
            logger.exception(f"Error in _search_by_site_and_vector")
            logger.log_with_context(
                LogLevel.ERROR,
                "OpenSearch retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "sites": sites,
                    "top_n": top_n
                }
            )
            raise
    
    async def search_by_url(self, url: str, index_name: Optional[str] = None, 
                          top_n: int = 1) -> Optional[List[str]]:
        """
        Retrieve records by exact URL match
        
        Args:
            url: URL to search for
            index_name: Optional index name (defaults to configured index name)
            top_n: Maximum number of results to return
            
        Returns:
            Optional[List[str]]: Search result or None if not found
        """
        index_name = index_name or self.default_index_name
        logger.info(f"Retrieving item by URL: {url} from index: {index_name}")
        
        search_query = {
            "size": top_n,
            "_source": ["url", "site", "schema_json", "name"],
            "query": {
                "term": {
                    "url.keyword": url
                }
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_endpoint}/{index_name}/_search",
                    json=search_query,
                    headers=self._get_auth_headers(),
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                hits = result.get('hits', {}).get('hits', [])
                
                if hits:
                    source = hits[0].get('_source', {})
                    logger.info(f"Successfully retrieved item for URL: {url}")
                    return [
                        source.get('url', ''),
                        source.get('schema_json', '{}'),
                        source.get('name', ''),
                        source.get('site', '')
                    ]
                
                logger.warning(f"No item found for URL: {url}")
                return None
        
        except Exception as e:
            logger.exception(f"Error retrieving item with URL: {url}")
            logger.log_with_context(
                LogLevel.ERROR,
                "OpenSearch item retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "url": url
                }
            )
            raise
    
    async def search_all_sites(self, query: str, top_n: int = 10, 
                             index_name: Optional[str] = None, query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search across all sites using vector similarity
        
        Args:
            query: The search query to embed and search with
            top_n: Maximum number of results to return
            index_name: Optional index name (defaults to configured index name)
            
        Returns:
            List[List[str]]: List of search results
        """
        index_name = index_name or self.default_index_name
        logger.info(f"Starting global OpenSearch (all sites) - index: {index_name}, top_n: {top_n}")
        logger.debug(f"Query: {query}")
        
        try:
            query_embedding = await get_embedding(query, query_params=query_params)
            logger.debug(f"Generated embedding with dimension: {len(query_embedding)}")
            
            # Build OpenSearch query based on k-NN availability (no site filter)
            if self.use_knn:
                # Use k-NN plugin query
                search_query = {
                    "size": top_n,
                    "_source": ["url", "site", "schema_json", "name"],
                    "query": {
                        "knn": {
                            "embedding": {
                                "vector": query_embedding,
                                "k": top_n
                            }
                        }
                    }
                }
            else:
                # Use script_score for vector similarity
                search_query = {
                    "size": top_n,
                    "_source": ["url", "site", "schema_json", "name"],
                    "query": {
                        "script_score": {
                            "query": {
                                "match_all": {}
                            },
                            "script": {
                                "source": """
                                    double dotProduct = 0.0;
                                    double normA = 0.0;
                                    double normB = 0.0;
                                    for (int i = 0; i < params.query_vector.length; i++) {
                                        dotProduct += params.query_vector[i] * doc['embedding'][i];
                                        normA += params.query_vector[i] * params.query_vector[i];
                                        normB += doc['embedding'][i] * doc['embedding'][i];
                                    }
                                    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB)) + 1.0;
                                """,
                                "params": {
                                    "query_vector": query_embedding
                                }
                            }
                        }
                    }
                }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_endpoint}/{index_name}/_search",
                    json=search_query,
                    headers=self._get_auth_headers(),
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                hits = result.get('hits', {}).get('hits', [])
                
                # Process results into the expected format
                processed_results = []
                for hit in hits:
                    source = hit.get('_source', {})
                    processed_result = [
                        source.get('url', ''),
                        source.get('schema_json', '{}'),
                        source.get('name', ''),
                        source.get('site', '')
                    ]
                    processed_results.append(processed_result)
                
                logger.info(f"Global search completed, found {len(processed_results)} results")
                return processed_results
        
        except Exception as e:
            logger.exception(f"Error in search_all_sites")
            logger.log_with_context(
                LogLevel.ERROR,
                "Global OpenSearch failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "query": query[:50] + "..." if len(query) > 50 else query
                }
            )
            raise
    
    async def get_sites(self, index_name: Optional[str] = None) -> List[str]:
        """
        Get list of all unique sites in the database.
        
        Args:
            index_name: Optional index name (defaults to configured index name)
            
        Returns:
            List[str]: List of unique site names
        """
        index_name = index_name or self.default_index_name
        logger.info(f"Retrieving list of sites from index: {index_name}")
        
        # Use aggregation to get unique site values
        aggregation_query = {
            "size": 0,
            "aggs": {
                "unique_sites": {
                    "terms": {
                        "field": "site.keyword",
                        "size": 1000  # Adjust based on expected number of sites
                    }
                }
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_endpoint}/{index_name}/_search",
                    json=aggregation_query,
                    headers=self._get_auth_headers(),
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                buckets = result.get('aggregations', {}).get('unique_sites', {}).get('buckets', [])
                
                sites = [bucket['key'] for bucket in buckets]
                logger.info(f"Retrieved {len(sites)} unique sites")
                return sorted(sites)
        
        except Exception as e:
            logger.exception(f"Error retrieving sites from index: {index_name}")
            logger.log_with_context(
                LogLevel.ERROR,
                "OpenSearch sites retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "index_name": index_name
                }
            )
            raise
