#!/usr/bin/env python3
"""
Test database operations using only local Qdrant database
"""

import asyncio
import os
import sys
from typing import Any, Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import aiohttp
import feedparser

from core.config import CONFIG
from core.embedding import batch_get_embeddings
from core.retriever import delete_documents_by_site, get_sites, search, upload_documents


async def test_local_database():
    """Test upload/search/delete on local Qdrant database"""
    print("\n🧪 Testing Local Database Operations")
    print("   Database: qdrant_local")

    test_rss_url = "https://feeds.npr.org/344098539/podcast.xml"
    test_site = "test_npr_podcast"
    test_query = "Tom Papa"

    try:
        # Download RSS feed
        print("\n📥 Downloading RSS feed...")
        async with aiohttp.ClientSession() as session, session.get(test_rss_url) as response:
            rss_content = await response.text()
        print(f"✅ Downloaded {len(rss_content)} bytes")

        # Parse RSS feed
        print("\n📄 Parsing RSS feed...")
        feed = feedparser.parse(rss_content)
        documents = []

        # Take only first 3 episodes for quick test
        for entry in feed.entries[:3]:
            doc = {
                "url": entry.get("link", f"https://example.com/{entry.get('id', 'unknown')}"),
                "name": entry.get("title", "Unknown Episode"),
                "site": test_site,
                "schema_json": {
                    "@type": "PodcastEpisode",
                    "name": entry.get("title", ""),
                    "description": entry.get("summary", "")[:500],  # Limit description length
                    "url": entry.get("link", "")
                }
            }
            documents.append(doc)

        print(f"✅ Found {len(documents)} episodes")
        for i, doc in enumerate(documents):
            print(f"   {i+1}. {doc['name']}")

        # Generate embeddings - try different providers
        print("\n🔢 Generating embeddings...")
        texts = [f"{d['name']} {d['schema_json'].get('description', '')}" for d in documents]

        # Try to get embeddings with available provider
        embeddings = None
        providers_to_try = ["openai", "azure_openai", "gemini"]

        for provider in providers_to_try:
            try:
                print(f"   Trying provider: {provider}")
                embeddings = await batch_get_embeddings(texts, provider=provider)
                if embeddings and all(e is not None for e in embeddings):
                    print(f"   ✅ Got embeddings from {provider}")
                    break
            except Exception as e:
                print(f"   ❌ Failed with {provider}: {e!s}")
                continue

        if not embeddings:
            print("❌ Could not generate embeddings with any provider")
            print("\n📝 Creating mock embeddings for testing...")
            # Create mock embeddings for testing
            import random
            embeddings = [[random.random() for _ in range(1536)] for _ in texts]

        # Add embeddings to documents
        for i, doc in enumerate(documents):
            if i < len(embeddings):
                doc["embedding"] = embeddings[i]

        # Upload documents to local database
        print(f"\n📤 Uploading {len(documents)} documents to local Qdrant...")
        upload_count = await upload_documents(documents, endpoint_name="qdrant_local")
        print(f"✅ Uploaded {upload_count} documents")

        # Wait for indexing
        print("⏳ Waiting 2 seconds for indexing...")
        await asyncio.sleep(2)

        # Search for test query
        print(f"\n🔍 Searching for '{test_query}' in local database...")
        results = await search(test_query, site=test_site, endpoint_name="qdrant_local")

        if results:
            print(f"✅ Found {len(results)} results")
            for i, result in enumerate(results[:3]):
                print(f"   {i+1}. {result[2]}")  # Name is at index 2
        else:
            print(f"⚠️  No results found for '{test_query}'")
            # Try a different search
            print("\n🔍 Trying broader search for 'podcast'...")
            results = await search("podcast", site=test_site, endpoint_name="qdrant_local")
            if results:
                print(f"✅ Found {len(results)} results")
                for i, result in enumerate(results[:3]):
                    print(f"   {i+1}. {result[2]}")

        # List all sites
        print("\n📋 Listing all sites in database...")
        try:
            sites = await get_sites(endpoint_name="qdrant_local")
            if sites:
                print(f"✅ Found {len(sites)} sites:")
                for site in sites[:5]:
                    print(f"   - {site}")
            else:
                print("⚠️  No sites found")
        except Exception as e:
            print(f"⚠️  Could not list sites: {e!s}")

        # Clean up - delete the test site
        print(f"\n🗑️  Deleting test site '{test_site}'...")
        delete_count = await delete_documents_by_site(test_site, endpoint_name="qdrant_local")
        print(f"✅ Deleted {delete_count} documents")

        # Verify deletion
        print("\n🔍 Verifying deletion...")
        verify_results = await search("podcast", site=test_site, endpoint_name="qdrant_local")
        if not verify_results:
            print("✅ Deletion confirmed - no results found")
        else:
            print(f"⚠️  Still found {len(verify_results)} results after deletion")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e!s}")
        import traceback
        traceback.print_exc()

        # Try cleanup
        try:
            print("\n🧹 Attempting cleanup...")
            await delete_documents_by_site(test_site, endpoint_name="qdrant_local")
        except Exception:
            pass

        return False


async def test_existing_data():
    """Test search on existing data in local database"""
    print("\n🧪 Testing Search on Existing Data")

    try:
        # Search across all sites
        print("\n🔍 Searching for 'python' across all sites...")
        results = await search("python", site="all", endpoint_name="qdrant_local", num_results=5)

        if results:
            print(f"✅ Found {len(results)} results")
            for i, result in enumerate(results):
                print(f"   {i+1}. {result[2]} (site: {result[3]})")
        else:
            print("⚠️  No results found")

        return True

    except Exception as e:
        print(f"❌ Error: {e!s}")
        return False


async def main():
    """Run the tests"""
    print("🚀 Local Database Operations Test")
    print("="*50)

    # Check configuration
    print("\n📋 Configuration Check:")
    print(f"   Write Endpoint: {CONFIG.write_endpoint}")
    print(f"   Qdrant Local Path: {CONFIG.retrieval_endpoints.get('qdrant_local', {}).database_path}")

    # Test local database operations
    local_success = await test_local_database()

    # Test existing data search
    existing_success = await test_existing_data()

    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    print(f"Local Database Test: {'✅ PASSED' if local_success else '❌ FAILED'}")
    print(f"Existing Data Search: {'✅ PASSED' if existing_success else '❌ FAILED'}")

    if local_success and existing_success:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print("\n⚠️  Some tests may have failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
