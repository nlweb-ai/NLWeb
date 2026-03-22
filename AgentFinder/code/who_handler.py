"""
Core WHO handler logic - orchestration, caching, and ranking.
Backend-agnostic implementation.
"""
import os
import asyncio
import hashlib
import time
from typing import List, Dict, Any, Optional, Tuple
from collections import OrderedDict

from search_backend import get_search_backend
from llm_backend import get_llm_backend

# Settings from environment variables
SETTINGS = {
    "score_threshold": int(os.getenv("WHO_SCORE_THRESHOLD", "70")),
    "early_threshold": int(os.getenv("WHO_EARLY_THRESHOLD", "85")),  # Return early if enough high scores
    "max_results": int(os.getenv("WHO_MAX_RESULTS", "10")),
    "search_top_k": int(os.getenv("WHO_SEARCH_TOP_K", "30")),
    "cache_ttl": int(os.getenv("WHO_CACHE_TTL", "3600")),
    "max_cache_entries": int(os.getenv("WHO_MAX_CACHE_ENTRIES", "10000")),
    "ranking_cache_entries": int(os.getenv("WHO_RANKING_CACHE_ENTRIES", "100000")),
}


class TTLCache:
    """Simple TTL cache with LRU eviction"""

    def __init__(self, max_size: int = 10000, ttl: int = 3600):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def get(self, key: Any) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                # Move to end for LRU
                self.cache.move_to_end(key)
                return value
            else:
                # Expired - remove it
                del self.cache[key]
        return None

    def set(self, key: Any, value: Any):
        """Set value in cache with current timestamp"""
        # Evict oldest if at capacity
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)

        self.cache[key] = (value, time.time())

    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()

    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)


class WHOHandler:
    """Main WHO query handler with caching and parallel processing"""

    def __init__(self):
        self.search_backend = None
        self.llm_backend = None

        # Caches with different TTLs and sizes
        self.embedding_cache = {}  # Never expires - embeddings are stable
        self.search_cache = TTLCache(
            max_size=SETTINGS["max_cache_entries"],
            ttl=SETTINGS["cache_ttl"]
        )
        self.ranking_cache = TTLCache(
            max_size=SETTINGS["ranking_cache_entries"],
            ttl=SETTINGS["cache_ttl"] * 2  # Rankings cached longer
        )

        # Statistics
        self.stats = {
            "queries_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_sites_ranked": 0,
        }

    async def initialize(self):
        """Initialize backends"""
        print("Initializing WHO Handler...")

        # Get and initialize backends
        self.search_backend = get_search_backend()
        self.llm_backend = get_llm_backend()

        await asyncio.gather(
            self.search_backend.initialize(),
            self.llm_backend.initialize()
        )

        print("WHO Handler initialized successfully")

    async def process_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Process a WHO query and return ranked results.

        Args:
            query: The user's question

        Returns:
            List of ranked sites with scores and descriptions
        """
        self.stats["queries_processed"] += 1
        start_time = time.time()

        try:
            # 1. Get embedding (with cache)
            embedding_start = time.time()
            if query not in self.embedding_cache:
                self.embedding_cache[query] = await self.llm_backend.get_embedding(query)
                print(f"Generated embedding for query in {time.time() - embedding_start:.2f}s")
            else:
                print(f"Using cached embedding")

            vector = self.embedding_cache[query]

            # 2. Search for relevant sites (with cache)
            search_start = time.time()
            cache_key = hashlib.md5(query.encode()).hexdigest()
            search_results = self.search_cache.get(cache_key)

            if search_results is None:
                self.stats["cache_misses"] += 1
                search_results = await self.search_backend.search(
                    query, vector, SETTINGS["search_top_k"]
                )
                self.search_cache.set(cache_key, search_results)
                print(f"Retrieved {len(search_results)} sites from search in {time.time() - search_start:.2f}s")
            else:
                self.stats["cache_hits"] += 1
                print(f"Using cached search results ({len(search_results)} sites)")

            if not search_results:
                print("No search results found")
                return []

            # 3. Rank sites in parallel
            ranking_start = time.time()
            ranking_tasks = []

            for site in search_results:
                rank_cache_key = (cache_key, site["url"])

                # Check if already ranked
                cached_ranking = self.ranking_cache.get(rank_cache_key)
                if cached_ranking is not None:
                    continue

                # Create ranking task
                ranking_tasks.append(self._rank_site(query, site, rank_cache_key))

            # Execute ranking tasks and check for early return
            high_score_results = []  # Track high-scoring results for early return
            completed_count = 0
            error_count = 0

            if ranking_tasks:
                print(f"Ranking {len(ranking_tasks)} new sites...")

                # Process results as they complete
                for completed_task in asyncio.as_completed(ranking_tasks):
                    try:
                        result = await completed_task
                        completed_count += 1

                        # Check cached result for high score
                        # The task has already cached the result, so check all cached results
                        for site in search_results:
                            rank_cache_key = (cache_key, site["url"])
                            ranking = self.ranking_cache.get(rank_cache_key)

                            if ranking and ranking["score"] >= SETTINGS["early_threshold"]:
                                # Check if we already have this high-scoring site
                                if not any(r["url"] == site["url"] for r in high_score_results):
                                    # Extract @type from json_ld
                                    schema_type = "Site"
                                    try:
                                        import json
                                        json_ld_data = json.loads(site.get("json_ld", "{}"))
                                        if isinstance(json_ld_data, dict):
                                            schema_type = json_ld_data.get("@type", "Site")
                                        elif isinstance(json_ld_data, list) and json_ld_data:
                                            schema_type = json_ld_data[0].get("@type", "Site")
                                    except:
                                        pass

                                    high_score_results.append({
                                        "@type": schema_type,
                                        "url": site["url"],
                                        "name": site["name"],
                                        "score": ranking["score"],
                                        "description": ranking["description"],
                                        "api_version": "1.0"
                                    })

                                    # Check if we have enough high-scoring results for early return
                                    if len(high_score_results) >= SETTINGS["max_results"]:
                                        print(f"Early return: Found {len(high_score_results)} high-scoring results (>= {SETTINGS['early_threshold']})")
                                        # Sort and return early
                                        high_score_results.sort(key=lambda x: x["score"], reverse=True)
                                        return high_score_results[:SETTINGS["max_results"]]

                    except Exception as e:
                        error_count += 1
                        # Continue processing other tasks

                print(f"Ranked {completed_count} sites, {error_count} errors in {time.time() - ranking_start:.2f}s")
            else:
                print("All sites already ranked (from cache)")

            # 4. Collect and filter results
            final_results = []

            for site in search_results:
                rank_cache_key = (cache_key, site["url"])
                ranking = self.ranking_cache.get(rank_cache_key)

                if ranking and ranking["score"] > SETTINGS["score_threshold"]:
                    # Extract @type from json_ld if available
                    schema_type = "Site"  # Default type
                    try:
                        import json
                        json_ld_data = json.loads(site.get("json_ld", "{}"))
                        if isinstance(json_ld_data, dict):
                            schema_type = json_ld_data.get("@type", "Site")
                        elif isinstance(json_ld_data, list) and json_ld_data:
                            schema_type = json_ld_data[0].get("@type", "Site")
                    except:
                        pass  # Use default if parsing fails

                    final_results.append({
                        "@type": schema_type,
                        "url": site["url"],
                        "name": site["name"],
                        "score": ranking["score"],
                        "description": ranking["description"],
                        "api_version": "1.0"  # Add API version number
                    })

            # 5. Sort by score and return top results
            final_results.sort(key=lambda x: x["score"], reverse=True)
            top_results = final_results[:SETTINGS["max_results"]]

            # Log performance metrics
            total_time = time.time() - start_time
            print(f"Query processed in {total_time:.2f}s - Returned {len(top_results)} results")

            # Update statistics
            self.stats["total_sites_ranked"] += len(ranking_tasks)

            return top_results

        except Exception as e:
            print(f"Error processing query: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _rank_site(self, query: str, site: Dict[str, Any], cache_key: Tuple) -> bool:
        """
        Rank a single site and cache the result.

        Args:
            query: The user's query
            site: Site information dictionary
            cache_key: Cache key for storing the ranking

        Returns:
            True if ranking was successful
        """
        try:
            # Get ranking from LLM
            ranking = await self.llm_backend.rank_site(query, site.get("json_ld", "{}"))

            # Cache the result
            self.ranking_cache.set(cache_key, ranking)

            return True

        except Exception as e:
            print(f"Error ranking site {site.get('name', 'Unknown')}: {e}")

            # Cache error result to avoid retrying
            self.ranking_cache.set(cache_key, {
                "score": 0,
                "description": f"Ranking failed: {str(e)[:50]}"
            })

            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics"""
        return {
            **self.stats,
            "embedding_cache_size": len(self.embedding_cache),
            "search_cache_size": self.search_cache.size(),
            "ranking_cache_size": self.ranking_cache.size(),
        }

    async def clear_caches(self):
        """Clear all caches"""
        self.embedding_cache.clear()
        self.search_cache.clear()
        self.ranking_cache.clear()
        print("All caches cleared")

    async def cleanup(self):
        """Cleanup resources"""
        print("Cleaning up WHO Handler...")

        # Cleanup backends
        cleanup_tasks = []
        if self.search_backend:
            cleanup_tasks.append(self.search_backend.close())
        if self.llm_backend:
            cleanup_tasks.append(self.llm_backend.close())

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

        print("WHO Handler cleanup complete")


# Global handler instance
_handler: Optional[WHOHandler] = None


async def get_handler() -> WHOHandler:
    """Get or create the global handler instance"""
    global _handler
    if _handler is None:
        _handler = WHOHandler()
        await _handler.initialize()
    return _handler


async def who_query(query: str) -> List[Dict[str, Any]]:
    """
    Main entry point for WHO queries.

    Args:
        query: The user's question

    Returns:
        List of relevant sites with scores and descriptions
    """
    handler = await get_handler()
    return await handler.process_query(query)


async def get_stats() -> Dict[str, Any]:
    """Get handler statistics"""
    handler = await get_handler()
    return await handler.get_stats()


async def clear_caches():
    """Clear all caches"""
    handler = await get_handler()
    await handler.clear_caches()


async def cleanup():
    """Cleanup resources on shutdown"""
    global _handler
    if _handler:
        await _handler.cleanup()
        _handler = None