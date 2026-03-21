#!/usr/bin/env python3
"""
Validate that all WHO sample queries return at least one result.
Identifies and reports queries with no results.
"""

import requests
import time
import re
import sys
from typing import List, Tuple

DEFAULT_ENDPOINT = "https://agentfinder.azurewebsites.net/who"

def extract_queries_from_js(file_path: str) -> List[str]:
    """Extract query strings from the JavaScript sample queries file."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Find the SAMPLE_QUERIES array
    array_match = re.search(r'SAMPLE_QUERIES\s*=\s*\[(.*?)\];', content, re.DOTALL)
    if not array_match:
        return []

    array_content = array_match.group(1)

    # Find all strings between quotes
    pattern = r'"([^"]+)"'
    queries = re.findall(pattern, array_content)

    return queries

def test_query(endpoint: str, query: str) -> Tuple[bool, int, str]:
    """
    Test a single query and return (has_results, num_results, error_msg).

    Returns:
        (True, num_results, "") if query has results
        (False, 0, error_msg) if query has no results or errors
    """
    try:
        params = {'query': query, 'streaming': 'false'}
        response = requests.get(endpoint, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()

            # Count results
            if isinstance(data, list):
                num_results = len(data)
            elif isinstance(data, dict) and 'content' in data:
                num_results = len(data.get('content', []))
            else:
                num_results = 0

            if num_results > 0:
                return (True, num_results, "")
            else:
                return (False, 0, "No results returned")
        else:
            return (False, 0, f"HTTP {response.status_code}")

    except requests.exceptions.Timeout:
        return (False, 0, "Request timeout")
    except Exception as e:
        return (False, 0, str(e))

def validate_queries(endpoint: str, queries: List[str], delay: float = 0.3):
    """Validate all queries and report which ones have no results."""

    print(f"Validating {len(queries)} WHO sample queries...")
    print(f"Endpoint: {endpoint}")
    print(f"Delay between requests: {delay}s")
    print("=" * 80)

    queries_with_results = []
    queries_without_results = []
    queries_with_errors = []

    for i, query in enumerate(queries, 1):
        # Show progress with full query
        print(f"[{i}/{len(queries)}] {query}")

        has_results, num_results, error_msg = test_query(endpoint, query)

        if has_results:
            print(f"  ✓ {num_results} results")
            queries_with_results.append((query, num_results))
        elif error_msg and "HTTP" not in error_msg and "timeout" not in error_msg.lower():
            print(f"  ✗ ERROR: {error_msg}")
            queries_with_errors.append((query, error_msg))
        else:
            print(f"  ✗ NO RESULTS")
            queries_without_results.append((query, error_msg))

        # Flush output immediately
        sys.stdout.flush()

        # Delay between requests
        if i < len(queries):
            time.sleep(delay)

    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total queries: {len(queries)}")
    print(f"Queries with results: {len(queries_with_results)} ({len(queries_with_results)/len(queries)*100:.1f}%)")
    print(f"Queries without results: {len(queries_without_results)} ({len(queries_without_results)/len(queries)*100:.1f}%)")
    print(f"Queries with errors: {len(queries_with_errors)} ({len(queries_with_errors)/len(queries)*100:.1f}%)")

    # Print queries without results
    if queries_without_results:
        print("\n" + "=" * 80)
        print("QUERIES WITHOUT RESULTS")
        print("=" * 80)
        for query, error in queries_without_results:
            print(f"\n• {query}")
            if error:
                print(f"  Error: {error}")

    # Print queries with errors
    if queries_with_errors:
        print("\n" + "=" * 80)
        print("QUERIES WITH ERRORS")
        print("=" * 80)
        for query, error in queries_with_errors:
            print(f"\n• {query}")
            print(f"  Error: {error}")

    # Print statistics
    if queries_with_results:
        avg_results = sum(num for _, num in queries_with_results) / len(queries_with_results)
        print(f"\nAverage results per successful query: {avg_results:.2f}")

    return queries_without_results, queries_with_errors

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Validate WHO sample queries')
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
        '--output',
        '-o',
        help='Output file for results (default: print to stdout)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.3,
        help='Delay between requests in seconds (default: 0.3)'
    )

    args = parser.parse_args()

    # Redirect output to file if specified
    if args.output:
        sys.stdout = open(args.output, 'w')
        sys.stderr = sys.stdout

    # Extract queries from file
    try:
        queries = extract_queries_from_js(args.queries_file)
        print(f"Extracted {len(queries)} queries from {args.queries_file}\n")
    except FileNotFoundError:
        print(f"Error: File not found: {args.queries_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading queries file: {e}")
        sys.exit(1)

    if not queries:
        print("Error: No queries found in file")
        sys.exit(1)

    # Validate queries
    try:
        no_results, errors = validate_queries(args.endpoint, queries, args.delay)

        # Exit with error code if any queries failed
        if no_results or errors:
            sys.exit(1)
        else:
            print("\n✓ All queries returned results!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)

if __name__ == '__main__':
    main()
