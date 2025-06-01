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
from prompts.prompt_runner import PromptRunner
from prompts.prompts import find_prompt, fill_item_details_prompt
from utils.logging_config_helper import get_configured_logger
from utils.trim import trim_json
from retrieval.retriever import get_vector_db_client
from llm.llm import ask_llm


logger = get_configured_logger("item_details")

FIND_ITEM_THRESHOLD = 70

class ItemDetailsHandler(PromptRunner):
    """Handler for finding and extracting details about specific items."""
    
    def __init__(self, params, handler):
        super().__init__(handler)
        self.handler = handler
        self.params = params
        self.item_name = ""
        self.details_requested = ""
        self.found_items = []
    
    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
           
            self.item_name = self.params.get('item_name', '')
            self.details_requested = self.params.get('details_requested', '')
            if not self.item_name or not self.details_requested:
                logger.warning("No item name found in tool routing results")
                await self._send_no_items_found_message()
                return
         
            client = get_vector_db_client(query_params=self.handler.query_params)
            candidate_items = await client.search(self.item_name, self.handler.site)
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
        print(f"Evaluating {len(candidate_items)} candidate items for '{self.item_name} {details_requested}'")

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
            prompt = fill_item_details_prompt(prompt_str, self.handler, description, details_requested)
            
            response = await ask_llm(prompt, ans_struc, level="high")
            if response and "score" in response:
                score = int(response.get("score", 0))
                explanation = response.get("explanation", "")
                
                # If score is above 75 and item_details are available, send message directly\
                if score > 59:
                    message = {
                        "message_type": "item_details",
                        "name": self.item_name,
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
    
    
    
    async def _send_no_items_found_message(self):
        """Send message when no matching items are found."""
        message = {
            "message_type": "item_details",
            "item_name": self.item_name,
            "details": f"Could not find any items matching '{self.item_name}' on {self.handler.site}.",
            "match_score": 0,
            "url": "",
            "site": self.handler.site
        }
        
        await self.handler.send_message(message)