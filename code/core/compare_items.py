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
from prompts.prompts import find_prompt, fill_prompt
from utils.logging_config_helper import get_configured_logger
from utils.json_utils import trim_json
from retrieval.retriever import get_vector_db_client
from llm.llm import ask_llm


logger = get_configured_logger("compare_items")

FIND_ITEM_THRESHOLD = 70

class CompareItemsHandler():
    """Handler for finding and extracting details about specific items."""
    
    def __init__(self, params, handler):
        self.handler = handler
        self.params = params
        self.item_name = ""
        self.details_requested = ""
        self.found_items = {}
    
    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
            print(f"Comparing items: {self.params}")
            self.item1_name = self.params.get('item1', '')
            self.item2_name = self.params.get('item2', '')
            self.details_requested = self.params.get('details_requested', '')

            if not self.item1_name or not self.item2_name:
                logger.warning("Item names not found in tool routing results")
                print(f"No items found for {self.item1_name} or {self.item2_name}")
                await self._send_no_items_found_message()
                return

            # Find matching items for both searches in parallel
            matching_tasks = [
                self._find_matching_items(self.item1_name),
                self._find_matching_items(self.item2_name)
            ]
            await asyncio.gather(*matching_tasks)

            if (self.found_items[self.item1_name] and self.found_items[self.item2_name]):
                await self.compare_items(self.found_items[self.item1_name]['item'], 
                                   self.found_items[self.item2_name]['item'],
                                   self.details_requested)
            else:
                print(f"No items found for {self.item1_name} or {self.item2_name}")
                await self._send_no_items_found_message()
                return
        
        except Exception as e:
            logger.error(f"Error in ItemDetailsHandler.do(): {e}")
            await self._send_no_items_found_message()
            return
    
    async def _find_matching_items(self, item_name):
        """Find items that match the requested item using parallel LLM calls."""

        client = get_vector_db_client(query_params=self.handler.query_params)   
        candidate_items = await client.search(item_name, self.handler.site, num_results=20)
        print(f"{item_name}")
        # Create tasks for parallel evaluation
        tasks = []
        for item in candidate_items:
            task = asyncio.create_task(self._evaluate_item_match(item, item_name))
            tasks.append(task)
        
        # Wait for all evaluations to complete
        results = [r for r in await asyncio.gather(*tasks, return_exceptions=True) if r is not None]
        print(f"Results: {len(results)} {item_name}")
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
            response = await ask_llm(prompt, ans_struc, level="high")
            
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
        #    print(f"Prompt: {prompt}")
            response = await ask_llm(prompt, ans_struc, level="high")
       
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
         #   print(f"Message: {message}")
            await self.handler.send_message(message)
            return message
      
        except Exception as e:
            logger.error(f"Error evaluating item match: {e}")
            return {"score": 0, "explanation": f"Error: {e}"}


