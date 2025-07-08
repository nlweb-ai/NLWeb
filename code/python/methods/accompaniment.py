# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Accompaniment Handler for finding items that complement or pair well with a main item.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from core.prompts import find_prompt, fill_prompt
from misc.logger.logging_config_helper import get_configured_logger
from core.retriever import get_vector_db_client
from core.ranking import Ranking

logger = get_configured_logger("accompaniment")


class AccompanimentHandler():
    """Handler for finding accompaniments, pairings, or complementary items."""
    
    def __init__(self, params, handler):
        self.handler = handler
        self.params = params
        self.search_query = params.get('search_query', '')
        self.main_item = params.get('main_item', '')
        
    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
            
            if not self.search_query:
                logger.warning("No search query found in tool routing results")
                await self._send_no_results_message()
                return
                
            # Step 1: Retrieve items using the decontextualized query
            logger.info(f"Searching for '{self.search_query}' as accompaniment for '{self.main_item}'")
            
            client = get_vector_db_client(query_params=self.handler.query_params)
            candidate_items = await client.search(self.search_query, self.handler.site)
            
            
            if not candidate_items:
                logger.warning(f"No items found for search query: {self.search_query}")
                await self._send_no_results_message()
                return
            
            # Step 2: Update the handler's query to include the context for ranking
            # Store original query
            original_query = self.handler.query
            
            # Set the query to include pairing context for ranking
            contextualized_query = f"{self.search_query} that would go well with {self.main_item}"
            self.handler.query = contextualized_query
            
            
            # Step 3: Use the Ranking class to rank items with the contextualized query
            logger.info(f"Ranking {len(candidate_items)} items for pairing compatibility")
            
            ranking = Ranking(self.handler, candidate_items, ranking_type=Ranking.REGULAR_TRACK)
            await ranking.do()
            
            
            # Restore original query
            self.handler.query = original_query
            
        except Exception as e:
            logger.error(f"Error in AccompanimentHandler.do(): {e}")
            await self._send_no_results_message()
            
    async def _send_no_results_message(self):
        """Send message when no matching accompaniments are found."""
        message = {
            "message_type": "no_results",
            "message": f"Could not find any {self.search_query} that would pair well with {self.main_item}."
        }
        
        await self.handler.send_message(message)