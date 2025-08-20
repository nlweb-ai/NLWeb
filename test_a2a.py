#!/usr/bin/env python3
"""
Simple test script for A2A protocol implementation
"""

import asyncio
import aiohttp
import json
import sys


async def test_a2a():
    """Test the A2A implementation"""
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("=" * 60)
        print("Testing A2A Protocol Implementation")
        print("=" * 60)
        
        # Test 1: Check A2A info endpoint
        print("\n1. Testing A2A info endpoint (GET /a2a)...")
        try:
            async with session.get(f"{base_url}/a2a") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ A2A Info: {json.dumps(data, indent=2)}")
                else:
                    print(f"✗ Failed with status {resp.status}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 2: Check health endpoint
        print("\n2. Testing A2A health endpoint...")
        try:
            async with session.get(f"{base_url}/a2a/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ Health: {data}")
                else:
                    print(f"✗ Failed with status {resp.status}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 3: Register an agent
        print("\n3. Testing agent registration...")
        try:
            register_msg = {
                "from": "test-agent-1",
                "to": "nlweb",
                "type": "register",
                "content": {
                    "capabilities": ["search", "analyze"]
                }
            }
            async with session.post(f"{base_url}/a2a", json=register_msg) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ Registration response: {json.dumps(data, indent=2)}")
                else:
                    print(f"✗ Failed with status {resp.status}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 4: Send a simple query
        print("\n4. Testing query message...")
        try:
            query_msg = {
                "from": "test-agent-1",
                "to": "nlweb",
                "type": "query",
                "content": {
                    "query": "chocolate cake recipe",
                    "site": ["all"],
                    "generate_mode": "list"
                }
            }
            print(f"Sending query: {query_msg['content']['query']}")
            async with session.post(f"{base_url}/a2a", json=query_msg) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Pretty print the response
                    print(f"✓ Query response received:")
                    print(f"  From: {data.get('from', 'unknown')}")
                    print(f"  Type: {data.get('type', 'unknown')}")
                    if 'content' in data:
                        content = data['content']
                        if 'status' in content:
                            print(f"  Status: {content['status']}")
                        if 'content' in content:
                            print(f"  Content: {type(content['content'])}")
                            # Show first few characters of content
                            content_str = str(content['content'])[:200]
                            print(f"  Preview: {content_str}...")
                else:
                    print(f"✗ Failed with status {resp.status}")
                    error_text = await resp.text()
                    print(f"  Error: {error_text}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test 5: Discover agents
        print("\n5. Testing agent discovery...")
        try:
            discover_msg = {
                "from": "test-agent-2",
                "to": "nlweb",
                "type": "discover",
                "content": {}
            }
            async with session.post(f"{base_url}/a2a", json=discover_msg) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ Discovery response: {json.dumps(data, indent=2)}")
                else:
                    print(f"✗ Failed with status {resp.status}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        print("\n" + "=" * 60)
        print("A2A Testing Complete!")
        print("=" * 60)


def main():
    """Main entry point"""
    print("Starting A2A protocol tests...")
    print("Make sure the NLWeb server is running on localhost:8000")
    print("You can start it with: ./startup_aiohttp.sh")
    
    try:
        asyncio.run(test_a2a())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()