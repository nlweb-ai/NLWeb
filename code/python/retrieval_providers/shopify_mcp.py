# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Shopify MCP Client - Interface for Shopify MCP (Model Context Protocol) operations.
This client enables search via MCP endpoints provided by Shopify sites.
"""

import os
import json
import aiohttp
import asyncio
from typing import List, Dict, Optional, Any, Union

from core.config import CONFIG
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("shopify_mcp")


class ShopifyMCPClient:
    """
    Client for Shopify MCP operations, providing search functionality via MCP endpoints.
    Currently supports search_shop_catalog method with USD currency and 50 results by default.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Shopify MCP client.
        
        Args:
            endpoint_name: Name of the endpoint configuration in config_retrieval.yaml
        """
        self.endpoint_name = endpoint_name
    
    async def search(self, query: str, site: Union[str, List[str]], 
                    num_results: int = 50, query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search using the MCP search_shop_catalog method.
        
        Args:
            query: The search query string
            site: Site identifier or list of sites
            num_results: Maximum number of results to return
            **kwargs: Additional parameters
            
        Returns:
            List of search results formatted as [url, schema_json, name, site]
        """
        # Handle site parameter
        if isinstance(site, list):
            site = site[0] if site else None
        
        if not site:
            logger.error("No site specified for Shopify MCP search")
            return []
        
        # Construct the MCP endpoint URL based on the site
        endpoint = f"https://{site}/api/mcp"
        
        logger.info(f"Shopify MCP search initiated for query: '{query}' on site: {site}")
        
        # Prepare the MCP request
        mcp_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "search_shop_catalog",
                "arguments": {
                    "query": query,
                    "context": f"User is searching for: {query}",
                    "limit": 50,
                    "country": "US",
                    "language": "EN"
                }
            },
            "id": 1
        }
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.debug(f"Sending request to: {endpoint}")
                logger.debug(f"Request headers: {headers}")
                logger.debug(f"Request body: {json.dumps(mcp_request, indent=2)}")
                
                async with session.post(
                    endpoint,
                    json=mcp_request,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    logger.debug(f"Response status: {response.status}")
                    logger.debug(f"Response headers: {dict(response.headers)}")
                    
                    if response.status != 200:
                        logger.error(f"Shopify MCP request failed with status {response.status}")
                        return []
                    
                    # Check content type (but be lenient since some servers misconfigure this)
                    content_type = response.headers.get('Content-Type', '')
                    
                    # Try to parse as JSON regardless of content type
                    # Some Shopify MCP endpoints incorrectly return text/html for JSON responses
                    try:
                        result = await response.json(content_type=None)  # Force JSON parsing
                    except Exception as json_error:
                        # If JSON parsing fails, then it's really not JSON
                        text = await response.text()
                        logger.error(f"Failed to parse response as JSON. Content-Type: {content_type}")
                        logger.debug(f"Response text (first 500 chars): {text[:500]}")
                        return []
                    
                    # Check for JSON-RPC error
                    if 'error' in result:
                        logger.error(f"Shopify MCP error: {result['error']}")
                        return []
                    
                    # Extract search results
                    # Handle different response formats
                    mcp_result = result.get('result', {})
                    
                    # Check if result is wrapped in content array (some MCP implementations do this)
                    if 'content' in mcp_result and isinstance(mcp_result['content'], list):
                        for content_item in mcp_result['content']:
                            if content_item.get('type') == 'text' and 'text' in content_item:
                                try:
                                    # Parse the text as JSON
                                    search_data = json.loads(content_item['text'])
                                    return self._format_results(search_data, site)
                                except json.JSONDecodeError:
                                    logger.error(f"Failed to parse search results from content text")
                    
                    # Otherwise try direct format
                    return self._format_results(mcp_result, site)
                    
        except asyncio.TimeoutError:
            logger.error("Shopify MCP request timed out")
            return []
        except Exception as e:
            logger.error(f"Shopify MCP request failed: {str(e)}")
            return []
    
    def _format_results(self, mcp_result: Dict, site: str) -> List[List[str]]:
        """
        Format MCP search results into the expected format for NLWeb.
        
        Args:
            mcp_result: Raw result from MCP search_shop_catalog
            site: The site name/domain
            
        Returns:
            List of formatted search results as [url, schema_json, name, site]
        """
        formatted_results = []
        
        try:
            # Extract products from the MCP response
            products = mcp_result.get('products', [])
            
            for product in products:
                # Start with basic schema.org structure
                schema_object = {
                    '@context': 'https://schema.org',
                    '@type': 'Product'
                }
                
                # Copy all fields from the product, mapping field names as needed
                field_mappings = {
                    'title': 'name',
                    'product_id': 'productID',
                    'product_type': 'category',
                    'vendor': 'brand',
                    'price_range': 'offers',
                    'image_url': 'image',
                    'image_alt_text': 'imageAltText'
                }
                
                # Copy all fields from product to schema_object
                for key, value in product.items():
                    if value is not None and value != '':
                        # Use mapped name if available, otherwise use original key
                        schema_key = field_mappings.get(key, key)
                        
                        # Special handling for certain fields
                        if key == 'vendor' and value:
                            # Format vendor as Brand object
                            schema_object[schema_key] = {
                                '@type': 'Brand',
                                'name': value
                            }
                        elif key == 'price_range' and value:
                            # Format price_range as AggregateOffer
                            schema_object[schema_key] = {
                                '@type': 'AggregateOffer',
                                'priceCurrency': value.get('currency', 'USD'),
                                'lowPrice': float(value.get('min', '0')) if value.get('min') else 0,
                                'highPrice': float(value.get('max', '0')) if value.get('max') else 0
                            }
                        elif key == 'variants' and value and len(value) > 1:
                            # If multiple variants, create individual offers
                            offers_list = []
                            for variant in value:
                                offer = {'@type': 'Offer'}
                                # Copy all variant fields
                                for v_key, v_value in variant.items():
                                    if v_value is not None and v_value != '':
                                        offer[v_key] = v_value
                                offers_list.append(offer)
                            
                            # Override the price_range offer with individual offers
                            if offers_list:
                                schema_object['offers'] = offers_list
                        else:
                            # Copy field as-is
                            schema_object[schema_key] = value
                
                # Format as expected by NLWeb: [url, schema_json, name, site]
                formatted_result = [
                    product.get('url', ''),  # url
                    json.dumps(schema_object),  # schema_json
                    product.get('title', ''),  # name
                    site  # site
                ]
                
                formatted_results.append(formatted_result)
                
        except Exception as e:
            logger.error(f"Error formatting Shopify MCP results: {str(e)}")
        
        logger.info(f"Formatted {len(formatted_results)} results from Shopify MCP")
        return formatted_results
    
    def _extract_price(self, product: Dict) -> str:
        """
        Extract price information from product data.
        
        Args:
            product: Product data from MCP
            
        Returns:
            Price string or empty string if not available
        """
        try:
            price_range = product.get('priceRange', {})
            min_price = price_range.get('minVariantPrice', {})
            if min_price:
                amount = min_price.get('amount', '')
                currency = min_price.get('currencyCode', 'USD')
                return f"{amount} {currency}"
        except:
            pass
        return ''
    
    async def search_all_sites(self, query: str, num_results: int = 50, 
                             query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search across all sites - not implemented for Shopify MCP.
        
        Args:
            query: Search query
            num_results: Maximum number of results
            query_params: Optional query parameters
            **kwargs: Additional parameters
            
        Returns:
            Empty list - Shopify MCP doesn't support cross-site search
        """
        return []
    
    async def get_sites(self) -> List[str]:
        """
        Get list of available Shopify sites from shop_sites.txt.
        
        Returns:
            List of Shopify site domains that support MCP
        """
        sites = []
        # Get config directory - try different methods
        config_dir = getattr(CONFIG, 'config_directory', None) or os.path.join(os.path.dirname(__file__), '../../config')
        shop_sites_path = os.path.join(config_dir, 'shop_sites.txt')
        
        try:
            with open(shop_sites_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        sites.append(line)
            
            logger.info(f"Loaded {len(sites)} Shopify sites from shop_sites.txt")
            return sites
            
        except FileNotFoundError:
            logger.warning(f"shop_sites.txt not found at {shop_sites_path}")
            return []
        except Exception as e:
            logger.error(f"Error reading shop_sites.txt: {str(e)}")
            return []
    
    async def close(self):
        """
        Close the MCP client. No cleanup needed for now.
        """
        pass