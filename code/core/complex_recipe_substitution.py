# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Enhanced Substitution Handler that leverages the recipe database for better suggestions.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from llm.llm import ask_llm
from utils.logging_config_helper import get_configured_logger
from retrieval.retriever import get_vector_db_client
from core.ranking import Ranking

logger = get_configured_logger("substitution")


class SubstitutionHandler():
    """Enhanced handler for finding ingredient substitutions in recipes."""
    
    def __init__(self, params, handler):
        self.handler = handler
        self.params = params
        self.recipe_name = params.get('recipe_name', '')
        self.dietary_need = params.get('dietary_need', '')
        self.unavailable_ingredient = params.get('unavailable_ingredient', '')
        self.preference = params.get('preference', '')
        
    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
            # Strategy 1: Find recipes that already match the dietary need
            reference_recipes = await self._find_reference_recipes()
            
            # Strategy 2: Find the specific recipe if mentioned
            target_recipe = None
            if self.recipe_name:
                target_recipe = await self._find_target_recipe()
            
            # Strategy 3: Generate substitutions using both reference recipes and LLM
            await self._generate_smart_substitutions(target_recipe, reference_recipes)
            
        except Exception as e:
            logger.error(f"Error in SubstitutionHandler.do(): {e}")
            await self._send_error_message(str(e))
    
    async def _find_reference_recipes(self):
        """Find recipes that already meet the dietary requirements."""
        search_queries = []
        
        # Build search queries based on the substitution need
        if self.dietary_need:
            if "dairy-free" in self.dietary_need.lower():
                search_queries.extend(["dairy free", "vegan", "lactose free"])
            elif "gluten-free" in self.dietary_need.lower():
                search_queries.extend(["gluten free", "celiac", "wheat free"])
            elif "vegan" in self.dietary_need.lower():
                search_queries.extend(["vegan", "plant based", "no animal products"])
            elif "egg-free" in self.dietary_need.lower():
                search_queries.extend(["egg free", "vegan", "no eggs"])
            else:
                search_queries.append(self.dietary_need)
        
        if self.unavailable_ingredient:
            # Search for recipes that might have substitution info
            search_queries.append(f"substitute for {self.unavailable_ingredient}")
            search_queries.append(f"without {self.unavailable_ingredient}")
        
        # Also search for the type of recipe if mentioned
        if self.recipe_name:
            # Extract recipe type (e.g., "chocolate cake" -> "cake")
            recipe_type = self._extract_recipe_type(self.recipe_name)
            for query in search_queries[:]:  # Copy to avoid modifying during iteration
                search_queries.append(f"{query} {recipe_type}")
        
        # Collect reference recipes
        reference_recipes = []
        client = get_vector_db_client(query_params=self.handler.query_params)
        
        for query in search_queries[:3]:  # Limit to avoid too many searches
            logger.info(f"Searching for reference recipes with query: {query}")
            candidates = await client.search(query, self.handler.site)
            
            if candidates:
                # Use ranking to find the most relevant ones
                original_query = self.handler.query
                self.handler.query = f"{query} recipe with substitution information"
                
                ranking = Ranking(self.handler, candidates[:10], ranking_type=Ranking.REGULAR_TRACK)
                await ranking.do()
                
                # Get top ranked results
                if hasattr(ranking, 'rankedAnswers'):
                    for answer in ranking.rankedAnswers[:3]:
                        if answer.get('ranking', {}).get('score', 0) > 70:
                            reference_recipes.append(answer)
                
                self.handler.query = original_query
        
        logger.info(f"Found {len(reference_recipes)} reference recipes")
        return reference_recipes
    
    async def _find_target_recipe(self):
        """Find the specific recipe mentioned by the user."""
        logger.info(f"Finding target recipe: {self.recipe_name}")
        
        client = get_vector_db_client(query_params=self.handler.query_params)
        candidates = await client.search(self.recipe_name, self.handler.site)
        
        if not candidates:
            return None
        
        # Rank to find the best match
        original_query = self.handler.query
        self.handler.query = self.recipe_name
        
        ranking = Ranking(self.handler, candidates[:10], ranking_type=Ranking.REGULAR_TRACK)
        await ranking.do()
        
        target_recipe = None
        if hasattr(ranking, 'rankedAnswers') and ranking.rankedAnswers:
            best_match = max(ranking.rankedAnswers, key=lambda x: x.get('ranking', {}).get('score', 0))
            if best_match.get('ranking', {}).get('score', 0) > 75:
                target_recipe = best_match
        
        self.handler.query = original_query
        return target_recipe
    
    async def _generate_smart_substitutions(self, target_recipe, reference_recipes):
        """Generate substitutions using both database knowledge and LLM."""
        
        # Extract useful information from reference recipes
        substitution_examples = self._extract_substitution_patterns(reference_recipes)
        
        # Build a comprehensive prompt
        prompt_parts = ["Generate detailed ingredient substitution suggestions.\n"]
        
        # Add target recipe context
        if target_recipe:
            recipe_info = self._extract_recipe_info(target_recipe)
            prompt_parts.append(f"\nTarget Recipe:\n{recipe_info}\n")
        elif self.recipe_name:
            prompt_parts.append(f"\nRecipe Type: {self.recipe_name}\n")
        
        # Add substitution need
        if self.dietary_need:
            prompt_parts.append(f"Dietary Requirement: {self.dietary_need}\n")
        if self.unavailable_ingredient:
            prompt_parts.append(f"Ingredient to Replace: {self.unavailable_ingredient}\n")
        if self.preference:
            prompt_parts.append(f"Preference: {self.preference}\n")
        
        # Add examples from reference recipes
        if substitution_examples:
            prompt_parts.append("\nExamples from similar recipes:\n")
            for example in substitution_examples[:5]:
                prompt_parts.append(f"- {example}\n")
        
        # Request comprehensive substitution advice
        prompt_parts.append("""
Please provide:
1. Primary substitution recommendation with exact measurements
2. Alternative substitutions if the primary isn't available
3. How to adjust other ingredients or cooking method
4. Expected differences in taste, texture, and appearance
5. Tips for best results with the substitution
6. Common mistakes to avoid

Be specific and practical. If you found examples in the reference recipes, incorporate that knowledge.""")
        
        prompt = "".join(prompt_parts)
        
        # Enhanced response structure
        response_structure = {
            "primary_substitution": {
                "original": "string",
                "substitute": "string",
                "ratio": "string",
                "preparation_notes": "string"
            },
            "alternative_substitutions": [
                {
                    "substitute": "string",
                    "ratio": "string",
                    "notes": "string"
                }
            ],
            "recipe_adjustments": {
                "ingredient_changes": "string",
                "method_changes": "string",
                "timing_changes": "string"
            },
            "expected_differences": {
                "taste": "string",
                "texture": "string",
                "appearance": "string"
            },
            "tips_for_success": ["string"],
            "common_mistakes": ["string"],
            "confidence_level": "high/medium/low",
            "reasoning": "string"
        }
        
        try:
            logger.info("Generating enhanced substitution suggestions")
            response = await ask_llm(prompt, response_structure, level="high")
            
            # Send the enhanced substitution suggestions
            await self._send_enhanced_substitution_message(response, reference_recipes)
            
        except Exception as e:
            logger.error(f"Error generating substitutions: {e}")
            await self._send_error_message("Could not generate substitution suggestions")
    
    def _extract_recipe_type(self, recipe_name):
        """Extract the general type from a recipe name."""
        # Simple extraction - could be enhanced
        words = recipe_name.lower().split()
        
        # Common recipe types
        recipe_types = ['cake', 'cookie', 'bread', 'pasta', 'sauce', 'soup', 'salad', 
                       'pie', 'muffin', 'pancake', 'waffle', 'curry', 'stew']
        
        for word in words:
            if word in recipe_types:
                return word
        
        # If no specific type found, use last word as approximation
        return words[-1] if words else recipe_name
    
    def _extract_substitution_patterns(self, reference_recipes):
        """Extract substitution patterns from reference recipes."""
        patterns = []
        
        for recipe in reference_recipes:
            schema_obj = recipe.get('schema_object', {})
            if isinstance(schema_obj, list) and schema_obj:
                schema_obj = schema_obj[0]
            
            # Look for substitution mentions in description
            description = schema_obj.get('description', '')
            if any(word in description.lower() for word in ['substitute', 'instead of', 'replacement', 'free']):
                patterns.append(description)
            
            # Check recipe name for substitution hints
            name = schema_obj.get('headline', '') or schema_obj.get('name', '')
            if any(word in name.lower() for word in ['vegan', 'gluten-free', 'dairy-free', 'egg-free']):
                patterns.append(f"{name} - {description[:100]}")
        
        return patterns
    
    def _extract_recipe_info(self, recipe):
        """Extract relevant recipe information."""
        schema_obj = recipe.get('schema_object', {})
        if isinstance(schema_obj, list) and schema_obj:
            schema_obj = schema_obj[0]
        
        info_parts = []
        
        name = schema_obj.get('headline', '') or schema_obj.get('name', '')
        if name:
            info_parts.append(f"Name: {name}")
        
        ingredients = schema_obj.get('recipeIngredient', [])
        if ingredients:
            info_parts.append(f"Key Ingredients: {', '.join(ingredients[:10])}")
        
        description = schema_obj.get('description', '')
        if description:
            info_parts.append(f"Description: {description[:200]}")
        
        return "\n".join(info_parts)
    
    async def _send_enhanced_substitution_message(self, substitution_data, reference_recipes):
        """Send enhanced substitution suggestions to the client."""
        
        # Format the message with confidence indicators
        message_parts = []
        
        # Header with confidence level
        confidence = substitution_data.get('confidence_level', 'medium')
        confidence_emoji = {'high': '✅', 'medium': '⚡', 'low': '⚠️'}.get(confidence, '❓')
        
        if self.recipe_name and self.dietary_need:
            message_parts.append(f"# {confidence_emoji} {self.dietary_need.title()} Substitutions for {self.recipe_name}\n")
        elif self.unavailable_ingredient:
            message_parts.append(f"# {confidence_emoji} Substituting {self.unavailable_ingredient}\n")
        else:
            message_parts.append(f"# {confidence_emoji} Ingredient Substitutions\n")
        
        # Primary substitution
        primary = substitution_data.get('primary_substitution', {})
        if primary.get('substitute'):
            message_parts.append("## Recommended Substitution\n")
            message_parts.append(f"**{primary.get('original', 'Original')}** → **{primary['substitute']}**")
            if primary.get('ratio'):
                message_parts.append(f" ({primary['ratio']})")
            message_parts.append("\n")
            if primary.get('preparation_notes'):
                message_parts.append(f"*{primary['preparation_notes']}*\n")
        
        # Alternative options
        alternatives = substitution_data.get('alternative_substitutions', [])
        if alternatives:
            message_parts.append("\n## Alternative Options\n")
            for alt in alternatives:
                message_parts.append(f"- {alt.get('substitute', '')}")
                if alt.get('ratio'):
                    message_parts.append(f" ({alt['ratio']})")
                if alt.get('notes'):
                    message_parts.append(f" - {alt['notes']}")
                message_parts.append("\n")
        
        # Recipe adjustments
        adjustments = substitution_data.get('recipe_adjustments', {})
        if any(adjustments.values()):
            message_parts.append("\n## Recipe Adjustments\n")
            if adjustments.get('ingredient_changes'):
                message_parts.append(f"**Ingredients:** {adjustments['ingredient_changes']}\n")
            if adjustments.get('method_changes'):
                message_parts.append(f"**Method:** {adjustments['method_changes']}\n")
            if adjustments.get('timing_changes'):
                message_parts.append(f"**Timing:** {adjustments['timing_changes']}\n")
        
        # Expected differences
        differences = substitution_data.get('expected_differences', {})
        if any(differences.values()):
            message_parts.append("\n## What to Expect\n")
            if differences.get('taste'):
                message_parts.append(f"**Taste:** {differences['taste']}\n")
            if differences.get('texture'):
                message_parts.append(f"**Texture:** {differences['texture']}\n")
            if differences.get('appearance'):
                message_parts.append(f"**Appearance:** {differences['appearance']}\n")
        
        # Tips
        tips = substitution_data.get('tips_for_success', [])
        if tips:
            message_parts.append("\n## Tips for Success\n")
            for tip in tips:
                message_parts.append(f"• {tip}\n")
        
        # Common mistakes
        mistakes = substitution_data.get('common_mistakes', [])
        if mistakes:
            message_parts.append("\n## Common Mistakes to Avoid\n")
            for mistake in mistakes:
                message_parts.append(f"⚠️ {mistake}\n")
        
        # Add reference recipes if found
        if reference_recipes:
            message_parts.append("\n## Similar Recipes for Reference\n")
            for i, recipe in enumerate(reference_recipes[:3]):
                schema_obj = recipe.get('schema_object', {})
                if isinstance(schema_obj, list) and schema_obj:
                    schema_obj = schema_obj[0]
                
                name = schema_obj.get('headline', '') or schema_obj.get('name', '')
                url = recipe.get('url', '')
                if name and url:
                    message_parts.append(f"{i+1}. [{name}]({url})\n")
        
        message = {
            "message_type": "substitution_suggestions",
            "content": "".join(message_parts),
            "substitution_data": substitution_data,
            "confidence_level": confidence,
            "reference_recipes_count": len(reference_recipes)
        }
        
        await self.handler.send_message(message)
    
    async def _send_error_message(self, error_msg):
        """Send an error message to the client."""
        message = {
            "message_type": "error",
            "message": f"Could not generate substitution suggestions: {error_msg}"
        }
        
        await self.handler.send_message(message)