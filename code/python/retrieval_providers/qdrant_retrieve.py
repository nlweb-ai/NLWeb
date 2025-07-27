# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility not guaranteed at this time.
"""

import asyncio
import json
import time
import threading
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from core.embedding import get_embedding
from core.config import CONFIG
from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

logger = get_configured_logger("qdrant_retrieve")

# Use an asyncio.Lock instead of threading.Lock to avoid deadlock in async contexts
_client_lock = asyncio.Lock()
qdrant_clients: Dict[str, AsyncQdrantClient] = {}


def _create_client_params(endpoint_config):
    """Extract client parameters from endpoint config."""
    params = {}
    url = endpoint_config.api_endpoint
    path = endpoint_config.database_path
    api_key = endpoint_config.api_key

    if url:
        params["url"] = url
        if api_key:
            params["api_key"] = api_key
    elif path:
        params["path"] = path
    else:
        raise ValueError("Either `api_endpoint` or `database_path` must be set.")

    return params


async def initialize_client(endpoint_name: Optional[str] = None):
    """Initialize Qdrant client."""
    endpoint_name = endpoint_name or CONFIG.write_endpoint

    # Validate endpoint exists
    if endpoint_name not in CONFIG.retrieval_endpoints:
        raise ValueError(f"Unknown Qdrant endpoint: {endpoint_name}")

    async with _client_lock:
        if endpoint_name not in qdrant_clients:
            logger.info(f"Initializing Qdrant client for endpoint: {endpoint_name}")
            try:
                endpoint_config = CONFIG.retrieval_endpoints[endpoint_name]
                params = _create_client_params(endpoint_config)
                client = AsyncQdrantClient(**params)
                qdrant_clients[endpoint_name] = client

                # Test connection
                await asyncio.wait_for(client.get_collections(), timeout=10.0)
                logger.info(f"Successfully initialized Qdrant client for {endpoint_name}")
                logger.debug("Qdrant connection test successful")
            except asyncio.TimeoutError:
                logger.error(f"Timeout initializing Qdrant client for {endpoint_name}")
                raise
            except Exception as e:
                logger.exception(f"Failed to initialize Qdrant client: {e}")
                raise


async def get_qdrant_client(endpoint_name: Optional[str] = None) -> AsyncQdrantClient:
    """Get or initialize Qdrant client."""
    endpoint_name = endpoint_name or CONFIG.write_endpoint
    if endpoint_name not in qdrant_clients:
        await initialize_client(endpoint_name)
    return qdrant_clients[endpoint_name]


def get_collection_name(endpoint_name: Optional[str] = None) -> str:
    """Get collection name from endpoint config or use default."""
    endpoint_name = endpoint_name or CONFIG.write_endpoint
    if endpoint_name not in CONFIG.retrieval_endpoints:
        raise ValueError(f"Unknown Qdrant endpoint: {endpoint_name}")
    endpoint_config = CONFIG.retrieval_endpoints[endpoint_name]
    index_name = endpoint_config.index_name
    return index_name or "nlweb_collection"


def create_site_filter(site) -> Optional[models.Filter]:
    """Create a Qdrant filter for site filtering."""
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


def format_results(search_result) -> List[List[Any]]:
    """Format Qdrant search results to match expected API: [url, text_json, name, site]."""
    results = []
    for item in search_result:
        payload = item.payload
        results.append([
            payload.get("url", ""),
            payload.get("schema_json", ""),
            payload.get("name", ""),
            payload.get("site", ""),
        ])
    return results


async def search_db(
    query: str,
    site: str,
    num_results: int = 50,
    endpoint_name: Optional[str] = None,
    query_params: Optional[Dict[str, Any]] = None,
) -> List[List[Any]]:
    """Search Qdrant for records filtered by site and ranked by vector similarity."""
    endpoint_name = endpoint_name or CONFIG.write_endpoint

    logger.info(
        f"Starting Qdrant search - endpoint: {endpoint_name}, site: {site}, "
        f"num_results: {num_results}"
    )

    try:
        start_embed = time.time()
        embedding = await get_embedding(query, query_params=query_params)
        embed_time = time.time() - start_embed

        start_retrieve = time.time()
        client = await get_qdrant_client(endpoint_name)
        collection = get_collection_name(endpoint_name)
        filter_condition = create_site_filter(site)

        # Add timeout to the query_points call
        response = await asyncio.wait_for(
            client.query_points(
                collection_name=collection,
                query=embedding,
                limit=num_results,
                with_payload=True,
                query_filter=filter_condition,
            ),
            timeout=15.0
        )
        search_result = response.points
        retrieve_time = time.time() - start_retrieve

        results = format_results(search_result)

        # Standard INFO logging
        logger.info(
            f"Qdrant search completed: embed_time={embed_time:.2f}s, "
            f"retrieve_time={retrieve_time:.2f}s, "
            f"total_time={(embed_time + retrieve_time):.2f}s, "
            f"results_count={len(results)}, embedding_dim={len(embedding)}"
        )
        # Structured context
        logger.log_with_context(
            LogLevel.INFO,
            "Qdrant search completed",
            {
                "embedding_time": f"{embed_time:.2f}s",
                "retrieval_time": f"{retrieve_time:.2f}s",
                "total_time": f"{embed_time + retrieve_time:.2f}s",
                "results_count": len(results),
                "embedding_dim": len(embedding),
            },
        )

        return results

    except asyncio.TimeoutError:
        logger.error(f"Qdrant query_points timed out after 15s (endpoint={endpoint_name}, site={site})")
        raise
    except UnexpectedResponse as e:
        logger.warning("Qdrant collection likely missing - did you run indexing first?")
        logger.error(
            f"Qdrant search failed: {type(e).__name__}: {e} "
            f"(endpoint={endpoint_name}, site={site})"
        )
        logger.log_with_context(
            LogLevel.ERROR,
            "Qdrant search failed",
            {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "endpoint": endpoint_name,
                "site": site,
            },
        )
        raise
    except Exception as e:
        logger.exception(f"Error in Qdrant search_db: {e}")
        logger.error(
            f"Qdrant search failed: {type(e).__name__}: {e} "
            f"(endpoint={endpoint_name}, site={site})"
        )
        logger.log_with_context(
            LogLevel.ERROR,
            "Qdrant search failed",
            {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "endpoint": endpoint_name,
                "site": site,
            },
        )
        raise


async def retrieve_item_with_url(
    url: str,
    endpoint_name: Optional[str] = None) -> List[Any]:
    """Retrieve a specific item by URL from Qdrant database."""
    endpoint_name = endpoint_name or CONFIG.write_endpoint
    logger.info(f"Retrieving Qdrant item - url: {url}, endpoint: {endpoint_name}")

    try:
        client = await get_qdrant_client(endpoint_name)
        collection = get_collection_name(endpoint_name)
        filter_condition = models.Filter(
            must=[models.FieldCondition(key="url", match=models.MatchValue(value=url))]
        )

        response, _offset = await asyncio.wait_for(
            client.scroll(
                collection_name=collection,
                scroll_filter=filter_condition,
                limit=1,
                with_payload=True,
            ),
            timeout=10.0
        )
        points = response

        if not points:
            logger.warning(f"No item found for URL: {url}")
            return []

        item = points[0]
        payload = item.payload
        formatted_result = [
            payload.get("url", ""),
            payload.get("schema_json", ""),
            payload.get("name", ""),
            payload.get("site", ""),
        ]

        logger.info(f"Successfully retrieved item for URL: {url}")
        logger.log_with_context(
            LogLevel.INFO,
            "Qdrant item retrieval succeeded",
            {"url": url, "endpoint": endpoint_name},
        )
        return formatted_result

    except asyncio.TimeoutError:
        logger.error(f"Qdrant scroll timed out after 10s (url={url}, endpoint={endpoint_name})")
        raise
    except UnexpectedResponse as e:
        logger.warning("Qdrant collection likely missing - did you run indexing first?")
        logger.error(
            f"Qdrant item retrieval failed: {type(e).__name__}: {e} "
            f"(url={url}, endpoint={endpoint_name})"
        )
        logger.log_with_context(
            LogLevel.ERROR,
            "Qdrant item retrieval failed",
            {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "url": url,
                "endpoint": endpoint_name,
            },
        )
        raise
    except Exception as e:
        logger.exception(f"Error retrieving item with URL: {url}: {e}")
        logger.error(
            f"Qdrant item retrieval failed: {type(e).__name__}: {e} "
            f"(url={url}, endpoint={endpoint_name})"
        )
        logger.log_with_context(
            LogLevel.ERROR,
            "Qdrant item retrieval failed",
            {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "url": url,
                "endpoint": endpoint_name,
            },
        )
        raise
