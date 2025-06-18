import asyncio
import json
from typing import List, Dict, Any, Optional
from retrieval.retriever import search
from utils.trim import trim_json_hard
from llm.llm import ask_llm
import logging

logger = logging.getLogger(__name__)

class EnsembleToolHandler:
    """
    Handles ensemble requests where users ask for multiple related items that go together.
    Examples: meal courses, travel itineraries, outfits, etc.
    """
    
    def __init__(self, params, handler):
        # Store handler reference and params
        self.handler = handler
        self.params = params
        
    async def handle_ensemble_request(self, queries: List[str], ensemble_type: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute multiple parallel queries and combine results using LLM.
        
        Args:
            queries: List of search queries to execute
            ensemble_type: Type of ensemble request (meal_course, travel_itinerary, outfit, etc.)
            query_params: Parameters for the retrieval backend
            
        Returns:
            Dict containing the ensemble recommendations
        """
        try:
            original_query = query_params.get('query', '')
            
            # Execute retrieval and ranking in parallel for each query
            ranked_results_per_query = await self._execute_parallel_retrieval_and_ranking(
                queries, query_params, original_query
            )
            
            # Select top results per query
            top_results = self._select_top_results_from_ranked(ranked_results_per_query, num_per_query=3)
            
            # Trim the top results - extract and trim JSON from tuples
            trimmed_results = []
            for item_data in top_results:
                # item_data['item'] is the original 4-tuple (url, json_str, name, site)
                url, json_str, name, site = item_data['item']
                try:
                    item_dict = json.loads(json_str) if isinstance(json_str, str) else json_str
                    trimmed_item = trim_json_hard(item_dict)
                    trimmed_results.append(trimmed_item)
                except:
                    logger.warning(f"Failed to trim item: {name}")
                    continue
            
            # Generate ensemble recommendations using LLM
            ensemble_response = await self._generate_ensemble_recommendations(
                trimmed_results, 
                queries, 
                ensemble_type,
                original_query
            )
            
            # Calculate total items retrieved
            total_items = sum(len(results) for results in ranked_results_per_query)
            
            return {
                "success": True,
                "ensemble_type": ensemble_type,
                "recommendations": ensemble_response,
                "total_items_retrieved": total_items
            }
            
        except Exception as e:
            logger.error(f"Error in ensemble request: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _retrieve_and_rank_for_query(self, query: str, query_idx: int, queries_count: int, query_params: Dict[str, Any], original_query: str) -> List[Dict]:
        """Retrieve and rank results for a single query."""
        try:
            # Execute search with appropriate limit per query
            # Aim for ~60 total results across all queries
            results_per_query = max(10, 60 // queries_count)
            
            # Get site from handler or query_params
            site = self.handler.site if hasattr(self, 'handler') and self.handler else query_params.get('site', 'all')
            
            # Use the search abstraction from retriever.py
            results = await search(
                query=query,
                site=site,
                num_results=results_per_query,
                query_params=query_params
            )
            
            # Immediately rank the results for this query
            ranked_results = await self._rank_query_results(results, original_query, query, query_idx)
            
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
            
            # Create a concise representation of the item for ranking
            item_summary = {
                'name': name or item_dict.get('name', 'Unknown'),
                'type': item_dict.get('@type', 'Unknown'),
                'description': item_dict.get('description', '')[:200],  # First 200 chars
                'url': url or item_dict.get('url', '')
            }
            
            ranking_prompt = f"""Given the user's query: "{original_query}"

And this item:
Name: {item_summary['name']}
Type: {item_summary['type']}
Description: {item_summary['description']}

Rate how relevant this item is for answering the user's query on a scale of 0-100.
Consider:
- Does this item directly address what the user is looking for?
- Is it the right type of item (e.g., restaurant vs attraction)?
- Does it match any specific criteria mentioned in the query?

Provide your response as a JSON object with a 'score' field containing the relevance score."""
            
            response_structure = {
                "score": "integer between 0 and 100"
            }
            
            result = await ask_llm(ranking_prompt, response_structure, level="low", timeout=5)
            
            if result and 'score' in result:
                return float(result['score'])
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error ranking item {idx}: {str(e)}")
            return 0.0
    
    def _select_top_results_from_ranked(self, ranked_results_per_query: List[List[Dict]], num_per_query: int = 3) -> List[Dict]:
        """Select top N results from each query's ranked results."""
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
                    selected_results.append(item)
                    selected_count += 1
                elif not item_id:
                    # Include items without identifiers
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
        
        # Build prompt based on ensemble type
        prompt = self._build_ensemble_prompt(ensemble_type, queries, trimmed_results, original_query)
        
        try:
            # Use the existing ask_llm function
            system_prompt = "You are a helpful assistant that creates cohesive recommendations from search results."
            full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Define expected response structure
            response_structure = {
                "recommendations": "array of recommended items with explanations",
                "summary": "brief summary of the ensemble"
            }
            response = await ask_llm(full_prompt, response_structure, level="high", timeout=30)
            
            if response:
                return response
            else:
                return {"recommendations": "Unable to generate recommendations"}
                
        except Exception as e:
            logger.error(f"Error generating ensemble recommendations: {str(e)}")
            raise
    
    def _build_ensemble_prompt(self, ensemble_type: str, queries: List[str], results: List[Dict], original_query: str) -> str:
        """Build appropriate prompt based on ensemble type."""
        
        base_prompt = f"""
Based on the user's request: "{original_query}"

I searched for: {', '.join(queries)}

Here are the search results:
{json.dumps(results, indent=2)}

Please create a cohesive recommendation that addresses the user's request.
"""
        
        type_specific_prompts = {
            "meal_course": """
Create a complete meal recommendation with:
1. Appetizer/Starter
2. Main Course
3. Dessert

For each course, provide:
- Name of the dish
- Brief description
- Why it complements the other courses
- Any relevant details (prep time, difficulty, dietary info)

Ensure the courses work well together in terms of flavors, textures, and overall dining experience.
""",
            
            "travel_itinerary": """
Create a travel itinerary recommendation with:
1. Attractions/Museums to visit
2. Nearby restaurants for meals
3. Suggested order/timing

For each recommendation, provide:
- Name and location
- Why it's worth visiting
- Time needed
- How it connects to other recommendations
- Any practical tips (hours, tickets, reservations)
""",
            
            "outfit": """
Create a complete outfit recommendation with:
1. Essential items (footwear, jacket, base layers)
2. Accessories
3. Additional considerations

For each item, provide:
- Specific type recommended
- Why it's suitable for the conditions
- Key features to look for
- Any alternatives

Consider weather, activity level, and safety.
"""
        }
        
        # Get type-specific prompt or use a generic one
        type_prompt = type_specific_prompts.get(ensemble_type, """
Create a cohesive set of recommendations that work well together.
For each item, explain why it's recommended and how it complements the other items.
""")
        
        full_prompt = base_prompt + type_prompt + """

Format your response as a JSON object with the following structure:
{
  "theme": "Brief description of the overall recommendation theme",
  "items": [
    {
      "category": "Category name (e.g., Appetizer, Museum, Footwear)",
      "name": "Specific item name",
      "description": "Detailed description",
      "why_recommended": "Why this item fits the request",
      "details": {
        // Any relevant details specific to the item type
      }
    }
  ],
  "overall_tips": ["Any general tips or considerations"]
}
"""
        
        return full_prompt