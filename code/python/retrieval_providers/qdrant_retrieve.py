# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from typing import Dict
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
import json
import time
import threading
from core.embedding import get_embedding
from core.config import CONFIG
from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

logger = get_configured_logger("qdrant_retrieve")

_client_lock = threading.Lock()
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
        raise ValueError("Either `api_endpoint_env` or `database_path` must be set.")

    return params


async def initialize_client(endpoint_name=None):
    """Initialize Qdrant client."""
    global qdrant_clients
    endpoint_name = endpoint_name or CONFIG.write_endpoint

    with _client_lock:
        if endpoint_name not in qdrant_clients:
            logger.info(f"Initializing Qdrant client for endpoint: {endpoint_name}")
            try:
                endpoint_config = CONFIG.retrieval_endpoints[endpoint_name]

                params = _create_client_params(endpoint_config)

                qdrant_clients[endpoint_name] = AsyncQdrantClient(**params)
                logger.info(
                    f"Successfully initialized Qdrant client for {endpoint_name}"
                )

                await qdrant_clients[endpoint_name].get_collections()
                logger.debug("Qdrant connection test successful")
            except Exception as e:
                logger.exception(f"Failed to initialize Qdrant client: {str(e)}")
                raise


async def get_qdrant_client(endpoint_name=None):
    """Get or initialize Qdrant client."""
    endpoint_name = endpoint_name or CONFIG.write_endpoint
    if endpoint_name not in qdrant_clients:
        await initialize_client(endpoint_name)
    return qdrant_clients[endpoint_name]


def get_collection_name(endpoint_name=None):
    """Get collection name from endpoint config or use default."""
    endpoint_name = endpoint_name or CONFIG.write_endpoint
    endpoint_config = CONFIG.retrieval_endpoints[endpoint_name]
    index_name = endpoint_config.index_name
    return index_name or "nlweb_collection"


def create_site_filter(site):
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


def format_results(search_result):
    """Format Qdrant search results to match expected API: [url, text_json, name, site]."""
    results = []
    for item in search_result:
        payload = item.payload
        url = payload.get("url", "")
        schema = payload.get("schema_json", "")
        name = payload.get("name", "")
        site_name = payload.get("site", "")

        results.append([url, schema, name, site_name])

    return results


async def search_db(query, site, num_results=50, endpoint_name=None, query_params=None):
    """Search Qdrant for records filtered by site and ranked by vector similarity."""
    endpoint_name = endpoint_name or CONFIG.write_endpoint
    logger.info(
        f"Starting Qdrant search - endpoint: {endpoint_name}, site: {site}, num_results: {num_results}"
    )

    try:
        start_embed = time.time()
        embedding = await get_embedding(query, query_params=query_params)
        embed_time = time.time() - start_embed

        start_retrieve = time.time()
        client = await get_qdrant_client(endpoint_name)
        collection = get_collection_name(endpoint_name)
        filter_condition = create_site_filter(site)

        search_result = (
            await client.query_points(
                collection_name=collection,
                query=embedding,
                limit=num_results,
                with_payload=True,
                query_filter=filter_condition,
            )
        ).points

        results = format_results(search_result)
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
            },
        )

        return results

    except Exception as e:
        logger.exception(f"Error in Qdrant search_db: {str(e)}")
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


async def retrieve_item_with_url(url, endpoint_name=None):
    """Retrieve a specific item by URL from Qdrant database."""
    endpoint_name = endpoint_name or CONFIG.write_endpoint
    logger.info(f"Retrieving item by URL: {url}")

    try:
        client = await get_qdrant_client(endpoint_name)
        collection = get_collection_name(endpoint_name)

        filter_condition = models.Filter(
            must=[models.FieldCondition(key="url", match=models.MatchValue(value=url))]
        )

        points, _offset = await client.scroll(
            collection_name=collection,
            scroll_filter=filter_condition,
            limit=1,
            with_payload=True,
        )

        if not points:
            logger.warning(f"No item found for URL: {url}")
            return None

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
        logger.exception(f"Error retrieving item with URL: {str(e)}")
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
