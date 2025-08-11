#!/usr/bin/env python3
"""
Comprehensive test script to:
1. Run queries and report on results (total after dedup and per source)
2. Clear local database
3. Load RSS feed data and run queries
4. Save results to JSON file
"""

import asyncio
import json
import subprocess
import sys
import os
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.retriever import get_vector_db_client
from data_loading.db_load import main as db_load_main


class QueryTester:
    def __init__(self):
        self.retriever = None
        
    async def initialize(self):
        """Initialize the retriever client"""
        self.retriever = get_vector_db_client()
        
    async def run_query(self, query: str, site: str = "all", num_results: int = 50) -> Dict[str, Any]:
        """
        Run a single query and analyze results
        
        Returns:
            Dict containing:
            - query: the query string
            - total_results: total number of results
            - unique_results: number after deduplication
            - results_by_source: dict of source -> count
            - duplicates: number of duplicate results
        """
        print(f"\n{'='*60}")
        print(f"Query: '{query}' | Site: {site}")
        print('='*60)
        
        try:
            # Run the search
            results = await self.retriever.search(query, site, num_results)
            
            # Analyze results
            total_results = len(results)
            
            # Track unique URLs and sources
            unique_urls = set()
            results_by_source = {}
            url_to_sources = {}
            
            for result in results:
                # Extract URL and source from result
                # Result format is typically [url, json, name, site]
                if len(result) >= 4:
                    url = result[0]  # URL is first
                    source = result[3]  # site/source is fourth
                    
                    # Track unique URLs
                    unique_urls.add(url)
                    
                    # Track sources
                    if source not in results_by_source:
                        results_by_source[source] = 0
                    results_by_source[source] += 1
                    
                    # Track which sources have each URL (for duplicate detection)
                    if url not in url_to_sources:
                        url_to_sources[url] = []
                    url_to_sources[url].append(source)
            
            # Find duplicates
            duplicates = {url: sources for url, sources in url_to_sources.items() if len(sources) > 1}
            
            analysis = {
                "query": query,
                "site": site,
                "total_results": total_results,
                "unique_results": len(unique_urls),
                "results_by_source": results_by_source,
                "duplicate_count": len(duplicates),
                "duplicates": duplicates if duplicates else None
            }
            
            # Print summary
            print(f"Total results: {total_results}")
            print(f"Unique results (after dedup): {len(unique_urls)}")
            print(f"Duplicate URLs: {len(duplicates)}")
            
            print(f"\nResults by source:")
            for source, count in sorted(results_by_source.items()):
                print(f"  {source}: {count}")
            
            if duplicates and len(duplicates) <= 5:
                print(f"\nDuplicate URLs found in multiple sources:")
                for url, sources in list(duplicates.items())[:5]:
                    print(f"  - {url[:80]}...")
                    print(f"    Found in: {', '.join(sources)}")
            elif duplicates:
                print(f"\nFound {len(duplicates)} duplicate URLs (too many to display)")
                
            return analysis
            
        except Exception as e:
            print(f"Error running query: {e}")
            return {
                "query": query,
                "site": site,
                "error": str(e)
            }
    
    async def run_query_set(self, queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run a set of queries and return all results
        
        Args:
            queries: List of dicts with 'query' and optional 'site', 'num_results'
        """
        results = []
        for q in queries:
            query = q.get('query')
            site = q.get('site', 'all')
            num_results = q.get('num_results', 50)
            
            result = await self.run_query(query, site, num_results)
            results.append(result)
            
            # Small delay between queries
            await asyncio.sleep(0.5)
        
        return results
    
    def print_summary(self, results: List[Dict[str, Any]]):
        """Print overall summary of all queries"""
        print("\n" + "="*80)
        print("OVERALL SUMMARY")
        print("="*80)
        
        total_queries = len(results)
        successful_queries = len([r for r in results if 'error' not in r])
        
        print(f"Total queries run: {total_queries}")
        print(f"Successful queries: {successful_queries}")
        
        if successful_queries > 0:
            # Aggregate statistics
            total_results = sum(r.get('total_results', 0) for r in results if 'error' not in r)
            total_unique = sum(r.get('unique_results', 0) for r in results if 'error' not in r)
            total_duplicates = sum(r.get('duplicate_count', 0) for r in results if 'error' not in r)
            
            print(f"\nAggregate statistics:")
            print(f"  Total results across all queries: {total_results}")
            print(f"  Total unique results: {total_unique}")
            print(f"  Total duplicates: {total_duplicates}")
            
            # Aggregate by source
            all_sources = {}
            for r in results:
                if 'error' not in r and 'results_by_source' in r:
                    for source, count in r['results_by_source'].items():
                        if source not in all_sources:
                            all_sources[source] = 0
                        all_sources[source] += count
            
            if all_sources:
                print(f"\nTotal results by source across all queries:")
                for source, count in sorted(all_sources.items()):
                    print(f"  - {source}: {count}")


async def load_rss_feed(rss_url: str, site_name: str = None, use_subprocess: bool = True):
    """Load an RSS feed using db_load
    
    Args:
        rss_url: URL of the RSS feed
        site_name: Name for the site (auto-generated if not provided)
        use_subprocess: If True, use subprocess to call db_load (more isolated)
    """
    print(f"\nLoading RSS feed: {rss_url}")
    
    if not site_name:
        # Extract site name from URL
        from urllib.parse import urlparse
        parsed = urlparse(rss_url)
        site_name = parsed.netloc.replace('www.', '').replace('.com', '').replace('.', '_')
    
    print(f"Using site name: {site_name}")
    
    if use_subprocess:
        # Use subprocess for better isolation
        print("Loading RSS feed using subprocess...")
        cmd = [
            sys.executable,
            os.path.join(os.path.dirname(__file__), "..", "tools", "db_load.py"),
            "--rss", rss_url,
            "--site", site_name,
            "--delete"  # Delete existing data first
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error loading RSS: {result.stderr}")
                raise Exception(f"db_load failed: {result.stderr}")
            print("RSS feed loaded successfully")
            return site_name
        except Exception as e:
            print(f"Error loading RSS feed: {e}")
            raise
    else:
        # Direct call to db_load_main
        args = [
            '--rss', rss_url,
            '--site', site_name,
            '--delete'
        ]
        
        try:
            original_argv = sys.argv
            sys.argv = ['db_load.py'] + args
            
            db_load_main()
            
            print(f"Successfully loaded RSS feed for site: {site_name}")
            return site_name
            
        except Exception as e:
            print(f"Error loading RSS feed: {e}")
            raise
        finally:
            sys.argv = original_argv


async def clear_local_qdrant():
    """Clear all data from the local Qdrant database"""
    print("\nClearing local Qdrant database...")
    try:
        # Get the write endpoint client
        retriever = get_vector_db_client()
        
        # Get all sites first
        all_sites = await retriever.get_sites()
        
        if all_sites:
            print(f"Found {len(all_sites)} sites to delete: {all_sites}")
            
            # Delete each site
            for site in all_sites:
                try:
                    deleted_count = await retriever.delete_documents_by_site(site)
                    print(f"  Deleted {deleted_count} documents from site: {site}")
                except Exception as e:
                    print(f"  Error deleting site {site}: {e}")
        else:
            print("No sites found or backend doesn't support listing sites")
            # Try to delete some common sites that might exist
            common_sites = ["recodedecode", "seriouseats", "techcrunch"]
            for site in common_sites:
                try:
                    deleted_count = await retriever.delete_documents_by_site(site)
                    if deleted_count > 0:
                        print(f"  Deleted {deleted_count} documents from site: {site}")
                except Exception as e:
                    # Silently skip if site doesn't exist
                    pass
                    
        print("Local Qdrant database cleared\n")
    except Exception as e:
        print(f"Error clearing Qdrant database: {e}\n")


async def main():
    # Check if we're in the right directory
    if not os.path.exists("retrieval"):
        print("Please run this script from the code/ directory")
        sys.exit(1)
    
    # Clear the local Qdrant database first
    await clear_local_qdrant()
    
    # Initialize tester
    tester = QueryTester()
    await tester.initialize()
    
    all_results = []
    
    # Part 1: Run test queries
    print("\nPart 1: Running test queries")
    print("="*80)
    
    queries = [
        {
            "query": "machine learning",
            "site": "all",
            "num_results": 50
        },
        {
            "query": "artificial intelligence",
            "site": "all",
            "num_results": 50
        },
        {
            "query": "python programming",
            "site": "all",
            "num_results": 50
        },
        {
            "query": "latest technology news",
            "site": "all",
            "num_results": 40
        },
        {
            "query": "climate change",
            "site": "all",
            "num_results": 50
        },
        {
            "query": "spicy crunchy snacks",
            "site": "seriouseats",
            "num_results": 50
        }
    ]
    
    results = await tester.run_query_set(queries)
    all_results.extend(results)
    
    print("\nInitial query set summary:")
    tester.print_summary(results)
    
    # Part 2: Load RSS feed and run queries
    print("\n\nPart 2: Loading RSS feed and running queries")
    print("="*80)
    
    rss_url = "https://feeds.megaphone.fm/recodedecode"
    site_name = "recodedecode"
    
    # Load the RSS feed
    try:
        loaded_site = await load_rss_feed(rss_url, site_name)
        
        # Wait for indexing
        print("Waiting for indexing to complete...")
        await asyncio.sleep(5)
        
        # Define queries for the RSS content
        rss_queries = [
            {"query": "podcast", "site": loaded_site},
            {"query": "technology", "site": loaded_site},
            {"query": "decode", "site": loaded_site},
            {"query": "recode", "site": loaded_site},
            {"query": "episode", "site": loaded_site},
            {"query": "all", "site": loaded_site}  # Get all content
        ]
        
        print(f"\nRunning queries on RSS feed content (site: {loaded_site}):")
        rss_results = await tester.run_query_set(rss_queries)
        all_results.extend(rss_results)
        
        print("\nRSS query set summary:")
        tester.print_summary(rss_results)
        
    except Exception as e:
        print(f"Error loading RSS feed: {e}")
    
    # Save all results
    output_file = f"query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "results": all_results
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n\nResults saved to: {output_file}")
    
    # Print final summary
    print("\n\nFINAL SUMMARY (ALL QUERIES)")
    print("="*80)
    tester.print_summary(all_results)


# Example queries.json file format:
EXAMPLE_QUERIES = """
[
  {
    "query": "machine learning",
    "site": "all",
    "num_results": 50
  },
  {
    "query": "artificial intelligence applications",
    "site": "techcrunch",
    "num_results": 30
  },
  {
    "query": "latest technology news",
    "site": "all",
    "num_results": 40
  },
  {
    "query": "spicy crunchy snacks",
    "site": "seriouseats",
    "num_results": 50
  }
]
"""

if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())