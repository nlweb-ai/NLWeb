import json
import asyncio
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from misc.logger.logging_config_helper import get_configured_logger
from core.llm import ask_llm
from core.prompts import find_prompt, fill_prompt
from core.config import CONFIG

logger = get_configured_logger("statistics_handler")

@dataclass
class StatisticsQuery:
    query_type: str
    variables: List[str]
    places: List[str]
    filters: Optional[Dict] = None
    time_range: Optional[Dict] = None
    aggregation: Optional[str] = None
    limit: Optional[int] = None
    original_query: str = ""



class StatisticsHandler():
    def __init__(self, params, handler):
        self.handler = handler
        self.params = params
        self.templates = self._load_templates()
        self.dcid_mappings = self._load_dcid_mappings()
        self.sent_message = False
        
    def _load_templates(self) -> List[Dict]:
        """Load query templates from the statistics_templates.txt file."""
        templates = []
        try:
            import os
            # Get templates path from config directory
            templates_path = os.path.join(CONFIG.config_directory, 'statistics_templates.txt')
            with open(templates_path, 'r') as f:
                content = f.read()
                
            # Parse templates from the file
            lines = content.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('-'):
                    # Match lines that start with a number followed by a period
                    if line[0].isdigit() and '.' in line:
                        parts = line.split('.', 1)
                        if len(parts) == 2:
                            template_num = parts[0].strip()
                            template_text = parts[1].strip()
                            
                            # Initialize default values
                            pattern = ""
                            variables_dict = {}
                            visualization_hints = []
                            
                            # Check if there's a third column in square brackets
                            if '[' in template_text and ']' in template_text:
                                bracket_start = template_text.rfind('[')
                                bracket_end = template_text.rfind(']')
                                
                                if bracket_start < bracket_end:
                                    # Extract visualization hints from the third column
                                    viz_hints_str = template_text[bracket_start+1:bracket_end].strip()
                                    
                                    # Parse function-style syntax: func(param1, param2) or just func
                                    if '(' in viz_hints_str and ')' in viz_hints_str:
                                        # Extract function name (visualization type)
                                        func_name = viz_hints_str[:viz_hints_str.index('(')].strip()
                                        # Also store the full hint for title generation
                                        visualization_hints = [func_name, viz_hints_str]
                                    else:
                                        # Simple format without parameters
                                        visualization_hints = [viz_hints_str.strip()]
                                    
                                    # Remove the third column from the template text
                                    template_text = template_text[:bracket_start].strip()
                            
                            # Extract the template pattern and variables
                            if '{' in template_text:
                                pattern_end = template_text.find('{')
                                pattern = template_text[:pattern_end].strip()
                                vars_json_str = template_text[pattern_end:].strip()
                                
                                # Parse the variables JSON
                                try:
                                    # Parse the JSON directly (templates now use proper double quotes)
                                    variables_dict = json.loads(vars_json_str)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Error parsing variables JSON for template {template_num}: {e}")
                                    variables_dict = {}
                            else:
                                # No variables specified
                                pattern = template_text
                                variables_dict = {}
                            
                            # Add score field to all templates
                            variables_dict['score'] = 'integer between 0 and 100'
                                
                            templates.append({
                                'id': template_num,
                                'pattern': pattern,
                                'variables': variables_dict,
                                'visualization_hints': visualization_hints,
                                'original': line
                            })
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
        
        print(f"Loaded {len(templates)} templates from statistics_templates.txt")
        if templates and len(templates) > 0:
            print(f"First template: {templates[0]}")
            print(f"Last template: {templates[-1]}")
            
        return templates
    
    def _load_dcid_mappings(self) -> Dict:
        """Load DCID mappings from the JSON file."""
        try:
            import os
            # Get mappings path from config directory
            mappings_path = os.path.join(CONFIG.config_directory, 'dcid_mappings.json')
            with open(mappings_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading DCID mappings: {e}")
            return {"variables": {}, "place_types": {}}
    
    async def score_template_match(self, user_query: str, template: Dict) -> Tuple[str, int, Dict]:
        """Score how well a template matches the user's query using LLM and extract values."""
        prompt = f"""
        User query: "{user_query}"
        Template pattern: "{template['pattern']}"
        
        Rate how well this template pattern matches the user's query on a scale of 0 to 100.
        Consider semantic similarity, intent match, and whether the template could answer the query.
        
        For example:
        - If the query perfectly matches the template pattern, return 100
        - If the query is similar but not exact, return 70-90
        - If the query doesn't match at all, return 0-30
        
        If the template score is 70 or higher, also extract the specific values 
        from the user's query that match the template variables and fill them in the return structure.
        """
        
        try:
            # Pass the template variables (which now includes score) directly to LLM
            response = await ask_llm(prompt, template['variables'], level="low", query_params=self.handler.query_params)
            
            # Extract the score and values from the response
            score = 0
            extracted_values = {}
            
            if isinstance(response, dict):
                score = int(response.get('score', 0))
                # Get all fields except score as the extracted values
                extracted_values = {k: v for k, v in response.items() if k != 'score'}
            
            # Don't print individual scores - we'll show top 3 later
            logger.info(f"Template {template['id']} scored {score} for query '{user_query}'")
            return (template['id'], min(max(score, 0), 100), extracted_values)
        except Exception as e:
            logger.error(f"Error scoring template {template['id']}: {e}, response was: {response if 'response' in locals() else 'N/A'}")
            return (template['id'], 0, {})
    
    async def match_templates(self, query: str, threshold: int = 70) -> List[Dict]:
        """Find templates that match the user's query above the threshold."""
        logger.info(f"Matching query '{query}' against {len(self.templates)} templates")
        
        if not self.templates:
            logger.error("No templates loaded!")
            return []
            
        # Create tasks for parallel template matching
        tasks = []
        for template in self.templates:
            task = self.score_template_match(query, template)
            tasks.append(task)
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks)
        
        # Filter templates above threshold
        matched_templates = []
        for (template_id, score, extracted_values) in results:
            if score >= threshold:
                # Find the template by ID
                for template in self.templates:
                    if template['id'] == template_id:
                        matched_templates.append({
                            'template': template,
                            'score': score,
                            'extracted_values': extracted_values
                        })
                        logger.info(f"Template {template_id} matched with score {score}: {template['pattern']}")
                        break
        
        # Sort by score descending
        matched_templates.sort(key=lambda x: x['score'], reverse=True)
        logger.info(f"Found {len(matched_templates)} matching templates above threshold {threshold}")
        
        # Print top 3 template scores sorted by score
        print("\nTop 3 matching templates:")
        all_template_scores = []
        for (template_id, score, extracted_values) in results:
            template = next((t for t in self.templates if t['id'] == template_id), None)
            if template:
                all_template_scores.append((score, template_id, template['pattern']))
        
        all_template_scores.sort(reverse=True)
        for i, (score, tid, pattern) in enumerate(all_template_scores[:3]):
            print(f"  {i+1}. Template {tid}: {score} - '{pattern}'")
        
        return matched_templates
    
    
    async def map_to_dcids(self, variables: List[str], places: List[str]) -> Tuple[List[str], List[str]]:
        """Map variable and place names to Data Commons DCIDs."""
        # Create tasks for parallel processing
        variable_tasks = []
        place_tasks = []
        
        # Create tasks for mapping variables
        for var in variables:
            var_lower = var.lower()
            dcid = self.dcid_mappings['variables'].get(var_lower)
            if dcid:
                # Direct mapping found, create a completed task
                async def return_dcid(dcid=dcid):
                    return dcid
                variable_tasks.append(asyncio.create_task(return_dcid()))
            else:
                # Use LLM to find closest match
                prompt = f"""
                Variable: "{var}"
                Available DCIDs: {json.dumps(self.dcid_mappings['variables'], indent=2)}
                
                Find the best matching DCID for this variable. Return only the DCID value.
                If no good match exists, return "UNKNOWN".
                """
                # Create async task for LLM call
                async def get_variable_dcid(prompt=prompt):
                    response = await ask_llm(prompt, {"dcid": "string"}, level="low", query_params=self.handler.query_params)
                    response = response.get('dcid', 'UNKNOWN') if isinstance(response, dict) else str(response).strip()
                    return response if response.strip() != "UNKNOWN" else None
                
                variable_tasks.append(asyncio.create_task(get_variable_dcid()))
        
        # Create tasks for mapping places
        for place in places:
            # Handle common cases directly
            place_lower = place.lower()
            if place_lower in ["us", "usa", "united states", "america", "us counties"]:
                async def return_usa(p=place):
                    return (p, "country/USA")
                place_tasks.append(asyncio.create_task(return_usa()))
                continue
                
            prompt = f"""
            Place name: "{place}"
            
            Convert this place name to a Data Commons place DCID. Common patterns:
            - US States: geoId/01 (Alabama), geoId/06 (California), geoId/48 (Texas)
            - US Counties: geoId/06075 (San Francisco County, CA), geoId/06037 (Los Angeles County, CA)
            - US Cities: geoId/0644000 (Los Angeles city, CA), geoId/0667000 (San Francisco city, CA)
            - Countries: country/USA, country/CAN, country/MEX
            
            Special mappings:
            - "US", "USA", "United States" → country/USA
            
            Return just the DCID in the format geoId/XXXXX or country/XXX.
            If unsure, return just the FIPS code of the place.
            """
            
            # Create async task for LLM call
            async def get_place_dcid(place=place, prompt=prompt):
                response = await ask_llm(prompt, {"dcid": "string"}, level="low", query_params=self.handler.query_params)
                dcid = response.get('dcid', '') if isinstance(response, dict) else str(response).strip()
                
                # Fallback to simple heuristic if LLM fails
                if not dcid or dcid == "UNKNOWN":
                    if "us counties" in place.lower():
                        # For generic "US counties", return country/USA
                        dcid = "country/USA"
                    elif "county" in place.lower():
                        place_name = place.lower().replace(" county", "").strip()
                        dcid = f"geoId/{place_name}"
                    else:
                        dcid = place
                        
                return (place, dcid)
            
            place_tasks.append(asyncio.create_task(get_place_dcid()))
        
        # Execute all tasks in parallel
        variable_results = await asyncio.gather(*variable_tasks) if variable_tasks else []
        place_results = await asyncio.gather(*place_tasks) if place_tasks else []
        
        # Process results
        variable_dcids = [dcid for dcid in variable_results if dcid is not None]
        
        place_dcids = []
        for place_result in place_results:
            if isinstance(place_result, tuple):
                place, dcid = place_result
                place_dcids.append(dcid)
                print(f"  Place '{place}' -> DCID '{dcid}'")
            else:
                place_dcids.append(place_result)
        
        return variable_dcids, place_dcids
    
    def determine_visualization_type(self, template_hints: List[str]) -> Optional[str]:
        """Return the visualization type from template hints."""
        
        if template_hints and len(template_hints) > 0:
            # Return the first hint directly (without 'datacommons-' prefix)
            return template_hints[0]
        
        # Return None if no hints provided
        return None
    
    def generate_title_from_hint(self, template_hints: List[str], extracted_values: Dict, 
                                 variable_dcids: List[str], place_dcids: List[str]) -> str:
        """Generate a descriptive title from visualization hints and actual DCID values."""
        
        if not template_hints or len(template_hints) == 0:
            return ""
        
        # Get the visualization type
        viz_type = template_hints[0]
        
        # Generate title based on visualization type using actual DCIDs
        if viz_type == 'ranking':
            # Ranking of [variable] by [place_type]
            variable = variable_dcids[0] if variable_dcids else "metric"
            # Determine place type from extracted values or places
            place_type = extracted_values.get('place_type', extracted_values.get('place-type', 'regions'))
            if 'place' in extracted_values:
                place = extracted_values.get('place')
                return f"Ranking of {variable} by {place_type} in {place}"
            return f"Ranking of {variable} by {place_type}"
            
        elif viz_type == 'map':
            # Map of [variable] across [place_type]
            variable = variable_dcids[0] if variable_dcids else "metric"
            place_type = extracted_values.get('place_type', extracted_values.get('place-type', 'counties'))
            return f"Map of {variable} across {place_type}"
            
        elif viz_type == 'bar':
            # Comparison of [variable]: [place1] vs [place2]
            variable = variable_dcids[0] if variable_dcids else "metric"
            # For bar charts, we should use the actual place names from extracted values
            if 'county_a' in extracted_values and 'county_b' in extracted_values:
                return f"Comparison of {variable}: {extracted_values['county_a']} vs {extracted_values['county_b']}"
            elif len(place_dcids) >= 2:
                # Use place DCIDs if we have them
                return f"Comparison of {variable}"
            return f"Comparison of {variable}"
            
        elif viz_type == 'line':
            # Trend of [variable] over time
            variable = variable_dcids[0] if variable_dcids else "metric"
            # For line charts, typically show trend over time
            return f"Trend of {variable} over time"
            
        elif viz_type == 'scatter':
            # Correlation: [variable1] vs [variable2] across [place_type]
            if len(variable_dcids) >= 2:
                variable1 = variable_dcids[0]
                variable2 = variable_dcids[1]
            else:
                variable1 = variable_dcids[0] if variable_dcids else 'Variable 1'
                variable2 = 'Variable 2'
            place_type = extracted_values.get('place_type', extracted_values.get('place-type', 'regions'))
            return f"Correlation: {variable1} vs {variable2} across {place_type}"
            
        elif viz_type == 'highlight':
            # [variable] in [place]
            variable = variable_dcids[0] if variable_dcids else extracted_values.get('variable', 'metric')
            # For highlight, use the extracted place name if available
            place = extracted_values.get('place', 'location')
            return f"{variable} in {place}"
        
        # Default: use visualization type as title
        return viz_type.capitalize()
    
    async def process_template(self, match: Dict, query: str) -> Optional[Dict]:
        """Process a single template match."""
        if match['score'] < 70:
            return None
            
        template = match['template']
        
        # Skip templates without visualization hints
        if not template.get('visualization_hints'):
            print(f"  Template {template['id']} - Skipping - no visualization hints")
            return None
            
        extracted_values = match.get('extracted_values', {})
        # Check for empty lists in extracted values
        if any(isinstance(v, list) and not v for v in extracted_values.values()):
            print(f"  Template {template['id']} - Skipping - empty list found in extracted values")
            return None
            
        # Check if all required template parameters have been properly extracted
        # A parameter is required if it's defined in the template variables
        template_vars = template.get('variables', {})
        for var_name in template_vars.keys():
            if var_name == 'score':  # Skip the score field
                continue
            # Check if the variable was extracted and has a meaningful value
            if var_name not in extracted_values or not extracted_values[var_name]:
                print(f"  Template {template['id']} - Skipping - missing required parameter '{var_name}'")
                return None
            # Check for placeholder values that indicate failed extraction
            value = str(extracted_values[var_name]).strip()
            if value in ['US', 'US counties', 'counties'] and var_name == 'place' and template['id'] == '7':
                # For template 7, "US" alone is not a valid specific place
                print(f"  Template {template['id']} - Skipping - '{var_name}' has generic value '{value}'")
                return None
            
        print(f"\nProcessing template {template['id']} (score: {match['score']}): {template['pattern']}")
        print(f"  Extracted values: {extracted_values}")
        
        try:
            # Extract variables and places from the extracted values
            variables = []
            places = []
            
            # Check if all required template variables have valid values
            # Skip templates with placeholder/invalid values
            # These are generic placeholders that indicate extraction failure
            invalid_placeholders = {'<variable1>', '<variable2>', '<place>', '<county>', 
                                  '<state>', '<city>', '<variable>', '<place-type>', ''}
            
            has_invalid = False
            for key, value in extracted_values.items():
                # Check if the value is invalid or a placeholder
                if not value or str(value).strip() in invalid_placeholders or str(value).startswith('<'):
                    print(f"  Template {template['id']} - Skipping - invalid/placeholder value for {key}: '{value}'")
                    has_invalid = True
                    break
                
                # For place-type parameters, valid values include: county, state, city, zip code, etc.
                # These should NOT be considered invalid
                
                if 'variable' in key.lower():
                    variables.append(value)
                elif 'place-type' in key.lower() or 'place_type' in key.lower():
                    # This is a place type (e.g., "counties", "states"), not a place
                    # Don't add to places list - it will be used for childPlaceType parameter
                    pass
                elif any(place_name in key.lower() for place_name in ['county', 'place', 'state', 'city', 'containing']):
                    places.append(value)
            
            # Skip this template if it has invalid values
            if has_invalid:
                return None
            
            print(f"  Template {template['id']} - Variables: {variables}, Places: {places}")
            
            # Map to DCIDs (this is already parallelized internally)
            variable_dcids, place_dcids = await self.map_to_dcids(variables, places)
            print(f"  Template {template['id']} - DCIDs - Variables: {variable_dcids}, Places: {place_dcids}")
            
            # Skip if we couldn't extract any variables
            if not variable_dcids:
                print(f"  Template {template['id']} - Skipping - no variables extracted")
                return None
            
            # Default to US if no places extracted for correlation queries
            if not place_dcids and query_type in ['correlation', 'comparison', 'ranking']:
                place_dcids = ['country/USA']
                print(f"  Template {template['id']} - Defaulting to US for place")
            
            # Step 4: Determine visualization type
            template_hints = template.get('visualization_hints', [])
            viz_type = self.determine_visualization_type(template_hints)
            
            if viz_type is None:
                print(f"  Template {template['id']} - Skipping - no visualization type determined")
                return None
                
            print(f"  Template {template['id']} - Visualization type: {viz_type}")
            
            # Step 5: Create web component
            additional_params = {}
            if 'limit' in self.params and self.params['limit']:
                additional_params['limit'] = self.params['limit']
            
            # Generate title from visualization hints and actual DCIDs
            title = self.generate_title_from_hint(template_hints, extracted_values, variable_dcids, place_dcids)
            
            # If title generation failed or returned empty, use a fallback
            if not title:
                title = f"{viz_type.capitalize()} visualization"
                
            component_html = self.create_web_component(
                viz_type,
                place_dcids,
                variable_dcids,
                title=title,
                query_params=additional_params
            )
            
            print(f"  Template {template['id']} - Generated: {component_html}")
            
            # Return component info
            return {
                'template': template,
                'score': match['score'],
                'variables': variables,
                'places': places,
                'variable_dcids': variable_dcids,
                'place_dcids': place_dcids,
                'viz_type': viz_type,
                'html': component_html,
                'title': title,
                'component_key': f"{viz_type}|{','.join(sorted(variable_dcids))}|{','.join(sorted(place_dcids))}"
            }
            
        except Exception as e:
            logger.error(f"Error processing template {template['id']}: {e}")
            print(f"  Template {template['id']} - Error: {e}")
            return None
    
    def create_web_component(self, component_type: str, places: List[str], variables: List[str], 
                           title: str = "", query_params: Optional[Dict] = None) -> str:
        """Create the HTML for a Data Commons web component."""
        # Add 'datacommons-' prefix to component type
        component_type = f'datacommons-{component_type}'
        
        # Convert lists to space-separated strings (Data Commons web components use spaces, not commas)
        places_str = ' '.join(places) if places else ""
        variables_str = ' '.join(variables) if variables else ""
        
        # Build the component HTML based on component type
        component_html = f'<{component_type}'
        
        # Always add header if provided
        if title:
            component_html += f' header="{title}"'
        
        # Handle different component types with their specific attributes
        if component_type == 'datacommons-line':
            # Line chart: can use either 'places' OR 'parentPlace/childPlaceType'
            # For queries about specific places, use places attribute
            # For "across counties/states" queries, use parentPlace/childPlaceType
            if len(places) == 0 or any('counties' in p.lower() or 'us' in p.lower() for p in places):
                # Use parentPlace/childPlaceType for aggregate queries
                component_html += f' parentPlace="country/USA"'
                component_html += f' childPlaceType="County"'
            elif len(places) > 1 or (len(places) == 1 and 'geoId' in places[0]):
                # Multiple specific places or specific place DCIDs
                component_html += f' places="{places_str}"'
            elif len(places) == 1:
                # Single place that might be a parent - check if it's a state/country
                if places[0].startswith('country/') or places[0].startswith('geoId/') and len(places[0].split('/')[1]) == 2:
                    # It's a country or state - use as parentPlace
                    component_html += f' parentPlace="{places[0]}"'
                    component_html += f' childPlaceType="County"'
                else:
                    # It's a specific place
                    component_html += f' places="{places_str}"'
            if variables_str:
                component_html += f' variables="{variables_str}"'
                
        elif component_type == 'datacommons-bar':
            # Bar chart: can use 'places' OR parentPlace/childPlaceType
            if places_str:
                component_html += f' places="{places_str}"'
            if variables_str:
                component_html += f' variables="{variables_str}"'
                
        elif component_type == 'datacommons-scatter':
            # Scatter plot: needs exactly 2 variables and uses parentPlace/childPlaceType
            # For "across US counties" queries, use country/USA as parent and County as child type
            if len(places) == 0 or any('counties' in p.lower() or 'us' in p.lower() for p in places):
                # Default to US counties when no specific place or US mentioned
                component_html += f' parentPlace="country/USA"'
                component_html += f' childPlaceType="County"'
            elif len(places) == 1:
                # If we have a specific state/place, use it as parent
                component_html += f' parentPlace="{places[0]}"'
                component_html += f' childPlaceType="County"'
            if variables_str:
                component_html += f' variables="{variables_str}"'
                
        elif component_type == 'datacommons-map':
            # Map: uses 'variable' (singular) and parentPlace/childPlaceType
            # For "across US counties" queries, use country/USA as parent and County as child type
            if len(places) == 0 or any('counties' in p.lower() or 'us' in p.lower() for p in places):
                # Default to US counties when no specific place or US mentioned
                component_html += f' parentPlace="country/USA"'
                component_html += f' childPlaceType="County"'
            elif len(places) == 1:
                # If we have a specific state/place, use it as parent
                component_html += f' parentPlace="{places[0]}"'
                component_html += f' childPlaceType="County"'  # Default to County
            if variables:
                component_html += f' variable="{variables[0]}"'  # Map uses singular 'variable'
                
        elif component_type == 'datacommons-ranking':
            # Ranking: uses parentPlace/childPlaceType and 'variable' (singular)
            # For "across US counties" queries, use country/USA as parent and County as child type
            if len(places) == 0 or any('counties' in p.lower() or 'us' in p.lower() for p in places):
                # Default to US counties when no specific place or US mentioned
                component_html += f' parentPlace="country/USA"'
                component_html += f' childPlaceType="County"'
            elif len(places) == 1:
                # If we have a specific state/place, use it as parent
                component_html += f' parentPlace="{places[0]}"'
                component_html += f' childPlaceType="County"'  # Default to County
            if variables:
                component_html += f' variable="{variables[0]}"'  # Ranking uses singular 'variable'
            # Add ranking count if available in query_params
            if query_params and 'limit' in query_params:
                component_html += f' rankingCount="{query_params["limit"]}"'
                
        elif component_type == 'datacommons-highlight':
            # Highlight: simple display, uses 'place' (singular) and 'variable' (singular)
            if places:
                component_html += f' place="{places[0]}"'  # Highlight uses singular 'place'
            if variables:
                component_html += f' variable="{variables[0]}"'  # Highlight uses singular 'variable'
        
        # Add any additional query parameters
        if query_params:
            for key, value in query_params.items():
                component_html += f' {key}="{value}"'
        
        component_html += f'></{component_type}>'
        
        return component_html
    
    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
            # Get the original query from handler
            query = self.handler.query
            logger.info(f"Statistics handler processing query: '{query}'")
            logger.info(f"Templates available: {len(self.templates)}")
            
            # Step 1: Match templates
            matched_templates = await self.match_templates(query)
            
            if not matched_templates:
                logger.warning(f"No templates matched for query: '{query}'")
                await self._send_error_message("I couldn't match your query to any statistical patterns. Please try rephrasing.")
                return
            
            # Process all templates with score > 70 in parallel
            # Process all templates in parallel
            template_tasks = [self.process_template(match, query) for match in matched_templates]
            template_results = await asyncio.gather(*template_tasks)
            
            # Filter out None results and deduplicate
            all_components = []
            seen_components = set()
            seen_html = set()  # Track HTML to avoid exact duplicates
            
            for component in template_results:
                if component is None:
                    continue
                    
                # Skip if we've already generated this exact component (by key)
                if component['component_key'] in seen_components:
                    print(f"  Skipping duplicate component by key: {component['component_key']}")
                    continue
                    
                # Also skip if the HTML is exactly the same
                if component['html'] in seen_html:
                    print(f"  Skipping duplicate component with identical HTML")
                    continue
                    
                seen_components.add(component['component_key'])
                seen_html.add(component['html'])
                # Remove the component_key from the stored data
                del component['component_key']
                all_components.append(component)
            
            if not all_components:
                logger.warning("No components could be generated")
                await self._send_error_message("I couldn't generate any visualizations for your query.")
                return
            
            print(f"\nGenerated {len(all_components)} components total")
            
            # Create response message with all components
            best_component = all_components[0]  # The highest scoring one
            
            message = {
                "message_type": "statistics_result",
                "@type": "StatisticalAnalysis",
                "content": f"Found {len(all_components)} matching visualizations for your query:",
                "all_components": [
                    {
                        "template_pattern": comp['template']['pattern'],
                        "template_id": comp['template']['id'],
                        "confidence_score": comp['score'],
                        "type": comp['viz_type'],
                        "html": comp['html'],
                        "variables": comp['variable_dcids'],
                        "places": comp['place_dcids'],
                        "title": comp.get('title', '')
                    }
                    for comp in all_components
                ],
                "data_commons_component": {
                    "type": best_component['viz_type'],
                    "html": best_component['html'],
                    "places": best_component['place_dcids'],
                    "variables": best_component['variable_dcids'],
                    "script": '<script src="https://datacommons.org/datacommons.js"></script>',
                    "embed_instructions": "To embed this component, include the script tag and the HTML component in your page."
                },
                "metadata": {
                    "total_matches": len(all_components),
                    "templates_used": [
                        {
                            "pattern": comp['template']['pattern'],
                            "id": comp['template']['id'],
                            "score": comp['score']
                        }
                        for comp in all_components
                    ]
                }
            }
            
            # Send the message
            asyncio.create_task(self.handler.send_message(message))
            
            # Also send a chart result message with all components
            all_html = []
            for i, comp in enumerate(all_components):
                html_section = f"""
<!-- Component {i+1}: {comp['template']['pattern']} (score: {comp['score']}) -->
{comp['html']}
"""
                all_html.append(html_section.strip())
            
            chart_message = {
                "message_type": "chart_result",
                "@type": "DataVisualization",
                "html": f"""
<!-- Data Commons Web Components ({len(all_components)} visualizations) -->
{chr(10).join(all_html)}

<!-- Required Script -->
<script src="https://datacommons.org/datacommons.js"></script>

<!-- Total Components: {len(all_components)} -->
""".strip()
            }
            asyncio.create_task(self.handler.send_message(chart_message))
            
            self.sent_message = True
            
        except Exception as e:
            logger.error(f"Error in statistics handler: {e}")
            await self._send_error_message(f"An error occurred while processing your statistical query: {str(e)}")
    
    async def _send_error_message(self, error_text: str):
        """Send an error message to the user."""
        if not self.sent_message:
            asyncio.create_task(self.handler.send_message({
                "message_type": "error",
                "content": error_text,
                "error": True
            }))
            self.sent_message = True