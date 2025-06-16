# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Substitution Handler for finding ingredient substitutions in recipes.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from llm.llm import ask_llm
from utils.logging_config_helper import get_configured_logger
from retrieval.retriever import get_vector_db_client
from core.item_details import ItemDetails

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
            # Step 1: Find the recipe if a specific recipe is mentioned
            recipe_details = None
            if self.recipe_name:
                logger.info(f"Finding recipe: {self.recipe_name}")
                # Use ItemDetails to find the specific recipe
                item_details = ItemDetails(self.handler)
                item_details.item_name = self.recipe_name
                item_details.details_requested = "ingredients and instructions"
                
                # Get candidate items
                client = get_vector_db_client(query_params=self.handler.query_params)
                candidate_items = await client.search(self.recipe_name, self.handler.site)
                
                if candidate_items:
                    # Find the best matching recipe
                    await item_details.rankAndSendItems(candidate_items)
                    # Get the top result if any
                    if hasattr(item_details, 'rankedAnswers') and item_details.rankedAnswers:
                        best_match = max(item_details.rankedAnswers, key=lambda x: x.get('ranking', {}).get('score', 0))
                        if best_match.get('ranking', {}).get('score', 0) > 70:
                            recipe_details = best_match
            
            # Step 2: Generate substitution suggestions
            await self._generate_substitutions(recipe_details)
            
        except Exception as e:
            logger.error(f"Error in SubstitutionHandler.do(): {e}")
            await self._send_error_message(str(e))
    
    async def _generate_substitutions(self, recipe_details=None):
        """Generate substitution suggestions using LLM."""
        
        # Build the prompt based on what information we have
        prompt_parts = ["Generate ingredient substitution suggestions for the following request:\n"]
        
        if recipe_details:
            recipe_info = recipe_details.get('ranking', {}).get('item_details', '')
            if not recipe_info and recipe_details.get('schema_object'):
                # Extract recipe info from schema object
                schema_obj = recipe_details['schema_object']
                if isinstance(schema_obj, list) and schema_obj:
                    schema_obj = schema_obj[0]
                    
                ingredients = schema_obj.get('recipeIngredient', [])
                instructions = schema_obj.get('recipeInstructions', [])
                
                recipe_info = f"Recipe: {self.recipe_name}\n"
                if ingredients:
                    recipe_info += f"Ingredients: {', '.join(ingredients)}\n"
                if instructions:
                    recipe_info += f"Instructions: {len(instructions)} steps\n"
            
            if recipe_info:
                prompt_parts.append(f"\nRecipe Context:\n{recipe_info}\n")
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
            response = await ask_llm(prompt, response_structure, level="high")
            
            # Send the substitution suggestions
            await self._send_substitution_message(response)
            
        except Exception as e:
            logger.error(f"Error generating substitutions: {e}")
            await self._send_error_message("Could not generate substitution suggestions")
    
    async def _send_substitution_message(self, substitution_data):
        """Send the substitution suggestions to the client."""
        
        # Format the message
        message_parts = []
        
        # Add header based on the request
        if self.recipe_name and self.dietary_need:
            message_parts.append(f"# Substitutions for making {self.recipe_name} {self.dietary_need}\n")
        elif self.recipe_name and self.unavailable_ingredient:
            message_parts.append(f"# Substituting {self.unavailable_ingredient} in {self.recipe_name}\n")
        elif self.dietary_need:
            message_parts.append(f"# {self.dietary_need.title()} Substitutions\n")
        else:
            message_parts.append("# Ingredient Substitutions\n")
        
        # Add specific substitutions
        if substitution_data.get('substitutions'):
            message_parts.append("## Specific Substitutions\n")
            for sub in substitution_data['substitutions']:
                original = sub.get('original_ingredient', '')
                substitute = sub.get('substitute', '')
                ratio = sub.get('ratio', '')
                notes = sub.get('notes', '')
                
                if original and substitute:
                    message_parts.append(f"- **{original}** → {substitute}")
                    if ratio and ratio != '1:1':
                        message_parts.append(f" ({ratio})")
                    if notes:
                        message_parts.append(f"\n  *{notes}*")
                    message_parts.append("\n")
        
        # Add other sections
        if substitution_data.get('general_tips'):
            message_parts.append(f"\n## General Tips\n{substitution_data['general_tips']}\n")
        
        if substitution_data.get('cooking_adjustments'):
            message_parts.append(f"\n## Cooking Adjustments\n{substitution_data['cooking_adjustments']}\n")
        
        if substitution_data.get('taste_texture_impact'):
            message_parts.append(f"\n## Impact on Taste & Texture\n{substitution_data['taste_texture_impact']}\n")
        
        if substitution_data.get('additional_suggestions'):
            message_parts.append(f"\n## Additional Suggestions\n{substitution_data['additional_suggestions']}\n")
        
        message = {
            "message_type": "substitution_suggestions",
            "content": "".join(message_parts),
            "substitution_data": substitution_data
        }
        
        await self.handler.send_message(message)
    
    async def _send_error_message(self, error_msg):
        """Send an error message to the client."""
        message = {
            "message_type": "error",
            "message": f"Could not generate substitution suggestions: {error_msg}"
        }
        
        await self.handler.send_message(message)