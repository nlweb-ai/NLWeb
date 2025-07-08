#!/usr/bin/env python3
"""
Query test runner with deduplication analysis
"""

import asyncio
import json
import sys
import os
from collections import defaultdict
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.retriever import search


class QueryAnalyzer:
    def __init__(self):
        pass  # No longer need to store a client instance
        
    async def analyze_query(self, query: str, site: str = "all", num_results: int = 50):
        """Analyze a single query for duplicates and source distribution"""
        results = await search(query, site, num_results)
        
        # Data structures for analysis
        url_to_results = defaultdict(list)
        source_counts = defaultdict(int)
        
        # Process each result
        for idx, result in enumerate(results):
            if len(result) >= 4:
                title = result[0]
                url = result[1]
                snippet = result[2]
                source = result[3]
                
                # Store full result info
                url_to_results[url].append({
                    'index': idx,
                    'title': title,
                    'source': source,
                    'snippet': snippet[:100]  # First 100 chars
                })
                
                source_counts[source] += 1
        
        # Analysis
        unique_urls = len(url_to_results)
        total_results = len(results)
        duplicate_groups = {url: sources for url, sources in url_to_results.items() if len(sources) > 1}
        
        return {
            'query': query,
            'site': site,
            'timestamp': datetime.now().isoformat(),
            'total_results': total_results,
            'unique_urls': unique_urls,
            'duplicates': len(duplicate_groups),
            'dedup_ratio': f"{(unique_urls/total_results*100):.1f}%" if total_results > 0 else "N/A",
            'source_distribution': dict(source_counts),
            'duplicate_details': duplicate_groups
        }
    
    def print_analysis(self, analysis):
        """Pretty print the analysis results"""
        print(f"\n{'='*70}")
        print(f"Query: '{analysis['query']}' | Site: {analysis['site']}")
        print(f"Time: {analysis['timestamp']}")
        print('='*70)
        
        print(f"\nRESULTS SUMMARY:")
        print(f"  Total results returned: {analysis['total_results']}")
        print(f"  Unique URLs: {analysis['unique_urls']}")
        print(f"  Duplicate URLs: {analysis['duplicates']}")
        print(f"  Deduplication ratio: {analysis['dedup_ratio']}")
        
        print(f"\nSOURCE DISTRIBUTION:")
        for source, count in sorted(analysis['source_distribution'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {source:30} : {count:3} results")
        
        if analysis['duplicate_details']:
            print(f"\nDUPLICATE ANALYSIS (showing first 3):")
            for i, (url, occurrences) in enumerate(list(analysis['duplicate_details'].items())[:3]):
                print(f"\n  Duplicate #{i+1}: {url[:80]}...")
                print(f"  Found {len(occurrences)} times in:")
                for occ in occurrences:
                    print(f"    - Source: {occ['source']} (position: {occ['index']+1})")
                    print(f"      Title: {occ['title'][:60]}...")
    
    async def run_test_suite(self, queries):
        """Run multiple queries and aggregate results"""
        all_results = []
        
        for q in queries:
            if isinstance(q, str):
                query = q
                site = "all"
            elif isinstance(q, dict):
                query = q['query']
                site = q.get('site', 'all')
            else:
                query, site = q
            
            print(f"\nProcessing: {query}")
            analysis = await self.analyze_query(query, site)
            self.print_analysis(analysis)
            all_results.append(analysis)
            
            await asyncio.sleep(0.5)  # Rate limiting
        
        # Aggregate summary
        self.print_aggregate_summary(all_results)
        return all_results
    
    def print_aggregate_summary(self, all_results):
        """Print summary across all queries"""
        print(f"\n\n{'='*70}")
        print("AGGREGATE SUMMARY ACROSS ALL QUERIES")
        print('='*70)
        
        total_queries = len(all_results)
        total_results = sum(r['total_results'] for r in all_results)
        total_unique = sum(r['unique_urls'] for r in all_results)
        total_duplicates = sum(r['duplicates'] for r in all_results)
        
        print(f"\nQueries run: {total_queries}")
        print(f"Total results: {total_results}")
        print(f"Total unique URLs: {total_unique}")
        print(f"Total duplicate URLs: {total_duplicates}")
        print(f"Overall dedup ratio: {(total_unique/total_results*100):.1f}%" if total_results > 0 else "N/A")
        
        # Aggregate by source
        all_sources = defaultdict(int)
        for result in all_results:
            for source, count in result['source_distribution'].items():
                all_sources[source] += count
        
        print(f"\nTOTAL RESULTS BY SOURCE:")
        for source, count in sorted(all_sources.items(), key=lambda x: x[1], reverse=True):
            percentage = (count/total_results*100) if total_results > 0 else 0
            print(f"  {source:30} : {count:4} results ({percentage:.1f}%)")


async def main():
    # Default test queries
    test_queries = [
        "machine learning algorithms",
        "artificial intelligence ethics",
        "python programming tutorial",
        "climate change impact",
        "quantum computing basics",
        {"query": "technology news", "site": "all"},
        {"query": "latest updates", "site": "all"},
        {"query": "spicy crunchy snacks", "site": "seriouseats"}
    ]
    
    # Check for custom queries file
    if len(sys.argv) > 1:
        queries_file = sys.argv[1]
        if os.path.exists(queries_file):
            with open(queries_file, 'r') as f:
                test_queries = json.load(f)
            print(f"Loaded {len(test_queries)} queries from {queries_file}")
    
    # Run analysis
    analyzer = QueryAnalyzer()
    results = await analyzer.run_test_suite(test_queries)
    
    # Save results
    output_file = f"query_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    print("Query Test Runner - Deduplication Analysis")
    print("Usage: python query_test_runner.py [queries.json]")
    asyncio.run(main())