# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Substitution Handler for finding ingredient substitutions in recipes.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
from core.llm import ask_llm
from misc.logger.logging_config_helper import get_configured_logger
from core.retriever import get_vector_db_client

logger = get_configured_logger("substitution")


class SubstitutionHandler():
    """Handler for finding ingredient substitutions in recipes."""
    
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
            # Log the parameters we received
            logger.info(f"SubstitutionHandler params: recipe_name='{self.recipe_name}', dietary_need='{self.dietary_need}', unavailable_ingredient='{self.unavailable_ingredient}'")
            
            # Step 1: Search for recipes - use recipe_name if available, otherwise use the query
            search_query = self.recipe_name if self.recipe_name else self.handler.query
            logger.info(f"Searching for recipes based on query: {search_query}")
            
            client = get_vector_db_client(query_params=self.handler.query_params)
            candidate_items = await client.search(search_query, self.handler.site)
            
            logger.info(f"Found {len(candidate_items) if candidate_items else 0} recipes from search")
            
            recipe_details = None
            if candidate_items and len(candidate_items) > 0:
                # Collect recipes and check if they need substitutions
                recipe_details = {
                    'recipes': []
                }
                
                # Get up to 3 relevant recipes
                for i, item in enumerate(candidate_items[:3]):
                    if isinstance(item, list) and len(item) >= 3:
                        recipe_info = {
                            'url': item[0],
                            'schema_object': json.loads(item[1]) if isinstance(item[1], str) else item[1],
                            'name': item[2]
                        }
                        recipe_details['recipes'].append(recipe_info)
                        logger.info(f"Found recipe: {item[2]} - {item[0]}")
                
                # Step 2: Check if substitutions are needed
                needs_substitution = await self._check_if_substitution_needed(recipe_details)
                
                if needs_substitution:
                    # Step 3: Generate substitution suggestions
                    await self._generate_substitutions(recipe_details)
                else:
                    await self._send_no_substitution_needed_message(recipe_details)
            
            else:
                # No recipes found
                await self._send_no_results_message()
                
        except Exception as e:
            logger.error(f"Error in SubstitutionHandler.do(): {e}")
            await self._send_error_message(str(e))
    
    async def _check_if_substitution_needed(self, recipe_details):
        """Check if the retrieved recipes need substitutions based on user requirements."""
        # For now, always assume substitutions are needed if we have dietary needs or unavailable ingredients
        if self.dietary_need or self.unavailable_ingredient:
            return True
        
        # If user is asking about substitutions in general, return True
        query_lower = self.handler.query.lower()
        substitution_keywords = ['substitute', 'instead', 'replace', 'without', 'dairy-free', 
                                'gluten-free', 'vegan', 'egg-free', 'nut-free']
        
        return any(keyword in query_lower for keyword in substitution_keywords)
    
    async def _generate_substitutions(self, recipe_details=None):
        """Generate substitution suggestions using LLM."""
        
        # Store recipe details if available
        recipe_info_list = []
        
        # Build the prompt based on what information we have
        prompt_parts = ["Generate ingredient substitution suggestions for the following request:\n"]
        
        if recipe_details and 'recipes' in recipe_details:
            # Handle multiple recipes
            prompt_parts.append("\nReference Recipes:\n")
            
            for i, recipe in enumerate(recipe_details['recipes']):
                # Store full recipe info
                recipe_info = {
                    'name': recipe['name'],
                    'url': recipe['url'],
                    'schema_object': recipe.get('schema_object')
                }
                recipe_info_list.append(recipe_info)
                
                schema_obj = recipe.get('schema_object')
                if isinstance(schema_obj, list) and schema_obj:
                    schema_obj = schema_obj[0]
                
                ingredients = schema_obj.get('recipeIngredient', []) if schema_obj else []
                
                prompt_parts.append(f"\n{i+1}. {recipe['name']}\n")
                if ingredients:
                    prompt_parts.append(f"   Ingredients: {', '.join(ingredients[:10])}...\n" if len(ingredients) > 10 else f"   Ingredients: {', '.join(ingredients)}\n")
                
        elif self.recipe_name:
            prompt_parts.append(f"\nRecipe: {self.recipe_name}\n")
        
        # Add specific substitution request details
        if self.dietary_need:
            prompt_parts.append(f"Dietary Need: {self.dietary_need}\n")
        if self.unavailable_ingredient:
            prompt_parts.append(f"Ingredient to Substitute: {self.unavailable_ingredient}\n")
        if self.preference:
            prompt_parts.append(f"Preference: {self.preference}\n")
        
        # Add request for comprehensive substitution advice
        prompt_parts.append("""
Please provide:
1. Specific substitution suggestions for the ingredients mentioned
2. General tips for the dietary need or substitution type
3. Any adjustments needed to cooking method or quantities
4. Potential impact on taste and texture
5. Common substitutions for this type of modification

Be specific and practical in your suggestions.""")
        
        prompt = "".join(prompt_parts)
        
        # Define the structure for the response
        response_structure = {
            "substitutions": [
                {
                    "original_ingredient": "string",
                    "substitute": "string",
                    "ratio": "string (e.g., '1:1', '3/4 cup for 1 cup')",
                    "notes": "string"
                }
            ],
            "general_tips": "string",
            "cooking_adjustments": "string",
            "taste_texture_impact": "string",
            "additional_suggestions": "string"
        }
        
        try:
            # Get substitution suggestions from LLM
            logger.info("Generating substitution suggestions")
            response = await ask_llm(prompt, response_structure, level="high", query_params=self.handler.query_params)
            
            # Send the substitution suggestions
            await self._send_substitution_message(response, recipe_info_list)
            
        except Exception as e:
            logger.error(f"Error generating substitutions: {e}")
            await self._send_error_message("Could not generate substitution suggestions")
    
    async def _send_substitution_message(self, substitution_data, recipe_info_list=None):
        """Send the substitution suggestions to the client."""
        
        # Format the message as HTML
        message_parts = []
        
        # Add header based on the request
        if self.recipe_name and self.dietary_need:
            message_parts.append(f"<h2>Substitutions for making {self.recipe_name} {self.dietary_need}</h2>")
        elif self.recipe_name and self.unavailable_ingredient:
            message_parts.append(f"<h2>Substituting {self.unavailable_ingredient} in {self.recipe_name}</h2>")
        elif self.dietary_need:
            message_parts.append(f"<h2>{self.dietary_need.title()} Substitutions</h2>")
        else:
            message_parts.append("<h2>Ingredient Substitutions</h2>")
        
        # Add specific substitutions
        if substitution_data.get('substitutions'):
            message_parts.append("<h3>Specific Substitutions</h3>")
            message_parts.append("<ul>")
            for sub in substitution_data['substitutions']:
                original = sub.get('original_ingredient', '')
                substitute = sub.get('substitute', '')
                ratio = sub.get('ratio', '')
                notes = sub.get('notes', '')
                
                if original and substitute:
                    message_parts.append("<li>")
                    message_parts.append(f"<strong>{original}</strong> → {substitute}")
                    if ratio and ratio != '1:1':
                        message_parts.append(f" ({ratio})")
                    if notes:
                        message_parts.append(f"<br><em>{notes}</em>")
                    message_parts.append("</li>")
            message_parts.append("</ul>")
        
        # Add other sections
        if substitution_data.get('general_tips'):
            message_parts.append("<h3>General Tips</h3>")
            message_parts.append(f"<p>{substitution_data['general_tips']}</p>")
        
        if substitution_data.get('cooking_adjustments'):
            message_parts.append("<h3>Cooking Adjustments</h3>")
            message_parts.append(f"<p>{substitution_data['cooking_adjustments']}</p>")
        
        if substitution_data.get('taste_texture_impact'):
            message_parts.append("<h3>Impact on Taste & Texture</h3>")
            message_parts.append(f"<p>{substitution_data['taste_texture_impact']}</p>")
        
        if substitution_data.get('additional_suggestions'):
            message_parts.append("<h3>Additional Suggestions</h3>")
            message_parts.append(f"<p>{substitution_data['additional_suggestions']}</p>")
        
        message = {
            "message_type": "substitution_suggestions",
            "content": "".join(message_parts),
            "substitution_data": substitution_data
        }
        
        # Add full recipe information if available
        if recipe_info_list:
            message["reference_recipes"] = recipe_info_list
        
        await self.handler.send_message(message)
    
    async def _send_error_message(self, error_msg):
        """Send an error message to the client."""
        message = {
            "message_type": "error",
            "message": f"Could not generate substitution suggestions: {error_msg}"
        }
        
        await self.handler.send_message(message)
    
    async def _send_no_results_message(self):
        """Send message when no recipes are found."""
        message = {
            "message_type": "no_results",
            "message": f"No recipes found for: {self.handler.query}"
        }
        
        await self.handler.send_message(message)
    
    async def _send_no_substitution_needed_message(self, recipe_details):
        """Send message when recipes already meet requirements."""
        message_parts = [f"# Recipe Recommendations\n\n"]
        message_parts.append("The following recipes already meet your requirements:\n\n")
        
        if recipe_details and 'recipes' in recipe_details:
            for recipe in recipe_details['recipes']:
                message_parts.append(f"- [{recipe['name']}]({recipe['url']})\n")
        
        message = {
            "message_type": "substitution_suggestions",
            "content": "".join(message_parts),
            "substitution_data": {"message": "No substitutions needed"},
            "reference_recipes": recipe_details['recipes'] if recipe_details else []
        }
        
        await self.handler.send_message(message)