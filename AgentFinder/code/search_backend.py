"""
Swappable search backend interface.
Implement SearchBackend class for your provider (Azure, Elasticsearch, etc.)
"""
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio

# Configuration from environment variables
SEARCH_CONFIG = {
    "provider": os.getenv("SEARCH_PROVIDER", "azure"),  # azure, elasticsearch, qdrant
    "endpoint": os.getenv("SEARCH_ENDPOINT"),  # Must be set via environment variable
    "api_key": os.getenv("SEARCH_API_KEY"),  # Must be set via environment variable
    "index": os.getenv("SEARCH_INDEX", "embeddings1536"),
    "site": os.getenv("SEARCH_SITE", "nlweb_sites"),  # Site filter for queries
}


class SearchBackend(ABC):
    """Abstract base for search backends"""

    @abstractmethod
    async def initialize(self):
        """Initialize connection pools"""
        pass

    @abstractmethod
    async def search(self, query: str, vector: List[float], top_k: int = 30) -> List[Dict[str, Any]]:
        """
        Search for sites.
        Returns: List of {"url": str, "json_ld": str, "name": str, "site": str}
        """
        pass

    @abstractmethod
    async def close(self):
        """Cleanup connections"""
        pass


class AzureSearchBackend(SearchBackend):
    """Azure AI Search implementation"""

    def __init__(self):
        self.client = None
        self.session = None

    async def initialize(self):
        """Initialize Azure Search client with connection pooling"""
        import aiohttp
        from azure.search.documents.aio import SearchClient
        from azure.core.credentials import AzureKeyCredential

        # Validate required configuration
        if not SEARCH_CONFIG["endpoint"]:
            raise ValueError(
                "SEARCH_ENDPOINT environment variable is required. "
                "Please set it to your Azure Search endpoint URL (e.g., https://your-search.search.windows.net)"
            )

        if not SEARCH_CONFIG["api_key"]:
            raise ValueError(
                "SEARCH_API_KEY environment variable is required. "
                "Please set it to your Azure Search API key"
            )

        # Create session with connection pooling
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=50,
                limit_per_host=50,
                force_close=False,
                enable_cleanup_closed=True
            ),
            timeout=aiohttp.ClientTimeout(total=10)
        )

        # Create search client
        self.client = SearchClient(
            endpoint=SEARCH_CONFIG["endpoint"],
            index_name=SEARCH_CONFIG["index"],
            credential=AzureKeyCredential(SEARCH_CONFIG["api_key"]),
            session=self.session
        )

        print(f"Azure Search initialized: {SEARCH_CONFIG['endpoint']}/{SEARCH_CONFIG['index']}")

    async def search(self, query: str, vector: List[float], top_k: int = 30) -> List[Dict[str, Any]]:
        """Search Azure AI Search with vector search"""
        results = []

        try:
            # Configure search request for vector search
            search_kwargs = {
                "search_text": None,  # Use None for vector search
                "select": ["url", "schema_json", "name", "site"],  # Use correct field name
                "top": top_k,
            }

            # Add site filter if configured
            if SEARCH_CONFIG.get("site"):
                search_kwargs["filter"] = f"site eq '{SEARCH_CONFIG['site']}'"

            # Add vector search if vector is provided
            if vector:
                search_kwargs["vector_queries"] = [{
                    "kind": "vector",
                    "vector": vector,
                    "fields": "embedding",
                    "k": top_k  # Use "k" instead of "k_nearest_neighbors"
                }]

            # Execute search
            response = await self.client.search(**search_kwargs)

            # Collect results - map schema_json to json_ld
            async for item in response:
                results.append({
                    "url": item.get("url", ""),
                    "json_ld": item.get("schema_json", "{}"),  # Map schema_json to json_ld
                    "name": item.get("name", "Unknown"),
                    "site": item.get("site", "")
                })

        except Exception as e:
            print(f"Azure Search error: {e}")
            # Return empty results on error rather than crashing
            return []

        return results

    async def close(self):
        """Cleanup Azure Search connections"""
        if self.session:
            await self.session.close()


class ElasticsearchBackend(SearchBackend):
    """Elasticsearch implementation (placeholder for future implementation)"""

    def __init__(self):
        self.client = None

    async def initialize(self):
        """Initialize Elasticsearch client"""
        # Example implementation
        # from elasticsearch import AsyncElasticsearch
        # self.client = AsyncElasticsearch(
        #     hosts=[SEARCH_CONFIG["endpoint"]],
        #     api_key=SEARCH_CONFIG["api_key"]
        # )
        raise NotImplementedError("Elasticsearch backend not yet implemented")

    async def search(self, query: str, vector: List[float], top_k: int = 30) -> List[Dict[str, Any]]:
        """Search Elasticsearch"""
        raise NotImplementedError("Elasticsearch backend not yet implemented")

    async def close(self):
        """Cleanup Elasticsearch connections"""
        if self.client:
            await self.client.close()


class QdrantBackend(SearchBackend):
    """Qdrant implementation (placeholder for future implementation)"""

    def __init__(self):
        self.client = None

    async def initialize(self):
        """Initialize Qdrant client"""
        # Example implementation
        # from qdrant_client import QdrantClient
        # self.client = QdrantClient(
        #     url=SEARCH_CONFIG["endpoint"],
        #     api_key=SEARCH_CONFIG["api_key"]
        # )
        raise NotImplementedError("Qdrant backend not yet implemented")

    async def search(self, query: str, vector: List[float], top_k: int = 30) -> List[Dict[str, Any]]:
        """Search Qdrant"""
        raise NotImplementedError("Qdrant backend not yet implemented")

    async def close(self):
        """Cleanup Qdrant connections"""
        pass


# Factory function
def get_search_backend() -> SearchBackend:
    """Get the configured search backend"""
    provider = SEARCH_CONFIG["provider"].lower()

    if provider == "azure":
        return AzureSearchBackend()
    elif provider == "elasticsearch":
        return ElasticsearchBackend()
    elif provider == "qdrant":
        return QdrantBackend()
    else:
        raise ValueError(f"Unknown search provider: {SEARCH_CONFIG['provider']}")