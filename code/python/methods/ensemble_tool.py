import asyncio
import json
from typing import List, Dict, Any, Optional
from core.retriever import search
from core.utils.trim import trim_json_hard
from core.llm import ask_llm
from core.prompts import find_prompt, fill_prompt
import logging

logger = logging.getLogger(__name__)

# Total number of results to send for ensemble building
NUM_RESULTS_FOR_ENSEMBLE_BUILDING = 9
AGGREGATION_CALL_TIMEOUT = 60

class EnsembleToolHandler:
    """
    Handles ensemble requests where users ask for multiple related items that go together.
    Examples: meal courses, travel itineraries, outfits, etc.
    """
    
    def __init__(self, params, handler):
        # Store handler reference and params
        self.handler = handler
        self.params = params
        self.queries = params.get('queries', [])
        self.ensemble_type = params.get('ensemble_type', 'general')
        
    async def do(self):
        """
        Main entry point following NLWeb module pattern.
        Execute multiple parallel queries and combine results using LLM.
        """
        print(f"Ensemble type: {self.ensemble_type} params: {self.handler.query_params}")
        try:
            original_query = self.handler.query
            
            # Execute retrieval and ranking in parallel for each query
            ranked_results_per_query = await self._execute_parallel_retrieval_and_ranking(
                self.queries, self.handler.query_params, original_query
            )
            
            # Calculate number of results per query based on total desired and number of queries
            num_queries = len(self.queries)
            results_per_query = max(1, NUM_RESULTS_FOR_ENSEMBLE_BUILDING // num_queries)
            
            # Select top results per query
            top_results = self._select_top_results_from_ranked(ranked_results_per_query, num_per_query=results_per_query)
            
            # Process the top results - extract JSON and add schema_object field
            trimmed_results = []
            url_to_schema_map = {}  # Map URLs to schema objects for later matching
            name_to_schema_map = {}  # Map names to schema objects for fallback matching
            
            for item_data in top_results:
                # item_data has 'item' (4-tuple) and 'schema_object' from _select_top_results_from_ranked
                url, json_str, name, site = item_data['item']
                # Use the schema_object that was added in _select_top_results_from_ranked
                item_dict = item_data.get('schema_object', {})
                if not item_dict:
                    try:
                        item_dict = json.loads(json_str) if isinstance(json_str, str) else json_str
                    except:
                        item_dict = {}
                
                try:
                    trimmed_item = trim_json_hard(item_dict)
                    # Add the full schema object to the trimmed item
                    trimmed_item['schema_object'] = item_dict
                    # Ensure URL is in the trimmed item for matching
                    trimmed_item['url'] = url or item_dict.get('url', '')
                    # Ensure name is in the trimmed item for matching
                    # Handle case where name might be a list from collateObjAttr
                    trimmed_name = trimmed_item.get('name')
                    if isinstance(trimmed_name, list):
                        trimmed_name = trimmed_name[0] if trimmed_name else None
                    
                    dict_name = item_dict.get('name')
                    if isinstance(dict_name, list):
                        dict_name = dict_name[0] if dict_name else None
                    
                    trimmed_item['name'] = trimmed_name or dict_name or name
                    
                    trimmed_results.append(trimmed_item)
                    
                    # Store mappings for later use
                    if trimmed_item['url']:
                        url_to_schema_map[trimmed_item['url']] = item_dict
                    if trimmed_item.get('name'):
                        name_for_key = trimmed_item['name']
                        # Handle case where name might be a list
                        if isinstance(name_for_key, list):
                            name_for_key = name_for_key[0] if name_for_key else ''
                        name_key = str(name_for_key).lower().strip()
                        name_to_schema_map[name_key] = item_dict
                except Exception as e:
                    logger.warning(f"Failed to trim item: {name}, error: {e}")
                    continue
            
            # Calculate total items for the message
            total_items = sum(len(results) for results in ranked_results_per_query)
            
            # Send informative intermediate message
            query_details = []
            for i, query in enumerate(self.queries):
                if i < len(ranked_results_per_query):
                    count = len(ranked_results_per_query[i])
                    query_details.append(f"  • {count} from '{query}'")
            
            query_breakdown = '\n'.join(query_details)
            
            await self.handler.send_message({
                "message_type": "intermediate_message", 
                "message": f"Found {total_items} total results:\n{query_breakdown}\n\nCombing through top results for each of these queries to answer the question..."
            })
            
            # Generate ensemble recommendations using LLM
            ensemble_response = await self._generate_ensemble_recommendations(
                trimmed_results, 
                self.queries, 
                self.ensemble_type,
                original_query
            )
            
            logger.info(f"LLM response type: {type(ensemble_response)}")
            if isinstance(ensemble_response, dict):
                logger.info(f"LLM response keys: {list(ensemble_response.keys())}")
                if 'items' in ensemble_response:
                    logger.info(f"Number of items in LLM response: {len(ensemble_response.get('items', []))}")
            
            # Total items already calculated above
            # Add schema objects to ensemble response items
            # Check for either 'items' or 'recommendations' key
            items_key = None
            if isinstance(ensemble_response, dict):
                if 'items' in ensemble_response:
                    items_key = 'items'
                elif 'recommendations' in ensemble_response and isinstance(ensemble_response['recommendations'], list):
                    items_key = 'recommendations'
                elif 'recommendations' in ensemble_response and isinstance(ensemble_response['recommendations'], dict) and 'items' in ensemble_response['recommendations']:
                    # Handle nested structure
                    ensemble_response = ensemble_response['recommendations']
                    items_key = 'items'
            
            if items_key and isinstance(ensemble_response, dict) and items_key in ensemble_response:
                logger.info(f"Processing {len(ensemble_response[items_key])} items in ensemble response")
                matched_count = 0
                
                for item in ensemble_response[items_key]:
                    # Try to match by URL first
                    if 'url' in item and item['url'] in url_to_schema_map:
                        item['schema_object'] = url_to_schema_map[item['url']]
                        matched_count += 1
                        logger.debug(f"Matched item by URL: {item['url']}")
                    else:
                        # Fallback: try to match by name
                        item_name_raw = item.get('name', '')
                        # Handle case where name might be a list
                        if isinstance(item_name_raw, list):
                            item_name = item_name_raw[0] if item_name_raw else ''
                        else:
                            item_name = item_name_raw
                        item_name = str(item_name).lower().strip()
                        matched = False
                        
                        for result in trimmed_results:
                            result_name_raw = result.get('name', '')
                            # Handle case where name might be a list
                            if isinstance(result_name_raw, list):
                                result_name = result_name_raw[0] if result_name_raw else ''
                            else:
                                result_name = result_name_raw
                            result_name = str(result_name).lower().strip()
                            
                            # Also check the schema object for name
                            if 'schema_object' in result and 'name' in result['schema_object']:
                                schema_name_raw = result['schema_object'].get('name', '')
                                # Handle case where name might be a list
                                if isinstance(schema_name_raw, list):
                                    schema_name = schema_name_raw[0] if schema_name_raw else ''
                                else:
                                    schema_name = schema_name_raw
                                schema_name = str(schema_name).lower().strip()
                            else:
                                schema_name = ''
                            
                            # Match by name similarity
                            if (item_name and result_name and (item_name in result_name or result_name in item_name)) or \
                               (item_name and schema_name and (item_name in schema_name or schema_name in item_name)):
                                if 'schema_object' in result:
                                    item['schema_object'] = result['schema_object']
                                    matched_count += 1
                                    matched = True
                                    logger.debug(f"Matched item by name: {item_name} -> {result_name or schema_name}")
                                    break
                        
                        if not matched:
                            logger.warning(f"Could not match item: {item.get('name', 'Unknown')} with URL: {item.get('url', 'None')}")
                
                logger.info(f"Successfully matched {matched_count}/{len(ensemble_response[items_key])} items with schema objects")
            else:
                logger.warning(f"Ensemble response is not in expected format. Type: {type(ensemble_response)}, Keys: {list(ensemble_response.keys()) if isinstance(ensemble_response, dict) else 'N/A'}")
            # Ensure the response has the expected structure
            if not isinstance(ensemble_response, dict):
                ensemble_response = {"items": [], "theme": "Error: Invalid response format"}
            
            # Clean up the response to remove circular references before sending
            cleaned_response = self._clean_for_json(ensemble_response)
            
            # Send the result as a message
            result = {
                "success": True,
                "ensemble_type": self.ensemble_type,
                "recommendations": cleaned_response,
                "total_items_retrieved": total_items
            }
            
            await self.handler.send_message({
                "message_type": "ensemble_result",
                "result": result
            })
            
            # Mark query as done to prevent further processing
            self.handler.query_done = True
            
        except Exception as e:
            logger.error(f"Error in ensemble request: {str(e)}")
            await self.handler.send_message({
                "message_type": "ensemble_result",
                "result": {
                    "success": False,
                    "error": str(e)
                }
            })
    
    async def _retrieve_and_rank_for_query(self, query: str, query_idx: int, queries_count: int, query_params: Dict[str, Any], original_query: str) -> List[Dict]:
        """Retrieve and rank results for a single query."""
        try:
            # Execute search with appropriate limit per query
            # Aim for ~60 total results across all queries
            results_per_query = max(10, 60 // queries_count)
            
            # Get site from handler or query_params
            site = self.handler.site if hasattr(self, 'handler') and self.handler else query_params.get('site', 'all')
            
            # Send intermediate message for this query
            await self.handler.send_message({
                "message_type": "intermediate_message",
                "message": f"Looking for {query}"
            })
            
            # Use the search abstraction from retriever.py
            results = await search(
                query=query,
                site=site,
                num_results=results_per_query,
                query_params=query_params
            )
            
            # Immediately rank the results for this query
            ranked_results = await self._rank_query_results(results, original_query, query, query_idx)
            
            # Send top 2 ranked results as intermediate message
            if ranked_results and len(ranked_results) > 0:
                top_results = ranked_results[:2]  # Get top 2 results
                top_items = []
                
                for result in top_results:
                    if isinstance(result, dict) and 'name' in result:
                        # Result is already in the format we need
                        top_items.append(result)
                    elif isinstance(result, list) and len(result) >= 4:
                        # Result is in [url, json_str, name, site] format
                        url, json_str, name, site = result[0], result[1], result[2], result[3]
                        try:
                            schema_object = json.loads(json_str) if json_str else {}
                        except:
                            schema_object = {}
                        
                        top_items.append({
                            "name": name,
                            "url": url,
                            "site": site,
                            "schema_object": schema_object
                        })
                
                if top_items:
                    await self.handler.send_message({
                        "message_type": "intermediate_message",
                        "results": top_items
                    })
            
            return ranked_results
            
        except Exception as e:
            logger.error(f"Error in retrieve and rank for query '{query}': {str(e)}")
            return []
    
    async def _execute_parallel_retrieval_and_ranking(self, queries: List[str], query_params: Dict[str, Any], original_query: str) -> List[List[Dict]]:
        """Execute retrieval and ranking in parallel for all queries."""
        # Execute retrieval and ranking for all queries in parallel
        tasks = [self._retrieve_and_rank_for_query(query, idx, len(queries), query_params, original_query) for idx, query in enumerate(queries)]
        ranked_results_per_query = await asyncio.gather(*tasks)
        
        return ranked_results_per_query
    
    async def _rank_query_results(self, results: List[tuple], original_query: str, search_query: str, query_idx: int) -> List[Dict]:
        """Rank results from a single query.
        
        Args:
            results: List of 4-tuples (url, json_str, name, site) from search
            original_query: The original user query
            search_query: The specific search query used
            query_idx: Index of this query in the ensemble
        """
        # First, deduplicate within this query's results
        seen_ids = set()
        unique_results = []
        
        for result_tuple in results:
            # Unpack the 4-tuple
            url, json_str, name, site = result_tuple
            
            # Parse JSON string to dict for processing
            try:
                item_dict = json.loads(json_str) if isinstance(json_str, str) else json_str
            except:
                item_dict = {}
            
            item_id = self._get_item_identifier(item_dict)
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                unique_results.append(result_tuple)
            elif not item_id:
                unique_results.append(result_tuple)
        
        # Rank each unique result
        ranking_tasks = []
        for idx, result_tuple in enumerate(unique_results):
            task = self._rank_single_item(result_tuple, original_query, idx)
            ranking_tasks.append(task)
        
        # Execute all ranking tasks in parallel
        scores = await asyncio.gather(*ranking_tasks)
        
        # Create ranked results with metadata
        ranked_results = []
        for result_tuple, score in zip(unique_results, scores):
            url, json_str, name, site = result_tuple
            ranked_results.append({
                'item': result_tuple,  # Store the original tuple
                'relevance_score': score,
                'source_query_idx': query_idx,
                'search_query': search_query
            })
        
        # Sort by relevance score
        ranked_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        logger.info(f"Ranked {len(ranked_results)} items for query '{search_query}'")
        return ranked_results
    
    
    def _get_item_identifier(self, item: Dict) -> Optional[str]:
        """Extract a unique identifier from an item."""
        if not isinstance(item, dict):
            return None
            
        # Try different fields that might contain unique identifiers
        if 'url' in item and item['url']:
            return item['url']
        elif '@id' in item and item['@id']:
            return item['@id']
        elif 'identifier' in item and item['identifier']:
            return item['identifier']
        elif 'name' in item and '@type' in item:
            # Fallback to name + type combination
            return f"{item.get('name', '')}|{item.get('@type', '')}"
        return None
    
    def _clean_for_json(self, obj, seen=None):
        """Remove circular references and clean object for JSON serialization."""
        if seen is None:
            seen = set()
        
        # Handle None, bool, int, float, str
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj
        
        # Handle lists
        if isinstance(obj, list):
            return [self._clean_for_json(item, seen) for item in obj]
        
        # Handle dictionaries
        if isinstance(obj, dict):
            # Check if we've seen this object before (circular reference)
            obj_id = id(obj)
            if obj_id in seen:
                return {"_circular_reference": True}
            
            seen.add(obj_id)
            
            cleaned = {}
            for key, value in obj.items():
                # Skip certain problematic keys that often contain circular references
                if key in ['_parent', '_root', '__dict__', '_cache']:
                    continue
                    
                try:
                    cleaned[key] = self._clean_for_json(value, seen.copy())
                except Exception as e:
                    logger.debug(f"Skipping key {key} due to error: {e}")
                    
            return cleaned
        
        # For other types, convert to string
        return str(obj)
    
    
    async def _rank_single_item(self, result_tuple: tuple, original_query: str, idx: int) -> float:
        """Rank a single item for relevance to the query.
        
        Args:
            result_tuple: 4-tuple (url, json_str, name, site)
            original_query: The original user query
            idx: Index of the item
        """
        try:
            # Unpack the tuple
            url, json_str, name, site = result_tuple
            
            # Parse JSON to get item details
            try:
                item_dict = json.loads(json_str) if isinstance(json_str, str) else json_str
            except:
                item_dict = {}
            
            # Ensure item_dict is a dictionary, not a list
            if isinstance(item_dict, list):
                item_dict = item_dict[0] if item_dict else {}
            
            if not isinstance(item_dict, dict):
                item_dict = {}
            
            # Create a concise representation of the item for ranking
            # Handle cases where fields might be lists due to collateObjAttr
            name_value = item_dict.get('name', name) if isinstance(item_dict, dict) else name
            if isinstance(name_value, list):
                name_value = name_value[0] if name_value else 'Unknown'
            
            type_value = item_dict.get('@type', 'Unknown') if isinstance(item_dict, dict) else 'Unknown'
            if isinstance(type_value, list):
                type_value = type_value[0] if type_value else 'Unknown'
            
            desc_value = item_dict.get('description', '') if isinstance(item_dict, dict) else ''
            if isinstance(desc_value, list):
                desc_value = desc_value[0] if desc_value else ''
            desc_value = str(desc_value)[:200]  # First 200 chars
            
            url_value = item_dict.get('url', url) if isinstance(item_dict, dict) else url
            if isinstance(url_value, list):
                url_value = url_value[0] if url_value else ''
            
            item_summary = {
                'name': name_value or 'Unknown',
                'type': type_value,
                'description': desc_value,
                'url': url_value or ''
            }
            
            # Get the ranking prompt from XML
            prompt_str, return_struc = find_prompt(self.handler.site, self.handler.item_type, "EnsembleItemRankingPrompt")
            
            if not prompt_str:
                logger.error("EnsembleItemRankingPrompt not found")
                return 0.0
            
            # Prepare variables for prompt filling
            pr_dict = {
                "item.name": item_summary['name'],
                "item.type": item_summary['type'],
                "item.description": item_summary['description']
            }
            
            # Fill the prompt with variables
            filled_prompt = fill_prompt(prompt_str, self.handler, pr_dict)
            
            result = await ask_llm(filled_prompt, return_struc, level="low", timeout=5, query_params=self.handler.query_params)
            
            if result and 'score' in result:
                return float(result['score'])
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error ranking item {idx}: {str(e)}")
            return 0.0
    
    def _select_top_results_from_ranked(self, ranked_results_per_query: List[List[Dict]], num_per_query: int = 3) -> List[Dict]:
        """Select top N results from each query's ranked results.
        
        Returns:
            List of dicts, each containing:
            - item: the original 4-tuple (url, json_str, name, site)
            - relevance_score: the ranking score
            - source_query_idx: which query this came from
            - search_query: the query that found this item
            - schema_object: the full parsed JSON object
        """
        selected_results = []
        seen_ids = set()  # Track globally to avoid duplicates across queries
        
        for query_results in ranked_results_per_query:
            # Take top N items for this query
            selected_count = 0
            for item in query_results:
                if selected_count >= num_per_query:
                    break
                    
                # Extract item dict from the tuple for ID checking
                url, json_str, name, site = item['item']
                try:
                    item_dict = json.loads(json_str) if isinstance(json_str, str) else json_str
                except:
                    item_dict = {}
                
                item_id = self._get_item_identifier(item_dict)
                
                # Add if not seen globally
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    # Add the schema_object to the item data
                    item['schema_object'] = item_dict
                    selected_results.append(item)
                    selected_count += 1
                elif not item_id:
                    # Include items without identifiers
                    item['schema_object'] = item_dict
                    selected_results.append(item)
                    selected_count += 1
            
            if query_results:
                logger.info(f"Selected {selected_count} items from query '{query_results[0]['search_query']}'")
        
        return selected_results
    
    async def _generate_ensemble_recommendations(self, 
                                                 trimmed_results: List[Dict], 
                                                 queries: List[str], 
                                                 ensemble_type: str,
                                                 original_query: str) -> Dict[str, Any]:
        """Generate ensemble recommendations using LLM."""
        
        # Map ensemble types to prompt names
        prompt_name_map = {
            "meal planning": "EnsembleMealPlanningPrompt",
            "travel_itinerary": "EnsembleTravelItineraryPrompt",
            "outfit": "EnsembleOutfitPrompt"
        }
        
        # Get the appropriate prompt name, defaulting to generic
        prompt_name = prompt_name_map.get(ensemble_type, "EnsembleGenericPrompt")
        
        # Get prompt from XML
        prompt_str, return_struc = find_prompt(self.handler.site, self.handler.item_type, prompt_name)
        
        if not prompt_str:
            logger.warning(f"Could not find prompt {prompt_name}, using base prompt")
            prompt_str, return_struc = find_prompt(self.handler.site, self.handler.item_type, "EnsembleBasePrompt")
        
        if not prompt_str:
            logger.error("No ensemble prompts found")
            return {"recommendations": "Unable to generate recommendations - no prompts found"}
        
        # Prepare variables for prompt filling - exclude schema_object from LLM prompt to save tokens
        trimmed_for_llm = []
        for result in trimmed_results:
            result_copy = result.copy()
            # Remove schema_object from the copy sent to LLM
            result_copy.pop('schema_object', None)
            trimmed_for_llm.append(result_copy)
        
        pr_dict = {
            "ensemble.queries": json.dumps(queries),
            "ensemble.results": json.dumps(trimmed_for_llm, indent=2)
        }
        
        # Fill the prompt with variables
        filled_prompt = fill_prompt(prompt_str, self.handler, pr_dict)
        
        try:
            # Use the existing ask_llm function
            response = await ask_llm(filled_prompt, return_struc, level="high", timeout=AGGREGATION_CALL_TIMEOUT, max_length=2056, query_params=self.handler.query_params)
            
            if response:
                logger.info(f"LLM ensemble response structure: {list(response.keys()) if isinstance(response, dict) else type(response)}")
                return response
            else:
                return {"items": [], "theme": "Unable to generate recommendations"}
                
        except Exception as e:
            logger.error(f"Error generating ensemble recommendations: {str(e)}")
            raise
    
    # Note: _build_ensemble_prompt method has been removed as prompts are now loaded from XML