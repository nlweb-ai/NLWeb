#!/usr/bin/env python3
"""
Robust Shopify MCP parser that handles all response formats.
This can be integrated back into shopify_mcp.py's _format_results method.
"""

import json
import asyncio
import aiohttp
import sys
import os
from typing import List, Dict, Any, Optional, Union


class RobustShopifyParser:
    """
    Robust parser for Shopify MCP responses that handles:
    - Normal dictionary products
    - JSON string products (double-encoded)
    - Shopify GID references
    - Mixed/malformed data
    """
    
    @staticmethod
    async def call_mcp_method(site: str, method: str, arguments: Dict[str, Any]) -> Optional[Dict]:
        """
        Call a Shopify MCP method on a given site.
        
        Args:
            site: The Shopify site domain
            method: The MCP method name
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
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=request,
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status != 200:
                        return None
                    
                    result = await response.json(content_type=None)
                    
                    if 'error' in result:
                        return None
                    
                    return result
                    
        except Exception:
            return None
    
    @staticmethod
    async def fetch_product_by_gid(gid: str, site: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed product information using a GID.
        
        Args:
            gid: The Shopify GID (e.g., "gid://shopify/Product/7234567890")
            site: The site domain
            
        Returns:
            Product details or None if fetch fails
        """
        # Call get_product_details MCP method
        response = await RobustShopifyParser.call_mcp_method(
            site,
            "get_product_details",
            {"product_id": gid}
        )
        
        if not response:
            return None
        
        # Extract product from response
        result = response.get('result', {})
        
        # Check if result has content array
        if 'content' in result and isinstance(result['content'], list):
            for content_item in result['content']:
                if content_item.get('type') == 'text' and 'text' in content_item:
                    try:
                        # Parse the text content as JSON
                        product_data = json.loads(content_item['text'])
                        
                        # The product data might be wrapped
                        if 'product' in product_data:
                            return product_data['product']
                        else:
                            return product_data
                            
                    except json.JSONDecodeError:
                        pass
        
        # Check if product is directly in result
        if 'product' in result:
            return result['product']
        
        return None
    
    @staticmethod
    async def parse_single_product(product: Any, site: str, fetch_gids: bool = False) -> Optional[Dict[str, Any]]:
        """
        Parse a single product which might be in various formats.
        
        Args:
            product: The product data (could be dict, string, GID, None, etc.)
            site: The site domain for context
            fetch_gids: If True, fetch full details for GID references
            
        Returns:
            Normalized product dictionary or None if invalid
        """
        # Case 1: None or empty string - skip
        if product is None or product == "":
            return None
        
        # Case 2: Already a valid dictionary - return as is
        if isinstance(product, dict):
            return product
        
        # Case 3: String that might need parsing
        if isinstance(product, str):
            # Try to parse as JSON (double-encoded case)
            try:
                parsed = json.loads(product)
                if isinstance(parsed, dict):
                    # Successfully parsed to dict
                    return parsed
                else:
                    # Parsed but not a dict (could be list, string, etc.)
                    return None
            except json.JSONDecodeError:
                pass
            
            # Check if it's a Shopify GID that needs fetching
            if product.startswith("gid://shopify/"):
                if fetch_gids:
                    # Fetch the full product details
                    fetched = await RobustShopifyParser.fetch_product_by_gid(product, site)
                    if fetched:
                        return fetched
                
                # If fetch failed or not fetching, return minimal structure
                parts = product.split("/")
                if len(parts) >= 5:
                    product_id = parts[4]
                    return {
                        "product_id": product,
                        "title": f"Product {product_id} (GID reference)",
                        "url": f"https://{site}/products/{product_id}",
                        "_needs_fetch": True,
                        "_gid": product
                    }
            
            # Unknown string format - skip
            return None
        
        # Case 4: Other types (list, number, etc.) - skip
        return None
    
    @staticmethod
    async def format_products(mcp_result: Dict, site: str, fetch_gids: bool = False) -> List[List[str]]:
        """
        Format MCP search results into the expected format for NLWeb.
        This is a drop-in replacement for the _format_results method.
        
        Args:
            mcp_result: The MCP result containing products
            site: The site name/domain
            fetch_gids: If True, fetch full details for GID references
            
        Returns:
            List of formatted search results as [url, schema_json, name, site]
        """
        formatted_results = []
        
        try:
            # Extract products from the MCP response
            products = mcp_result.get('products', [])
            
            if not isinstance(products, list):
                # Products should be a list
                return []
            
            for raw_product in products:
                # Parse the product robustly
                product = await RobustShopifyParser.parse_single_product(raw_product, site, fetch_gids)
                
                if not product:
                    # Skip invalid products
                    continue
                
                # Now format the valid product
                # Start with basic schema.org structure
                schema_object = {
                    '@context': 'https://schema.org',
                    '@type': 'Product'
                }
                
                # Copy fields with proper mapping
                field_mappings = {
                    'title': 'name',
                    'product_id': 'productID',
                    'product_type': 'category',
                    'vendor': 'brand',
                    'price_range': 'offers',
                    'image_url': 'image',
                    'description': 'description'
                }
                
                # Safely iterate over product fields
                if isinstance(product, dict):
                    for key, value in product.items():
                        if value is not None and value != '':
                            schema_key = field_mappings.get(key, key)
                            
                            # Special handling for certain fields
                            if key == 'vendor' and value:
                                # Format vendor as Brand object
                                if isinstance(value, str):
                                    schema_object[schema_key] = {
                                        '@type': 'Brand',
                                        'name': value
                                    }
                                elif isinstance(value, dict):
                                    schema_object[schema_key] = value
                                    
                            elif key == 'price_range' and isinstance(value, dict):
                                # Format price_range as AggregateOffer
                                schema_object[schema_key] = {
                                    '@type': 'AggregateOffer',
                                    'priceCurrency': value.get('currency', 'USD'),
                                    'lowPrice': float(value.get('min', '0')) if value.get('min') else 0,
                                    'highPrice': float(value.get('max', '0')) if value.get('max') else 0
                                }
                                
                            elif key == 'variants' and isinstance(value, list) and len(value) > 1:
                                # If multiple variants, create individual offers
                                offers_list = []
                                for variant in value:
                                    if isinstance(variant, dict):
                                        offer = {'@type': 'Offer'}
                                        for v_key, v_value in variant.items():
                                            if v_value is not None and v_value != '':
                                                offer[v_key] = v_value
                                        offers_list.append(offer)
                                
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
            # Log but don't crash
            print(f"Error formatting products: {e}")
        
        return formatted_results


async def test_parser():
    """Test the robust parser with various input formats"""
    
    parser = RobustShopifyParser()
    site = "example.com"
    
    # Test 1: Normal products (what we see from hashipottery.com)
    print("Test 1: Normal dictionary products")
    print("-" * 50)
    normal_data = {
        "products": [
            {
                "product_id": "gid://shopify/Product/123",
                "title": "Beautiful Plate",
                "url": "https://example.com/plate",
                "price_range": {"min": "25", "max": "35", "currency": "USD"}
            }
        ]
    }
    results = await parser.format_products(normal_data, site)
    print(f"Formatted {len(results)} results")
    if results:
        result = results[0]
        print(f"  URL: {result[0]}")
        print(f"  Name: {result[2]}")
    
    # Test 2: Products as JSON strings (double-encoded)
    print("\nTest 2: Double-encoded JSON products")
    print("-" * 50)
    json_string_data = {
        "products": [
            '{"product_id": "456", "title": "JSON String Product", "url": "https://example.com/json"}'
        ]
    }
    results = await parser.format_products(json_string_data, site)
    print(f"Formatted {len(results)} results")
    if results:
        result = results[0]
        print(f"  URL: {result[0]}")
        print(f"  Name: {result[2]}")
    
    # Test 3: Mixed valid and invalid
    print("\nTest 3: Mixed valid and invalid products")
    print("-" * 50)
    mixed_data = {
        "products": [
            {"title": "Valid Product", "url": "https://example.com/valid"},
            None,
            "",
            "invalid_string",
            '{"title": "JSON String", "url": "https://example.com/json2"}',
            {"title": "Another Valid", "url": "https://example.com/valid2"}
        ]
    }
    results = await parser.format_products(mixed_data, site)
    print(f"Formatted {len(results)} results (should be 3)")
    for i, result in enumerate(results):
        print(f"  Result {i+1}: {result[2]}")
    
    # Test 4: Shopify GIDs (without fetching)
    print("\nTest 4: Shopify GID references (without fetching)")
    print("-" * 50)
    gid_data = {
        "products": [
            "gid://shopify/Product/7234567890"
        ]
    }
    results = await parser.format_products(gid_data, site, fetch_gids=False)
    print(f"Formatted {len(results)} results")
    if results:
        result = results[0]
        print(f"  URL: {result[0]}")
        print(f"  Name: {result[2]}")
        schema = json.loads(result[1])
        if "_needs_fetch" in schema:
            print(f"  Note: Needs fetching")
    
    # Test 5: Shopify GIDs with fetching (real site)
    print("\nTest 5: Shopify GID with fetching (real site)")
    print("-" * 50)
    real_site = "hashipottery.com"
    real_gid_data = {
        "products": [
            "gid://shopify/Product/7241139093575"  # Real product from earlier test
        ]
    }
    print(f"Attempting to fetch product details for GID...")
    results = await parser.format_products(real_gid_data, real_site, fetch_gids=True)
    print(f"Formatted {len(results)} results")
    if results:
        result = results[0]
        print(f"  URL: {result[0]}")
        print(f"  Name: {result[2]}")
        # Check if we got real details
        schema = json.loads(result[1])
        if "description" in schema:
            print(f"  ✓ Successfully fetched full product details")
        else:
            print(f"  ✗ Failed to fetch details, using fallback")


async def run_test_queries():
    """Run all test queries from shopify_stores_with_queries.jsonl"""
    import time
    from datetime import datetime
    from collections import defaultdict
    
    input_file = 'shopify_stores_with_queries.jsonl'
    output_file = 'shopify_query_results.jsonl'
    
    stats = defaultdict(int)
    stores_with_results = set()  # Track stores that have at least one non-empty result
    start_time = time.time()
    
    # Load stores with queries
    stores = []
    with open(input_file, 'r') as f:
        for line in f:
            store = json.loads(line.strip())
            if store.get('test_queries'):  # Only process stores with queries
                stores.append(store)
    
    stats['total_stores'] = len(stores)
    stats['total_queries'] = sum(len(s.get('test_queries', [])) for s in stores)
    
    print(f"Starting query execution for {len(stores)} stores with {stats['total_queries']} total queries")
    print("=" * 100)
    
    # Open output file for incremental writing
    with open(output_file, 'w') as out_file:
        for store_idx, store_data in enumerate(stores):
            store_name = store_data.get('name', 'Unknown')
            store_url = store_data.get('url')
            queries = store_data.get('test_queries', [])
            
            for query_idx, query in enumerate(queries):
                stats['queries_processed'] += 1
                
                # Update display
                elapsed = int(time.time() - start_time)
                sys.stdout.write(
                    f"\r[{elapsed}s] "
                    f"Stores: {store_idx+1}/{stats['total_stores']} | "
                    f"With Results: {len(stores_with_results)} | "
                    f"Queries: {stats['queries_processed']}/{stats['total_queries']} | "
                    f"Results: {stats['total_results']} | "
                    f"Full: {stats['full_json']} | "
                    f"GID: {stats['gid_only']} | "
                    f"Empty: {stats['empty_results']} | "
                    f"Errors: {stats['errors']} | "
                    f"Current: {store_name[:20]}..."
                )
                sys.stdout.flush()
                
                # Process the query
                result = {
                    "store_url": store_url,
                    "store_name": store_name,
                    "query": query,
                    "timestamp": datetime.now().isoformat(),
                    "products": [],
                    "raw_response": None,
                    "parsed_products": [],
                    "error": None,
                    "result_type": "empty"
                }
                
                try:
                    # Call MCP method with proper arguments
                    response = await RobustShopifyParser.call_mcp_method(
                        store_url, "search_shop_catalog", {
                            "query": query,
                            "context": f"User is searching for: {query}",
                            "limit": 50,
                            "country": "US",
                            "language": "EN"
                        }
                    )
                    
                    result["raw_response"] = response
                    
                    if response and "result" in response and response["result"]:
                        # Handle wrapped content format
                        products = []
                        if "content" in response["result"]:
                            content = response["result"]["content"]
                            if content and len(content) > 0 and content[0].get("type") == "text":
                                try:
                                    text_data = json.loads(content[0].get("text", "{}"))
                                    products = text_data.get("products", [])
                                except json.JSONDecodeError:
                                    pass
                        else:
                            # Direct products format
                            products = response["result"].get("products", [])
                        
                        if products:
                            # Parse products
                            parsed = []
                            for product in products:
                                parsed_product = await RobustShopifyParser.parse_single_product(product, store_url, fetch_gids=True)
                                if parsed_product:
                                    parsed.append(parsed_product)
                            
                            result["parsed_products"] = parsed
                            
                            # Categorize result type
                            if parsed:
                                has_full = any('title' in p for p in parsed)
                                has_gid = any(p.get('type') == 'gid_fetched' for p in parsed)
                                
                                if has_full:
                                    result["result_type"] = "full_json"
                                    stats["full_json"] += 1
                                elif has_gid:
                                    result["result_type"] = "gid_fetched"
                                    stats["gid_only"] += 1
                                
                                stats["total_results"] += len(parsed)
                                stores_with_results.add(store_url)  # Track store with results
                            else:
                                stats["empty_results"] += 1
                        else:
                            stats["empty_results"] += 1
                    else:
                        stats["empty_results"] += 1
                        
                except Exception as e:
                    result["error"] = str(e)
                    stats["errors"] += 1
                
                # Write result immediately
                out_file.write(json.dumps(result) + '\n')
                out_file.flush()
                
                # Wait 0.1 seconds between queries
                await asyncio.sleep(0.1)
            
            stats['stores_processed'] = store_idx + 1
    
    # Final stats
    print()  # New line after progress
    print("\n" + "=" * 100)
    print("✅ Query execution complete!")
    print(f"📁 Results saved to: {output_file}")
    
    elapsed = time.time() - start_time
    print(f"\n📊 Final Statistics:")
    print(f"   Duration: {int(elapsed // 60)}m {int(elapsed % 60)}s")
    print(f"   Stores processed: {stats['stores_processed']}")
    print(f"   Stores with results: {len(stores_with_results)} ({len(stores_with_results)/stats['stores_processed']*100:.1f}%)")
    print(f"   Queries executed: {stats['queries_processed']}")
    print(f"   Total results: {stats['total_results']}")
    print(f"\n   Result breakdown:")
    print(f"   - Full JSON products: {stats['full_json']} queries")
    print(f"   - GID fetched: {stats['gid_only']} queries")
    print(f"   - Empty results: {stats['empty_results']} queries")
    print(f"   - Errors: {stats['errors']} queries")
    
    if stats['queries_processed'] > 0:
        avg_results = stats['total_results'] / stats['queries_processed']
        print(f"\n   Average results per query: {avg_results:.2f}")
        success_rate = (stats['queries_processed'] - stats['errors']) / stats['queries_processed'] * 100
        print(f"   Success rate: {success_rate:.1f}%")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Shopify MCP with queries or run tests')
    parser.add_argument('--test', action='store_true', help='Run built-in tests')
    parser.add_argument('--queries', action='store_true', help='Run all test queries from file')
    parser.add_argument('--limit', type=int, help='Limit number of stores to process')
    
    args = parser.parse_args()
    
    if args.queries:
        if args.limit:
            # Create limited file
            with open('shopify_stores_with_queries.jsonl', 'r') as inf:
                with open('limited_stores.jsonl', 'w') as outf:
                    for i, line in enumerate(inf):
                        if i >= args.limit:
                            break
                        outf.write(line)
            
            # Temporarily swap files
            import shutil
            shutil.move('shopify_stores_with_queries.jsonl', 'shopify_stores_with_queries.jsonl.bak')
            shutil.move('limited_stores.jsonl', 'shopify_stores_with_queries.jsonl')
            
            try:
                await run_test_queries()
            finally:
                # Restore original
                shutil.move('shopify_stores_with_queries.jsonl.bak', 'shopify_stores_with_queries.jsonl')
                if os.path.exists('limited_stores.jsonl'):
                    os.remove('limited_stores.jsonl')
        else:
            await run_test_queries()
    else:
        # Run original test
        print("Testing Robust Shopify Parser")
        print("=" * 60)
        await test_parser()
        
        print("\n" + "=" * 60)
        print("Summary:")
        print("This parser handles:")
        print("1. Normal dictionary products (most common)")
        print("2. JSON string products (double-encoded)")
        print("3. Shopify GID references (with optional fetching)")
        print("4. Mixed valid/invalid data")
        print("5. None values and empty strings")
        print("\nNew feature: Can fetch full product details for GID references!")
        print("\nTo run test queries: python shopify_mcp_robust_parser.py --queries")
        print("To run with limit: python shopify_mcp_robust_parser.py --queries --limit 5")


if __name__ == "__main__":
    asyncio.run(main())