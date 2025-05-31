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
from prompts.prompts import find_prompt, fill_ranking_prompt
from utils.logging_config_helper import get_configured_logger
from utils.trim import trim_json

logger = get_configured_logger("item_details")

FIND_ITEM_THRESHOLD = 70

class ItemDetailsHandler(PromptRunner):
    """Handler for finding and extracting details about specific items."""
    
    def __init__(self, handler):
        super().__init__(handler)
        self.handler = handler
        self.item_name = ""
        self.details_requested = ""
        self.found_items = []
    
    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
            logger.info("Starting item details handler")
            
            # Get the item name and details requested from tool routing results
            if not hasattr(self.handler, 'tool_routing_results') or not self.handler.tool_routing_results:
                logger.warning("No tool routing results available")
                return
            
            logger.debug(f"Tool routing results found: {self.handler.tool_routing_results.keys()}")
            
            top_tool = self.handler.tool_routing_results.get('top_tool')
            if not top_tool:
                logger.warning("No top tool found")
                return
                
            logger.debug(f"Top tool: {top_tool.tool.name}")
            extracted_params = top_tool.extracted_params if top_tool else {}
            logger.debug(f"Extracted params: {extracted_params}")
            
            item_name = extracted_params.get('item_name', '')
            if not item_name:
                logger.warning("No item name found in tool routing results")
                await self._send_no_items_found_message()
                return
            
            # Use the full query - let the LLM determine what details to extract
            details_requested = self.handler.query
            logger.debug(f"Processing query: '{details_requested}' for item: '{item_name}'")
            
            await self.handle_item_details_query(item_name, details_requested)
            
            logger.info("Item details handler completed")
            
        except Exception as e:
            logger.exception(f"Error in ItemDetailsHandler.do(): {e}")
            await self._send_no_items_found_message()
        
    async def handle_item_details_query(self, item_name: str, details_requested: str = ""):
        """
        Main method to handle item details queries.
        
        Args:
            item_name: The name of the item to find details for
            details_requested: Specific details being requested by the user
        """
        logger.info(f"Starting item details search for: {item_name}")
        
        self.item_name = item_name
        self.details_requested = details_requested
        
        # Get candidate items from fast track or retrieval
        candidate_items = await self._get_candidate_items()
        logger.debug(f"Got {len(candidate_items)} candidate items")
        
        if not candidate_items:
            logger.warning(f"No candidate items found for: {item_name}")
            await self._send_no_items_found_message()
            return
        
        # Find matching items in parallel
        await self._find_matching_items(candidate_items)
        
        if not self.found_items:
            logger.warning(f"No matching items found for: {item_name}")
            await self._send_no_items_found_message()
            return
        
        # Extract details for found items in parallel
        await self._extract_item_details()
    
    async def _get_candidate_items(self):
        """Get candidate items from fast track results or vector database."""
        try:
            # First try to use fast track results if available
            if hasattr(self.handler, 'fast_track_results') and self.handler.fast_track_results:
                logger.debug(f"Using fast track results: {len(self.handler.fast_track_results)} items")
                return self.handler.fast_track_results
            
            # Try to get from vector database if available
            if hasattr(self.handler, 'vector_db_client') and self.handler.vector_db_client:
                # Use the item name as search query
                results = await self.handler.vector_db_client.search(
                    query=self.item_name,
                    top_k=20,  # Get more candidates for better matching
                    site=self.handler.site
                )
                logger.debug(f"Vector DB search returned {len(results)} results")
                return results
            else:
                # Fallback to use final_retrieved_items if available
                if hasattr(self.handler, 'final_retrieved_items') and self.handler.final_retrieved_items:
                    logger.debug(f"Using final_retrieved_items: {len(self.handler.final_retrieved_items)} items")
                    return self.handler.final_retrieved_items
                else:
                    logger.warning("No vector database client or final_retrieved_items available")
                    return []
        except Exception as e:
            logger.error(f"Error retrieving candidate items: {e}")
            return []
    
    async def _find_matching_items(self, candidate_items: List[Dict[str, Any]]):
        """Find items that match the requested item using parallel LLM calls."""
        logger.info(f"Evaluating {len(candidate_items)} candidate items for '{self.item_name}'")
        
        # Create tasks for parallel evaluation
        tasks = []
        for item in candidate_items:
            task = asyncio.create_task(self._evaluate_item_match(item))
            tasks.append(task)
        
        # Wait for all evaluations to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and collect matching items
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error evaluating item {i}: {result}")
                continue
            
            if result and result.get("score", 0) >= FIND_ITEM_THRESHOLD:
                # Create a wrapper object like ranking.py does, preserving JSON data
                original_item = candidate_items[i]
                url, json_str, name, site = original_item[0], original_item[1], original_item[2], original_item[3]
                item_data = {
                    "url": url,
                    "site": site,
                    "name": name,
                    "json_str": json_str,  # Preserve the JSON string like ranking.py
                    "schema_object": json.loads(json_str),  # Parse JSON like ranking.py
                    "match_score": result["score"],
                    "match_explanation": result.get("explanation", "")
                }
                self.found_items.append(item_data)
        
        # Sort by match score descending and keep only top 5
        self.found_items.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        self.found_items = self.found_items[:5]  # Keep only top 5 items
        
        logger.info(f"Found {len(self.found_items)} matching items above threshold {FIND_ITEM_THRESHOLD} (limited to top 5)")
    
    async def _evaluate_item_match(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Evaluate if an item matches the requested item."""
        try:
            # Extract components like ranking.py does
            if isinstance(item, list) and len(item) >= 4:
                # Item format: [url, json_str, name, site]
                url, json_str, name, site = item[0], item[1], item[2], item[3]
            else:
                logger.error(f"Unexpected item format: {item}")
                return {"score": 0, "explanation": "Unexpected item format"}
            
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
            prompt = fill_ranking_prompt(prompt_str, self.handler, description)
            
            # Run the LLM request directly
            from llm.llm import ask_llm
            response = await ask_llm(prompt, ans_struc, level="low")
            
            logger.debug(f"Item matching response for '{self.item_name}': {response}")
            
            if response and "score" in response:
                return {
                    "score": int(response.get("score", 0)),
                    "explanation": response.get("explanation", "")
                }
            else:
                logger.warning("No valid response from ItemMatchingPrompt")
                return {"score": 0, "explanation": "No response from LLM"}
                
        except Exception as e:
            logger.error(f"Error evaluating item match: {e}")
            return {"score": 0, "explanation": f"Error: {str(e)}"}
    
    async def _extract_item_details(self):
        """Extract requested details from found items in parallel."""
        logger.info(f"Extracting details for {len(self.found_items)} items")
        
        # Create tasks for parallel detail extraction
        tasks = []
        for item in self.found_items:
            task = asyncio.create_task(self._extract_single_item_details(item))
            tasks.append(task)
        
        # Wait for all extractions to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Send results to client
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error extracting details for item {i}: {result}")
                continue
            
            if result:
                await self._send_item_details_message(result, self.found_items[i])
    
    async def _extract_single_item_details(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract details for a single item."""
        try:
            # Use the same description method as ranking.py
            description = trim_json(item["json_str"])
            
            # Set handler attributes for prompt filling
            self.handler.details_requested = self.details_requested
            
            # Get the prompt template and structure
            prompt_str, ans_struc = find_prompt(self.handler.site, self.handler.item_type, "ItemDetailsExtractionPrompt")
            if not prompt_str:
                logger.error("ItemDetailsExtractionPrompt not found")
                return None
            
            # Fill the prompt using the ranking prompt pattern
            prompt = fill_ranking_prompt(prompt_str, self.handler, description)
            
            # Run the LLM request directly
            from llm.llm import ask_llm
            response = await ask_llm(prompt, ans_struc, level="low")
            
            logger.debug(f"Item details response: {response}")
            
            # Handle both "details" and "item_details" keys from LLM response
            if response and ("details" in response or "item_details" in response):
                details = response.get("details") or response.get("item_details")
                return {
                    "details": details
                }
            else:
                logger.warning("No valid response from ItemDetailsExtractionPrompt")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting item details: {e}")
            return None
    
    async def _send_item_details_message(self, result: Dict[str, Any], item: Any):
        """Send item details message to the client."""
        # Use the new data structure format that matches ranking.py
        url = item.get("url", "")
        site = item.get("site", self.handler.site)
        match_score = item.get("match_score", 0)
        match_explanation = item.get("match_explanation", "")
        
        message = {
            "message_type": "item_details",
            "item_name": self.item_name,
            "details": result["details"],
            "match_score": match_score,
            "match_explanation": match_explanation,
            "url": url,
            "site": site,
            "schema_object": item.get("schema_object", {})
        }
        
        
        await self.handler.send_message(message)
        logger.info(f"Sent item details for: {self.item_name}")
    
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