# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Item Details Handler for extracting details about specific items.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Union
from core.prompts import PromptRunner
from core.prompts import find_prompt, fill_prompt
from misc.logger.logging_config_helper import get_configured_logger
from core.utils.json_utils import trim_json
from core.retriever import search, search_by_url
from core.llm import ask_llm


logger = get_configured_logger("compare_items")

FIND_ITEM_THRESHOLD = 70

class CompareItemsHandler():
    """Handler for finding and extracting details about specific items."""
    
    def __init__(self, params, handler):
        self.handler = handler
        self.params = params
        self.item_name = ""
        self.details_requested = ""
        self.item1_url = ""
        self.item2_url = ""
        self.found_items = {}
    
    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
            self.item1_name = self.params.get('item1_name', '')
            self.item2_name = self.params.get('item2_name', '')
            self.item1_url = self.params.get('item1_url', '')
            self.item2_url = self.params.get('item2_url', '')
            self.details_requested = self.params.get('details_requested', '')

            if not self.item1_name or not self.item2_name:
                logger.warning("Item names not found in tool routing results")
                await self._send_no_items_found_message()
                return

            # Find matching items for both searches in parallel
            # Use URL-based retrieval if URLs are provided, otherwise use vector search
            matching_tasks = [
                self._get_item_by_url(self.item1_url, self.item1_name) if self.item1_url else self._find_matching_items(self.item1_name),
                self._get_item_by_url(self.item2_url, self.item2_name) if self.item2_url else self._find_matching_items(self.item2_name)
            ]
            await asyncio.gather(*matching_tasks)

            if (self.found_items[self.item1_name] and self.found_items[self.item2_name]):
                await self.compare_items(self.found_items[self.item1_name]['item'], 
                                   self.found_items[self.item2_name]['item'],
                                   self.details_requested)
            else:
                logger.warning(f"No items found for {self.item1_name} or {self.item2_name}")
                await self._send_no_items_found_message()
                return
        
        except Exception as e:
            logger.error(f"Error in ItemDetailsHandler.do(): {e}")
            await self._send_no_items_found_message()
            return
    
    async def _find_matching_items(self, item_name):
        """Find items that match the requested item using parallel LLM calls."""

        candidate_items = await search(
            item_name, 
            self.handler.site, 
            num_results=20,
            query_params=self.handler.query_params
        )
        logger.info(f"Searching for item: {item_name}")
        # Create tasks for parallel evaluation
        tasks = []
        for item in candidate_items:
            task = asyncio.create_task(self._evaluate_item_match(item, item_name))
            tasks.append(task)
        
        # Wait for all evaluations to complete
        results = [r for r in await asyncio.gather(*tasks, return_exceptions=True) if r is not None]
        logger.info(f"Found {len(results)} matches for {item_name}")
        if results:
            results.sort(key=lambda x: x["score"], reverse=True)
            self.found_items[item_name] = results[0]

    async def _evaluate_item_match(self, item, item_name):
        """Evaluate if an item matches the requested item."""
        try:
            prompt_str, ans_struc = find_prompt(self.handler.site, self.handler.item_type, "FindItemPrompt")
            if not prompt_str:
                logger.error("FindItemPrompt not found")
                return {"score": 0, "explanation": "Prompt not found"}
            
            description = trim_json(item[1])
            pr_dict = {"item.description": description, "item.name": item_name}
            prompt = fill_prompt(prompt_str, self.handler, pr_dict)
            response = await ask_llm(prompt, ans_struc, level="high", query_params=self.handler.query_params)
            
            if response and "score" in response:
                score = int(response["score"])
                if score > 75:
                    return {"score": score, "item": item}
                else:
                    return None
        except Exception as e:
            logger.error(f"Error evaluating item match: {e}")
            return {"score": 0, "explanation": f"Error: {e}"}
        
    async def compare_items(self, item1, item2, details_requested):
        """Compare the two items and return the results."""
        try:
            if (len(details_requested) > 0):
                prompt_str, ans_struc = find_prompt(self.handler.site, self.handler.item_type, "CompareItemDetailsPrompt")
            else:
                prompt_str, ans_struc = find_prompt(self.handler.site, self.handler.item_type, "CompareItemsPrompt")
            if not prompt_str:
                logger.error("CompareItemsPrompt or CompareItemDetailsPrompt not found")
                return {"score": 0, "explanation": "Prompt not found"}
            desc1 = trim_json(item1[1])
            desc2 = trim_json(item2[1])
            pr_dict = {"request.item1_description": desc1, "request.item2_description": desc2, "request.details_requested": details_requested}
            prompt = fill_prompt(prompt_str, self.handler, pr_dict)
            response = await ask_llm(prompt, ans_struc, level="high", query_params=self.handler.query_params)
       
            if response :
                message = {
                "message_type": "compare_items",
                "comparison" : response.get("comparison", ""),
                "item1": 
                   {"name" : item1[2],
                    "schema_object" : item1[1],
                    "url" : item1[0]
                    },
                "item2" : 
                   {"name" : item2[2],
                    "schema_object" : item2[1],
                    "url" : item2[0]
                    }
            }
            await self.handler.send_message(message)
            return message
      
        except Exception as e:
            logger.error(f"Error evaluating item match: {e}")
            return {"score": 0, "explanation": f"Error: {e}"}

    async def _get_item_by_url(self, item_url, item_name):
        """Get item using URL-based retrieval."""
        try:
            results = await search_by_url(
                item_url,
                query_params=self.handler.query_params
            )
            
            if not results or len(results) == 0:
                logger.warning(f"No item found for URL: {item_url}")
                return None
            
            # Store the item in found_items
            item = results[0]
            self.found_items[item_name] = {"score": 100, "item": item}
            logger.info(f"Retrieved item by URL for: {item_name}")
            
        except Exception as e:
            logger.error(f"Error in _get_item_by_url: {e}")
            # Fall back to vector search if URL retrieval fails
            await self._find_matching_items(item_name)
    
    async def _send_no_items_found_message(self):
        """Send message when items cannot be found for comparison."""
        message = {
            "message_type": "compare_items",
            "comparison": f"Could not find one or both items: '{self.item1_name}' and '{self.item2_name}' on {self.handler.site}.",
            "item1": {"name": self.item1_name, "url": "", "schema_object": {}},
            "item2": {"name": self.item2_name, "url": "", "schema_object": {}}
        }
        await self.handler.send_message(message)


