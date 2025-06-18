import asyncio
import json
from typing import List, Dict, Any
from retrieval.retriever import get_vector_db_client
from utils.trim import trim_json_hard
from utils.text_embedding import get_openai_client
import logging

logger = logging.getLogger(__name__)

class EnsembleToolHandler:
    """
    Handles ensemble requests where users ask for multiple related items that go together.
    Examples: meal courses, travel itineraries, outfits, etc.
    """
    
    def __init__(self):
        self.openai_client = get_openai_client()
        
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
            # Execute all queries in parallel
            results = await self._execute_parallel_queries(queries, query_params)
            
            # Trim results to reduce token usage
            trimmed_results = self._trim_results(results)
            
            # Generate ensemble recommendations using LLM
            ensemble_response = await self._generate_ensemble_recommendations(
                trimmed_results, 
                queries, 
                ensemble_type,
                query_params.get('query', '')
            )
            
            return {
                "success": True,
                "ensemble_type": ensemble_type,
                "recommendations": ensemble_response,
                "total_items_retrieved": sum(len(r) for r in results)
            }
            
        except Exception as e:
            logger.error(f"Error in ensemble request: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_parallel_queries(self, queries: List[str], query_params: Dict[str, Any]) -> List[List[Dict]]:
        """Execute multiple search queries in parallel."""
        async def execute_single_query(query: str):
            try:
                # Get retrieval client
                client = get_vector_db_client(query_params)
                
                # Execute search with appropriate limit per query
                # Aim for ~60 total results across all queries
                results_per_query = max(10, 60 // len(queries))
                
                results = await client.search(
                    query=query,
                    limit=results_per_query,
                    filters=query_params.get('filters', {})
                )
                
                return results
            except Exception as e:
                logger.error(f"Error executing query '{query}': {str(e)}")
                return []
        
        # Execute all queries concurrently
        tasks = [execute_single_query(query) for query in queries]
        results = await asyncio.gather(*tasks)
        
        return results
    
    def _trim_results(self, results: List[List[Dict]]) -> List[Dict]:
        """Trim results to reduce token usage."""
        trimmed_all = []
        
        for query_results in results:
            for item in query_results:
                # Use hard trimming to aggressively reduce size
                trimmed_item = trim_json_hard(item)
                trimmed_all.append(trimmed_item)
        
        return trimmed_all
    
    async def _generate_ensemble_recommendations(self, 
                                                 trimmed_results: List[Dict], 
                                                 queries: List[str], 
                                                 ensemble_type: str,
                                                 original_query: str) -> Dict[str, Any]:
        """Generate ensemble recommendations using LLM."""
        
        # Build prompt based on ensemble type
        prompt = self._build_ensemble_prompt(ensemble_type, queries, trimmed_results, original_query)
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates cohesive recommendations from search results."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            # Parse the response
            content = response.choices[0].message.content
            
            # Try to parse as JSON, fallback to text if not valid JSON
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"recommendations": content}
                
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