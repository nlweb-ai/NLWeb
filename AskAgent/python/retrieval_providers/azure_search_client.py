# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License


"""
Azure AI Search Client - Interface for Azure AI Search operations.
"""

import sys
import time
import threading
import asyncio
from typing import List, Dict, Union, Optional, Any, Tuple

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
    VectorSearchAlgorithmKind
)

from core.config import CONFIG
from core.embedding import get_embedding
from core.retriever import RetrievalClientBase
from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

logger = get_configured_logger("azure_search_client")

class AzureSearchClient(RetrievalClientBase):
    """
    Client for Azure AI Search operations, providing a unified interface for 
    indexing, storing, and retrieving vector-based search results.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Azure Search client.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        super().__init__()  # Initialize the base class with caching
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        self._client_lock = threading.Lock()
        self._search_clients = {}  # Cache for search clients
        self._index_clients = {}   # Cache for index clients
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        
        # Safely handle None values
        if self.endpoint_config.api_endpoint is None:
            raise ValueError(f"api_endpoint is not configured for endpoint {self.endpoint_name}")
        if self.endpoint_config.api_key is None:
            raise ValueError(f"api_key is not configured for endpoint {self.endpoint_name}")
            
        self.api_endpoint = self.endpoint_config.api_endpoint.strip('"')
        self.api_key = self.endpoint_config.api_key.strip('"')
        self.default_index_name = self.endpoint_config.index_name or "embeddings1536"

        logger.info(f"Initialized AzureSearchClient for endpoint: {self.endpoint_name}")
    
    def _get_endpoint_config(self):
        """Get the Azure Search endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Verify this is an Azure AI Search endpoint
        if endpoint_config.db_type != "azure_ai_search":
            error_msg = f"Endpoint {self.endpoint_name} is not an Azure AI Search endpoint (type: {endpoint_config.db_type})"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _get_index_client(self) -> SearchIndexClient:
        """Get the Azure AI Search index client for managing indices"""
        with self._client_lock:
            if "index" not in self._index_clients:
                logger.debug(f"Creating index client for {self.endpoint_name}")
                credential = AzureKeyCredential(self.api_key)
                self._index_clients["index"] = SearchIndexClient(
                    endpoint=self.api_endpoint,
                    credential=credential
                )
        
        return self._index_clients["index"]
    
    def _get_search_client(self, index_name: Optional[str] = None) -> SearchClient:
        """
        Get the Azure AI Search client for a specific index
        
        Args:
            index_name: Name of the index (defaults to the configured index name)
            
        Returns:
            SearchClient: The Azure Search client for the specified index
        """
        index_name = index_name or self.default_index_name
        
        with self._client_lock:
            if index_name not in self._search_clients:
                logger.debug(f"Creating search client for index: {index_name}")
                credential = AzureKeyCredential(self.api_key)
                self._search_clients[index_name] = SearchClient(
                    endpoint=self.api_endpoint,
                    index_name=index_name,
                    credential=credential
                )
        
        return self._search_clients[index_name]
    
    def _create_vector_search_config(self, algorithm_name: str = "hnsw_config", 
                                   profile_name: str = "vector_config") -> VectorSearch:
        """Create and return a vector search configuration"""
        return VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name=algorithm_name,
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
                    name=profile_name,
                    algorithm_configuration_name=algorithm_name,
                )
            ]
        )
    
    def _create_index_definition(self, index_name: str, embedding_size: int, 
                                profile_name: str = "vector_config") -> SearchIndex:
        """Create and return an index definition with specified embedding size"""
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SimpleField(name="url", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="name", type=SearchFieldDataType.String, filterable=True, sortable=True),
            SimpleField(name="site", type=SearchFieldDataType.String, filterable=True, sortable=True, facetable=True),
            SimpleField(name="schema_json", type=SearchFieldDataType.String, filterable=False),
            SearchField(
                name="embedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=embedding_size,
                vector_search_profile_name=profile_name
            )
        ]
        
        vector_search = self._create_vector_search_config(profile_name=profile_name)
        return SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
    
    def index_exists(self, index_name: Optional[str] = None) -> bool:
        """
        Check if the specified index exists.
        
        Args:
            index_name: Name of the index to check (defaults to configured index)
            
        Returns:
            bool: True if the index exists, False otherwise
        """
        index_name = index_name or self.default_index_name
        index_client = self._get_index_client()
        
        try:
            index = index_client.get_index(index_name)
            return True
        except Exception:
            return False
    
    def create_index(self, index_name: Optional[str] = None, 
                    embedding_size: int = 1536) -> bool:
        """
        Create a single search index with the specified name and embedding size.
        
        Args:
            index_name: Name of the index to create (defaults to configured index)
            embedding_size: Size of the embedding vectors
            
        Returns:
            bool: True if the index was created, False if it already existed
        """
        index_name = index_name or self.default_index_name
        
        # Check if index already exists
        if self.index_exists(index_name):
            logger.info(f"Index '{index_name}' already exists")
            return False
            
        index_client = self._get_index_client()
        index = self._create_index_definition(index_name, embedding_size)
        index_client.create_or_update_index(index)
        logger.info(f"Index '{index_name}' created successfully")
        return True
    
    def ensure_index_exists(self, index_name: Optional[str] = None, 
                          embedding_size: int = 1536) -> bool:
        """
        Ensure that the specified index exists, creating it if necessary.
        
        Args:
            index_name: Name of the index (defaults to configured index)
            embedding_size: Size of the embedding vectors
            
        Returns:
            bool: True if the index already existed, False if it was created
        """
        index_name = index_name or self.default_index_name
        
        logger.info(f"Ensuring index '{index_name}' exists with embedding size {embedding_size}")
        
        if self.index_exists(index_name):
            logger.info(f"Index '{index_name}' already exists")
            return True
        else:
            logger.info(f"Index '{index_name}' does not exist, creating it")
            self.create_index(index_name, embedding_size)
            return False
    
    def drop_index(self, index_name: Optional[str] = None) -> bool:
        """
        Drop an index from Azure Search service.
        
        Args:
            index_name: Name of the index to drop (defaults to configured index)
            
        Returns:
            bool: True if the index was dropped, False otherwise
        """
        index_name = index_name or self.default_index_name
        
        index_client = self._get_index_client()
        try:
            index_client.delete_index(index_name)
            logger.info(f"Index '{index_name}' dropped successfully")
            
            # Clear cached client if it exists
            with self._client_lock:
                if index_name in self._search_clients:
                    del self._search_clients[index_name]
                    
            return True
        except Exception as e:
            error_message = str(e)
            if "ResourceNotFound" in error_message:
                logger.warning(f"Index '{index_name}' does not exist, skipping")
            else:
                logger.error(f"Error dropping index '{index_name}': {error_message}")
            return False
    
    async def delete_documents_by_site(self, site_value: str, 
                                     index_name: Optional[str] = None) -> int:
        """
        Delete all documents from the index where site equals the given value.
        If the index doesn't exist, it will be created automatically.
        
        Args:
            site_value: The site value to filter by
            index_name: Optional index name (defaults to configured index name)
            
        Returns:
            int: Number of documents deleted
        """
        index_name = index_name or self.default_index_name
        
        # Ensure the index exists
        self.ensure_index_exists(index_name)
        
        # Get a search client for the index
        search_client = self._get_search_client(index_name)
        
        try:
            # Find all documents with the specified site value
            filter_expression = f"site eq '{site_value}'"
            
            # Execute the search asynchronously
            def search_sync():
                return search_client.search("*", filter=filter_expression, 
                                           select="id", include_total_count=True)
            
            search_results = await asyncio.get_event_loop().run_in_executor(None, search_sync)
            
            # Get the total count of matching documents
            total_matching = search_results.get_count()
            logger.info(f"Found {total_matching} documents in '{index_name}' with site = '{site_value}'")
            
            # If there are matching documents, delete them
            if total_matching > 0:
                # Collect all document IDs to delete
                doc_ids_to_delete = []
                for result in search_results:
                    doc_ids_to_delete.append({"id": result["id"]})
                
                # Delete documents in batches
                batch_size = 1000
                deleted_count = 0
                
                for i in range(0, len(doc_ids_to_delete), batch_size):
                    batch = doc_ids_to_delete[i:i+batch_size]
                    
                    # Execute delete asynchronously
                    def delete_sync():
                        return search_client.delete_documents(batch)
                    
                    await asyncio.get_event_loop().run_in_executor(None, delete_sync)
                    deleted_count += len(batch)
                    logger.info(f"Deleted batch of {len(batch)} documents")
                
                logger.info(f"Successfully deleted {deleted_count} documents from '{index_name}' with site = '{site_value}'")
                return deleted_count
            else:
                logger.info(f"No documents found in '{index_name}' with site = '{site_value}'")
                return 0
        except Exception as e:
            logger.error(f"Error deleting documents for site {site_value}: {str(e)}")
            return 0
    
    async def upload_documents(self, documents: List[Dict[str, Any]], 
                             index_name: Optional[str] = None) -> int:
        """
        Upload documents to Azure AI Search.
        If the index doesn't exist, it will be created automatically.
        
        Args:
            documents: List of documents to upload
            index_name: Optional index name (defaults to configured index name)
            
        Returns:
            int: Number of documents uploaded
        """
        if not documents:
            return 0
        
        index_name = index_name or self.default_index_name
            
        logger.info(f"Uploading {len(documents)} documents to index '{index_name}'")
        
        # Determine the embedding size from the first document
        embedding_size = None
        for doc in documents:
            if "embedding" in doc and doc["embedding"]:
                embedding_size = len(doc["embedding"])
                break
                
        if embedding_size is None:
            logger.warning("Could not determine embedding size from documents")
            embedding_size = 1536  # Default
        
        # Ensure the index exists
        self.ensure_index_exists(index_name, embedding_size)
        
        # Get a search client for the index
        search_client = self._get_search_client(index_name)
        
        try:
            # Upload the documents asynchronously
            def upload_sync():
                return search_client.upload_documents(documents)
            
            await asyncio.get_event_loop().run_in_executor(None, upload_sync)
            
            # Log the API endpoint and index where data was loaded
            logger.info(f"Successfully uploaded {len(documents)} documents to Azure AI Search")
            logger.info(f"API Endpoint: {self.api_endpoint}")
            logger.info(f"Index: {index_name}")
            
            return len(documents)
        except Exception as e:
            logger.error(f"Error uploading documents to index '{index_name}': {str(e)}")
            return 0
    
    async def search(self, query: str, site: Union[str, List[str]], 
                   num_results: int = 50, index_name: Optional[str] = None, 
                   query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search the Azure AI Search index for records filtered by site and ranked by vector similarity
        
        Args:
            query: The search query to embed and search with
            site: Site to filter by (string or list of strings)
            num_results: Maximum number of results to return
            index_name: Optional index name (defaults to configured index name)
            query_params: Additional query parameters
            
        Returns:
            List[List[str]]: List of search results
        """
        index_name = index_name or self.default_index_name
        
        # Get embedding for the query
        start_embed = time.time()
        embedding = await get_embedding(query, query_params=query_params)
        embed_time = time.time() - start_embed
        
        # Perform the search
        start_retrieve = time.time()
        results = await self._retrieve_by_site_and_vector(site, embedding, num_results, index_name)
        retrieve_time = time.time() - start_retrieve
        
       
        return results
    
    async def _retrieve_by_site_and_vector(self, sites: Union[str, List[str]], 
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
        
        # Validate embedding dimension
        if len(vector_embedding) != 1536:
            error_msg = f"Embedding dimension {len(vector_embedding)} not supported. Must be 1536."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        search_client = self._get_search_client(index_name)
        
        # Handle both single site and multiple sites
        if isinstance(sites, str):
            sites = [sites]
        
        site_restrict = ""
        for site in sites:
            if len(site_restrict) > 0:
                site_restrict += " or "
            site_restrict += f"site eq '{site}'"
        
        logger.debug(f"Site filter: {site_restrict}")
        
        # Create the search options with vector search and filtering
        search_options = {
            "filter": site_restrict,
            "vector_queries": [
                {
                    "kind": "vector",
                    "vector": vector_embedding,
                    "fields": "embedding",
                    "k": top_n
                }
            ],
            "top": top_n,
            "select": "url,name,site,schema_json"
        }
        
        try:
            # Execute the search asynchronously
            def search_sync():
                return search_client.search(search_text=None, **search_options)
            
            results = await asyncio.get_event_loop().run_in_executor(None, search_sync)
            
            # Process results into a more convenient format
            processed_results = []
            for result in results:
                processed_result = [result["url"], result["schema_json"], result["name"], result["site"]]
                processed_results.append(processed_result)
            
            logger.debug(f"Retrieved {len(processed_results)} results")
            return processed_results
        
        except Exception as e:
            logger.exception(f"Error in _retrieve_by_site_and_vector")
            logger.log_with_context(
                LogLevel.ERROR,
                "Azure Search retrieval failed",
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
        
        search_client = self._get_search_client(index_name)
        
        # Create the search options with URL filter
        search_options = {
            "filter": f"url eq '{url}'",
            "top": top_n,
            "select": "url,name,site,schema_json"
        }
        
        try:
            # Execute the search asynchronously
            def search_sync():
                return search_client.search(search_text=None, **search_options)
            
            results = await asyncio.get_event_loop().run_in_executor(None, search_sync)
            
            for result in results:
                logger.info(f"Successfully retrieved item for URL: {url}")
                return [result["url"], result["schema_json"], result["name"], result["site"]]
            
            logger.warning(f"No item found for URL: {url}")
            return None
        
        except Exception as e:
            logger.exception(f"Error retrieving item with URL: {url}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Azure item retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "url": url
                }
            )
            raise
    
    async def search_all_sites(self, query: str, num_results: int = 50, 
                             index_name: Optional[str] = None,
                             query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search across all sites using vector similarity
        
        Args:
            query: The search query to embed and search with
            num_results: Maximum number of results to return
            index_name: Optional index name (defaults to configured index name)
            query_params: Additional query parameters
            
        Returns:
            List[List[str]]: List of search results
        """
        index_name = index_name or self.default_index_name
        logger.info(f"Starting global Azure Search (all sites) - index: {index_name}, num_results: {num_results}")
        logger.debug(f"Query: {query}")
        
        try:
            query_embedding = await get_embedding(query, query_params=query_params)
            logger.debug(f"Generated embedding with dimension: {len(query_embedding)}")
            
            # Validate embedding dimension
            if len(query_embedding) != 1536:
                error_msg = f"Unsupported embedding size: {len(query_embedding)}. Must be 1536."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            search_client = self._get_search_client(index_name)
            
            # Create the search options with vector search only (no site filter)
            search_options = {
                "vector_queries": [
                    {
                        "kind": "vector",
                        "vector": query_embedding,
                        "fields": "embedding",
                        "k": num_results
                    }
                ],
                "top": num_results,
                "select": "url,name,site,schema_json"
            }
            
            # Execute the search asynchronously
            def search_sync():
                return search_client.search(search_text=None, **search_options)
            
            results = await asyncio.get_event_loop().run_in_executor(None, search_sync)
            
            # Process results into a more convenient format
            processed_results = []
            for result in results:
                processed_result = [result["url"], result["schema_json"], result["name"], result["site"]]
                processed_results.append(processed_result)
            
            logger.info(f"Global search completed, found {len(processed_results)} results")
            return processed_results
        
        except Exception as e:
            logger.exception(f"Error in search_all_sites")
            logger.log_with_context(
                LogLevel.ERROR,
                "Global Azure Search failed",
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
        
        search_client = self._get_search_client(index_name)
        
        try:
            # Use a facet query to get distinct sites
            search_options = {
                "facets": ["site,count:0"],
                "search_text": "*",
                "top": 0  # We only want facets, not actual documents
            }
            
            # Execute the search asynchronously
            def search_sync():
                result = search_client.search(**search_options)
                return result
            
            results = await asyncio.get_event_loop().run_in_executor(None, search_sync)
            
            # Extract unique sites from facets
            sites = []
            if hasattr(results, 'get_facets'):
                facets = results.get_facets()
                if facets:
                    site_facets = facets.get('site', [])
                    sites = [facet['value'] for facet in site_facets]
                else:
                    logger.warning("No site facets found in response")
                    sites = []
            else:
                logger.warning("No facets found in search response")
                sites = []
            
            logger.info(f"Retrieved {len(sites)} unique sites")
            return sorted(sites)
        
        except Exception as e:
            import traceback
            logger.exception(f"Error retrieving sites from index: {index_name}")
            logger.log_with_context(
                LogLevel.ERROR,
                "Azure sites retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "index_name": index_name
                }
            )
            raise