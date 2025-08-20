#!/usr/bin/env python3
"""
Demonstrate GID fetching capability
"""

import asyncio
import json
from shopify_mcp_robust_parser import RobustShopifyParser


async def demo_gid_fetching():
    """Demonstrate fetching product details from GIDs"""
    
    site = "hashipottery.com"
    
    # Simulate a response that contains only GIDs (like some MCP responses might)
    print("Scenario: MCP returns products as GID references")
    print("=" * 60)
    
    gid_response = {
        "products": [
            "gid://shopify/Product/7241139093575",  # Juli Kirk plate
            "gid://shopify/Product/7238348406855",  # Ayumi Nojiri bowl
        ]
    }
    
    print("\nInput products (GID references):")
    for i, gid in enumerate(gid_response['products'], 1):
        print(f"  {i}. {gid}")
    
    print("\n" + "-" * 60)
    print("Processing WITHOUT fetching (fast but minimal info):")
    print("-" * 60)
    
    results = await RobustShopifyParser.format_products(gid_response, site, fetch_gids=False)
    
    for i, result in enumerate(results, 1):
        url, schema_json, name, site_name = result
        print(f"\n{i}. {name}")
        print(f"   URL: {url}")
    
    print("\n" + "-" * 60)
    print("Processing WITH fetching (slower but full details):")
    print("-" * 60)
    
    results = await RobustShopifyParser.format_products(gid_response, site, fetch_gids=True)
    
    for i, result in enumerate(results, 1):
        url, schema_json, name, site_name = result
        schema = json.loads(schema_json)
        
        print(f"\n{i}. {name}")
        print(f"   URL: {url}")
        
        # Show some additional details we got from fetching
        if 'description' in schema:
            desc = schema['description'][:100] + "..." if len(schema['description']) > 100 else schema['description']
            print(f"   Description: {desc}")
        
        if 'offers' in schema:
            offers = schema['offers']
            if isinstance(offers, dict):
                print(f"   Price: ${offers.get('lowPrice', '?')} - ${offers.get('highPrice', '?')} {offers.get('priceCurrency', '')}")
    
    print("\n" + "=" * 60)
    print("Summary: GID fetching provides complete product information!")


if __name__ == "__main__":
    print("GID Fetching Demonstration")
    print("=" * 60)
    asyncio.run(demo_gid_fetching())