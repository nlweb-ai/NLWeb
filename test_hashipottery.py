#!/usr/bin/env python3
"""
Test hashipottery.com with "tea cup" query
"""

import json
import asyncio
import aiohttp

async def test_hashipottery():
    """Test hashipottery.com MCP endpoint"""
    
    site = "hashipottery.com"
    query = "tea cup"
    
    endpoint = f"https://{site}/api/mcp"
    
    request = {
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
    
    print(f"Testing {site} with query: '{query}'")
    print("=" * 60)
    print(f"Endpoint: {endpoint}")
    print(f"Request: {json.dumps(request, indent=2)}")
    print("=" * 60)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=request,
                headers={'Content-Type': 'application/json'},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                print(f"Response status: {response.status}")
                
                if response.status != 200:
                    print(f"Error: HTTP {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return
                
                result = await response.json(content_type=None)
                
                print("\nRaw response structure:")
                print(json.dumps(result, indent=2)[:1000] + "..." if len(json.dumps(result)) > 1000 else json.dumps(result, indent=2))
                
                # Parse the actual products
                if result and "result" in result:
                    if "content" in result["result"]:
                        # Products are in content[0].text as JSON string
                        content = result["result"]["content"]
                        if content and len(content) > 0:
                            text_content = content[0].get("text", "{}")
                            try:
                                parsed = json.loads(text_content)
                                products = parsed.get("products", [])
                                
                                print(f"\n✓ Found {len(products)} products")
                                
                                for i, product in enumerate(products[:3], 1):
                                    print(f"\nProduct {i}:")
                                    print(f"  Title: {product.get('title', 'N/A')}")
                                    print(f"  URL: {product.get('url', 'N/A')}")
                                    print(f"  Price: {product.get('price_range', {})}")
                                    
                            except json.JSONDecodeError as e:
                                print(f"Failed to parse products JSON: {e}")
                    elif "products" in result["result"]:
                        # Direct products array
                        products = result["result"]["products"]
                        print(f"\n✓ Found {len(products)} products (direct)")
                    else:
                        print("\n❌ No products found in response")
                        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_hashipottery())