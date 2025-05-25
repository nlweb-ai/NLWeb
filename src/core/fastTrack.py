# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the code for the 'fast track' path, which assumes that the query is a simple question,
not requiring decontextualization, query is relevant, the query has all the information needed, etc.
Those checks are done in parallel with fast track. Results are sent to the client only after
all those checks are done, which should arrive by the time the results are ready.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from retrieval.retriever import get_vector_db_client
import core.ranking as ranking
from utils.logging_config_helper import get_configured_logger
import asyncio
import time
from functools import lru_cache
from typing import List, Dict, Any, Optional
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor

# Configure logger
logger = get_configured_logger("fast_track")

# Performance metrics
class PerformanceMetrics:
    def __init__(self):
        self.start_time: float = 0
        self.end_time: float = 0
        self.items_processed: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0

    def start_timer(self):
        self.start_time = time.time()

    def stop_timer(self):
        self.end_time = time.time()

    def get_duration(self) -> float:
        return self.end_time - self.start_time if self.end_time > self.start_time else 0

# Cache for query results
@lru_cache(maxsize=1000)
def get_query_cache_key(query: str, site: str) -> str:
    """Generate a cache key for query and site combination."""
    return hashlib.md5(f"{query}_{site}".encode()).hexdigest()


class FastTrack:
    # Constants for configuration
    MAX_CONCURRENT_REQUESTS = 10  # Limit concurrent requests to prevent overload
    CACHE_TTL_SECONDS = 300  # 5 minutes cache TTL
    
    def __init__(self, handler):
        self.handler = handler
        self.metrics = PerformanceMetrics()
        self._cache = {}
        self._cache_lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT_REQUESTS)
        logger.debug("FastTrack initialized")
        
    async def _get_cached_results(self, query: str, site: str) -> Optional[List[Dict]]:
        """Get cached results for a query if available and not expired."""
        cache_key = get_query_cache_key(query, site)
        async with self._cache_lock:
            if cache_key in self._cache:
                cached_time, results = self._cache[cache_key]
                if time.time() - cached_time < self.CACHE_TTL_SECONDS:
                    self.metrics.cache_hits += 1
                    logger.debug(f"Cache hit for query: {query}")
                    return results
                else:
                    # Cache expired, remove it
                    del self._cache[cache_key]
                    self.metrics.cache_misses += 1
            else:
                self.metrics.cache_misses += 1
        return None
    
    async def _cache_results(self, query: str, site: str, results: List[Dict]):
        """Cache the results of a query."""
        cache_key = get_query_cache_key(query, site)
        async with self._cache_lock:
            self._cache[cache_key] = (time.time(), results)
            
    def _log_metrics(self):
        """Log performance metrics."""
        duration = self.metrics.get_duration()
        logger.info(
            f"FastTrack metrics - Duration: {duration:.2f}s, "
            f"Items: {self.metrics.items_processed}, "
            f"Cache hits: {self.metrics.cache_hits}, "
            f"Cache misses: {self.metrics.cache_misses}",
            extra={
                'duration_seconds': duration,
                'items_processed': self.metrics.items_processed,
                'cache_hits': self.metrics.cache_hits,
                'cache_misses': self.metrics.cache_misses
            }
        )

    def is_fastTrack_eligible(self):
        """Check if query is eligible for fast track processing"""
        if (self.handler.context_url != ''):
            logger.debug("Fast track not eligible: context_url present")
            return False
        if (len(self.handler.prev_queries) > 0):
            logger.debug(f"Fast track not eligible: {len(self.handler.prev_queries)} previous queries present")
            return False
        logger.info("Query is eligible for fast track")
        return True
        
    async def _process_items(self, items: List[Dict]) -> List[Dict]:
        """Process items with parallel execution where possible."""
        if not items:
            return []
            
        # Process items in parallel using ThreadPoolExecutor
        loop = asyncio.get_event_loop()
        
        # Process items in batches to avoid overwhelming the system
        batch_size = min(len(items), self.MAX_CONCURRENT_REQUESTS)
        processed_items = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            # Process batch in parallel
            tasks = []
            for item in batch:
                # Convert sync operations to async using run_in_executor
                task = loop.run_in_executor(
                    self._executor,
                    self._process_single_item,
                    item
                )
                tasks.append(task)
                
            # Wait for all tasks in batch to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Error processing item: {str(result)}")
                    continue
                if result:
                    processed_items.append(result)
                    self.metrics.items_processed += 1
        
        return processed_items
    
    def _process_single_item(self, item: Dict) -> Optional[Dict]:
        """Process a single item (runs in thread pool)."""
        try:
            # Add any synchronous processing here
            return item
        except Exception as e:
            logger.error(f"Error processing item: {str(e)}")
            return None
    
    async def _retrieve_items(self) -> List[Dict]:
        """Retrieve items from vector store with caching."""
        # Check cache first
        cached_results = await self._get_cached_results(self.handler.query, self.handler.site)
        if cached_results is not None:
            logger.info(f"Using cached results for query: {self.handler.query}")
            return cached_results
        
        # Not in cache, fetch from vector store
        logger.debug(f"Cache miss, retrieving items for query: {self.handler.query}")
        client = get_vector_db_client(query_params=self.handler.query_params)
        items = await client.search(self.handler.query, self.handler.site, limit=50)  # Add limit
        
        # Cache the results
        if items:
            await self._cache_results(self.handler.query, self.handler.site, items)
            
        return items
    
    async def do(self):
        """Execute fast track processing with optimizations."""
        self.metrics.start_timer()
        
        if not self.is_fastTrack_eligible():
            logger.info("Fast track processing skipped - not eligible")
            return
        
        logger.info("Starting optimized fast track processing")
        
        try:
            # Signal that retrieval has started
            self.handler.retrieval_done_event.set()
            
            # Process items in parallel
            items = await self._retrieve_items()
            self.handler.final_retrieved_items = items
            
            logger.info(f"Fast track retrieved {len(items)} items")
            
            if not items:
                logger.info("No items found, skipping further processing")
                return
            
            # Process items in parallel
            processed_items = await self._process_items(items)
            
            # Wait for decontextualization with timeout
            decon_done = False
            try:
                decon_done = await asyncio.wait_for(
                    self.handler.state.wait_for_decontextualization(),
                    timeout=3.0  # Reduced timeout for faster response
                )
            except asyncio.TimeoutError:
                logger.warning("Decontextualization timed out in fast track")
                return
            
            # Process based on decontextualization status
            if decon_done and self.handler.requires_decontextualization:
                logger.info("Fast track aborted: decontextualization required")
                self.handler.abort_fast_track_event.set()
                return
                
            if not self.handler.query_done and not self.handler.abort_fast_track_event.is_set():
                logger.info("Proceeding with ranking")
                self.handler.fastTrackRanker = ranking.Ranking(
                    self.handler, 
                    processed_items, 
                    ranking.Ranking.FAST_TRACK
                )
                await self.handler.fastTrackRanker.do()
                
        except Exception as e:
            logger.error(
                f"Error during fast track processing: {str(e)}",
                exc_info=True,
                extra={'error_details': str(e), 'traceback': traceback.format_exc()}
            )
            raise
        finally:
            self.metrics.stop_timer()
            self._log_metrics()
            
        logger.info("Fast track processing completed")