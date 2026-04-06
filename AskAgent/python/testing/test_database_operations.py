#!/usr/bin/env python3
"""
Test suite for database operations including upload, search, and delete.

This test will:
1. Load an RSS feed into each enabled database endpoint
2. Search for specific content to verify upload
3. Delete the uploaded content
4. Test search operations against existing data
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
from core.retriever import delete_documents_by_site, get_sites, search, search_all_sites, upload_documents


class DatabaseOperationsTest:
    def __init__(self):
        self.test_rss_url = "https://feeds.npr.org/344098539/podcast.xml"
        self.test_site = "test_npr_podcast"
        self.test_query = "Tom Papa"
        self.prod_query = "spicy crunchy snacks"
        self.prod_endpoint = "nlweb_west"

    async def download_rss_feed(self) -> str:
        """Download RSS feed content"""
        print(f"\n📥 Downloading RSS feed from: {self.test_rss_url}")
        async with aiohttp.ClientSession() as session, session.get(self.test_rss_url) as response:
            content = await response.text()
            print(f"✅ Downloaded RSS feed ({len(content)} bytes)")
            return content

    async def parse_rss_to_documents_with_embeddings(self, rss_content: str) -> list[dict[str, Any]]:
        """Parse RSS content and add embeddings"""
        print("\n📄 Parsing RSS feed...")

        # Parse RSS using feedparser
        feed = feedparser.parse(rss_content)
        documents = []

        for entry in feed.entries[:10]:  # Limit to first 10 entries for testing
            doc = {
                "url": entry.get("link", ""),
                "name": entry.get("title", ""),
                "site": self.test_site,
                "schema_json": {
                    "@type": "PodcastEpisode",
                    "name": entry.get("title", ""),
                    "description": entry.get("summary", ""),
                    "url": entry.get("link", ""),
                    "datePublished": entry.get("published", "")
                }
            }
            documents.append(doc)

        print(f"✅ Parsed {len(documents)} episodes from RSS feed")

        # Generate embeddings
        print(f"\n🔢 Generating embeddings for {len(documents)} documents...")
        texts_to_embed = []
        for doc in documents:
            # Create text from title and description
            title = doc["schema_json"].get("name", "")
            description = doc["schema_json"].get("description", "")
            text = f"{title} {description}"
            texts_to_embed.append(text)

        # Get embeddings in batch
        embeddings = await batch_get_embeddings(texts_to_embed)

        # Add embeddings to documents
        for i, doc in enumerate(documents):
            if i < len(embeddings):
                doc["embedding"] = embeddings[i]

        print(f"✅ Generated embeddings for {len(embeddings)} documents")
        return documents

    async def test_endpoint_operations(self, endpoint_name: str) -> bool:
        """Test upload, search, and delete operations on a single endpoint"""
        print(f"\n{'='*60}")
        print(f"🧪 Testing endpoint: {endpoint_name}")
        print(f"{'='*60}")

        try:
            # Download and parse RSS feed
            rss_content = await self.download_rss_feed()
            documents = await self.parse_rss_to_documents_with_embeddings(rss_content)

            # Upload documents
            print(f"\n📤 Uploading {len(documents)} documents to {endpoint_name}...")
            upload_count = await upload_documents(documents, endpoint_name=endpoint_name)
            print(f"✅ Successfully uploaded {upload_count} documents")

            # Wait a bit for indexing
            print("⏳ Waiting 2 seconds for indexing...")
            await asyncio.sleep(2)

            # Search for test query
            print(f"\n🔍 Searching for '{self.test_query}' in {endpoint_name}...")
            search_results = await search(self.test_query, site=self.test_site, endpoint_name=endpoint_name)

            if search_results:
                print(f"✅ Found {len(search_results)} results for '{self.test_query}'")
                # Print first result
                if len(search_results) > 0:
                    first_result = search_results[0]
                    print(f"   First result: {first_result[2]}")  # Name is at index 2
            else:
                print(f"❌ No results found for '{self.test_query}'")
                return False

            # Delete the site
            print(f"\n🗑️  Deleting site '{self.test_site}' from {endpoint_name}...")
            delete_count = await delete_documents_by_site(self.test_site, endpoint_name=endpoint_name)
            print(f"✅ Deleted {delete_count} documents")

            # Verify deletion
            print("\n🔍 Verifying deletion by searching again...")
            verify_results = await search(self.test_query, site=self.test_site, endpoint_name=endpoint_name)

            if not verify_results:
                print("✅ Deletion verified - no results found")
            else:
                print(f"❌ Deletion failed - still found {len(verify_results)} results")
                return False

            return True

        except Exception as e:
            print(f"❌ Error testing endpoint {endpoint_name}: {e!s}")
            traceback.print_exc()
            # Try to clean up
            with contextlib.suppress(BaseException):
                await delete_documents_by_site(self.test_site, endpoint_name=endpoint_name)
            return False

    async def test_production_search(self) -> bool:
        """Test search operations against production data"""
        print(f"\n{'='*60}")
        print(f"🧪 Testing production search on {self.prod_endpoint}")
        print(f"{'='*60}")

        try:
            # Test regular search
            print(f"\n🔍 Testing search() for '{self.prod_query}' on {self.prod_endpoint}...")
            search_results = await search(
                self.prod_query,
                site="all",
                endpoint_name=self.prod_endpoint
            )

            if search_results:
                print(f"✅ search() returned {len(search_results)} results")
                # Print first few results
                for i, result in enumerate(search_results[:3]):
                    print(f"   Result {i+1}: {result[2]}")  # Name at index 2
            else:
                print("❌ No results found with search()")
                return False

            # Test search_all_sites
            print(f"\n🔍 Testing search_all_sites() for '{self.prod_query}' on {self.prod_endpoint}...")
            all_sites_results = await search_all_sites(
                self.prod_query,
                top_n=10,
                endpoint_name=self.prod_endpoint
            )

            if all_sites_results:
                print(f"✅ search_all_sites() returned {len(all_sites_results)} results")
                # Print first few results
                for i, result in enumerate(all_sites_results[:3]):
                    print(f"   Result {i+1}: {result[2]}")  # Name at index 2
            else:
                print("❌ No results found with search_all_sites()")
                return False

            return True

        except Exception as e:
            print(f"❌ Error in production search test: {e!s}")
            traceback.print_exc()
            return False

    async def run_all_tests(self):
        """Run all database operation tests"""
        print("\n🚀 Starting Database Operations Test Suite")
        print(f"   RSS Feed: {self.test_rss_url}")
        print(f"   Test Site: {self.test_site}")
        print(f"   Test Query: {self.test_query}")
        print(f"   Production Query: {self.prod_query}")

        # Get enabled endpoints that support write operations
        enabled_endpoints = []
        for name, config in CONFIG.retrieval_endpoints.items():
            if config.enabled:
                enabled_endpoints.append(name)

        print(f"\n📋 Found {len(enabled_endpoints)} enabled endpoints: {', '.join(enabled_endpoints)}")

        # Test each endpoint
        endpoint_results = {}
        for endpoint in enabled_endpoints:
            success = await self.test_endpoint_operations(endpoint)
            endpoint_results[endpoint] = success

        # Test production search
        prod_success = await self.test_production_search()

        # Summary
        print(f"\n{'='*60}")
        print("📊 TEST SUMMARY")
        print(f"{'='*60}")

        print("\nEndpoint Tests:")
        for endpoint, success in endpoint_results.items():
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"  {endpoint:30} : {status}")

        print(f"\nProduction Search Test: {'✅ PASSED' if prod_success else '❌ FAILED'}")

        # Overall result
        all_passed = all(endpoint_results.values()) and prod_success
        print(f"\n{'='*60}")
        if all_passed:
            print("✅ ALL TESTS PASSED!")
        else:
            print("❌ SOME TESTS FAILED!")
        print(f"{'='*60}")

        return all_passed


async def main():
    """Main test runner"""
    tester = DatabaseOperationsTest()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
