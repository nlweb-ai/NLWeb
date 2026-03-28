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
        # Create reverse mapping for converting DCIDs back to human-readable names
        self.dcid_to_human_map = self._create_reverse_dcid_mapping()
        
    def _load_templates(self) -> List[Dict]:
        """Load query templates from the statistics_templates.txt file."""
        templates = []
        try:
            import os
            # Get templates path from config directory
            templates_path = os.path.join(CONFIG.config_directory, 'statistics_templates.txt')
            with open(templates_path, 'r') as f:
                content = f.read()

            # Parse the JSON array
            templates = json.loads(content)

            # Add an ID to each template based on its position
            for idx, template in enumerate(templates):
                template['id'] = str(idx + 1)
                # Ensure score field exists in extract
                if 'extract' in template and 'score' not in template['extract']:
                    template['extract']['score'] = 'score'

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing templates JSON: {e}")
        except Exception as e:
            logger.error(f"Error loading templates: {e}")

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

    def _create_reverse_dcid_mapping(self) -> Dict[str, str]:
        """Create a reverse mapping from DCIDs to human-readable names."""
        reverse_map = {}

        if self.dcid_mappings and 'variables' in self.dcid_mappings:
            for human_name, dcid in self.dcid_mappings['variables'].items():
                # Store the reverse mapping
                reverse_map[dcid] = human_name

        return reverse_map

    def dcid_to_human_readable(self, dcid: str) -> str:
        """Convert a DCID to a human-readable name.

        Falls back to cleaning up the DCID if no mapping exists.
        """
        # Check if we have a mapping for this DCID
        if dcid in self.dcid_to_human_map:
            return self.dcid_to_human_map[dcid]

        # Fallback: clean up the DCID
        # Remove common prefixes
        cleaned = dcid
        for prefix in ['Count_', 'Percent_', 'Median_', 'Mean_', 'Total_']:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break

        # Replace underscores with spaces and convert to lowercase
        cleaned = cleaned.replace('_', ' ').lower()

        # Handle common patterns
        cleaned = cleaned.replace('person with', 'with')
        cleaned = cleaned.replace('person ', '')

        return cleaned

    def map_place_type_to_dcid(self, place_type: str) -> str:
        """Map a place type string to its Data Commons DCID format.

        This uses an algorithmic approach to handle variations and plurals.
        """
        if not place_type:
            return "Place"

        # Normalize the input
        normalized = place_type.lower().strip()

        # Remove common suffixes and normalize to singular
        # Handle plurals by removing 's' or 'ies' endings
        if normalized.endswith('ies'):
            # cities -> city, counties -> county
            normalized = normalized[:-3] + 'y'
        elif normalized.endswith('es'):
            # states -> state (but keep 'states' as special case)
            if normalized != 'states':
                normalized = normalized[:-2]
            else:
                normalized = 'state'
        elif normalized.endswith('s') and len(normalized) > 3:
            # Remove trailing 's' for simple plurals
            normalized = normalized[:-1]

        # Map common variations to standard Data Commons types
        place_type_mapping = {
            # Administrative divisions
            'country': 'Country',
            'state': 'State',
            'county': 'County',
            'city': 'City',
            'town': 'Town',
            'village': 'Village',
            'borough': 'Borough',
            'municipality': 'Municipality',
            'parish': 'Parish',

            # Statistical areas
            'metro': 'MetroArea',
            'metro area': 'MetroArea',
            'metropolitan area': 'MetroArea',
            'metropolitan statistical area': 'MetroArea',
            'msa': 'MetroArea',
            'micropolitan area': 'MicroArea',
            'micropolitan statistical area': 'MicroArea',
            'statistical area': 'StatisticalArea',

            # Geographic regions
            'region': 'Region',
            'district': 'District',
            'province': 'Province',
            'territory': 'Territory',
            'division': 'Division',
            'subdivision': 'Subdivision',

            # Postal/Census areas
            'zip': 'ZipCode',
            'zip code': 'ZipCode',
            'zipcode': 'ZipCode',
            'postal code': 'PostalCode',
            'census tract': 'CensusTract',
            'tract': 'CensusTract',
            'census block': 'CensusBlock',
            'block': 'Block',
            'census designated place': 'CensusDesignatedPlace',
            'cdp': 'CensusDesignatedPlace',

            # School districts
            'school district': 'SchoolDistrict',
            'elementary school district': 'ElementarySchoolDistrict',
            'secondary school district': 'SecondarySchoolDistrict',
            'unified school district': 'UnifiedSchoolDistrict',

            # Congressional districts
            'congressional district': 'CongressionalDistrict',
            'legislative district': 'LegislativeDistrict',
            'state house district': 'StateHouseDistrict',
            'state senate district': 'StateSenateDistrict',

            # Other
            'neighborhood': 'Neighborhood',
            'place': 'Place',
            'area': 'Area',
            'zone': 'Zone',
            'ward': 'Ward',
            'precinct': 'Precinct'
        }

        # Check if we have a direct mapping
        if normalized in place_type_mapping:
            return place_type_mapping[normalized]

        # Check for compound types (e.g., "us counties" -> "County")
        for key, value in place_type_mapping.items():
            if key in normalized:
                return value

        # If no mapping found, convert to Title Case as fallback
        # This handles custom or unknown place types
        return ''.join(word.capitalize() for word in place_type.split())
    
    async def score_template_match(self, user_query: str, template: Dict) -> Dict:
        """Score how well a template matches the user's query using LLM and extract values."""
        prompt = f"""
        The user is trying to get an answer from a statistical database. The user's query is
        "{user_query}".

        We have a set of templates for query patterns. I want you to judge whether the following
        template matches the intent of the query. Provide a score from 0 to 100 for how closely
        answering the template would answer the user's query. If the score is over 75,
        extract the template variables, which are in '<' '>'
        brackets and fill in the attached json structure.

        Template pattern: "{template['template']}

        Associated with the template is the following visualization hint for the chart to
        display the data. Suggest a title for the chart in the attribute charTitle.

        Visualization hint: "{template['action']}"
        """

        # Debug: Show template being evaluated
        # print(f"\nEvaluating template {template['id']}: {template['template']}")

        try:
            # Pass the extract structure to LLM for extraction
            response = await ask_llm(prompt, template['extract'], level="high", query_params=self.handler.query_params)

            # Debug: Show LLM response
            # print(f"Template {template['id']} - Score: {response.get('score', 0)}")

            return response
        except Exception as e:
            logger.error(f"LLM error for template {template['id']}: {e}")
            return None
    
    async def match_templates(self, query: str, threshold: int = 70) -> List[Dict]:
        """Find templates that match the user's query above the threshold."""

        if not self.templates:
            print("No templates loaded!")
            return []

        # Debug: Starting template matching
        # print(f"\nMatching templates for query: '{query}'")

        # Create tasks for parallel template matching
        tasks = []
        for template in self.templates:
            task = self.score_template_match(query, template)
            tasks.append(task)

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks)

        # Filter templates above threshold
        matched_templates = []
        for i, result in enumerate(results):
            if result and 'score' in result:
                # Convert score to int if it's a string
                try:
                    score = int(result['score']) if isinstance(result['score'], str) else result['score']
                    if score > threshold:
                        matched_templates.append({
                            'score': score,
                            'template': self.templates[i],
                            'extracted_values': result
                        })
                except (ValueError, TypeError) as e:
                    logger.debug(f"Template {self.templates[i]['id']} - Error converting score: {e}")

        # Sort by score descending
        matched_templates.sort(key=lambda x: x['score'], reverse=True)

        # Debug summary
        if matched_templates:
            logger.info(f"Matched {len(matched_templates)} templates for query: '{query}'")
            # Limit to top 3
            if len(matched_templates) > 3:
                matched_templates = matched_templates[:3]
                logger.info(f"Limited to top 3 templates")
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
    
    
    async def map_extracted_values_to_dcids(self, extracted_values: Dict) -> Dict:
        """Map all extracted values to their corresponding DCIDs.

        Returns a dictionary with the same keys but DCID values.
        """
        dcid_mapped = {}

        # Collect all variables and places to map in parallel
        variables_to_map = []
        places_to_map = []
        variable_keys = []
        place_keys = []
        placetype_keys = []

        # Process each extracted value
        for key, value in extracted_values.items():
            if key == 'score':
                # Skip the score field
                dcid_mapped[key] = value
                continue

            # Check if this is a placeType field (special handling)
            if key in ['placeType', 'place_type', 'place-type']:
                placetype_keys.append(key)
                # Use algorithmic mapping for place types
                dcid_mapped[key] = self.map_place_type_to_dcid(value)
            # Check if this is a variable field
            elif 'variable' in key.lower():
                variables_to_map.append(value)
                variable_keys.append(key)
            # Otherwise it's a place field
            else:
                places_to_map.append(value)
                place_keys.append(key)

        # Map all values through the same process
        variable_dcids, place_dcids = await self.map_to_dcids(variables_to_map, places_to_map)

        # Assign mapped DCIDs back to their keys
        for i, key in enumerate(variable_keys):
            dcid_mapped[key] = variable_dcids[i] if i < len(variable_dcids) else extracted_values[key]

        for i, key in enumerate(place_keys):
            dcid_mapped[key] = place_dcids[i] if i < len(place_dcids) else extracted_values[key]

        # Debug: DCID mapping complete
        # for key, value in dcid_mapped.items():
        #     if key != 'score':
        #         print(f"    {key}: '{extracted_values[key]}' → '{dcid_mapped[key]}'")

        return dcid_mapped

    async def process_template(self, match: Dict, query: str) -> Optional[Dict]:
        """Process a single template match."""
        # Ensure score is an integer
        score = int(match['score']) if isinstance(match['score'], str) else match['score']
        if score < 70:
            return None
            
        template = match['template']
        
        # Skip templates without action
        if not template.get('action'):
            # print(f"  Template {template['id']} - Skipping - no action defined")
            return None
            
        extracted_values = match.get('extracted_values', {})
        # Check for empty lists in extracted values
        if any(isinstance(v, list) and not v for v in extracted_values.values()):
            # print(f"  Template {template['id']} - Skipping - empty list found in extracted values")
            return None
            
        # Check if all required template parameters have been properly extracted
        # A parameter is required if it's defined in the template extract
        template_extract = template.get('extract', {})
        for var_name in template_extract.keys():
            if var_name == 'score':  # Skip the score field
                continue
            # Check if the variable was extracted and has a meaningful value
            if var_name not in extracted_values or not extracted_values[var_name]:
                # print(f"  Template {template['id']} - Skipping - missing required parameter '{var_name}'")
                return None
            # Check for placeholder values that indicate failed extraction
            value = str(extracted_values[var_name]).strip()
            if value in ['US', 'US counties', 'counties'] and var_name == 'place' and template['id'] == '7':
                # For template 7, "US" alone is not a valid specific place
                # print(f"  Template {template['id']} - Skipping - '{var_name}' has generic value '{value}'")
                return None
            
        # Debug: Processing template
        # print(f"Processing template {template['id']} (score: {match['score']}): {template['template']}")
        
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
                    # print(f"  Template {template['id']} - Skipping - invalid/placeholder value for {key}: '{value}'")
                    has_invalid = True
                    break
                
                # For placeType parameters, valid values include: county, state, city, zip code, etc.
                # These should NOT be considered invalid

                if 'variable' in key.lower():
                    variables.append(value)
                elif key in ['placeType', 'place_type', 'place-type']:
                    # This is a place type (e.g., "counties", "states"), not a place
                    # Don't add to places list - it will be used for childPlaceType parameter
                    pass
                elif any(place_name in key.lower() for place_name in ['county', 'place', 'state', 'city', 'containing']):
                    places.append(value)
            
            # Skip this template if it has invalid values
            if has_invalid:
                return None
            
            # print(f"  Template {template['id']} - Variables: {variables}, Places: {places}")
            
            # Map to DCIDs (this is already parallelized internally)
            variable_dcids, place_dcids = await self.map_to_dcids(variables, places)
            # print(f"  Template {template['id']} - DCIDs - Variables: {variable_dcids}, Places: {place_dcids}")
            
            # Skip if we couldn't extract any variables
            if not variable_dcids:
                logger.debug(f"Template {template['id']} - Skipping - no variables extracted")
                return None

            # Default to US if no places extracted
            if not place_dcids:
                place_dcids = ['country/USA']
                # print(f"  Template {template['id']} - Defaulting to US for place")
            
            # Step 4: Determine visualization type from action
            action = template.get('action', {})
            viz_type = action.get('type')

            if viz_type is None:
                logger.debug(f"Template {template['id']} - Skipping - no visualization type in action")
                return None

            # print(f"  Template {template['id']} - Visualization type: {viz_type}")
            
            # Step 5: Create web component
            additional_params = {}
            if 'limit' in self.params and self.params['limit']:
                additional_params['limit'] = self.params['limit']
            
            # Use the chartTitle from the LLM's extracted values
            title = extracted_values.get('chartTitle', '')

            # If no title was extracted by the LLM, use a fallback
            if not title:
                title = f"{viz_type.capitalize()} visualization"
                
            component_html = self.create_web_component(
                viz_type,
                place_dcids,
                variable_dcids,
                title=title,
                query_params=additional_params,
                extracted_values=extracted_values
            )
            
            # print(f"  Template {template['id']} - Generated component")
            
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
            # print(f"  Template {template['id']} - Error: {e}")
            return None
    
    def create_web_component(self, component_type: str, places: List[str], variables: List[str],
                           title: str = "", query_params: Optional[Dict] = None,
                           extracted_values: Optional[Dict] = None) -> str:
        """Create the HTML for a Data Commons web component."""
        # Debug: Creating web component
        # print(f"Creating {component_type} component with title: {title}")

        # Add 'datacommons-' prefix to component type
        component_type = f'datacommons-{component_type}'

        # Get the place type from extracted values if available
        place_type = None
        if extracted_values:
            place_type = extracted_values.get('placeType') or extracted_values.get('place_type') or extracted_values.get('place-type')
            # Convert place type to proper childPlaceType format
            if place_type:
                # Convert to title case for Data Commons (e.g., "county" -> "County")
                if place_type.lower() == 'county':
                    place_type = 'County'
                elif place_type.lower() == 'state':
                    place_type = 'State'
                elif place_type.lower() == 'city':
                    place_type = 'City'
                else:
                    # Title case for other types
                    place_type = place_type.title()
                # print(f"    Processed place type: {place_type}")

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

        # print(f"Generated HTML for {component_type}")
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
                    logger.debug(f"Skipping duplicate component by key: {component['component_key']}")
                    continue
                    
                # Also skip if the HTML is exactly the same
                if component['html'] in seen_html:
                    logger.debug(f"Skipping duplicate component with identical HTML")
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
            
            logger.info(f"Generated {len(all_components)} components for statistics query")

            # Send each component as a separate message
            for i, comp in enumerate(all_components):
                message = {
                    "message_type": "result",
                    
                    "content": {
                        "@type": "StatisticalResult",
                        "visualizationType": comp['viz_type'],
                        "html": comp['html'],
                        "places": comp['place_dcids'],
                        "variables": comp['variable_dcids'],
                        "script": '<script src="https://datacommons.org/datacommons.js"></script>',
                        "embed_instructions": "To embed this component, include the script tag and the HTML component in your page."
                        }
                    }
                

                # Send the message
                await self.handler.send_message(message)

            logger.info(f"Sent {len(all_components)} statistics components successfully")

            self.sent_message = True
            
        except Exception as e:
            logger.error(f"Error in statistics handler: {e}")
            await self._send_error_message(f"An error occurred while processing your statistical query: {str(e)}")
    
    async def _send_error_message(self, error_text: str):
        """Send an error message to the user."""
        if not self.sent_message:
            await self.handler.send_message({
                "message_type": "error",
                "content": error_text,
                "error": True
            })
            self.sent_message = True