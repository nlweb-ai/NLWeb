#!/usr/bin/env python3
"""
Test queries against agentfinder.azurewebsites.net/who and rank by quality (parallel version)
"""

import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple

ENDPOINT = "https://agentfinder.azurewebsites.net/who"
MAX_WORKERS = 10  # Number of parallel requests

def load_queries(filename: str) -> List[str]:
    """Load queries from text file"""
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def test_query(query: str) -> Tuple[str, any]:
    """Test a single query and return results"""
    try:
        params = {'query': query, 'streaming': 'false'}
        response = requests.get(ENDPOINT, params=params, headers={'Accept': 'application/json'}, timeout=30)

        if response.status_code == 200:
            data = response.json()
            return query, data
        else:
            return query, {'error': f'HTTP {response.status_code}'}
    except Exception as e:
        return query, {'error': str(e)}

def rank_result_quality(query: str, result) -> Dict:
    """
    Rank the quality of results based on multiple factors
    """
    score = 0
    num_results = 0
    avg_score = 0

    # Handle errors
    if isinstance(result, dict) and 'error' in result:
        return {
            'query': query,
            'quality_score': 0,
            'num_results': 0,
            'avg_result_score': 0,
            'error': result.get('error', 'Unknown error')
        }

    # Extract results from various possible response formats
    if isinstance(result, list):
        content = result
    elif isinstance(result, dict):
        content = result.get('content', [])
    else:
        content = []

    if isinstance(content, list):
        num_results = len(content)

        # Calculate average score if available
        scores = []
        for item in content:
            if isinstance(item, dict) and 'score' in item:
                try:
                    scores.append(float(item['score']))
                except (ValueError, TypeError):
                    pass

        if scores:
            avg_score = sum(scores) / len(scores)

        # Quality scoring
        if num_results >= 1:
            score += 10
        if num_results >= 3:
            score += 20
        if num_results >= 5:
            score += 30

        if avg_score > 0.5:
            score += 20
        if avg_score > 0.7:
            score += 30
        if avg_score > 0.8:
            score += 40

    return {
        'query': query,
        'quality_score': score,
        'num_results': num_results,
        'avg_result_score': round(avg_score, 3),
        'error': None
    }

def main():
    print("Loading queries from test_queries_200.txt...")
    queries = load_queries('test_queries_200.txt')
    print(f"Loaded {len(queries)} queries\n")

    print(f"Testing queries with {MAX_WORKERS} parallel workers...")
    print("=" * 80)

    results = []
    completed = 0

    # Use ThreadPoolExecutor for parallel requests
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_query = {executor.submit(test_query, query): query for query in queries}

        # Process completed tasks
        for future in as_completed(future_to_query):
            query_text, result = future.result()
            quality = rank_result_quality(query_text, result)
            results.append(quality)
            completed += 1

            # Print progress
            if completed % 10 == 0 or completed == len(queries):
                print(f"Progress: {completed}/{len(queries)} queries tested")

    print("\n" + "=" * 80)
    print("Ranking queries by quality...\n")

    # Sort by quality score (descending)
    results.sort(key=lambda x: (-x['quality_score'], -x['num_results'], -x['avg_result_score']))

    # Save all results to JSON
    with open('query_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("Saved detailed results to query_test_results.json")

    # Get top 100
    top_100 = results[:100]

    # Save top 100 queries to file
    with open('top_100_queries.txt', 'w') as f:
        for item in top_100:
            f.write(f"{item['query']}\n")
    print("Saved top 100 queries to top_100_queries.txt")

    # Print summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)

    total_queries = len(results)
    queries_with_results = sum(1 for r in results if r['num_results'] > 0)
    queries_with_errors = sum(1 for r in results if r['error'])

    print(f"Total queries tested: {total_queries}")
    print(f"Queries with results: {queries_with_results} ({queries_with_results/total_queries*100:.1f}%)")
    print(f"Queries with errors: {queries_with_errors} ({queries_with_errors/total_queries*100:.1f}%)")
    print(f"Queries with no results: {total_queries - queries_with_results - queries_with_errors}")

    if queries_with_results > 0:
        avg_results = sum(r['num_results'] for r in results if r['num_results'] > 0) / queries_with_results
        print(f"Average results per successful query: {avg_results:.2f}")

    print("\n" + "=" * 80)
    print("TOP 20 QUERIES BY QUALITY")
    print("=" * 80)
    for i, item in enumerate(top_100[:20], 1):
        print(f"\n{i}. {item['query']}")
        print(f"   Quality Score: {item['quality_score']}, "
              f"Results: {item['num_results']}, "
              f"Avg Score: {item['avg_result_score']:.3f}")

    print("\n" + "=" * 80)
    print(f"Successfully selected top 100 queries from {total_queries} tested")
    print("=" * 80)

if __name__ == '__main__':
    main()
