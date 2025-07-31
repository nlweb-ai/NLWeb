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

from core.retriever import search
import core.ranking as ranking
from misc.logger.logging_config_helper import get_configured_logger
import asyncio

logger = get_configured_logger("fast_track")


class FastTrack:
    def __init__(self, handler):
        self.handler = handler
        logger.debug("FastTrack initialized")

    def is_fastTrack_eligible(self):
        """Check if query is eligible for fast track processing"""
        # Skip fast track for sites without embeddings
        if "datacommons" in self.handler.site:
            logger.debug("Fast track not eligible: DataCommons site has no embeddings")
            return False
        if (self.handler.context_url != ''):
            logger.debug("Fast track not eligible: context_url present")
            return False
        if (len(self.handler.prev_queries) > 0):
            logger.debug(f"Fast track not eligible: {len(self.handler.prev_queries)} previous queries present")
            return False
        logger.info("Query is eligible for fast track")
        return True
        
    async def do(self):
        """Execute fast track processing"""
        if (not self.is_fastTrack_eligible()):
            logger.info("Fast track processing skipped - not eligible")
            return
        
        logger.info("Starting fast track processing")
        
        self.handler.retrieval_done_event.set()  # Use event instead of flag
        
        try:
            logger.debug(f"Retrieving items for query: {self.handler.query}")
            items = await search(
                self.handler.query, 
                self.handler.site,
                query_params=self.handler.query_params,
                handler=self.handler
            )
            self.handler.final_retrieved_items = items
            logger.info(f"Fast track retrieved {len(items)} items")
            
            # Wait for decontextualization to complete with timeout
            decon_done = False
            try:
                decon_done = await asyncio.wait_for(
                    self.handler.state.wait_for_decontextualization(),
                    timeout=5.0  # 5 second timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Decontextualization timed out in fast track")
                return
            
            if decon_done:
                logger.debug("Decontextualization is done")
                
                # Check all abort conditions using centralized method
                if self.handler.state.abort_fast_track_if_needed():
                    logger.info("Fast track aborted: abort conditions met")
                    return
                elif (not self.handler.query_done and not self.handler.abort_fast_track_event.is_set()):
                    logger.info("Fast track proceeding: decontextualization not required")
                    self.handler.fastTrackRanker = ranking.Ranking(self.handler, items, ranking.Ranking.FAST_TRACK)
                    await self.handler.fastTrackRanker.do()
                    logger.info("Fast track ranking completed")
                    return  
            elif (not self.handler.query_done and not self.handler.abort_fast_track_event.is_set()):
                logger.info("Fast track proceeding: decontextualization call pending, query not done")
                self.handler.fastTrackRanker = ranking.Ranking(self.handler, items, ranking.Ranking.FAST_TRACK)
                await self.handler.fastTrackRanker.do()
                logger.info("Fast track ranking completed")
                return
                
        except Exception as e:
            logger.error(f"Error during fast track processing: {str(e)}")
            logger.debug("Fast track error details:", exc_info=True)
            raise
        
        logger.info("Fast track processing completed")