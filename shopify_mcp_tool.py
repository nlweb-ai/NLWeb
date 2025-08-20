#!/usr/bin/env python3
"""
Standalone Shopify MCP tool for testing and parsing various response formats.
Handles:
- JSON string products that need double parsing
- Shopify GID references
- Mixed valid and invalid products
- Fetching additional details when needed
"""

import json
import asyncio
import aiohttp
import argparse
import sys
from typing import List, Dict, Any, Optional, Union
from datetime import datetime


class ShopifyMCPTool:
    """Standalone tool for testing Shopify MCP endpoints and parsing responses"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
    def log(self, message: str, level: str = "INFO"):
        """Simple logging"""
        if self.verbose or level in ["ERROR", "WARNING"]:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}", file=sys.stderr)
    
    async def call_mcp_method(self, site: str, method: str, arguments: Dict[str, Any]) -> Optional[Dict]:
        """
        Call a Shopify MCP method on a given site.
        
        Args:
            site: The Shopify site domain (e.g., "hashipottery.com")
            method: The MCP method name (e.g., "search_shop_catalog")
            arguments: Method arguments
            
        Returns:
            The parsed MCP response or None on error
        """
        endpoint = f"https://{site}/api/mcp"
        
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": method,
                "arguments": arguments
            },
            "id": 1
        }
        
        self.log(f"Calling {method} on {site}", "INFO")
        if self.verbose:
            self.log(f"Request: {json.dumps(request, indent=2)}", "DEBUG")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=request,
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status != 200:
                        self.log(f"HTTP {response.status} from {site}", "ERROR")
                        return None
                    
                    result = await response.json(content_type=None)
                    
                    if 'error' in result:
                        self.log(f"MCP error: {result['error']}", "ERROR")
                        return None
                    
                    return result
                    
        except Exception as e:
            self.log(f"Request failed: {e}", "ERROR")
            return None
    
    def parse_product(self, product: Any, site: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single product which might be in various formats.
        
        Args:
            product: The product data (could be dict, string, GID, etc.)
            site: The site domain for context
            
        Returns:
            Normalized product dictionary or None if invalid
        """
        # Case 1: Already a valid dictionary
        if isinstance(product, dict):
            self.log(f"Product is already a dict with keys: {list(product.keys())}", "DEBUG")
            return product
        
        # Case 2: None or empty
        if product is None or product == "":
            self.log("Product is None or empty", "DEBUG")
            return None
        
        # Case 3: String that might be JSON
        if isinstance(product, str):
            # Try to parse as JSON
            try:
                parsed = json.loads(product)
                if isinstance(parsed, dict):
                    self.log(f"Parsed JSON string to dict with keys: {list(parsed.keys())}", "DEBUG")
                    return parsed
                else:
                    self.log(f"JSON parsed but not a dict: {type(parsed)}", "WARNING")
                    return None
            except json.JSONDecodeError:
                pass
            
            # Check if it's a Shopify GID
            if product.startswith("gid://shopify/"):
                self.log(f"Found Shopify GID: {product}", "INFO")
                # Extract the type and ID
                parts = product.split("/")
                if len(parts) >= 4:
                    gid_type = parts[3]  # Product or ProductVariant
                    gid_id = parts[4] if len(parts) > 4 else None
                    
                    return {
                        "_needs_fetch": True,
                        "_gid": product,
                        "_gid_type": gid_type,
                        "_gid_id": gid_id,
                        "title": f"Product {gid_id}",  # Placeholder
                        "url": f"https://{site}/products/{gid_id}"  # Guess URL
                    }
            
            # Check if it's a simple product ID
            if product.replace("-", "").replace("_", "").isalnum():
                self.log(f"Found product ID: {product}", "INFO")
                return {
                    "_needs_fetch": True,
                    "_id": product,
                    "title": f"Product {product}",
                    "url": f"https://{site}/products/{product}"
                }
            
            # Unknown string format
            self.log(f"Unknown string format: {product[:50]}...", "WARNING")
            return None
        
        # Case 4: Unexpected type
        self.log(f"Unexpected product type: {type(product)}", "WARNING")
        return None
    
    def extract_products_from_response(self, mcp_response: Dict) -> List[Any]:
        """
        Extract products from an MCP response, handling various wrapper formats.
        
        Args:
            mcp_response: The full MCP response
            
        Returns:
            List of raw products (might be dicts, strings, etc.)
        """
        products = []
        
        # Navigate to the result
        result = mcp_response.get('result', {})
        
        # Check if result has content array (common MCP format)
        if 'content' in result and isinstance(result['content'], list):
            for content_item in result['content']:
                if content_item.get('type') == 'text' and 'text' in content_item:
                    try:
                        # Parse the text content as JSON
                        search_data = json.loads(content_item['text'])
                        
                        # Look for products in various locations
                        if 'products' in search_data:
                            products.extend(search_data['products'])
                        elif 'items' in search_data:
                            products.extend(search_data['items'])
                        elif 'results' in search_data:
                            products.extend(search_data['results'])
                        elif isinstance(search_data, list):
                            # The search_data itself might be a list of products
                            products.extend(search_data)
                            
                    except json.JSONDecodeError:
                        self.log("Failed to parse content text as JSON", "WARNING")
        
        # Also check if products are directly in result
        elif 'products' in result:
            products = result['products']
        elif 'items' in result:
            products = result['items']
        
        self.log(f"Extracted {len(products)} raw products", "INFO")
        return products
    
    async def search_and_parse(self, site: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search a Shopify site and parse the results intelligently.
        
        Args:
            site: The Shopify site domain
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of normalized product dictionaries
        """
        # Call search_shop_catalog
        response = await self.call_mcp_method(
            site,
            "search_shop_catalog",
            {
                "query": query,
                "context": f"User is searching for: {query}",
                "limit": limit,
                "country": "US",
                "language": "EN"
            }
        )
        
        if not response:
            return []
        
        # Extract products from response
        raw_products = self.extract_products_from_response(response)
        
        # Parse each product
        parsed_products = []
        for i, raw_product in enumerate(raw_products):
            self.log(f"\nProcessing product {i}: type={type(raw_product).__name__}", "DEBUG")
            
            parsed = self.parse_product(raw_product, site)
            if parsed:
                parsed_products.append(parsed)
                
                # If product needs fetching, we could fetch details here
                if parsed.get("_needs_fetch"):
                    self.log(f"Product {i} needs additional fetching (GID or ID reference)", "INFO")
                    # In a real implementation, we could call get_product here
                    # For now, we'll just mark it
        
        return parsed_products
    
    def format_product_for_display(self, product: Dict[str, Any]) -> str:
        """Format a product for display"""
        lines = []
        
        title = product.get('title', product.get('name', 'Untitled'))
        lines.append(f"  Title: {title}")
        
        if 'url' in product:
            lines.append(f"  URL: {product['url']}")
        
        if 'product_id' in product:
            lines.append(f"  ID: {product['product_id']}")
        elif '_gid' in product:
            lines.append(f"  GID: {product['_gid']}")
        elif '_id' in product:
            lines.append(f"  ID: {product['_id']}")
        
        if 'price' in product:
            lines.append(f"  Price: {product['price']}")
        elif 'price_range' in product:
            pr = product['price_range']
            if isinstance(pr, dict):
                lines.append(f"  Price: {pr.get('min', '?')} - {pr.get('max', '?')} {pr.get('currency', '')}")
        
        if 'vendor' in product:
            vendor = product['vendor']
            if isinstance(vendor, dict):
                vendor = vendor.get('name', vendor)
            lines.append(f"  Vendor: {vendor}")
        
        if product.get('_needs_fetch'):
            lines.append(f"  ⚠️  Needs fetching (reference only)")
        
        return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description='Test Shopify MCP endpoints and parsing')
    parser.add_argument('site', help='Shopify site domain (e.g., hashipottery.com)')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--limit', type=int, default=10, help='Maximum results (default: 10)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--raw', action='store_true', help='Show raw response')
    
    args = parser.parse_args()
    
    tool = ShopifyMCPTool(verbose=args.verbose)
    
    print(f"Searching '{args.site}' for: {args.query}")
    print("=" * 60)
    
    # If raw mode, show the full response
    if args.raw:
        response = await tool.call_mcp_method(
            args.site,
            "search_shop_catalog",
            {
                "query": args.query,
                "context": f"User is searching for: {args.query}",
                "limit": args.limit,
                "country": "US",
                "language": "EN"
            }
        )
        print("\nRaw MCP Response:")
        print(json.dumps(response, indent=2))
        return
    
    # Otherwise, parse and display nicely
    products = await tool.search_and_parse(args.site, args.query, args.limit)
    
    print(f"\nFound {len(products)} products:\n")
    
    for i, product in enumerate(products):
        print(f"Product {i+1}:")
        print(tool.format_product_for_display(product))
        print()
    
    # Summary statistics
    needs_fetch = sum(1 for p in products if p.get('_needs_fetch'))
    if needs_fetch > 0:
        print(f"\n⚠️  {needs_fetch} products are references that need additional fetching")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)