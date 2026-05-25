#!/usr/bin/env python3
"""
Simplified test for database operations - tests only the write endpoint and production search.
"""

import asyncio
import os
import sys
import traceback
from typing import Any, Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import contextlib

import aiohttp
import feedparser

from core.config import CONFIG
from core.embedding import batch_get_embeddings
from core.retriever import delete_documents_by_site, search, search_all_sites, upload_documents


async def test_write_endpoint():
    """Test upload/search/delete on the configured write endpoint"""
    print("\n🧪 Testing Write Endpoint Operations")
    print(f"   Write Endpoint: {CONFIG.write_endpoint}")

    test_rss_url = "https://feeds.npr.org/344098539/podcast.xml"
    test_site = "test_npr_podcast"
    test_query = "Tom Papa"

    try:
        # Download RSS feed
        print("\n📥 Downloading RSS feed...")
        async with aiohttp.ClientSession() as session, session.get(test_rss_url) as response:
            rss_content = await response.text()

        # Parse RSS feed
        print("📄 Parsing RSS feed...")
        feed = feedparser.parse(rss_content)
        documents = []

        # Take only first 5 episodes for quick test
        for entry in feed.entries[:5]:
            doc = {
                "url": entry.get("link", ""),
                "name": entry.get("title", ""),
                "site": test_site,
                "schema_json": {
                    "@type": "PodcastEpisode",
                    "name": entry.get("title", ""),
                    "description": entry.get("summary", ""),
                    "url": entry.get("link", "")
                }
            }
            documents.append(doc)

        print(f"✅ Found {len(documents)} episodes")

        # Generate embeddings
        print("🔢 Generating embeddings...")
        texts = [f"{d['name']} {d['schema_json'].get('description', '')}" for d in documents]
        embeddings = await batch_get_embeddings(texts)

        for i, doc in enumerate(documents):
            if i < len(embeddings):
                doc["embedding"] = embeddings[i]

        # Upload documents (uses write_endpoint by default)
        print("\n📤 Uploading documents to write endpoint...")
        upload_count = await upload_documents(documents)
        print(f"✅ Uploaded {upload_count} documents")

        # Wait for indexing
        await asyncio.sleep(2)

        # Search for test query
        print(f"\n🔍 Searching for '{test_query}'...")
        results = await search(test_query, site=test_site)

        if results:
            print(f"✅ Found {len(results)} results")
            print(f"   First result: {results[0][2]}")
        else:
            print("❌ No results found")
            return False

        # Clean up - delete the test site
        print("\n🗑️  Deleting test site...")
        delete_count = await delete_documents_by_site(test_site)
        print(f"✅ Deleted {delete_count} documents")

        return True

    except Exception as e:
        print(f"❌ Error: {e!s}")
        # Try cleanup
        with contextlib.suppress(BaseException):
            await delete_documents_by_site(test_site)
        return False


async def test_production_search():
    """Test search against production data"""
    print("\n🧪 Testing Production Search")

    prod_query = "spicy crunchy snacks"
    prod_endpoint = "nlweb_west"

    try:
        # Test regular search
        print(f"\n🔍 Testing search() for '{prod_query}'...")
        results = await search(prod_query, site="all", endpoint_name=prod_endpoint)

        if results:
            print(f"✅ Found {len(results)} results")
            for i, result in enumerate(results[:3]):
                print(f"   {i+1}. {result[2]}")
        else:
            print("❌ No results found")
            return False

        # Test search_all_sites
        print(f"\n🔍 Testing search_all_sites() for '{prod_query}'...")
        results = await search_all_sites(prod_query, top_n=10, endpoint_name=prod_endpoint)

        if results:
            print(f"✅ Found {len(results)} results")
            for i, result in enumerate(results[:3]):
                print(f"   {i+1}. {result[2]}")
        else:
            print("❌ No results found")
            return False

        return True

    except Exception as e:
        print(f"❌ Error: {e!s}")
        traceback.print_exc()
        return False


async def main():
    """Run the tests"""
    print("🚀 Database Operations Test (Simplified)")

    # Test write endpoint
    write_success = await test_write_endpoint()

    # Test production search
    search_success = await test_production_search()

    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    print(f"Write Endpoint Test: {'✅ PASSED' if write_success else '❌ FAILED'}")
    print(f"Production Search Test: {'✅ PASSED' if search_success else '❌ FAILED'}")

    if write_success and search_success:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
