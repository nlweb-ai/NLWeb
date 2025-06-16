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

class ToolSelector:
    """Simple tool selector that loads tools and evaluates them for queries."""
    
    STEP_NAME = "ToolSelector"
    
    def __init__(self, handler):
        self.handler = handler
        self.handler.state.start_precheck_step(self.STEP_NAME)
        
        # Load tools if not already cached
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tools_xml_path = os.path.join(current_dir, "test_tools.xml")
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
                    
                    tool = Tool(
                        name=name,
                        path=path,
                        method=method,
                        arguments=arguments,
                        examples=examples,
                        schema_type=schema_type,
                        prompt=prompt,
                        return_structure=return_structure
                    )
                    tools.append(tool)
                
            logger.info(f"Loaded {len(tools)} tools")
            return tools
            
        except Exception as e:
            logger.error(f"Error loading tools from {tools_xml_path}: {e}")
            return []
    
    def get_tools_by_type(self, schema_type: str) -> List[Tool]:
        """Get tools for a specific schema type."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tools_xml_path = os.path.join(current_dir, "test_tools.xml")
        
        all_tools = _tools_cache.get(tools_xml_path, [])
        type_tools = [tool for tool in all_tools if tool.schema_type == schema_type]
        
        # Fall back to Thing if no tools found
        if not type_tools:
            type_tools = [tool for tool in all_tools if tool.schema_type == "Thing"]
            
        return type_tools
    
    async def do(self):
        """Main method that evaluates tools and stores results."""
        try:
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
                    else:
                        print(f"No result for tool {tool.name}")
                except Exception as e:
                    logger.error(f"Error processing result for tool {tool.name}: {e}")
            # Sort by score and take top 3
            tool_results.sort(key=lambda x: x["score"], reverse=True)
            tool_results = tool_results[:3]
            self.handler.tool_routing_results = tool_results
                
        except Exception as e:
            logger.error(f"Error in tool selection: {e}")
        finally:
            await self.handler.state.precheck_step_done(self.STEP_NAME)
    
    async def _evaluate_tool(self, query: str, tool: Tool) -> dict:
        """Evaluate a single tool for the query."""
        if not tool.prompt:
            return {"score": 0, "justification": "No prompt defined"}
        
        # Fill prompt with query
        filled_prompt = tool.prompt.replace("{request.query}", query)
        
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