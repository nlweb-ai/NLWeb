# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Unified vector database interface with support for Azure AI Search, Milvus, and Qdrant.
This module provides abstract base classes and concrete implementations for database operations.
"""

import time
import asyncio
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple, Type

from config.config import CONFIG
from utils.utils import get_param
from utils.logging_config_helper import get_configured_logger
from utils.logger import LogLevel

logger = get_configured_logger("retriever")

# Client cache for reusing instances
_client_cache = {}
_client_cache_lock = asyncio.Lock()

# Mapping of database types to their required pip packages
_db_type_packages = {
    "azure_ai_search": ["azure-core", "azure-search-documents>=11.4.0"],
    "milvus": ["pymilvus>=1.1.0", "numpy"],
    "opensearch": ["httpx>=0.28.1"],
    "qdrant": ["qdrant-client>=1.14.0"],
    "snowflake_cortex_search": ["httpx>=0.28.1"],
}

# Cache for installed packages
_installed_packages = set()

def _ensure_package_installed(db_type: str):
    """
    Ensure the required packages for a database type are installed.
    
    Args:
        db_type: The type of database backend
    """
    if db_type not in _db_type_packages:
        return
    
    packages = _db_type_packages[db_type]
    for package in packages:
        # Extract package name without version for caching
        package_name = package.split(">=")[0].split("==")[0]
        
        if package_name in _installed_packages:
            continue
            
        try:
            # Try to import the package first
            if package_name == "azure-core":
                __import__("azure.core")
            elif package_name == "azure-search-documents":
                __import__("azure.search.documents")
            elif package_name == "qdrant-client":
                __import__("qdrant_client")
            else:
                __import__(package_name)
            _installed_packages.add(package_name)
            logger.debug(f"Package {package_name} is already installed")
        except ImportError:
            # Package not installed, install it
            logger.info(f"Installing {package} for {db_type} backend...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", package, "--quiet"
                ])
                _installed_packages.add(package_name)
                logger.info(f"Successfully installed {package}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install {package}: {e}")
                raise ValueError(f"Failed to install required package {package} for {db_type}")


class VectorDBClientInterface(ABC):
    """
    Abstract base class defining the interface for vector database clients.
    All vector database implementations should implement these methods.
    """
    
    @abstractmethod
    async def delete_documents_by_site(self, site: str, **kwargs) -> int:
        """
        Delete all documents matching the specified site.
        
        Args:
            site: Site identifier
            **kwargs: Additional parameters
            
        Returns:
            Number of documents deleted
        """
        pass
    
    @abstractmethod
    async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs) -> int:
        """
        Upload documents to the database.
        
        Args:
            documents: List of document objects
            **kwargs: Additional parameters
            
        Returns:
            Number of documents uploaded
        """
        pass
    
    @abstractmethod
    async def search(self, query: str, site: Union[str, List[str]], 
                    num_results: int = 50, **kwargs) -> List[List[str]]:
        """
        Search for documents matching the query and site.
        
        Args:
            query: Search query string
            site: Site identifier or list of sites
            num_results: Maximum number of results to return
            **kwargs: Additional parameters
            
        Returns:
            List of search results
        """
        pass
    
    @abstractmethod
    async def search_by_url(self, url: str, **kwargs) -> Optional[List[str]]:
        """
        Retrieve a document by its exact URL.
        
        Args:
            url: URL to search for
            **kwargs: Additional parameters
            
        Returns:
            Document data or None if not found
        """
        pass
    
    @abstractmethod
    async def search_all_sites(self, query: str, num_results: int = 50, **kwargs) -> List[List[str]]:
        """
        Search across all sites.
        
        Args:
            query: Search query string
            num_results: Maximum number of results to return
            **kwargs: Additional parameters
            
        Returns:
            List of search results
        """
        pass
    
    @abstractmethod
    async def get_sites(self, **kwargs) -> List[str]:
        """
        Get list of all sites available in the database.
        
        Args:
            **kwargs: Additional parameters
            
        Returns:
            List of site names
        """
        pass


class VectorDBClient:
    """
    Unified client for vector database operations. This class routes operations to the appropriate
    client implementation based on the database type specified in configuration.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None, query_params: Optional[Dict[str, Any]] = None):
        """
        Initialize the database client.
        
        Args:
            endpoint_name: Optional name of the endpoint to use
            query_params: Optional query parameters for overriding endpoint
        """
        self.query_params = query_params or {}
        
        # Get default endpoint from config
        self.endpoint_name = endpoint_name or CONFIG.preferred_retrieval_endpoint
        
        # In development mode, allow query param override
        if CONFIG.is_development_mode() and self.query_params:
            self.endpoint_name = get_param(self.query_params, "db", str, self.endpoint_name)
            logger.debug(f"Development mode: endpoint overridden to {self.endpoint_name}")
        
        # Validate endpoint exists in config
        if self.endpoint_name not in CONFIG.retrieval_endpoints:
            error_msg = f"Invalid endpoint: {self.endpoint_name}. Must be one of: {list(CONFIG.retrieval_endpoints.keys())}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Get endpoint config and extract db_type
        self.endpoint_config = CONFIG.retrieval_endpoints[self.endpoint_name]
        self.db_type = self.endpoint_config.db_type
        self._retrieval_lock = asyncio.Lock()
        
        logger.info(f"VectorDBClient initialized - endpoint: {self.endpoint_name}, db_type: {self.db_type}")
    
    async def get_client(self) -> VectorDBClientInterface:
        """
        Get or initialize the appropriate vector database client based on database type.
        Uses a cache to avoid creating duplicate client instances.
        
        Returns:
            Appropriate vector database client
        """
        # Use cache key combining db_type and endpoint
        cache_key = f"{self.db_type}_{self.endpoint_name}"
        
        # Check if client already exists in cache
        async with _client_cache_lock:
            if cache_key in _client_cache:
                return _client_cache[cache_key]
            
            # Ensure required packages are installed
            _ensure_package_installed(self.db_type)
            
            # Create the appropriate client with dynamic imports
            logger.debug(f"Creating new client for {self.db_type} with endpoint {self.endpoint_name}")
            
            try:
                if self.db_type == "azure_ai_search":
                    from retrieval.azure_search_client import AzureSearchClient
                    client = AzureSearchClient(self.endpoint_name)
                elif self.db_type == "milvus":
                    from retrieval.milvus_client import MilvusVectorClient
                    client = MilvusVectorClient(self.endpoint_name)
                elif self.db_type == "opensearch":
                    from retrieval.opensearch_client import OpenSearchClient
                    client = OpenSearchClient(self.endpoint_name)
                elif self.db_type == "qdrant":
                    from retrieval.qdrant import QdrantVectorClient
                    client = QdrantVectorClient(self.endpoint_name)
                elif self.db_type == "snowflake_cortex_search":
                    from retrieval.snowflake_client import SnowflakeCortexSearchClient
                    client = SnowflakeCortexSearchClient(self.endpoint_name)
                else:
                    error_msg = f"Unsupported database type: {self.db_type}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            except ImportError as e:
                logger.error(f"Failed to import client for {self.db_type}: {e}")
                raise ValueError(f"Failed to load client for {self.db_type}: {e}")
            
            # Store in cache and return
            _client_cache[cache_key] = client
            return client
    
    async def delete_documents_by_site(self, site: str, **kwargs) -> int:
        """
        Delete all documents matching the specified site.
        
        Args:
            site: Site identifier
            **kwargs: Additional parameters
            
        Returns:
            Number of documents deleted
        """
        async with self._retrieval_lock:
            logger.info(f"Deleting documents for site: {site}")
            
            try:
                client = await self.get_client()
                count = await client.delete_documents_by_site(site, **kwargs)
                logger.info(f"Successfully deleted {count} documents for site: {site}")
                return count
            except Exception as e:
                logger.exception(f"Error deleting documents for site {site}: {e}")
                logger.log_with_context(
                    LogLevel.ERROR,
                    "Document deletion failed",
                    {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "site": site,
                        "db_type": self.db_type,
                        "endpoint": self.endpoint_name
                    }
                )
                raise
    
    async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs) -> int:
        """
        Upload documents to the database.
        
        Args:
            documents: List of document objects
            **kwargs: Additional parameters
            
        Returns:
            Number of documents uploaded
        """
        async with self._retrieval_lock:
            logger.info(f"Uploading {len(documents)} documents")
            
            try:
                client = await self.get_client()
                count = await client.upload_documents(documents, **kwargs)
                logger.info(f"Successfully uploaded {count} documents")
                return count
            except Exception as e:
                logger.exception(f"Error uploading documents: {e}")
                logger.log_with_context(
                    LogLevel.ERROR,
                    "Document upload failed",
                    {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "document_count": len(documents),
                        "db_type": self.db_type,
                        "endpoint": self.endpoint_name
                    }
                )
                raise
    
    async def search(self, query: str, site: Union[str, List[str]], 
                    num_results: int = 50, endpoint_name: Optional[str] = None, **kwargs) -> List[List[str]]:
        """
        Search for documents matching the query and site.
        
        Args:
            query: Search query string
            site: Site identifier or list of sites
            num_results: Maximum number of results to return
            endpoint_name: Optional endpoint name override
            **kwargs: Additional parameters
            
        Returns:
            List of search results
        """
        print(f"Searching for '{query[:50]}...' in site: {site}, num_results: {num_results}")
        if (site == "all"):
            sites = CONFIG.nlweb.sites
            if (len(sites) == 0 or sites == "all"):
                return await self.search_all_sites(query, num_results, **kwargs)
            else:
                site = sites

        # If endpoint is specified, create a new client for that endpoint
        if endpoint_name and endpoint_name != self.endpoint_name:
            temp_client = VectorDBClient(endpoint_name=endpoint_name)
            return await temp_client.search(query, site, num_results, **kwargs)
        
        # Process site parameter for consistency
        if isinstance(site, str) and ',' in site:
            site = site.replace('[', '').replace(']', '')
            site = [s.strip() for s in site.split(',')]
        elif isinstance(site, str):
            site = site.replace(" ", "_")

        async with self._retrieval_lock:
            logger.info(f"Searching for '{query[:50]}...' in site: {site}, num_results: {num_results}")
            start_time = time.time()
            
            try:
                client = await self.get_client()
                results = await client.search(query, site, num_results, **kwargs)
                
                end_time = time.time()
                search_duration = end_time - start_time
                
                logger.log_with_context(
                    LogLevel.INFO,
                    "Search completed",
                    {
                        "duration": f"{search_duration:.2f}s",
                        "results_count": len(results),
                        "db_type": self.db_type,
                        "site": site
                    }
                )
                return results
            except Exception as e:
                logger.exception(f"Error in search: {e}")
                logger.log_with_context(
                    LogLevel.ERROR,
                    "Search failed",
                    {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "query": query[:50] + "..." if len(query) > 50 else query,
                        "site": site,
                        "db_type": self.db_type,
                        "endpoint": self.endpoint_name
                    }
                )
                raise
    
    async def search_by_url(self, url: str, endpoint_name: Optional[str] = None, **kwargs) -> Optional[List[str]]:
        """
        Retrieve a document by its exact URL.
        
        Args:
            url: URL to search for
            endpoint_name: Optional endpoint name override
            **kwargs: Additional parameters
            
        Returns:
            Document data or None if not found
        """
        # If endpoint is specified, create a new client for that endpoint
        if endpoint_name and endpoint_name != self.endpoint_name:
            temp_client = VectorDBClient(endpoint_name=endpoint_name)
            return await temp_client.search_by_url(url, **kwargs)
        
        async with self._retrieval_lock:
            logger.info(f"Retrieving item with URL: {url}")
            
            try:
                client = await self.get_client()
                result = await client.search_by_url(url, **kwargs)
                
                if result:
                    logger.debug(f"Successfully retrieved item for URL: {url}")
                else:
                    logger.warning(f"No item found for URL: {url}")
                
                return result
            except Exception as e:
                logger.exception(f"Error retrieving item with URL: {url}")
                logger.log_with_context(
                    LogLevel.ERROR,
                    "Item retrieval failed",
                    {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "url": url,
                        "db_type": self.db_type,
                        "endpoint": self.endpoint_name
                    }
                )
                raise
    
    async def search_all_sites(self, query: str, num_results: int = 50, 
                             endpoint_name: Optional[str] = None, **kwargs) -> List[List[str]]:
        """
        Search across all sites.
        
        Args:
            query: Search query string
            num_results: Maximum number of results to return
            endpoint_name: Optional endpoint name override
            **kwargs: Additional parameters
            
        Returns:
            List of search results
        """
        # If endpoint is specified, create a new client for that endpoint
        if endpoint_name and endpoint_name != self.endpoint_name:
            temp_client = VectorDBClient(endpoint_name=endpoint_name)
            return await temp_client.search_all_sites(query, num_results, **kwargs)
        
        async with self._retrieval_lock:
            logger.info(f"Searching across all sites for '{query[:50]}...', num_results: {num_results}")
            start_time = time.time()
            
            try:
                client = await self.get_client()
                results = await client.search_all_sites(query, num_results, **kwargs)
                
                end_time = time.time()
                search_duration = end_time - start_time
                
                logger.log_with_context(
                    LogLevel.INFO,
                    "All-sites search completed",
                    {
                        "duration": f"{search_duration:.2f}s",
                        "results_count": len(results),
                        "db_type": self.db_type
                    }
                )
                return results
            except Exception as e:
                logger.exception(f"Error in search_all_sites: {e}")
                logger.log_with_context(
                    LogLevel.ERROR,
                    "All-sites search failed",
                    {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "query": query[:50] + "..." if len(query) > 50 else query,
                        "db_type": self.db_type,
                        "endpoint": self.endpoint_name
                    }
                )
                raise
    
    async def get_sites(self, endpoint_name: Optional[str] = None, **kwargs) -> List[str]:
        """
        Get list of all sites available in the database.
        
        Args:
            endpoint_name: Optional endpoint name override
            **kwargs: Additional parameters
            
        Returns:
            List of site names
        """
        # If endpoint is specified, create a new client for that endpoint
        if endpoint_name and endpoint_name != self.endpoint_name:
            temp_client = VectorDBClient(endpoint_name=endpoint_name)
            return await temp_client.get_sites(**kwargs)
        
        async with self._retrieval_lock:
            logger.info("Retrieving list of sites from database")
            
            try:
                client = await self.get_client()
                sites = await client.get_sites(**kwargs)
                
                logger.log_with_context(
                    LogLevel.INFO,
                    "Sites retrieved",
                    {
                        "sites_count": len(sites),
                        "db_type": self.db_type,
                        "endpoint": self.endpoint_name
                    }
                )
                return sites
            except Exception as e:
                logger.exception(f"Error retrieving sites: {e}")
                logger.log_with_context(
                    LogLevel.ERROR,
                    "Sites retrieval failed",
                    {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "db_type": self.db_type,
                        "endpoint": self.endpoint_name
                    }
                )
                raise


# Factory function to make it easier to get a client with the right type
def get_vector_db_client(endpoint_name: Optional[str] = None, 
                        query_params: Optional[Dict[str, Any]] = None) -> VectorDBClient:
    """
    Factory function to create a vector database client with the appropriate configuration.
    
    Args:
        endpoint_name: Optional name of the endpoint to use
        query_params: Optional query parameters for overriding endpoint
        
    Returns:
        Configured VectorDBClient instance
    """
    return VectorDBClient(endpoint_name=endpoint_name, query_params=query_params)