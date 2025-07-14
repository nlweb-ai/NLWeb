#!/usr/bin/env python3
"""
Simple test that extracts endpoint statistics from debug logs
"""

import asyncio
import sys
import os
import re
import logging
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.retriever import search
from misc.logger.logger import logger


# Capture endpoint statistics from logs
class EndpointStatsHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.stats = defaultdict(int)
        self.current_query = None
        
    def emit(self, record):
        # Look for "Got X results from endpoint_name" messages
        if "Got" in record.getMessage() and "results from" in record.getMessage():
            match = re.search(r'Got (\d+) results from (\w+)', record.getMessage())
            if match:
                count = int(match.group(1))
                endpoint = match.group(2)
                self.stats[endpoint] = count
    
    def reset(self):
        self.stats = defaultdict(int)


async def run_query_with_stats(query: str, site: str = "all", num_results: int = 50):
    """Run query and capture endpoint statistics"""
    
    # Set up stats handler
    stats_handler = EndpointStatsHandler()
    stats_handler.setLevel(logging.DEBUG)
    
    # Add handler to logger
    logger.logger.addHandler(stats_handler)
    original_level = logger.logger.level
    logger.logger.setLevel(logging.DEBUG)
    
    try:
        # Run query
        results = await search(query, site, num_results)
        
        # Extract stats
        endpoint_stats = dict(stats_handler.stats)
        
        # Analyze results
        print(f"\n{'='*80}")
        print(f"Query: '{query}' | Site: {site}")
        print('='*80)
        
        # Results analysis
        total = len(results)
        urls = set()
        sources = defaultdict(int)
        
        for result in results:
            if len(result) >= 4:
                url = result[1]
                source = result[3]
                urls.add(url)
                sources[source] += 1
        
        # Print endpoint results
        if endpoint_stats:
            print("\nRESULTS FROM EACH ENDPOINT:")
            total_before_dedup = sum(endpoint_stats.values())
            for endpoint, count in sorted(endpoint_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"  {endpoint:30} : {count:4} results")
            
            print(f"\nDEDUPLICATION:")
            print(f"  Total from all endpoints: {total_before_dedup}")
            print(f"  After deduplication: {total}")
            print(f"  Removed by deduplication: {total_before_dedup - total}")
            dedup_percentage = ((total_before_dedup - total) / total_before_dedup * 100) if total_before_dedup > 0 else 0
            print(f"  Deduplication ratio: {dedup_percentage:.1f}%")
        else:
            print("\nNo endpoint statistics captured (try running with debug logging)")
            print(f"Total results: {total}")
        
        print(f"\nUNIQUE URLs: {len(urls)}")
        
        if sources:
            print("\nRESULTS BY SOURCE:")
            for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
                print(f"  {source:30} : {count:4}")
                
    finally:
        # Restore logger
        logger.logger.removeHandler(stats_handler)
        logger.logger.setLevel(original_level)


async def main():
    print("\n" + "="*80)
    print("QUERY TEST WITH ENDPOINT RESULT COUNTS")
    print("="*80)
    
    # Test queries
    queries = [
        ("machine learning", "all"),
        ("artificial intelligence", "all"),
        ("python programming", "all"),
        ("spicy crunchy snacks", "seriouseats"),
        ("latest technology news", "all"),
        ("climate change", "all")
    ]
    
    for query, site in queries:
        await run_query_with_stats(query, site)
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())