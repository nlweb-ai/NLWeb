#!/usr/bin/env python3
"""Debug script to test ShopifyMCPClient's can_handle_query method"""

import asyncio
from core.retriever import VectorDBClient

async def test_shopify_handling():
    # Initialize the client with a specific endpoint to avoid write endpoint issues
    from retrieval_providers.shopify_mcp import ShopifyMCPClient
    
    # Create ShopifyMCPClient directly
    shopify_client = ShopifyMCPClient("shopify")
    
    print("Testing ShopifyMCPClient can_handle_query method")
    print("=" * 60)
    
    test_sites = [
        "chili-klaus-int.myshopify.com",
        "store.google.com",
        "shopify.com",
        "myshopify.com",
        "example-shop.myshopify.com"
    ]
    
    # Test with the shopify client
    try:
        print(f"Got Shopify client: {type(shopify_client).__name__}")
        print()
        
        for site in test_sites:
            result = await shopify_client.can_handle_query(site)
            print(f"Site: {site}")
            print(f"  Can handle: {result}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_shopify_handling())