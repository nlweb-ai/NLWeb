# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
HNSW (Hierarchical Navigable Small World) client for fast approximate nearest neighbor search.
This client provides read-only access to pre-built HNSW indices.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Union, Optional, Any

try:
    import hnswlib
except ImportError:
    hnswlib = None

from core.config import CONFIG
from core.embedding import get_embedding
from core.retriever import RetrievalClientBase
from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

logger = get_configured_logger("hnswlib_client")

# Module-level cache for HnswlibClient instances
_hnswlib_client_cache = {}


class HnswlibClient(RetrievalClientBase):
    """
    Client for HNSW-based vector search operations.
    Provides read-only access to pre-built indices created by build_hnswlib_index.py.
    """
    
    @classmethod
    def get_instance(cls, endpoint_name: Optional[str] = None):
        """
        Get a cached instance of HnswlibClient.
        This ensures the HNSW index is only loaded once per endpoint.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
            
        Returns:
            Cached HnswlibClient instance
        """
        cache_key = endpoint_name or 'default'
        
        if cache_key not in _hnswlib_client_cache:
            print(f"[HNSWLIB] Creating new cached instance for endpoint: {cache_key}")
            _hnswlib_client_cache[cache_key] = cls(endpoint_name)
        else:
            print(f"[HNSWLIB] Using cached instance for endpoint: {cache_key}")
            
        return _hnswlib_client_cache[cache_key]
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the HNSW client by loading pre-built index from disk.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to preferred endpoint in CONFIG)
        """
        print(f"[HNSWLIB] Initializing HnswlibClient with endpoint_name: {endpoint_name}")
        super().__init__()  # Initialize the base class with caching
        
        if hnswlib is None:
            print("[HNSWLIB] ERROR: hnswlib is not installed")
            raise ImportError("hnswlib is not installed. Please run: pip install hnswlib")
        
        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        print(f"[HNSWLIB] Using endpoint_name: {self.endpoint_name}")
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        self.database_path = self.endpoint_config.database_path
        self.index_name = self.endpoint_config.index_name or "nlweb_hnswlib"
        print(f"[HNSWLIB] Database path: {self.database_path}")
        print(f"[HNSWLIB] Index name: {self.index_name}")
        
        # Search parameter from config (can be overridden at query time)
        self.ef_search = getattr(self.endpoint_config, 'ef_search', 50)
        
        # Storage for loaded index and metadata
        self.index = None
        self.metadata = {}
        self.sites = {}
        self.dimension = None
        self._index_loaded = False  # Track if index has been loaded
        
        # Don't load the index immediately - use lazy loading
        print("[HNSWLIB] Initialization complete (index will be loaded on first use)")
        logger.info(f"Initialized HnswlibClient for endpoint: {self.endpoint_name} (lazy loading enabled)")
    
    def _get_endpoint_config(self):
        """Get the HNSW endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Verify this is an HNSW endpoint
        if endpoint_config.db_type != "hnswlib":
            error_msg = f"Endpoint {self.endpoint_name} is not an hnswlib endpoint (type: {endpoint_config.db_type})"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _resolve_path(self, path: str) -> Path:
        """
        Resolve relative paths to absolute paths.
        
        Args:
            path: The path to resolve
            
        Returns:
            Path: Resolved path object
        """
        if os.path.isabs(path):
            return Path(path)
            
        # Get the directory where this file is located
        current_dir = Path(__file__).parent
        # Go up to the project root directory
        project_root = current_dir.parent
        
        # Handle different relative path formats
        if path.startswith('./'):
            return project_root / path[2:]
        elif path.startswith('../'):
            return project_root.parent / path[3:]
        else:
            return project_root / path
    
    def _ensure_index_loaded(self):
        """
        Ensure the index is loaded. Uses lazy loading pattern - loads on first use.
        """
        if not self._index_loaded:
            print("[HNSWLIB] First use detected, loading index...")
            self._load_index()
            self._index_loaded = True
            print(f"[HNSWLIB] Successfully loaded index with {len(self.metadata)} documents from {len(self.sites)} sites")
            logger.info(f"Index loaded with {len(self.metadata)} documents from {len(self.sites)} sites")
    
    def _load_index(self):
        """
        Load pre-built HNSW index and metadata from disk.
        Raises an error if index doesn't exist.
        """
        print(f"[HNSWLIB] Resolving path: {self.database_path}")
        base_path = self._resolve_path(self.database_path)
        print(f"[HNSWLIB] Resolved to: {base_path}")
        
        if not base_path.exists():
            error_msg = (f"Index directory not found at {base_path}. "
                        f"Please run 'python -m tools.build_hnswlib_index' to build the index.")
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Find index file (detect dimension from filename)
        index_files = list(base_path.glob(f"{self.index_name}_*.bin"))
        if not index_files:
            error_msg = (f"No index files found matching {self.index_name}_*.bin in {base_path}. "
                        f"Please run 'python -m tools.build_hnswlib_index' to build the index.")
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Use the first index file found
        index_file = index_files[0]
        
        # Extract dimension from filename (e.g., nlweb_hnswlib_1536.bin -> 1536)
        try:
            self.dimension = int(index_file.stem.split('_')[-1])
        except (ValueError, IndexError):
            error_msg = f"Could not extract dimension from index filename: {index_file.name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Load HNSW index
        logger.info(f"Loading HNSW index from {index_file}")
        self.index = hnswlib.Index(space='cosine', dim=self.dimension)
        self.index.load_index(str(index_file))
        self.index.set_ef(self.ef_search)
        
        # Load metadata
        metadata_file = base_path / f"{self.index_name}_metadata.json"
        if not metadata_file.exists():
            error_msg = f"Metadata file not found: {metadata_file}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        with open(metadata_file, 'r') as f:
            # Convert string keys to integers
            self.metadata = {int(k): v for k, v in json.load(f).items()}
        
        # Load site index
        sites_file = base_path / f"{self.index_name}_sites.json"
        if not sites_file.exists():
            error_msg = f"Sites file not found: {sites_file}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        with open(sites_file, 'r') as f:
            self.sites = json.load(f)
        
        logger.info(f"Successfully loaded index with dimension {self.dimension}")
    
    async def delete_documents_by_site(self, site: str, **kwargs) -> int:
        """
        Delete documents by site - NOT SUPPORTED for HNSW.
        Index must be rebuilt using build_hnswlib_index.py.
        
        Args:
            site: Site identifier
            **kwargs: Additional parameters
            
        Returns:
            0 (operation not supported)
        """
        logger.warning(f"delete_documents_by_site not supported for HNSW. "
                      f"Rebuild index using 'python -m tools.build_hnswlib_index'")
        return 0
    
    async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs) -> int:
        """
        Upload documents - NOT SUPPORTED for HNSW.
        Index must be rebuilt using build_hnswlib_index.py.
        
        Args:
            documents: List of document objects
            **kwargs: Additional parameters
            
        Returns:
            0 (operation not supported)
        """
        logger.warning(f"upload_documents not supported for HNSW. "
                      f"Rebuild index using 'python -m tools.build_hnswlib_index'")
        return 0
    
    async def search(self, query: str, site: Union[str, List[str]], 
                    num_results: int = 50, query_params: Optional[Dict[str, Any]] = None, 
                    **kwargs) -> List[List[str]]:
        """
        Search for documents matching the query and site(s).
        
        Args:
            query: Search query string
            site: Site identifier or list of sites
            num_results: Maximum number of results to return
            query_params: Additional query parameters
            **kwargs: Additional parameters
            
        Returns:
            List of search results in format [url, schema_json, name, site]
        """
        # Ensure index is loaded
        self._ensure_index_loaded()
        
        # Get embedding for the query
        # Check if model is specified in query_params
        if query_params and 'model' in query_params:
            embedding = await get_embedding(query, model=query_params['model'])
        else:
            embedding = await get_embedding(query, query_params=query_params)
        
        if not embedding or len(embedding) != self.dimension:
            logger.error(f"Invalid embedding dimension: expected {self.dimension}, got {len(embedding) if embedding else 0}")
            return []
        
        # Convert site to list for uniform handling
        sites_to_search = [site] if isinstance(site, str) else site
        
        # Get all document IDs for the specified sites
        valid_ids = set()
        for s in sites_to_search:
            if s in self.sites:
                valid_ids.update(self.sites[s])
        
        if not valid_ids:
            logger.info(f"No documents found for sites: {sites_to_search}")
            return []
        
        # Search with a larger k to ensure we get enough results after filtering
        k = min(len(valid_ids), num_results * 3)  # Search for more to account for filtering
        
        # Perform the search
        def search_sync():
            labels, distances = self.index.knn_query([embedding], k=k)
            return labels[0], distances[0]  # Return first (and only) query results
        
        labels, distances = await asyncio.get_event_loop().run_in_executor(None, search_sync)
        
        # Filter results by site and format output
        results = []
        for label, distance in zip(labels, distances):
            if label in valid_ids:
                meta = self.metadata[label]
                results.append([
                    meta["url"],
                    meta["schema_json"],
                    meta["name"],
                    meta["site"]
                ])
                if len(results) >= num_results:
                    break
        
        logger.debug(f"Search returned {len(results)} results for sites {sites_to_search}")
        return results
    
    async def search_by_url(self, url: str, **kwargs) -> Optional[List[str]]:
        """
        Retrieve a document by its exact URL.
        
        Args:
            url: URL to search for
            **kwargs: Additional parameters
            
        Returns:
            Document data [url, schema_json, name, site] or None if not found
        """
        # Ensure index is loaded
        self._ensure_index_loaded()
        
        # Linear search through metadata (could be optimized with a URL index)
        for doc_id, meta in self.metadata.items():
            if meta["url"] == url:
                return [
                    meta["url"],
                    meta["schema_json"],
                    meta["name"],
                    meta["site"]
                ]
        
        logger.debug(f"No document found with URL: {url}")
        return None
    
    async def search_all_sites(self, query: str, num_results: int = 50,
                              query_params: Optional[Dict[str, Any]] = None,
                              **kwargs) -> List[List[str]]:
        """
        Search across all sites.
        
        Args:
            query: Search query string
            num_results: Maximum number of results to return
            query_params: Additional query parameters
            **kwargs: Additional parameters
            
        Returns:
            List of search results in format [url, schema_json, name, site]
        """
        # Ensure index is loaded
        self._ensure_index_loaded()
        
        # Get embedding for the query
        # Check if model is specified in query_params
        if query_params and 'model' in query_params:
            embedding = await get_embedding(query, model=query_params['model'])
        else:
            embedding = await get_embedding(query, query_params=query_params)
        
        if not embedding or len(embedding) != self.dimension:
            logger.error(f"Invalid embedding dimension: expected {self.dimension}, got {len(embedding) if embedding else 0}")
            return []
        
        # Perform the search
        def search_sync():
            labels, distances = self.index.knn_query([embedding], k=num_results)
            return labels[0], distances[0]  # Return first (and only) query results
        
        labels, distances = await asyncio.get_event_loop().run_in_executor(None, search_sync)
        
        # Format results
        results = []
        for label in labels:
            if label in self.metadata:
                meta = self.metadata[label]
                results.append([
                    meta["url"],
                    meta["schema_json"],
                    meta["name"],
                    meta["site"]
                ])
        
        logger.debug(f"Global search returned {len(results)} results")
        return results
    
    async def get_sites(self, **kwargs) -> List[str]:
        """
        Get list of all sites available in the index.
        
        Args:
            **kwargs: Additional parameters
            
        Returns:
            List of site names
        """
        return sorted(list(self.sites.keys()))