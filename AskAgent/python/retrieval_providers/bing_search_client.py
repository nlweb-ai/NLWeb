# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Bing Web Search Client - Interface for Bing Web Search API operations.
Provides read-only access to web search results with site-specific filtering.
"""

import json
import httpx
import asyncio
import re
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urlparse, quote
from core.config import CONFIG
from core.retriever import RetrievalClientBase
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("bing_search_client")


class BingSearchClient(RetrievalClientBase):
    """
    Client for Bing Web Search API operations, providing read-only access
    to web search results with optional site-specific filtering.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Bing Search client.
        
        Args:
            endpoint_name: Name of the endpoint to use (defaults to "bing_search")
        """
        super().__init__()  # Initialize the base class
        self.endpoint_name = endpoint_name or "bing_search"
        
        # Get endpoint configuration
        self.endpoint_config = self._get_endpoint_config()
        
        # Get API key and endpoint
        self.api_key = self.endpoint_config.api_key
      
        # Get API endpoint or use default
        self.api_endpoint = self.endpoint_config.api_endpoint
        if not self.api_endpoint:
            self.api_endpoint = "https://www.bingapis.com/api/v7/search"
        
        logger.info(f"Initialized BingSearchClient for endpoint: {self.endpoint_name}")
    
    def _get_endpoint_config(self):
        """Get the Bing Search endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Verify this is a Bing Search endpoint
        if endpoint_config.db_type != "bing_search":
            error_msg = f"Endpoint {self.endpoint_name} is not a Bing Search endpoint (type: {endpoint_config.db_type})"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return endpoint_config
    
    async def can_handle_query(self, site: Union[str, List[str]], **kwargs) -> bool:
        """
        Check if Bing Search can handle a query for the given site(s).
        Bing is a fallback and should only be used when explicitly requested via db parameter.

        Args:
            site: Site identifier or list of sites
            **kwargs: Additional parameters including query_params

        Returns:
            True only if db parameter is explicitly set to 'bing' or 'bing_search'
        """
        # Check if db parameter is explicitly set to use Bing
        query_params = kwargs.get('query_params', {})
        db_param = query_params.get('db')

        # Handle case where db_param might be a list
        if isinstance(db_param, list) and len(db_param) > 0:
            db_param = db_param[0]

        # Only handle query if explicitly requested via db parameter
        if db_param and db_param in ['bing', 'bing_search']:
            return True

        # Otherwise, Bing should not handle this query (it's a fallback)
        return False

    def _extract_domain_from_url(self, url: str) -> str:
        """Extract domain from URL for site identification."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            # Remove www. prefix if present
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except:
            return "unknown"
    
    def _extract_product_info_from_snippet(self, title: str, snippet: str, grounding: str = "") -> Dict[str, Any]:
        """
        Extract product information from title and snippet text.
        
        Args:
            title: Page title from Bing result
            snippet: Snippet text from Bing result
            grounding: Additional grounding text from Bing (if available)
            
        Returns:
            Dictionary with extracted product information
        """
        product_info = {}
        
        # Combine title, snippet and grounding for better extraction
        full_text = f"{title} {snippet} {grounding}"
        
        # Price extraction patterns
        price_patterns = [
            r'\$([0-9,]+\.?\d*)',  # $299.99
            r'USD\s*([0-9,]+\.?\d*)',  # USD 299.99
            r'Starting at \$([0-9,]+\.?\d*)',  # Starting at $199
            r'From \$([0-9,]+\.?\d*)',  # From $199
            r'Price:\s*\$([0-9,]+\.?\d*)',  # Price: $299
            r'Sale:\s*\$([0-9,]+\.?\d*)',  # Sale: $199
            r'Now:\s*\$([0-9,]+\.?\d*)',  # Now: $199
        ]
        
        # Try to find a price
        for pattern in price_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(',', '')
                try:
                    product_info['price'] = float(price_str)
                    product_info['price_currency'] = 'USD'
                    break
                except ValueError:
                    pass
        
        # Price range extraction (e.g., "$99 - $299")
        range_pattern = r'\$([0-9,]+\.?\d*)\s*[-–]\s*\$([0-9,]+\.?\d*)'
        range_match = re.search(range_pattern, full_text)
        if range_match and 'price' not in product_info:
            try:
                low_price = float(range_match.group(1).replace(',', ''))
                high_price = float(range_match.group(2).replace(',', ''))
                product_info['price_range'] = {
                    'min': low_price,
                    'max': high_price,
                    'currency': 'USD'
                }
            except ValueError:
                pass
        
        # Brand extraction from title
        # Common patterns: "Brand Name Product | Site", "Brand Name - Product", "Product by Brand"
        brand_patterns = [
            r'^([A-Z][A-Za-z\-\s&]+?)\s+(?:Copper|Stainless|Non[\-\s]?Stick|Cast[\-\s]?Iron)',  # Brand before material
            r'^([A-Z][A-Za-z\-\s&]+?)\s*[-–|]',  # Brand followed by separator
            r'(?:by|from|By|From)\s+([A-Z][A-Za-z\-\s&]+?)(?:\s*[-–|]|\s+at\s+|\s*$)',  # by/from Brand
            r'^([A-Z][A-Za-z\-\s&]+?)\s+\d+[\-\s]?(?:inch|Inch|qt|Qt|piece|Piece)',  # Brand before size
        ]
        
        for pattern in brand_patterns:
            match = re.search(pattern, title)
            if match:
                brand = match.group(1).strip()
                # Filter out common non-brand words
                non_brands = ['Shop', 'Buy', 'The', 'New', 'Best', 'Top', 'Sale', 'Free']
                if brand and brand not in non_brands and len(brand) > 2:
                    product_info['brand'] = brand
                    break
        
        # Well-known cookware brands to look for
        known_brands = [
            'All-Clad', 'All Clad', 'AllClad',
            'Le Creuset', 'LeCreuset',
            'Williams Sonoma', 'Williams-Sonoma',
            'Calphalon', 'Cuisinart', 'Lodge',
            'T-fal', 'Tfal', 'Tefal',
            'Anolon', 'Rachael Ray', 'GreenPan',
            'Viking', 'Staub', 'Scanpan',
            'Swiss Diamond', 'Mauviel',
            'de Buyer', 'DeBuyer', 'Matfer Bourgeat'
        ]
        
        if 'brand' not in product_info:
            for brand in known_brands:
                if brand.lower() in title.lower() or brand.lower() in snippet.lower():
                    product_info['brand'] = brand
                    break
        
        # Extract product features from snippet
        features = []
        
        # Size extraction
        size_pattern = r'(\d+(?:\.\d+)?)\s*(?:inch|in|"|cm|quart|qt|liter|l)\b'
        size_matches = re.findall(size_pattern, full_text, re.IGNORECASE)
        if size_matches:
            features.append(f"Size: {size_matches[0]}")
        
        # Material extraction
        materials = ['copper', 'stainless steel', 'cast iron', 'aluminum', 'non-stick', 
                    'nonstick', 'ceramic', 'carbon steel', 'hard anodized', 'tri-ply']
        for material in materials:
            if material.lower() in full_text.lower():
                features.append(material.title())
                break
        
        # Special features
        feature_keywords = ['dishwasher safe', 'oven safe', 'induction compatible', 
                          'pfoa free', 'ptfe free', 'professional', 'commercial grade']
        for keyword in feature_keywords:
            if keyword.lower() in full_text.lower():
                features.append(keyword.title())
        
        if features:
            product_info['features'] = features
        
        return product_info
    
    def _convert_bing_result_to_nlweb_format(self, bing_result: Dict[str, Any], site: str = None, 
                                             extract_product_info: bool = True) -> List[str]:
        """
        Convert a single Bing search result to NLWeb format.
        
        Args:
            bing_result: Single result from Bing API
            site: Site filter used in the query (if any)
            extract_product_info: Whether to extract product information from snippets
            
        Returns:
            List in NLWeb format: [url, json_str, name, site]
        """
        url = bing_result.get("url", "")
        name = bing_result.get("name", "")
        snippet = bing_result.get("snippet", "")
        
        # Extract domain from URL if site not provided
        if not site or site == "all":
            site = self._extract_domain_from_url(url)
        
        # Try to extract product information if enabled
        if extract_product_info:
            # Get grounding text if available (contains richer product data)
            grounding_text = ""
            if "grounding" in bing_result and isinstance(bing_result["grounding"], dict):
                grounding_text = bing_result["grounding"].get("semanticDocument", "")
            
            product_info = self._extract_product_info_from_snippet(name, snippet, grounding_text)
        else:
            product_info = {}
        
        # Determine if this looks like a product based on extracted info
        is_product = bool(product_info and ('price' in product_info or 'brand' in product_info 
                                            or 'price_range' in product_info))
        
        # Create schema.org-like JSON object
        if is_product:
            # Use Product schema when product info is available
            schema_obj = {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": name,
                "description": snippet,
                "url": url
            }
            
            # Add brand if extracted
            if 'brand' in product_info:
                schema_obj["brand"] = {
                    "@type": "Brand",
                    "name": product_info['brand']
                }
            
            # Add price information
            if 'price' in product_info:
                schema_obj["offers"] = {
                    "@type": "Offer",
                    "price": product_info['price'],
                    "priceCurrency": product_info.get('price_currency', 'USD'),
                    "url": url
                }
            elif 'price_range' in product_info:
                schema_obj["offers"] = {
                    "@type": "AggregateOffer",
                    "lowPrice": product_info['price_range']['min'],
                    "highPrice": product_info['price_range']['max'],
                    "priceCurrency": product_info['price_range'].get('currency', 'USD'),
                    "url": url
                }
            
            # Add features if extracted
            if 'features' in product_info:
                schema_obj["additionalProperty"] = [
                    {"@type": "PropertyValue", "name": "Feature", "value": feature}
                    for feature in product_info['features']
                ]
            
            # Add image if available
            if bing_result.get("thumbnailUrl"):
                schema_obj["image"] = bing_result["thumbnailUrl"]
            
        else:
            # Use WebPage schema (original behavior)
            schema_obj = {
                "@type": "WebPage",
                "name": name,
                "description": snippet,
                "url": url,
                "datePublished": bing_result.get("dateLastCrawled"),
                "thumbnailUrl": bing_result.get("thumbnailUrl"),
                "isFamilyFriendly": bing_result.get("isFamilyFriendly", True)
            }
            
            # Add any additional metadata from Bing
            if "displayUrl" in bing_result:
                schema_obj["displayUrl"] = bing_result["displayUrl"]
        
        json_str = json.dumps(schema_obj)
        
        return [url, json_str, name, site]
    
    async def search(self, query: str, site: Union[str, List[str]], 
                    num_results: int = 50, **kwargs) -> List[List[str]]:
        """
        Search for documents matching the query and site using Bing Web Search.
        Supports using rewritten queries from handler for better results.
        
        Args:
            query: Search query string
            site: Site identifier or list of sites to search within
            num_results: Maximum number of results to return
            **kwargs: Additional parameters including:
                - handler: Optional handler with rewritten_queries
                - extract_product_info: Whether to extract product info from snippets (default: True)
                - query_params: Optional query parameters dict
            
        Returns:
            List of search results in NLWeb format
        """
        try:
            # Check for feature flags from query_params or kwargs
            query_params = kwargs.get('query_params', {})
            extract_product_info = kwargs.get('extract_product_info', 
                                             query_params.get('extract_product_info', 'true'))
            
            # Convert string to boolean if needed
            if isinstance(extract_product_info, str):
                extract_product_info = extract_product_info.lower() not in ['false', '0', 'no']
            
            # Check if we have pre-computed rewritten queries from the handler
            handler = kwargs.get('handler')
            
            # Wait for rewritten_queries to be available if handler exists
            if handler:
                max_wait = 10  # Maximum wait time in seconds
                wait_interval = 0.1  # Check every 100ms
                waited = 0
                
                while not hasattr(handler, 'rewritten_queries') and waited < max_wait:
                    await asyncio.sleep(wait_interval)
                    waited += wait_interval
                
                if waited >= max_wait:
                    logger.warning(f"Timeout waiting for rewritten_queries after {max_wait}s")
            
            rewritten_queries = getattr(handler, 'rewritten_queries', None) if handler else None
            
            # Use rewritten queries if available and multiple queries exist
            if rewritten_queries and len(rewritten_queries) > 1:
                logger.info(f"Using {len(rewritten_queries)} rewritten queries for Bing search: {rewritten_queries}")
                
                # Calculate results per query to maintain total count
                results_per_query = max(1, num_results // len(rewritten_queries))
                remainder = num_results % len(rewritten_queries)
                
                # Execute searches for each rewritten query in parallel
                tasks = []
                for i, rewritten_query in enumerate(rewritten_queries):
                    # Add remainder to first queries
                    query_results = results_per_query + (1 if i < remainder else 0)
                    
                    # Handle multiple sites
                    if isinstance(site, list):
                        # For multiple sites, divide results among sites for this query
                        for single_site in site:
                            site_results_count = max(1, query_results // len(site))
                            task = asyncio.create_task(
                                self._search_single_site(rewritten_query, single_site, site_results_count,
                                                       extract_product_info=extract_product_info)
                            )
                            tasks.append(task)
                    else:
                        # Single site
                        task = asyncio.create_task(
                            self._search_single_site(rewritten_query, site, query_results,
                                                   extract_product_info=extract_product_info)
                        )
                        tasks.append(task)
                
                # Execute all searches in parallel
                all_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Combine results, filtering out errors and deduplicating by URL
                combined_results = []
                seen_urls = set()
                
                for result in all_results:
                    if isinstance(result, Exception):
                        logger.warning(f"Search failed for a rewritten query: {result}")
                    elif result:
                        for item in result:
                            url = item[0] if item else None
                            if url and url not in seen_urls:
                                seen_urls.add(url)
                                combined_results.append(item)
                
                # Limit to requested number of results
                return combined_results[:num_results]
            
            # No rewritten queries - use original query
            # Handle multiple sites
            if isinstance(site, list):
                # For multiple sites, perform separate searches and combine results
                all_results = []
                results_per_site = max(10, num_results // len(site))
                
                for single_site in site:
                    site_results = await self._search_single_site(query, single_site, results_per_site,
                                                                 extract_product_info=extract_product_info)
                    all_results.extend(site_results)
                
                # Limit to requested number of results
                return all_results[:num_results]
            else:
                return await self._search_single_site(query, site, num_results,
                                                     extract_product_info=extract_product_info)
                
        except Exception as e:
            logger.error(f"Error in Bing search: {e}")
            return []
    
    async def _search_single_site(self, query: str, site: str, num_results: int,
                                  extract_product_info: bool = True) -> List[List[str]]:
        """
        Perform search for a single site.
        
        Args:
            query: Search query string
            site: Site to search within (or "all" for no site filter)
            num_results: Maximum number of results
            extract_product_info: Whether to extract product info from snippets
            
        Returns:
            List of search results
        """
        # Build the search query
        if site and site != "all":
            # Add site filter to query
            search_query = f"{query} site:{site}"
        else:
            search_query = query
        
        # Prepare request parameters
        params = {
            "q": search_query,
            "appid": self.api_key,
            "count": min(num_results, 50)  # Bing limits to 50 per request
        }
        
        try:
            logger.info(f"Searching Bing for: {search_query} (limit: {num_results})")

            # Make request to Bing API
            async with httpx.AsyncClient() as client:
                response = await client.get(self.api_endpoint, params=params, timeout=30.0)
                response.raise_for_status()

                data = response.json()

                # Extract web pages from response
                web_pages = data.get("webPages", {})
                results = web_pages.get("value", [])

                logger.info(f"Bing returned {len(results)} results")

                # Convert to NLWeb format
                nlweb_results = []
                for result in results[:num_results]:
                    nlweb_result = self._convert_bing_result_to_nlweb_format(result, site,
                                                                            extract_product_info=extract_product_info)
                    nlweb_results.append(nlweb_result)
                
                return nlweb_results
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during Bing search: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during Bing search: {e}")
            return []
    
    async def search_all_sites(self, query: str, num_results: int = 50, **kwargs) -> List[List[str]]:
        """
        Search across all sites (no site filter).
        
        Args:
            query: Search query string
            num_results: Maximum number of results to return
            **kwargs: Additional parameters
            
        Returns:
            List of search results
        """
        return await self.search(query, "all", num_results, **kwargs)
    
    async def search_by_url(self, url: str, **kwargs) -> Optional[List[str]]:
        """
        Retrieve a document by its exact URL.
        Note: This is not supported by Bing Search API.
        
        Args:
            url: URL to search for
            **kwargs: Additional parameters
            
        Returns:
            None (not supported)
        """
        logger.debug("search_by_url is not supported by Bing Search API")
        return None
    
    async def get_sites(self, **kwargs) -> Optional[List[str]]:
        """
        Get list of all sites available.
        Note: This is not applicable for web search.
        
        Args:
            **kwargs: Additional parameters
            
        Returns:
            None (not applicable)
        """
        return None
    
    async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs) -> int:
        """
        Upload documents to the database.
        Note: This is a read-only provider.
        
        Args:
            documents: List of document objects
            **kwargs: Additional parameters
            
        Raises:
            NotImplementedError: This is a read-only provider
        """
        raise NotImplementedError("BingSearchClient is a read-only provider - upload is not supported")
    
    async def delete_documents_by_site(self, site: str, **kwargs) -> int:
        """
        Delete all documents matching the specified site.
        Note: This is a read-only provider.
        
        Args:
            site: Site identifier
            **kwargs: Additional parameters
            
        Raises:
            NotImplementedError: This is a read-only provider
        """
        raise NotImplementedError("BingSearchClient is a read-only provider - delete is not supported")
