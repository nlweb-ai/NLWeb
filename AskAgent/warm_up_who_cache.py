#!/usr/bin/env python3
"""
Warm up the WHO query cache by issuing queries for all sample queries.
This script reads the sample-who-queries.js file and sends requests to warm up the cache.
"""

import requests
import time
import re
import sys
from typing import List

# Default endpoint
DEFAULT_ENDPOINT = "http://localhost:8000/who"

def extract_queries_from_js(file_path: str) -> List[str]:
    """Extract query strings from the JavaScript sample queries file."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Find the SAMPLE_QUERIES array
    # Extract everything between [ and ]
    array_match = re.search(r'SAMPLE_QUERIES\s*=\s*\[(.*?)\];', content, re.DOTALL)
    if not array_match:
        return []

    array_content = array_match.group(1)

    # Find all strings between quotes (double quotes in this case)
    # Match strings that span multiple lines if needed
    pattern = r'"([^"]+)"'
    queries = re.findall(pattern, array_content)

    return queries

def warm_up_cache(endpoint: str, queries: List[str], delay: float = 0.5):
    """Send queries to the WHO endpoint to warm up the cache."""
    print(f"Warming up WHO cache with {len(queries)} queries...")
    print(f"Endpoint: {endpoint}")
    print(f"Delay between requests: {delay}s")
    print("=" * 80)

    success_count = 0
    error_count = 0

    for i, query in enumerate(queries, 1):
        try:
            # Show progress
            print(f"[{i}/{len(queries)}] {query[:60]}{'...' if len(query) > 60 else ''}")

            # Send request (non-streaming for simplicity)
            params = {
                'query': query,
                'streaming': 'false'
            }

            response = requests.get(endpoint, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                # Count results if available
                if isinstance(data, list):
                    num_results = len(data)
                elif isinstance(data, dict) and 'content' in data:
                    num_results = len(data.get('content', []))
                else:
                    num_results = 0

                print(f"  ✓ Success - {num_results} results")
                success_count += 1
            else:
                print(f"  ✗ Error - HTTP {response.status_code}")
                error_count += 1

            # Delay between requests to avoid overwhelming the server
            if i < len(queries):
                time.sleep(delay)

        except requests.exceptions.Timeout:
            print(f"  ✗ Timeout")
            error_count += 1
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            error_count += 1

    print("\n" + "=" * 80)
    print("CACHE WARM-UP COMPLETE")
    print("=" * 80)
    print(f"Total queries: {len(queries)}")
    print(f"Successful: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Success rate: {success_count/len(queries)*100:.1f}%")

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Warm up WHO query cache')
    parser.add_argument(
        '--endpoint',
        default=DEFAULT_ENDPOINT,
        help=f'WHO endpoint URL (default: {DEFAULT_ENDPOINT})'
    )
    parser.add_argument(
        '--queries-file',
        default='static/sample-who-queries.js',
        help='Path to sample queries JavaScript file (default: static/sample-who-queries.js)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Delay between requests in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of queries to process (for testing)'
    )

    args = parser.parse_args()

    # Extract queries from file
    try:
        queries = extract_queries_from_js(args.queries_file)
        print(f"Extracted {len(queries)} queries from {args.queries_file}")
    except FileNotFoundError:
        print(f"Error: File not found: {args.queries_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading queries file: {e}")
        sys.exit(1)

    if not queries:
        print("Error: No queries found in file")
        sys.exit(1)

    # Apply limit if specified
    if args.limit:
        queries = queries[:args.limit]
        print(f"Limited to first {args.limit} queries")

    # Warm up the cache
    try:
        warm_up_cache(args.endpoint, queries, args.delay)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)

if __name__ == '__main__':
    main()
