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
from utils.logging_config_helper import get_configured_logger
from llm.llm import ask_llm
logger = get_configured_logger("tool_selector")

# Global cache for tools - loaded once and shared
_tools_cache: Dict[str, List['Tool']] = {}

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

class ToolSelector:
    """Simple tool selector that loads tools and evaluates them for queries."""
    
    STEP_NAME = "ToolSelector"
    MIN_TOOL_SCORE_THRESHOLD = 70  # Minimum score required to select a tool
    
    def __init__(self, handler):
        self.handler = handler
        self.handler.state.start_precheck_step(self.STEP_NAME)
        
        # Load tools if not already cached
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tools_xml_path = os.path.join(current_dir, "tools.xml")
        self._load_tools_if_needed(tools_xml_path)
        
    def _load_tools_if_needed(self, tools_xml_path: str):
        """Load tools from XML if not already cached."""
        global _tools_cache
        
        if tools_xml_path not in _tools_cache:
            logger.info(f"Loading tools from {tools_xml_path}")
            _tools_cache[tools_xml_path] = self._load_tools_from_file(tools_xml_path)
        else:
            logger.debug(f"Using cached tools from {tools_xml_path}")
    
    def _load_tools_from_file(self, tools_xml_path: str) -> List[Tool]:
        """Load tools from XML file."""
        tools = []
        try:
            tree = ET.parse(tools_xml_path)
            root = tree.getroot()
            
            for schema_elem in root:
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
                    
                    # Debug: Log when ensemble tool is loaded
                    if name == "ensemble":
                        logger.info(f"Loaded ENSEMBLE tool for schema type: {schema_type}")
                
            logger.info(f"Loaded {len(tools)} tools")
            return tools
            
        except Exception as e:
            logger.error(f"Error loading tools from {tools_xml_path}: {e}")
            return []
    
    def get_tools_by_type(self, schema_type: str) -> List[Tool]:
        """Get tools for a specific schema type, including inherited tools from parent types."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tools_xml_path = os.path.join(current_dir, "tools.xml")
        
        all_tools = _tools_cache.get(tools_xml_path, [])
        
        # Define schema.org type hierarchy (simplified)
        # All types inherit from Thing
        type_hierarchy = {
            "Recipe": ["Thing"],
            "Movie": ["Thing"],
            "Product": ["Thing"],
            "Restaurant": ["Thing"],
            # Add more types as needed
        }
        
        # Get all parent types including the current type
        types_to_check = [schema_type]
        if schema_type in type_hierarchy:
            types_to_check.extend(type_hierarchy[schema_type])
        elif schema_type != "Thing":
            # If type not in hierarchy, assume it inherits from Thing
            types_to_check.append("Thing")
        
        # Collect tools from all relevant types
        tools_by_name = {}
        
        # Process types from most general (Thing) to most specific
        # This ensures specific type tools override general ones
        for type_name in reversed(types_to_check):
            type_tools = [tool for tool in all_tools if tool.schema_type == type_name]
            for tool in type_tools:
                # More specific type tools override more general ones
                tools_by_name[tool.name] = tool
        
        # Convert back to list
        type_tools = list(tools_by_name.values())
        
        # Debug logging
        logger.debug(f"Schema type: {schema_type}, checking types: {types_to_check}")
        logger.debug(f"Found {len(type_tools)} tools: {[t.name for t in type_tools]}")
        
        return type_tools
    
    async def do(self):
        """Main method that evaluates tools and stores results."""
        try:
            # Check if tool selection is enabled in config
            from config.config import CONFIG
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
            schema_type = getattr(self.handler, 'item_type', 'Thing')
            
            # Extract just the type name if it's in namespace format
            if isinstance(schema_type, str) and '}' in schema_type:
                schema_type = schema_type.split('}')[1]
            
            # Get tools for this type
            tools = self.get_tools_by_type(schema_type)
            
            # Evaluate tools in parallel
            tasks = []
            for tool in tools:
                task = asyncio.create_task(self._evaluate_tool(query, tool))
                tasks.append((tool, task))
            
            # Wait for all evaluations to complete
            results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            
            # Process results
            tool_results = []
            
            for i, (tool, _) in enumerate(tasks):
                try:
                    result = results[i]
                  
                    if result and "score" in result:
                        score = int(result.get("score", 0))
                        tool_results.append({
                            "tool": tool,
                            "score": score,
                            "result": result
                        })
                        
                        # Log tool score
                        logger.debug(f"{tool.name} tool score: {score}")
                    else:
                        logger.debug(f"No result for tool {tool.name}: {result}")
                        
                except Exception as e:
                    logger.error(f"Error processing result for tool {tool.name}: {e}")
            
            # Sort by score
            tool_results.sort(key=lambda x: x["score"], reverse=True)
            
            # Log tool ranking summary (instead of printing to console)
            if tool_results:
                logger.debug(f"Tool scores for: {query}")
                for i, result in enumerate(tool_results):
                    logger.debug(f"  {result['tool'].name}: {result['score']}")
            
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
            
            # Send tool selection results as a message
            if tool_results:
                selected_tool = tool_results[0]
                message = {
                    "message_type": "tool_selection",
                    "selected_tool": selected_tool['tool'].name,
                    "score": selected_tool['score'],
                    "parameters": selected_tool['result'],
                    "query": query
                }
                await self.handler.send_message(message)
            else:
                # No tools selected - default to search
                logger.info(f"No tools selected (all below threshold {self.MIN_TOOL_SCORE_THRESHOLD}), defaulting to search")
                message = {
                    "message_type": "tool_selection",
                    "selected_tool": "search",
                    "score": 0,
                    "parameters": {"score": 0, "justification": "Default fallback - no tools met threshold"},
                    "query": query
                }
                await self.handler.send_message(message)
                # Create a dummy search tool result for the handler
                search_tool = next((t for t in tools if t.name == 'search'), None)
                if search_tool:
                    self.handler.tool_routing_results = [{
                        "tool": search_tool,
                        "score": 0,
                        "result": {"score": 0, "justification": "Default fallback"}
                    }]
                
        except Exception as e:
            logger.error(f"Error in tool selection: {e}")
        finally:
            
            await self.handler.state.precheck_step_done(self.STEP_NAME)
    
    async def _evaluate_tool(self, query: str, tool: Tool) -> dict:
        """Evaluate a single tool for the query."""
        if not tool.prompt:
            return {"score": 0, "justification": "No prompt defined"}
        
        # Import fill_prompt to use proper prompt filling
        from prompts.prompts import fill_prompt
        
        # Fill prompt using the proper mechanism that includes all context
        filled_prompt = fill_prompt(tool.prompt, self.handler)
        
        try:
            response = await ask_llm(filled_prompt, tool.return_structure, level="high")
            return response or {"score": 0, "justification": "No response from LLM"}
        except Exception as e:
            return {"score": 0, "justification": f"Error: {str(e)}"}
    
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
        
        await self.handler.send_message(message)