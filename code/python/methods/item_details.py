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
from core.prompts import find_prompt, fill_prompt
from misc.logger.logging_config_helper import get_configured_logger
from core.utils.json_utils import trim_json
from core.retriever import search, search_by_url
from core.llm import ask_llm


logger = get_configured_logger("item_details")

FIND_ITEM_THRESHOLD = 70


class ItemDetailsHandler():
    """Handler for finding and extracting details about specific items."""
    
    def __init__(self, params, handler):
        self.handler = handler
        self.params = params
        self.item_name = ""
        self.details_requested = ""
        self.item_url = ""
        self.found_items = []
        self.sent_message = False
    
    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
            self.item_name = self.params.get('item_name', '')
            self.details_requested = self.params.get('details_requested', '')
            self.item_url = self.params.get('item_url', '')
            
            if not self.details_requested:
                logger.warning("No details requested found in tool routing results")
                await self._send_no_items_found_message()
                return
            
            # If item_url is provided, use direct URL retrieval
            if self.item_url:
                logger.info(f"Using URL-based retrieval for: {self.item_url}")
                await self._get_item_by_url()
            else:
                # Otherwise use vector search
                if not self.item_name:
                    logger.warning("No item name found in tool routing results")
                    await self._send_no_items_found_message()
                    return
                
                logger.info(f"Using vector search for item: {self.item_name}")
                
                # Send intermediate message
                await self.handler.send_message({
                    "message_type": "intermediate_message",
                    "message": f"Searching for {self.item_name}"
                })
                candidate_items = await search(
                    self.item_name, 
                    self.handler.site,
                    query_params=self.handler.query_params
                )
                
                await self._find_matching_items(candidate_items, self.details_requested)
            
                if not self.found_items:
                    logger.warning(f"No matching items found for: {self.item_name}")
                    await self._send_no_items_found_message()
                    return
        except Exception as e:
            logger.error(f"Error in ItemDetailsHandler.do(): {e}")
            await self._send_no_items_found_message()
            return
    
    async def _find_matching_items(self, candidate_items: List[Dict[str, Any]], details_requested: str):
        """Find items that match the requested item using parallel LLM calls."""
        logger.info(f"Evaluating {len(candidate_items)} candidate items for '{self.item_name} {details_requested}'")

        # Create tasks for parallel evaluation
        tasks = []
        for item in candidate_items:
            task = asyncio.create_task(self._evaluate_item_match(item, details_requested))
            tasks.append(task)
        
        # Wait for all evaluations to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        if (self.sent_message):
            return
        else:
            self.found_items.sort(key=lambda x: x.get("score", 0), reverse=True)
            await self.handler.send_message(self.found_items[0])
            self.sent_message = True
    
    async def _evaluate_item_match(self, item: Dict[str, Any], details_requested: str) -> Optional[Dict[str, Any]]:
        """Evaluate if an item matches the requested item.
        If the score is above 75, also extract the details that the user is looking for."""
        try:
            # Extract components like ranking.py does
            if isinstance(item, list) and len(item) >= 4:
                # Item format: [url, json_str, name, site]
                url, json_str, name, site = item[0], item[1], item[2], item[3]
            
            # Use the same description method as ranking.py
            description = trim_json(json_str)
            
            # Set handler attributes for prompt filling
            self.handler.item_name = self.item_name
            
            # Get the prompt template and structure
            prompt_str, ans_struc = find_prompt(self.handler.site, self.handler.item_type, "ItemMatchingPrompt")
            if not prompt_str:
                logger.error("ItemMatchingPrompt not found")
                return {"score": 0, "explanation": "Prompt not found"}
            
            # Fill the prompt using the ranking prompt pattern (same as ranking.py)

            pr_dict = {"item.description": description, "request.details_requested": details_requested}
            prompt = fill_prompt(prompt_str, self.handler, pr_dict)
            
            response = await ask_llm(prompt, ans_struc, level="high", query_params=self.handler.query_params)
            if response and "score" in response:
                score = int(response.get("score", 0))
                explanation = response.get("explanation", "")
                
                # If score is above 75 and item_details are available, send message directly\
                if score > 59:
                    message = {
                        "message_type": "item_details",
                        "name": name,  # Use the actual recipe name, not the search term
                        "details": response["item_details"],
                        "score": score,
                        "explanation": explanation,
                        "url": url,
                        "site": site,
                        "schema_object": json.loads(json_str)
                    }
                else:
                    return
                if score > 75:
                    await self.handler.send_message(message)
                    logger.info(f"Sent item details for: {self.item_name}")
                    self.sent_message = True
                    # Add to found_items to prevent "not found" message
                self.found_items.append(message)
                
            else:
                logger.warning("No valid response from ItemMatchingPrompt")
                return {"score": 0, "explanation": "No response from LLM"}
                
        except Exception as e:
            logger.error(f"Error evaluating item match: {e}")
            return {"score": 0, "explanation": f"Error: {str(e)}"}
    

    async def _get_item_by_url(self):
        """Get item details using URL-based retrieval."""
        try:
            results = await search_by_url(
                self.item_url,
                query_params=self.handler.query_params
            )
            
            if not results or len(results) == 0:
                logger.warning(f"No item found for URL: {self.item_url}")
                await self._send_no_items_found_message()
                return
            
            # Extract the item from search results
            item = results[0]
            if isinstance(item, list) and len(item) >= 4:
                url, json_str, name, site = item[0], item[1], item[2], item[3]
                
                # Use ExtractItemDetailsPrompt to extract the requested details
                prompt_str, ans_struc = find_prompt(self.handler.site, self.handler.item_type, "ExtractItemDetailsPrompt")
                if not prompt_str:
                    logger.error("ExtractItemDetailsPrompt not found")
                    # Fallback to sending the whole schema
                    message = {
                        "message_type": "item_details",
                        "name": name,
                        "details": trim_json(json_str),
                        "url": url,
                        "site": site,
                        "schema_object": json.loads(json_str)
                    }
                    await self.handler.send_message(message)
                    return
                
                # Fill the prompt with item description and details requested
                pr_dict = {
                    "item.description": trim_json(json_str),
                    "request.details_requested": self.details_requested,
                    "request.query": self.handler.query
                }
                prompt = fill_prompt(prompt_str, self.handler, pr_dict)
                
                response = await ask_llm(prompt, ans_struc, level="high", query_params=self.handler.query_params)
                if response:
                    message = {
                        "message_type": "item_details",
                        "name": response.get("item_name", name),
                        "details": response.get("requested_details", "Details not found"),
                        "additional_context": response.get("additional_context", ""),
                        "url": url,
                        "site": site,
                        "schema_object": json.loads(json_str)
                    }
                    await self.handler.send_message(message)
                    logger.info(f"Sent item details for URL: {self.item_url}")
                else:
                    logger.error("No response from ExtractItemDetailsPrompt")
                    await self._send_no_items_found_message()
            else:
                logger.error(f"Invalid item format from search_by_url: {item}")
                await self._send_no_items_found_message()
                
        except Exception as e:
            logger.error(f"Error in _get_item_by_url: {e}")
            await self._send_no_items_found_message()

    async def _send_no_items_found_message(self):
        """Send message when no matching items are found."""
        message = {
            "message_type": "item_details",
            "item_name": self.item_name,
            "details": f"Could not find any items matching '{self.item_name}' on {self.handler.site}.",
            "score": 0,
            "url": "",
            "site": self.handler.site
        }
        
        await self.handler.send_message(message)
