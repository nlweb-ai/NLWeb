# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Utility for making requests to remote NLWebServer and parsing responses.

This module provides functions to query a remote NLWebServer endpoint
and parse the responses into arrays of JSON objects, with support for
both streaming and non-streaming modes.
"""

import aiohttp
import json
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("nlweb_client")


async def ask_nlweb_server(
    endpoint: str,
    query: str,
    streaming: bool = False,
    site: Optional[str] = None,
    top_k: int = 10,
    additional_params: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Make a request to an NLWebServer endpoint and parse the response.
    
    Args:
        endpoint: The full URL of the endpoint (e.g., "http://localhost:8000/ask")
        query: The query string to send
        streaming: Whether to use streaming mode (SSE)
        site: Optional site parameter
        top_k: Number of results to request
        additional_params: Any additional query parameters
        
    Returns:
        List of parsed result objects from the 'content' field of the response
        
    Raises:
        Exception: If the request fails or response parsing fails
    """
    params = {
        'query': query,
        'streaming': 'true' if streaming else 'false',
        'top_k': top_k
    }
    
    if site:
        params['site'] = site
    
    if additional_params:
        params.update(additional_params)
    
    logger.info(f"Making request to {endpoint} with params: {params}")
    
    try:
        async with aiohttp.ClientSession() as session:
            if streaming:
                return await _handle_streaming_response(session, endpoint, params)
            else:
                return await _handle_regular_response(session, endpoint, params)
    except Exception as e:
        logger.error(f"Error making request to {endpoint}: {str(e)}", exc_info=True)
        raise


async def _handle_regular_response(
    session: aiohttp.ClientSession,
    endpoint: str,
    params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Handle non-streaming response from NLWebServer.
    
    Args:
        session: The aiohttp session
        endpoint: The endpoint URL
        params: Query parameters
        
    Returns:
        List of result objects from the 'content' field
    """
    async with session.get(endpoint, params=params) as response:
        if response.status != 200:
            error_text = await response.text()
            raise Exception(f"Request failed with status {response.status}: {error_text}")
        
        result = await response.json()
        
        # Results are always in the 'content' field
        items = result.get('content', [])
        
        logger.info(f"Received {len(items)} items from {endpoint}")
        
        # Ensure we return a list
        if not isinstance(items, list):
            items = [items] if items else []
        
        return items


async def _handle_streaming_response(
    session: aiohttp.ClientSession,
    endpoint: str,
    params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Handle streaming (SSE) response from NLWebServer.
    
    Args:
        session: The aiohttp session
        endpoint: The endpoint URL
        params: Query parameters
        
    Returns:
        List of result objects collected from the stream
    """
    items = []
    
    async with session.get(endpoint, params=params) as response:
        if response.status != 200:
            error_text = await response.text()
            raise Exception(f"Request failed with status {response.status}: {error_text}")
        
        async for line in response.content:
            line = line.decode('utf-8').strip()
            
            if not line or line.startswith(':'):
                # Skip empty lines and comments
                continue
            
            if line.startswith('data: '):
                # Extract the JSON data after 'data: '
                data_str = line[6:]
                
                if data_str == '[DONE]':
                    # End of stream
                    break
                
                try:
                    data = json.loads(data_str)
                    
                    # Check message type
                    message_type = data.get('message_type', '')
                    
                    if message_type == 'result':
                        # Result message - the actual data is in the content field
                        if 'content' in data:
                            content = data['content']
                            if isinstance(content, list):
                                items.extend(content)
                            else:
                                items.append(content)
                    elif message_type == 'complete':
                        # Stream is complete
                        break
                    elif message_type == 'error':
                        # Error in stream
                        error_msg = data.get('error', 'Unknown error')
                        raise Exception(f"Stream error: {error_msg}")
                    elif 'content' in data:
                        # Handle content messages - results are in content field
                        content = data['content']
                        if isinstance(content, list):
                            items.extend(content)
                        else:
                            items.append(content)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse SSE data: {data_str}, error: {e}")
                    continue
    
    logger.info(f"Received {len(items)} items from streaming response")
    return items


async def ask_nlweb_streaming(
    endpoint: str,
    query: str,
    site: Optional[str] = None,
    **kwargs
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Make a streaming request to NLWebServer and yield results as they arrive.
    
    Args:
        endpoint: The full URL of the endpoint
        query: The query string
        site: Optional site parameter
        **kwargs: Additional parameters
        
    Yields:
        Individual result objects as they arrive
    """
    params = {
        'query': query,
        'streaming': 'true'
    }
    
    if site:
        params['site'] = site
    
    params.update(kwargs)
    
    logger.info(f"Starting streaming request to {endpoint}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint, params=params) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Request failed with status {response.status}: {error_text}")
            
            async for line in response.content:
                line = line.decode('utf-8').strip()
                
                if not line or line.startswith(':'):
                    continue
                
                if line.startswith('data: '):
                    data_str = line[6:]
                    
                    if data_str == '[DONE]':
                        break
                    
                    try:
                        data = json.loads(data_str)
                        
                        message_type = data.get('message_type', '')
                        
                        if message_type == 'result':
                            # Result message - the actual data is in the content field
                            if 'content' in data:
                                content = data['content']
                                if isinstance(content, list):
                                    for item in content:
                                        yield item
                                else:
                                    yield content
                        elif message_type == 'complete':
                            break
                        elif message_type == 'error':
                            raise Exception(f"Stream error: {data.get('error', 'Unknown error')}")
                        elif 'content' in data:
                            # Results are in content field
                            content = data['content']
                            if isinstance(content, list):
                                for item in content:
                                    yield item
                            else:
                                yield content
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SSE data: {e}")
                        continue


# Convenience functions for common endpoints

async def ask_endpoint(url: str, query: str, site: Optional[str] = None, streaming: bool = False, **kwargs) -> List[Dict[str, Any]]:
    """
    Query the /ask endpoint of an NLWebServer.
    
    Args:
        url: Base URL of the server (e.g., "http://localhost:8000")
        query: The query string
        site: Optional site to query
        streaming: Whether to use streaming mode
        **kwargs: Additional parameters
        
    Returns:
        List of result objects from the 'content' field
    """
    endpoint = f"{url.rstrip('/')}/ask"
    return await ask_nlweb_server(endpoint, query, streaming, site, **kwargs)


async def who_endpoint(url: str, query: str, streaming: bool = False, **kwargs) -> List[Dict[str, Any]]:
    """
    Query the /who endpoint of an NLWebServer.
    
    Args:
        url: Base URL of the server (e.g., "http://localhost:8000")
        query: The query string
        streaming: Whether to use streaming mode
        **kwargs: Additional parameters
        
    Returns:
        List of site/endpoint objects from the 'content' field
    """
    endpoint = f"{url.rstrip('/')}/who"
    return await ask_nlweb_server(endpoint, query, streaming, **kwargs)


def _extract_site_info(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract simplified site information from a /who response item.
    
    Args:
        item: A single item from the /who response
        
    Returns:
        Simplified site object with domain, name, score, etc.
    """
    # Extract domain from schema_object.url or from the url parameter
    schema_obj = item.get('schema_object', {})
    domain = schema_obj.get('url', '')
    
    # If domain not in schema_object, try to extract from url parameter
    if not domain:
        url_field = item.get('url', '')
        if 'site=' in url_field:
            domain = url_field.split('site=')[1].split('&')[0]
    
    site_info = {
        'domain': domain,
        'name': item.get('name', domain),
        'score': item.get('score', 0),
        'description': item.get('description', ''),
        'category': schema_obj.get('category', ''),
        '@type': item.get('@type', 'Item')  # Include the @type field
    }
    
    # Include the query field if present (for query rewriting)
    if 'query' in item:
        site_info['query'] = item['query']
    
    return site_info


async def sites_from_who(url: str, query: str, **kwargs) -> List[Dict[str, Any]]:
    """
    Query the /who endpoint and extract just the site information (non-streaming).
    
    Args:
        url: Base URL of the server (e.g., "http://localhost:8000")
        query: The query string
        **kwargs: Additional parameters
        
    Returns:
        List of simplified site objects sorted by score
    """
    # Get the full response from /who endpoint
    full_results = await who_endpoint(url, query, streaming=False, **kwargs)
    
    # Extract just the site information
    sites = [_extract_site_info(item) for item in full_results]
    
    # Sort by score descending
    sites.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    logger.info(f"Extracted {len(sites)} sites from /who response")
    return sites


async def sites_from_who_streaming(endpoint: str, query: str, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Query the /who endpoint and extract site information (streaming version).
    
    Args:
        endpoint: Full endpoint URL (e.g., "http://localhost:8000/who" or "https://whotoask.azurewebsites.net/who")
        query: The query string
        **kwargs: Additional parameters
        
    Yields:
        Individual simplified site objects as they arrive
    """
    # Use the endpoint as-is
    params = {
        'query': query,
        'streaming': 'true'
    }
    params.update(kwargs)
    
    logger.info(f"Starting streaming /who request for query: {query}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint, params=params) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Request failed with status {response.status}: {error_text}")
            
            async for line in response.content:
                line = line.decode('utf-8').strip()
                
                if not line or line.startswith(':'):
                    continue
                
                if line.startswith('data: '):
                    data_str = line[6:]
                    
                    if data_str == '[DONE]':
                        break
                    
                    try:
                        data = json.loads(data_str)
                        
                        message_type = data.get('message_type', '')
                        
                        if message_type == 'complete':
                            break
                        elif message_type == 'error':
                            raise Exception(f"Stream error: {data.get('error', 'Unknown error')}")
                        elif message_type == 'result':
                            # Result message - the actual data is in the content field
                            if 'content' in data:
                                content = data['content']
                                if isinstance(content, list):
                                    for item in content:
                                        yield _extract_site_info(item)
                                else:
                                    yield _extract_site_info(content)
                        elif 'content' in data:
                            # Content with potentially multiple items
                            content = data['content']
                            if isinstance(content, list):
                                for item in content:
                                    yield _extract_site_info(item)
                            else:
                                yield _extract_site_info(content)
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SSE data: {e}")
                        continue

