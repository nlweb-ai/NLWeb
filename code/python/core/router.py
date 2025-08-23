# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Tool Selection for routing queries to appropriate tools.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import asyncio
import os
import json
import time
from misc.logger.logging_config_helper import get_configured_logger
from core.llm import ask_llm
from core.config import CONFIG
from core.prompts import fill_prompt, get_site_element
logger = get_configured_logger("tool_selector")

@dataclass
class Tool:
    name: str
    path: str
    method: str
    arguments: Dict[str, str]
    examples: List[str]
    schema_type: str
    prompt: str
    return_structure: Optional[Dict[str, Any]] = None
    handler_class: Optional[str] = None

def init():
    """Initialize the router module by loading tools."""
    # Load tools from config directory for default site
    tools_xml_path = os.path.join(CONFIG.config_directory, "tools.xml")
    site_id = 'default'
    
    logger.info(f"Loading tools from {tools_xml_path} for site '{site_id}'")
    tools = _load_tools_from_file(tools_xml_path, site_id)
    cache_key = (tools_xml_path, site_id)
    _tools_cache[cache_key] = tools
    
    logger.info(f"Loaded {len(tools)} tools")
    logger.info("Router initialization complete")

def _load_tools_from_file(tools_xml_path: str, site_id: str = 'default') -> List[Tool]:
    """Load tools from XML file for a specific site.
    
    Args:
        tools_xml_path: Path to the tools.xml file
        site_id: The site ID to load tools for (default: 'default')
        
    Returns:
        List of Tool objects
    """
    tools = []
    try:
        tree = ET.parse(tools_xml_path)
        root = tree.getroot()
        
        # Find the Site element with the matching id
        site_element = None
        for site_elem in root:
            if site_elem.tag == 'Site' and site_elem.get('id') == site_id:
                site_element = site_elem
                break
        
        # If specific site not found and it's not 'default', try 'default' as fallback
        if site_element is None and site_id != 'default':
            for site_elem in root:
                if site_elem.tag == 'Site' and site_elem.get('id') == 'default':
                    site_element = site_elem
                    break
        
        if site_element is None:
            logger.warning(f"No Site element found with id='{site_id}' in {tools_xml_path}")
            return []
        
        # Now iterate through schema types within the Site element
        for schema_elem in site_element:
            if not hasattr(schema_elem, 'tag'):
                continue
                
            schema_type = schema_elem.tag
            tools_in_schema = schema_elem.findall('Tool')
            
            for tool_elem in tools_in_schema:
                # Check if tool is enabled (default to true if not specified)
                enabled = tool_elem.get('enabled', 'true').lower() == 'true'
                if not enabled:
                    logger.info(f"Skipping disabled tool: {tool_elem.get('name', 'unnamed')}")
                    continue
                
                name = tool_elem.get('name', '')
                path = tool_elem.findtext('path', '').strip()
                method = tool_elem.findtext('method', '').strip()
                
                # Parse arguments
                arguments = {}
                for arg_elem in tool_elem.findall('argument'):
                    arg_name = arg_elem.get('name', '')
                    arg_desc = arg_elem.text or ''
                    arguments[arg_name] = arg_desc.strip()
                
                # Parse examples
                examples = [ex.text.strip() for ex in tool_elem.findall('example') if ex.text]
                
                # Parse prompt
                prompt_elem = tool_elem.find('prompt')
                prompt = prompt_elem.text.strip() if prompt_elem is not None and prompt_elem.text else ""
                
                # Parse return structure
                return_struc_elem = tool_elem.find('returnStruc')
                return_structure = None
                if return_struc_elem is not None and return_struc_elem.text:
                    try:
                        return_structure = json.loads(return_struc_elem.text.strip())
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse return structure for tool {name}: {e}")
                
                # Parse handler class
                handler_elem = tool_elem.find('handler')
                handler_class = handler_elem.text.strip() if handler_elem is not None and handler_elem.text else None
                
                tool = Tool(
                    name=name,
                    path=path,
                    method=method,
                    arguments=arguments,
                    examples=examples,
                    schema_type=schema_type,
                    prompt=prompt,
                    return_structure=return_structure,
                    handler_class=handler_class
                )
                tools.append(tool)
        
        return tools
        
    except Exception as e:
        logger.error(f"Error loading tools from {tools_xml_path}: {e}")
        return []

# Global cache for tools - loaded once and shared
# Key is (tools_xml_path, site_id) tuple
_tools_cache: Dict[tuple, List['Tool']] = {}

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import List, Dict

class ToolSelector:
    """Simple tool selector that loads tools and evaluates them for queries."""
    
    STEP_NAME = "ToolSelector"
    MIN_TOOL_SCORE_THRESHOLD = 70  # Minimum score required to select a tool
    
    # Type hierarchy for schema.org types
    # TODO: This is a placeholder for now. We need to have a proper type hierarchy from schema.org
    TYPE_HIERARCHY = {
        "Recipe": ["Item"],
        "Movie": ["Item"],
        "Product": ["Item"],
        "Restaurant": ["Item"],
        "Event": ["Item"],
        "Podcast": ["Item"]
    }
    
    # Pre-cache these types for faster lookup
    PRE_CACHE_TYPES = ["Item", "Recipe", "Movie", "Product", "Restaurant", "Event", "Podcast", "Statistics"]
    
    # Class-level cache for get_tools_by_type results
    # Key is (site_id, schema_type) tuple
    _type_tools_cache: Dict[tuple, List[Tool]] = {}
    
    def __init__(self, handler):
        self.handler = handler
        self.handler.state.start_precheck_step(self.STEP_NAME)
        
        # Get site_id from handler (similar to how prompts.py does it)
        self.site_id = None
        if handler.site and isinstance(handler.site, list) and len(handler.site) > 0:
            self.site_id = handler.site[0]
        elif handler.site and isinstance(handler.site, str):
            self.site_id = handler.site
        if self.site_id is None:
            self.site_id = 'default'
        
        # Load tools if not already cached
        tools_xml_path = os.path.join(CONFIG.config_directory, "tools.xml")
        self._load_tools_if_needed(tools_xml_path)
        
        # Warm cache if empty
        if not self._type_tools_cache:
            self._warm_cache()
        
    def _load_tools_if_needed(self, tools_xml_path: str):
        """Load tools from XML if not already cached."""
        global _tools_cache
        
        # Cache key includes both path and site_id
        cache_key = (tools_xml_path, self.site_id)
        
        if cache_key not in _tools_cache:
            logger.info(f"Loading tools from {tools_xml_path} for site '{self.site_id}'")
            _tools_cache[cache_key] = self._load_tools_from_file(tools_xml_path, self.site_id)
        else:
            logger.info(f"Using cached tools from {tools_xml_path} for site '{self.site_id}'")
    
    def _load_tools_from_file(self, tools_xml_path: str, site_id: str = 'default') -> List[Tool]:
        """Load tools from XML file."""
        # Now just delegates to the module-level function with site_id
        return _load_tools_from_file(tools_xml_path, site_id)
    
    def _warm_cache(self):
        """Warm the cache for common types."""
        logger.info("Warming tools cache for common types")
        for schema_type in self.PRE_CACHE_TYPES:
            tools = self.get_tools_by_type(schema_type)
            logger.info(f"Cached {len(tools)} tools for type: {schema_type}")
    
    async def _evaluate_tools_with_early_termination(self, query: str, tools: List[Tool], threshold: int = 79) -> List[dict]:
        """Evaluate tools asynchronously with early termination for high-scoring results.
        
        Args:
            query: The query to evaluate
            tools: List of tools to evaluate
            threshold: Score threshold for early termination (default 90)
            
        Returns:
            List of tool results with scores
        """
        # Create tasks for all tools
        tasks = [asyncio.create_task(self._evaluate_tool(query, tool)) for tool in tools]
        
        tool_results = []
        
        try:
            # Process results as they complete
            for completed_task in asyncio.as_completed(tasks):
                try:
                    result = await completed_task
                    
                    if result and "score" in result:
                        score = int(result.get("score", 0))
                        tool_results.append(result)
                        
                        tool_name = result.get("tool", {}).name if result.get("tool") else "unknown"
                        # print(f"DEBUG: Tool {tool_name} completed with score {score}, threshold is {threshold}")
                        
                        # If score exceeds threshold, cancel remaining tasks
                        if score >= threshold:
                            # print(f"DEBUG: Score {score} >= threshold {threshold}, triggering early termination")
                            cancelled_count = 0
                            for task in tasks:
                                if not task.done():
                                    task.cancel()
                                    cancelled_count += 1
                            logger.debug(f"Cancelled {cancelled_count} remaining tasks")
                            # Return immediately with high-scoring result
                            logger.info(f"Early termination: Tool '{tool_name}' with score {score}")
                            return [result]
                        
                except asyncio.CancelledError:
                    # Task was cancelled, skip it
                    pass
                except Exception as e:
                    # Silently continue on error
                    pass
            
            # If no tool exceeded threshold, return all results
            return tool_results
            
        except Exception as e:
            # Cancel any remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            return tool_results
    
    def get_tools_by_type(self, schema_type: str) -> List[Tool]:
        """Get tools for a specific schema type, including inherited tools from parent types."""
        # Cache key includes site_id
        cache_key = (self.site_id, schema_type)
        
        # Check cache first
        if cache_key in self._type_tools_cache:
            logger.info(f"Using cached tools for type: {schema_type} (site: {self.site_id})")
            return self._type_tools_cache[cache_key]
        
        # Get all loaded tools
        tools_xml_path = os.path.join(CONFIG.config_directory, "tools.xml")
        tools_cache_key = (tools_xml_path, self.site_id)
        all_tools = _tools_cache.get(tools_cache_key, [])
        
        # Get all parent types including the current type
        types_to_check = [schema_type]
        if schema_type in self.TYPE_HIERARCHY:
            types_to_check.extend(self.TYPE_HIERARCHY[schema_type])
        elif schema_type != "Item":
            # If type not in hierarchy, assume it inherits from Item
            types_to_check.append("Item")
        
        # Collect tools from all relevant types
        tools_by_name = {}
        
        # Process types from most general (Item) to most specific
        # This ensures specific type tools override general ones
        for type_name in reversed(types_to_check):
            type_tools = [tool for tool in all_tools if tool.schema_type == type_name]
            for tool in type_tools:
                # More specific type tools override more general ones
                tools_by_name[tool.name] = tool
        
        # Convert back to list
        type_tools = list(tools_by_name.values())
        
        # Cache the result with site_id
        cache_key = (self.site_id, schema_type)
        self._type_tools_cache[cache_key] = type_tools
        
        # Debug logging
        logger.info(f"Schema type: {schema_type}, checking types: {types_to_check}")
        logger.info(f"Found {len(type_tools)} tools: {[t.name for t in type_tools]}")
        
        return type_tools
    
    async def _send_tool_selection_message(self, tool_results, query, tools):
        """Send tool selection messages in debug mode."""
        if not getattr(self.handler, 'debug_mode', False):
            # Not in debug mode, but still need to handle no tools case
            if not tool_results:
                logger.info(f"No tools selected (all below threshold {self.MIN_TOOL_SCORE_THRESHOLD}), defaulting to search")
                # Create a dummy search tool result for the handler
                search_tool = next((t for t in tools if t.name == 'search'), None)
                if search_tool:
                    self.handler.tool_routing_results = [{
                        "tool": search_tool,
                        "score": 0,
                        "result": {"score": 0, "justification": "Default fallback"}
                    }]
            return
        
        # In debug mode - send messages
        if tool_results:
            selected_tool = tool_results[0]
            elapsed_time = time.time() - self.handler.init_time
            logger.info(f"Tool selection complete: {selected_tool['tool'].name} (score: {selected_tool['score']:.2f})")
            message = {
                "message_type": "tool_selection",
                "selected_tool": selected_tool['tool'].name,
                "score": selected_tool['score'],
                "parameters": selected_tool['result'],
                "query": query,
                "time_elapsed": f"{elapsed_time:.3f}s"
            }
            asyncio.create_task(self.handler.send_message(message))
        else:
            # No tools selected - default to search
            logger.info(f"No tools selected (all below threshold {self.MIN_TOOL_SCORE_THRESHOLD}), defaulting to search")
            elapsed_time = time.time() - self.handler.init_time
            message = {
                "message_type": "tool_selection",
                "selected_tool": "search",
                "score": 0,
                "parameters": {"score": 0, "justification": "Default fallback - no tools met threshold"},
                "query": query,
                "time_elapsed": f"{elapsed_time:.3f}s"
            }
            asyncio.create_task(self.handler.send_message(message))
            # Create a dummy search tool result for the handler
            search_tool = next((t for t in tools if t.name == 'search'), None)
            if search_tool:
                self.handler.tool_routing_results = [{
                    "tool": search_tool,
                    "score": 0,
                    "result": {"score": 0, "justification": "Default fallback"}
                }]
    
    async def do(self):
        """Main method that evaluates tools and stores results."""
        try:
            # Check if tool selection is enabled in config
            if not CONFIG.is_tool_selection_enabled():
                logger.info("Tool selection is disabled in config, skipping")
                await self.handler.state.precheck_step_done(self.STEP_NAME)
                return
            

            # Skip tool selection if generate_mode is summarize or generate
            generate_mode = getattr(self.handler, 'generate_mode', 'none')
            if generate_mode in ['summarize', 'generate']:
                logger.info(f"Skipping tool selection because generate_mode is '{generate_mode}'")
                await self.handler.state.precheck_step_done(self.STEP_NAME)
                return

            # Wait for decontextualization
            await self.handler.state.wait_for_decontextualization()
            
            # Get query and schema type
            query = self.handler.decontextualized_query or self.handler.query
            schema_type = getattr(self.handler, 'item_type', 'Item')
            
            # Extract just the type name if it's in namespace format
            if isinstance(schema_type, str) and '}' in schema_type:
                schema_type = schema_type.split('}')[1]
            
            # Get tools for this type
            tools = self.get_tools_by_type(schema_type)
            
            # Handle case where no tools are available
            if len(tools) == 0:
                logger.warning(f"No tools available for schema type: {schema_type}")
                self.handler.tool_routing_results = []
                await self.handler.state.precheck_step_done(self.STEP_NAME)
                return
            
            # If there's only one tool, skip LLM evaluation and use it directly
            elif len(tools) == 1:
                logger.info(f"Only one tool available ({tools[0].name}), skipping LLM evaluation - saving API call")
                # Build result with default parameters based on tool requirements
                result = {
                    "score": 100,
                    "justification": "Only available tool for this query type"
                }
                
                # Add required parameters based on tool name
                # These are the common parameters that tools expect when skipping LLM
                if tools[0].name == "conversation_search":
                    result["search_query"] = query
                elif tools[0].name == "search":
                    result["search_query"] = query
                elif tools[0].name in ["who_and_search", "statistics_query"]:
                    # Add any default params these tools might need
                    pass
                
                tool_results = [{
                    "tool": tools[0],
                    "score": 100,
                    "result": result
                }]
                
                # Send debug message if in debug mode
                if getattr(self.handler, 'debug_mode', False):
                    elapsed_time = time.time() - self.handler.init_time
                    await self.handler.send_message({
                        "message_type": "tool_selection",
                        "selected_tool": tools[0].name,
                        "score": 100,
                        "parameters": {"score": 100, "justification": "Single tool available - skipped LLM evaluation"},
                        "query": query,
                        "time_elapsed": f"{elapsed_time:.3f}s",
                        "llm_skipped": True
                    })
            else:
                # Evaluate tools with early termination strategy
                tool_results = await self._evaluate_tools_with_early_termination(query, tools, threshold=90)
            
            # Sort by score
            tool_results.sort(key=lambda x: x["score"], reverse=True)
            
            # Log tool ranking summary (instead of printing to console)
            if tool_results:
                logger.info(f"Tool scores for: {query}")
                for i, result in enumerate(tool_results):
                    logger.info(f"  {result['tool'].name}: {result['score']}")
            
            # Filter out tools below threshold
            original_results = tool_results[:]
            tool_results = [r for r in tool_results if r['score'] >= self.MIN_TOOL_SCORE_THRESHOLD]
            
            # If no tools meet threshold, fall back to search if available
            if not tool_results and original_results:
                logger.info(f"No tools meet minimum threshold of {self.MIN_TOOL_SCORE_THRESHOLD}, checking for search fallback")
                # Look for search tool in original results
                search_result = next((r for r in original_results if r['tool'].name == 'search'), None)
                if search_result:
                    logger.info(f"Falling back to search tool (score: {search_result['score']})")
                    tool_results = [search_result]
                else:
                    logger.info("No search tool available as fallback")
            
            # Check if top tool is not search and abort fastTrack if needed
            if tool_results and tool_results[0]['tool'].name != 'search':
                logger.info(f"FastTrack aborted: Top tool is '{tool_results[0]['tool'].name}', not 'search'")
                # Abort fast track using the proper event mechanism
                self.handler.abort_fast_track_event.set()
            
            tool_results = tool_results[:3]
            
            # Log tool selection results
            logger.info(f"Tool selection results for query: {query}")
            for i, result in enumerate(tool_results):
                logger.info(f"{i+1}. Tool: {result['tool'].name} - Score: {result['score']}")
            
            self.handler.tool_routing_results = tool_results
            
            # Send tool selection message (handles debug mode internally)
            await self._send_tool_selection_message(tool_results, query, tools)
                
        except Exception as e:
            logger.error(f"Error in tool selection: {e}")
        finally:
            
            await self.handler.state.precheck_step_done(self.STEP_NAME)
    
    async def _evaluate_tool(self, query: str, tool: Tool) -> dict:
        """Evaluate a single tool for the query."""
        if not tool.prompt:
            return {"tool": tool, "score": 0, "justification": "No prompt defined"}
        
        # Fill prompt using the proper mechanism that includes all context
        filled_prompt = fill_prompt(tool.prompt, self.handler)
        
        try:
            # Use high level for all tools to ensure fair evaluation timing
            level = "high"
            start_time = time.time()
            response = await ask_llm(filled_prompt, tool.return_structure, level=level, query_params=self.handler.query_params)
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            result = response or {"score": 0, "justification": "No response from LLM"}
            
            # Debug print for conversation_search tool
            if tool.name == "conversation_search":
                print(f"\n--- Tool Evaluation: {tool.name} ---")
                print(f"Time taken: {elapsed_time:.3f} seconds")
                print(f"Response: {result}")
                print(f"Score: {result.get('score', 0)}")
                print("-" * 40)
            
            return {"tool": tool, "result": result, "score": result.get("score", 0)}
        except Exception as e:
            # print(f"\n--- Tool Evaluation ERROR: {tool.name} ---")
            # print(f"Error: {str(e)}")
            # print("-" * 40)
            logger.error(f"Tool evaluation error for {tool.name}: {str(e)}")
            return {"tool": tool, "score": 0, "result": {"score": 0, "justification": f"Error: {str(e)}"}}
    
    async def _send_message(self, tool_scores, query, schema_type):
        """Send tool selection results as message."""
        tools_info = []
        for i, tool_score in enumerate(tool_scores):
            tool_info = {
                'rank': i + 1,
                'name': tool_score.tool.name,
                'score': tool_score.score,
                'justification': tool_score.explanation or '',
                'schema_type': tool_score.tool.schema_type
            }
            if tool_score.extracted_params:
                tool_info['extracted_params'] = tool_score.extracted_params
            tools_info.append(tool_info)
        
        message = {
            "message_type": "tool_routing",
            "tools": tools_info,
            "query": query,
            "schema_type": schema_type
        }
        
        asyncio.create_task(self.handler.send_message(message))
