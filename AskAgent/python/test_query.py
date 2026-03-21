#!/usr/bin/env python3
"""General query test utility for NLWeb"""

import asyncio
import aiohttp
import json
import sys
import argparse

async def test_query(query, site='all', streaming=True, top_k=10, endpoint='ask'):
    base_url = "http://localhost:8000"
    url = f"{base_url}/{endpoint}"
    
    params = {
        'query': query,
        'site': site,
        'streaming': 'true' if streaming else 'false',
        'top_k': top_k
    }
    
    print(f"Query: '{query}'")
    print(f"Site: {site}")
    print(f"Endpoint: {url}")
    print(f"Streaming: {streaming}")
    print(f"Top-K: {top_k}")
    print("="*60)
    
    sites_queried = set()
    results_count = 0
    errors_count = 0
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            print(f"Response status: {response.status}")
            
            if not streaming:
                # Non-streaming response
                result = await response.json()
                content = result.get('content', [])
                print(f"\nReceived {len(content)} results")
                for i, item in enumerate(content[:10], 1):
                    name = item.get('name', 'N/A')
                    score = item.get('score', 0)
                    site_name = item.get('site', 'N/A')
                    print(f"{i}. [{site_name}] {name[:60]}... (score: {score})")
            else:
                # Streaming response
                print("-"*60)
                
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            data = json.loads(data_str)
                            message_type = data.get('message_type', '')
                            
                            if message_type == 'site_querying':
                                site_name = data.get('site_name', '')
                                site_domain = data.get('site', '')
                                index = data.get('index', 0)
                                total = data.get('total', 0)
                                sites_queried.add(f"{site_name} ({site_domain})")
                                print(f"Querying site {index}/{total}: {site_name}")
                            
                            elif message_type == 'result':
                                content = data.get('content', [])
                                if content and isinstance(content, list):
                                    for item in content:
                                        results_count += 1
                                        name = item.get('name', 'N/A')
                                        source = item.get('source_site_name', item.get('site', 'N/A'))
                                        score = item.get('score', 0)
                                        print(f"  Result {results_count}: {name[:50]}... (score: {score})")
                            
                            elif message_type == 'site_error':
                                errors_count += 1
                                site_domain = data.get('site', '')
                                error = data.get('error', '')
                                if "No valid endpoints" not in error:
                                    print(f"  Error for {site_domain}: {error[:80]}")
                            
                            elif message_type == 'site_complete':
                                site_domain = data.get('site', '')
                                count = data.get('results_count', 0)
                                if count > 0:
                                    print(f"  Completed {site_domain}: {count} results")
                            
                            elif message_type == 'multi_site_complete':
                                print("\n" + "="*60)
                                print("MULTI-SITE SUMMARY:")
                                print(f"  Sites queried: {data.get('sites_queried', 0)}")
                                print(f"  Sites successful: {data.get('sites_successful', 0)}")
                                print(f"  Sites failed: {data.get('sites_failed', 0)}")
                                print(f"  Total results: {data.get('total_results', 0)}")
                            
                        except json.JSONDecodeError:
                            pass
    
    if streaming and sites_queried:
        print("\n" + "="*60)
        print(f"Sites queried ({len(sites_queried)}):")
        for site in sorted(sites_queried):
            print(f"  - {site}")
        print(f"\nTotal results found: {results_count}")
        if errors_count:
            print(f"Sites with errors: {errors_count}")

def main():
    parser = argparse.ArgumentParser(description='Test NLWeb queries')
    parser.add_argument('query', help='Query string to test')
    parser.add_argument('--site', default='all', help='Site to query (default: all)')
    parser.add_argument('--endpoint', default='ask', help='Endpoint to use (ask or who)')
    parser.add_argument('--no-streaming', action='store_true', help='Disable streaming')
    parser.add_argument('--top-k', type=int, default=10, help='Number of results (default: 10)')
    
    args = parser.parse_args()
    
    asyncio.run(test_query(
        args.query, 
        args.site, 
        not args.no_streaming,
        args.top_k,
        args.endpoint
    ))

if __name__ == "__main__":
    main()