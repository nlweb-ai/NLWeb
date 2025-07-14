#!/usr/bin/env python3
"""
Complete test script that:
1. Clears the local Qdrant database
2. Runs queries and reports results
3. Loads RSS feed and runs queries
"""

import asyncio
import subprocess
import sys
import os
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.retriever import get_vector_db_client


async def clear_database():
    """Clear all data from local Qdrant"""
    print("\n" + "="*60)
    print("CLEARING LOCAL DATABASE")
    print("="*60)
    
    retriever = get_vector_db_client()
    
    # Get all sites
    try:
        sites = await retriever.get_sites()
        if sites:
            print(f"Found {len(sites)} sites to delete: {', '.join(sites[:5])}" + 
                  ("..." if len(sites) > 5 else ""))
            
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
        print(f"Error getting sites: {e}")


async def analyze_query_results(query, site, results):
    """Analyze and print query results"""
    print(f"\nQuery: '{query}' | Site: {site}")
    print("-" * 60)
    
    # Analysis
    total = len(results)
    urls = set()
    sources = defaultdict(int)
    duplicates = defaultdict(list)
    
    for result in results:
        if len(result) >= 4:
            url = result[1]
            source = result[3]
            
            urls.add(url)
            sources[source] += 1
            duplicates[url].append(source)
    
    # Results
    print(f"Total results: {total}")
    print(f"Unique URLs: {len(urls)}")
    print(f"Duplicates: {sum(1 for dups in duplicates.values() if len(dups) > 1)}")
    
    if sources:
        print("\nResults by source:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            print(f"  {source}: {count}")
    
    return {
        "query": query,
        "site": site,
        "total": total,
        "unique": len(urls),
        "sources": dict(sources)
    }


async def run_query_tests():
    """Run standard query tests"""
    print("\n" + "="*60)
    print("RUNNING QUERY TESTS")
    print("="*60)
    
    retriever = get_vector_db_client()
    
    queries = [
        ("machine learning", "all"),
        ("artificial intelligence", "all"),
        ("python programming", "all"),
        ("spicy crunchy snacks", "seriouseats"),
        ("latest technology news", "all")
    ]
    
    results_summary = []
    
    for query, site in queries:
        try:
            results = await retriever.search(query, site, num_results=50)
            summary = await analyze_query_results(query, site, results)
            results_summary.append(summary)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"\nError with query '{query}': {e}")
    
    return results_summary


async def load_rss_feed(url, site_name):
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
        "--delete"  # Delete existing first
    ]
    
    print("\nRunning db_load...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    
    print("RSS feed loaded successfully")
    return True


async def test_rss_queries(site_name):
    """Test queries on RSS content"""
    print(f"\n" + "="*60)
    print(f"TESTING RSS CONTENT")
    print("="*60)
    
    retriever = get_vector_db_client()
    
    queries = [
        ("podcast", site_name),
        ("technology", site_name),
        ("decode", site_name),
        ("recode", site_name),
        ("episode", site_name),
        ("all", site_name)
    ]
    
    results_summary = []
    
    for query, site in queries:
        try:
            results = await retriever.search(query, site, num_results=50)
            summary = await analyze_query_results(query, site, results)
            results_summary.append(summary)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"\nError with query '{query}': {e}")
    
    return results_summary


async def main():
    print("\n" + "="*80)
    print("NLWEB QUERY TEST WITH CLEAN DATABASE")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Clear database
    await clear_database()
    
    # Step 2: Run initial queries (should return no results)
    print("\n\nTesting queries on empty database...")
    empty_results = await run_query_tests()
    
    # Step 3: Load RSS feed
    rss_url = "https://feeds.megaphone.fm/recodedecode"
    site_name = "recodedecode"
    
    if await load_rss_feed(rss_url, site_name):
        # Wait for indexing
        print("\nWaiting 5 seconds for indexing...")
        await asyncio.sleep(5)
        
        # Step 4: Test RSS queries
        rss_results = await test_rss_queries(site_name)
    
    # Step 5: Run general queries again (should now include RSS content)
    print("\n\nRunning general queries (with RSS content)...")
    final_results = await run_query_tests()
    
    # Summary
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())