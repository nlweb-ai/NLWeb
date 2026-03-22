#!/usr/bin/env python3
"""Test batch 2 queries"""

import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

ENDPOINT = "https://agentfinder.azurewebsites.net/who"
MAX_WORKERS = 10

def load_queries(filename: str) -> List[str]:
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def test_query(query: str):
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
    score = 0
    num_results = 0
    avg_score = 0

    if isinstance(result, dict) and 'error' in result:
        return {'query': query, 'quality_score': 0, 'num_results': 0, 'avg_result_score': 0, 'error': result.get('error')}

    if isinstance(result, list):
        content = result
    elif isinstance(result, dict):
        content = result.get('content', [])
    else:
        content = []

    if isinstance(content, list):
        num_results = len(content)
        scores = []
        for item in content:
            if isinstance(item, dict) and 'score' in item:
                try:
                    scores.append(float(item['score']))
                except (ValueError, TypeError):
                    pass
        if scores:
            avg_score = sum(scores) / len(scores)

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

    return {'query': query, 'quality_score': score, 'num_results': num_results, 'avg_result_score': round(avg_score, 3), 'error': None}

def main():
    print("Testing batch 2 queries...")
    queries = load_queries('test_queries_batch2.txt')
    print(f"Loaded {len(queries)} queries\n")

    results = []
    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_query = {executor.submit(test_query, query): query for query in queries}
        for future in as_completed(future_to_query):
            query_text, result = future.result()
            quality = rank_result_quality(query_text, result)
            results.append(quality)
            completed += 1
            if completed % 10 == 0 or completed == len(queries):
                print(f"Progress: {completed}/{len(queries)} queries tested")

    results.sort(key=lambda x: (-x['quality_score'], -x['num_results'], -x['avg_result_score']))

    with open('query_test_results_batch2.json', 'w') as f:
        json.dump(results, f, indent=2)

    # Filter for good results (quality_score > 0)
    good_results = [r for r in results if r['quality_score'] > 0]

    with open('batch2_good_queries.txt', 'w') as f:
        for item in good_results:
            f.write(f"{item['query']}\n")

    print(f"\n{'='*80}")
    print(f"BATCH 2 RESULTS")
    print(f"{'='*80}")
    print(f"Total tested: {len(results)}")
    print(f"Good results: {len(good_results)} ({len(good_results)/len(results)*100:.1f}%)")
    print(f"Saved to batch2_good_queries.txt")

if __name__ == '__main__':
    main()
