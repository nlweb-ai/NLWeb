#!/usr/bin/env python3
"""
Enhanced test script that shows results from each endpoint
"""

import asyncio
import subprocess
import sys
import os
import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.retriever import VectorDBClient, get_vector_db_client


class EndpointTrackingClient(VectorDBClient):
    """Extended VectorDBClient that tracks endpoint statistics"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_endpoint_stats = {}
    
    def _aggregate_results(self, endpoint_results: Dict[str, List[List[str]]]) -> List[List[str]]:
        """Override to capture endpoint statistics before aggregation"""
        # Store endpoint statistics
        self.last_endpoint_stats = {}
        for endpoint_name, results in endpoint_results.items():
            if results:
                self.last_endpoint_stats[endpoint_name] = len(results)
        
        # Call parent method for actual aggregation
        return super()._aggregate_results(endpoint_results)
    
    async def search_with_stats(self, query: str, site: str, num_results: int = 50, **kwargs) -> Tuple[List[List[str]], Dict[str, int]]:
        """Search and return both results and endpoint statistics"""
        results = await self.search(query, site, num_results, **kwargs)
        return results, self.last_endpoint_stats.copy()


async def clear_database():
    """Clear all data from local Qdrant"""
    print("\n" + "="*60)
    print("CLEARING LOCAL DATABASE")
    print("="*60)
    
    retriever = get_vector_db_client()
    
    try:
        sites = await retriever.get_sites()
        if sites:
            print(f"Found {len(sites)} sites to delete")
            total_deleted = 0
            for site in sites:
                try:
                    count = await retriever.delete_documents_by_site(site)
                    if count > 0:
                        print(f"  Deleted {count} documents from: {site}")
                        total_deleted += count
                except Exception as e:
                    print(f"  Error deleting {site}: {e}")
            print(f"\nTotal documents deleted: {total_deleted}")
        else:
            print("No sites found in database")
    except Exception as e:
        print(f"Error: {e}")


async def analyze_query_with_endpoints(query: str, site: str, retriever: EndpointTrackingClient):
    """Run query and analyze results including endpoint statistics"""
    print(f"\n{'='*80}")
    print(f"Query: '{query}' | Site: {site}")
    print('='*80)
    
    try:
        # Get results and endpoint stats
        results, endpoint_stats = await retriever.search_with_stats(query, site, num_results=50)
        
        # Basic analysis
        total = len(results)
        urls = set()
        sources = defaultdict(int)
        url_to_endpoints = defaultdict(set)
        
        # Analyze results
        for result in results:
            if len(result) >= 4:
                url = result[1]
                source = result[3]
                
                urls.add(url)
                sources[source] += 1
        
        # Print endpoint statistics
        print("\nRESULTS BY ENDPOINT:")
        total_from_endpoints = sum(endpoint_stats.values())
        for endpoint, count in sorted(endpoint_stats.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_from_endpoints * 100) if total_from_endpoints > 0 else 0
            print(f"  {endpoint:30} : {count:4} results ({percentage:5.1f}%)")
        
        if not endpoint_stats:
            print("  No endpoint statistics available")
        
        # Print aggregated statistics
        print(f"\nAGGREGATED RESULTS:")
        print(f"  Total from all endpoints: {total_from_endpoints}")
        print(f"  After deduplication: {total}")
        print(f"  Unique URLs: {len(urls)}")
        dedup_ratio = ((total_from_endpoints - total) / total_from_endpoints * 100) if total_from_endpoints > 0 else 0
        print(f"  Deduplication ratio: {dedup_ratio:.1f}% removed")
        
        # Print source distribution
        if sources:
            print("\nRESULTS BY SOURCE/SITE:")
            for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
                print(f"  {source:30} : {count:4} results")
        
        return {
            "query": query,
            "site": site,
            "total": total,
            "unique_urls": len(urls),
            "endpoint_stats": endpoint_stats,
            "total_before_dedup": total_from_endpoints,
            "sources": dict(sources)
        }
        
    except Exception as e:
        print(f"Error running query: {e}")
        return None


async def run_query_tests():
    """Run standard query tests with endpoint tracking"""
    print("\n" + "="*60)
    print("RUNNING QUERY TESTS WITH ENDPOINT TRACKING")
    print("="*60)
    
    # Use our enhanced client
    retriever = EndpointTrackingClient()
    
    # Print enabled endpoints
    print(f"\nEnabled endpoints: {list(retriever.enabled_endpoints.keys())}")
    
    queries = [
        ("machine learning", "all"),
        ("artificial intelligence", "all"),
        ("python programming", "all"),
        ("spicy crunchy snacks", "seriouseats"),
        ("latest technology news", "all")
    ]
    
    all_results = []
    
    for query, site in queries:
        result = await analyze_query_with_endpoints(query, site, retriever)
        if result:
            all_results.append(result)
        await asyncio.sleep(0.5)
    
    # Print summary
    print_summary(all_results)
    
    return all_results


def print_summary(results: List[Dict[str, Any]]):
    """Print summary of all query results"""
    print("\n" + "="*80)
    print("SUMMARY OF ALL QUERIES")
    print("="*80)
    
    # Aggregate endpoint statistics
    endpoint_totals = defaultdict(int)
    total_before = 0
    total_after = 0
    
    for result in results:
        if result and "endpoint_stats" in result:
            for endpoint, count in result["endpoint_stats"].items():
                endpoint_totals[endpoint] += count
            total_before += result.get("total_before_dedup", 0)
            total_after += result.get("total", 0)
    
    print("\nTOTAL RESULTS BY ENDPOINT (across all queries):")
    grand_total = sum(endpoint_totals.values())
    for endpoint, count in sorted(endpoint_totals.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / grand_total * 100) if grand_total > 0 else 0
        print(f"  {endpoint:30} : {count:5} results ({percentage:5.1f}%)")
    
    print(f"\nOVERALL DEDUPLICATION:")
    print(f"  Total results before dedup: {total_before}")
    print(f"  Total results after dedup: {total_after}")
    dedup_ratio = ((total_before - total_after) / total_before * 100) if total_before > 0 else 0
    print(f"  Overall deduplication ratio: {dedup_ratio:.1f}% removed")


async def load_rss_feed(url: str, site_name: str):
    """Load RSS feed using db_load"""
    print(f"\n" + "="*60)
    print(f"LOADING RSS FEED")
    print("="*60)
    print(f"URL: {url}")
    print(f"Site: {site_name}")
    
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "..", "tools", "db_load.py"),
        "--rss", url,
        "--site", site_name,
        "--delete"
    ]
    
    print("\nRunning db_load...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    
    print("RSS feed loaded successfully")
    return True


async def main():
    print("\n" + "="*80)
    print("NLWEB QUERY TEST WITH ENDPOINT STATISTICS")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Clear database
    await clear_database()
    
    # Run initial queries
    print("\n\nPhase 1: Testing queries on clean database...")
    initial_results = await run_query_tests()
    
    # Load RSS feed
    rss_url = "https://feeds.megaphone.fm/recodedecode"
    site_name = "recodedecode"
    
    if await load_rss_feed(rss_url, site_name):
        print("\nWaiting 5 seconds for indexing...")
        await asyncio.sleep(5)
        
        # Test with RSS-specific queries
        print("\n\nPhase 2: Testing RSS-specific queries...")
        retriever = EndpointTrackingClient()
        
        rss_queries = [
            ("podcast", site_name),
            ("technology", site_name),
            ("decode", site_name),
            ("episode", site_name)
        ]
        
        rss_results = []
        for query, site in rss_queries:
            result = await analyze_query_with_endpoints(query, site, retriever)
            if result:
                rss_results.append(result)
            await asyncio.sleep(0.5)
        
        print_summary(rss_results)
    
    # Run general queries again
    print("\n\nPhase 3: Testing general queries (with RSS content)...")
    final_results = await run_query_tests()
    
    # Save detailed results
    output_file = f"endpoint_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "initial_results": initial_results,
            "final_results": final_results
        }, f, indent=2)
    
    print(f"\n\nDetailed results saved to: {output_file}")
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())