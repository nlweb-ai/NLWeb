# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the code for the ranking stage. 

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import json
import time
import hashlib
import traceback
from functools import lru_cache
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from llm.llm import ask_llm
from utils.trim import trim_json
from prompts.prompts import find_prompt, fill_ranking_prompt
from utils.logging_config_helper import get_configured_logger
from utils.utils import log

logger = get_configured_logger("ranking_engine")

# Performance metrics tracking
class RankingMetrics:
    def __init__(self):
        self.start_time: float = 0
        self.end_time: float = 0
        self.items_processed: int = 0
        self.llm_calls: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0

    def start_timer(self):
        self.start_time = time.time()

    def stop_timer(self):
        self.end_time = time.time()

    def get_duration(self) -> float:
        return self.end_time - self.start_time if self.end_time > self.start_time else 0

    def log_metrics(self):
        duration = self.get_duration()
        logger.info(
            f"Ranking metrics - Duration: {duration:.2f}s, "
            f"Items: {self.items_processed}, "
            f"LLM Calls: {self.llm_calls}, "
            f"Cache hits: {self.cache_hits}, "
            f"Cache misses: {self.cache_misses}",
            extra={
                'duration_seconds': duration,
                'items_processed': self.items_processed,
                'llm_calls': self.llm_calls,
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses
            }
        )


class Ranking:
    """
    Handles ranking of search results using LLM-based relevance scoring.
    Implements caching, batching, and parallel processing for performance.
    """
    # Configuration constants
    EARLY_SEND_THRESHOLD = 59
    NUM_RESULTS_TO_SEND = 10
    MAX_CONCURRENT_LLM_REQUESTS = 5  # Limit concurrent LLM requests
    CACHE_TTL_SECONDS = 300  # 5 minutes cache TTL
    
    # Ranking types
    FAST_TRACK = 1
    REGULAR_TRACK = 2
    
    # Cache for storing ranking results
    _ranking_cache = {}
    _cache_lock = asyncio.Lock()

    # This is the default ranking prompt, in case, for some reason, we can't find the site_type.xml file.
    RANKING_PROMPT = ["""  Assign a score between 0 and 100 to the following {site.itemType}
based on how relevant it is to the user's question. Use your knowledge from other sources, about the item, to make a judgement. 
If the score is above 50, provide a short description of the item highlighting the relevance to the user's question, without mentioning the user's question.
Provide an explanation of the relevance of the item to the user's question, without mentioning the user's question or the score or explicitly mentioning the term relevance.
If the score is below 75, in the description, include the reason why it is still relevant.
The user's question is: {request.query}. The item's description is {item.description}""",
    {"score" : "integer between 0 and 100", 
 "description" : "short description of the item"}]
 
    RANKING_PROMPT_NAME = "RankingPrompt"
     
    def get_ranking_prompt(self):
        site = self.handler.site
        item_type = self.handler.item_type
        prompt_str, ans_struc = find_prompt(site, item_type, self.RANKING_PROMPT_NAME)
        if prompt_str is None:
            logger.debug("Using default ranking prompt")
            return self.RANKING_PROMPT[0], self.RANKING_PROMPT[1]
        else:
            logger.debug(f"Using custom ranking prompt for site: {site}, item_type: {item_type}")
            return prompt_str, ans_struc
        
    def __init__(self, handler, items, ranking_type=FAST_TRACK):
        """Initialize the Ranking instance.
        
        Args:
            handler: The request handler instance
            items: List of items to rank
            ranking_type: Type of ranking (FAST_TRACK or REGULAR_TRACK)
        """
        self.metrics = RankingMetrics()
        self.metrics.start_timer()
        
        self.handler = handler
        self.items = items
        self.ranking_type = ranking_type
        self.ranking_type_str = "FAST_TRACK" if ranking_type == self.FAST_TRACK else "REGULAR_TRACK"
        
        # Initialize state
        self.num_results_sent = 0
        self.rankedAnswers = []
        self._results_lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT_LLM_REQUESTS)
        
        logger.info(
            f"Initializing Ranking with {len(items)} items, type: {self.ranking_type_str}",
            extra={'item_count': len(items), 'ranking_type': self.ranking_type_str}
        )

    def _generate_cache_key(self, prompt: str, description: str) -> str:
        """Generate a cache key for the ranking request."""
        key_str = f"{prompt}:{description}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def _get_cached_ranking(self, cache_key: str) -> Optional[Dict]:
        """Get a cached ranking result if available and not expired."""
        async with self._cache_lock:
            if cache_key in self._ranking_cache:
                cached_time, result = self._ranking_cache[cache_key]
                if time.time() - cached_time < self.CACHE_TTL_SECONDS:
                    self.metrics.cache_hits += 1
                    return result
                else:
                    # Cache expired, remove it
                    del self._ranking_cache[cache_key]
            self.metrics.cache_misses += 1
        return None
    
    async def _cache_ranking(self, cache_key: str, result: Dict):
        """Cache a ranking result."""
        async with self._cache_lock:
            self._ranking_cache[cache_key] = (time.time(), result)
    
    async def rankItem(self, url: str, json_str: str, name: str, site: str) -> Optional[Dict]:
        """Rank a single item using LLM with caching and error handling.
        
        Args:
            url: Item URL
            json_str: Item data as JSON string
            name: Item name
            site: Site identifier
            
        Returns:
            Dictionary with ranking result or None if ranking failed
        """
        # Check if we should continue processing
        if not self.handler.connection_alive_event.is_set():
            logger.warning("Connection lost, skipping item ranking")
            return None
            
        if self.ranking_type == self.FAST_TRACK and self.handler.abort_fast_track_event.is_set():
            logger.info("Fast track aborted, skipping item ranking")
            return None
        
        try:
            # Prepare prompt and check cache
            prompt_str, ans_struc = self.get_ranking_prompt()
            description = trim_json(json_str)
            prompt = fill_ranking_prompt(prompt_str, self.handler, description)
            cache_key = self._generate_cache_key(prompt, description)
            
            # Try to get from cache first
            cached_ranking = await self._get_cached_ranking(cache_key)
            if cached_ranking is not None:
                logger.debug(f"Cache hit for item: {name}")
                ranking = cached_ranking
            else:
                # Not in cache, call LLM
                logger.debug(f"Cache miss, ranking item: {name} from {site}")
                self.metrics.llm_calls += 1
                ranking = await ask_llm(prompt, ans_struc, level="low")
                
                # Cache the result if successful
                if ranking and 'score' in ranking:
                    await self._cache_ranking(cache_key, ranking)
            
            # Prepare the answer object
            ansr = {
                'url': url,
                'site': site,
                'name': name,
                'ranking': ranking,
                'schema_object': json.loads(json_str),
                'sent': False,
            }
            
            # Send high-scoring items immediately
            if ranking.get('score', 0) > self.EARLY_SEND_THRESHOLD:
                logger.info(
                    f"High score item: {name} (score: {ranking['score']}) - "
                    f"sending early {self.ranking_type_str}",
                    extra={
                        'item_name': name,
                        'score': ranking['score'],
                        'ranking_type': self.ranking_type_str
                    }
                )
                try:
                    await self.sendAnswers([ansr])
                except (BrokenPipeError, ConnectionResetError) as e:
                    logger.warning(
                        f"Client disconnected while sending early answer for {name}",
                        exc_info=True,
                        extra={'error': str(e), 'item_name': name}
                    )
                    self.handler.connection_alive_event.clear()
                    return None
            
            self.metrics.items_processed += 1
            return ansr
            
        except Exception as e:
            logger.error(
                f"Error ranking item {name}: {str(e)}",
                exc_info=True,
                extra={
                    'item_name': name,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }
            )
            return None
            
            async with self._results_lock:  # Use lock when modifying shared state
                self.rankedAnswers.append(ansr)
            logger.debug(f"Item {name} added to ranked answers")
        
        except Exception as e:
            logger.error(f"Error in rankItem for {name}: {str(e)}")
            logger.debug(f"Full error trace: ", exc_info=True)
            print(f"Error in rankItem for {name}: {str(e)}")

    def shouldSend(self, result):
        should_send = False
        if (self.num_results_sent < self.NUM_RESULTS_TO_SEND - 5):
            should_send = True
        else:
            for r in self.rankedAnswers:
                if r["sent"] == True and r["ranking"]["score"] < result["ranking"]["score"]:
                    should_send = True
                    break
        
        logger.debug(f"Should send result {result['name']}? {should_send} (sent: {self.num_results_sent})")
        return should_send
    
    async def sendAnswers(self, answers, force=False):
        if not self.handler.connection_alive_event.is_set():
            logger.warning("Connection lost during ranking, skipping sending results")
            print("Connection lost during ranking, skipping sending results")
            return
        
        if (self.ranking_type == Ranking.FAST_TRACK and self.handler.abort_fast_track_event.is_set()):
            logger.info("Fast track aborted, not sending answers")
            return
              
        json_results = []
        logger.debug(f"Considering sending {len(answers)} answers (force: {force})")
        
        for result in answers:
            if self.shouldSend(result) or force:
                json_results.append({
                    "url": result["url"],
                    "name": result["name"],
                    "site": result["site"],
                    "siteUrl": result["site"],
                    "score": result["ranking"]["score"],
                    "description": result["ranking"]["description"],
                    "schema_object": result["schema_object"],
                })
                
                result["sent"] = True
            
        if (json_results):  # Only attempt to send if there are results
            # Wait for pre checks to be done using event
            await self.handler.pre_checks_done_event.wait()
            
            # if we got here, prechecks are done. check once again for fast track abort
            if (self.ranking_type == Ranking.FAST_TRACK and self.handler.abort_fast_track_event.is_set()):
                logger.info("Fast track aborted after pre-checks")
                return
            
            try:
                if (self.ranking_type == Ranking.FAST_TRACK):
                    self.handler.fastTrackWorked = True
                    logger.info("Fast track ranking successful")
                
                to_send = {"message_type": "result_batch", "results": json_results, "query_id": self.handler.query_id}
                await self.handler.send_message(to_send)
                self.num_results_sent += len(json_results)
                logger.info(f"Sent {len(json_results)} results, total sent: {self.num_results_sent}")
            except (BrokenPipeError, ConnectionResetError) as e:
                logger.error(f"Client disconnected while sending answers: {str(e)}")
                log(f"Client disconnected while sending answers: {str(e)}")
                self.handler.connection_alive_event.clear()
            except Exception as e:
                logger.error(f"Error sending answers: {str(e)}")
                log(f"Error sending answers: {str(e)}")
                self.handler.connection_alive_event.clear()
  
    async def sendMessageOnSitesBeingAsked(self, top_embeddings):
        if (self.handler.site == "all" or self.handler.site == "nlws"):
            sites_in_embeddings = {}
            for url, json_str, name, site in top_embeddings:
                sites_in_embeddings[site] = sites_in_embeddings.get(site, 0) + 1
            
            top_sites = sorted(sites_in_embeddings.items(), key=lambda x: x[1], reverse=True)[:3]
            top_sites_str = ", ".join([self.prettyPrintSite(x[0]) for x in top_sites])
            message = {"message_type": "asking_sites",  "message": "Asking " + top_sites_str}
            
            logger.info(f"Sending sites message: {top_sites_str}")
            
            try:
                await self.handler.send_message(message)
                self.handler.sites_in_embeddings_sent = True
            except (BrokenPipeError, ConnectionResetError):
                logger.warning("Client disconnected when sending sites message")
                print("Client disconnected when sending sites message")
                self.handler.connection_alive_event.clear()
    
    async def _process_batch(self, batch: List[Tuple]) -> List[Dict]:
        """Process a batch of items in parallel.
        
        Args:
            batch: List of (url, json_str, name, site) tuples
            
        Returns:
            List of successfully processed items
        """
        tasks = []
        for item in batch:
            if not self.handler.connection_alive_event.is_set():
                logger.warning("Connection lost during batch processing")
                break
                
            if (self.ranking_type == self.FAST_TRACK and 
                self.handler.abort_fast_track_event.is_set()):
                logger.info("Fast track aborted during batch processing")
                break
                
            url, json_str, name, site = item
            task = asyncio.create_task(self.rankItem(url, json_str, name, site))
            tasks.append(task)
        
        # Process batch results
        results = []
        if tasks:
            try:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Error in batch processing: {str(result)}")
                    elif result is not None:
                        results.append(result)
            except Exception as e:
                logger.error(f"Error in batch processing: {str(e)}", exc_info=True)
        
        return results
    
    async def _process_all_batches(self):
        """Process all items in parallel batches."""
        if not self.items:
            logger.info("No items to process")
            return []
            
        batch_size = min(len(self.items), self.MAX_CONCURRENT_LLM_REQUESTS * 2)
        all_results = []
        
        for i in range(0, len(self.items), batch_size):
            if not self.handler.connection_alive_event.is_set():
                logger.warning("Connection lost, stopping batch processing")
                break
                
            batch = self.items[i:i + batch_size]
            logger.debug(f"Processing batch {i//batch_size + 1}/{(len(self.items)-1)//batch_size + 1} "
                         f"with {len(batch)} items")
            
            batch_results = await self._process_batch(batch)
            all_results.extend(batch_results)
            
            # Update ranked answers with new results
            if batch_results:
                async with self._results_lock:
                    self.rankedAnswers.extend(batch_results)
                    # Keep only top N results in memory if needed
                    if len(self.rankedAnswers) > self.NUM_RESULTS_TO_SEND * 2:
                        self.rankedAnswers.sort(
                            key=lambda x: x['ranking'].get('score', 0), 
                            reverse=True
                        )
                        self.rankedAnswers = self.rankedAnswers[:self.NUM_RESULTS_TO_SEND]
        
        return all_results
    
    async def _send_final_results(self):
        """Send final ranked results to the client."""
        if not self.handler.connection_alive_event.is_set():
            logger.warning("Connection lost, skipping final results")
            return
            
        # Wait for pre-checks to complete
        await self.handler.pre_checks_done_event.wait()
        
        if (self.ranking_type == self.FAST_TRACK and 
            self.handler.abort_fast_track_event.is_set()):
            logger.info("Fast track aborted after ranking")
            return
        
        # Filter and sort results
        filtered = [r for r in self.rankedAnswers if r['ranking'].get('score', 0) > 51]
        filtered.sort(key=lambda x: x['ranking'].get('score', 0), reverse=True)
        
        # Update final ranked answers in handler
        self.handler.final_ranked_answers = filtered[:self.NUM_RESULTS_TO_SEND]
        
        # Log results
        logger.info(f"Filtered to {len(filtered)} results with score > 51")
        if filtered:
            logger.debug(
                f"Top 3 results: {[(r['name'], r['ranking'].get('score', 0)) for r in filtered[:3]]}",
                extra={'top_scores': [r['ranking'].get('score', 0) for r in filtered[:3]]}
            )
        
        # Send remaining unsent results
        unsent_results = [r for r in filtered if not r.get('sent', False)]
        if not unsent_results or self.num_results_sent >= self.NUM_RESULTS_TO_SEND:
            logger.info(f"No new results to send (already sent {self.num_results_sent})")
            return
        
        # Calculate how many more results we can send
        remaining = max(0, self.NUM_RESULTS_TO_SEND - self.num_results_sent)
        to_send = unsent_results[:remaining]
        
        try:
            logger.info(f"Sending final batch of {len(to_send)} results")
            await self.sendAnswers(to_send, force=True)
        except (BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"Client disconnected during final answer sending: {str(e)}")
            self.handler.connection_alive_event.clear()
    
    async def do(self):
        """Main entry point for the ranking process."""
        logger.info(f"Starting ranking process with {len(self.items)} items")
        
        try:
            # Notify about sites being asked
            await self.sendMessageOnSitesBeingAsked(self.items)
            
            # Process all items in parallel batches
            await self._process_all_batches()
            
            # Send final results
            await self._send_final_results()
            
        except Exception as e:
            logger.error(f"Error in ranking process: {str(e)}", exc_info=True)
            if not self.handler.connection_alive_event.is_set():
                logger.warning("Connection lost during ranking")
            else:
                # Only log the error if the connection is still alive
                logger.error(f"Unexpected error in ranking process: {str(e)}", exc_info=True)
                
        finally:
            # Ensure metrics are logged even if an error occurs
            self.metrics.stop_timer()
            self.metrics.log_metrics()
            logger.info("Ranking process completed")

    def prettyPrintSite(self, site):
        ans = site.replace("_", " ")
        words = ans.split()
        return ' '.join(word.capitalize() for word in words)
