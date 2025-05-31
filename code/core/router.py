# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Query Router for tool selection.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import asyncio
import os
from prompts.prompt_runner import PromptRunner
from utils.logging_config_helper import get_configured_logger

logger = get_configured_logger("router")

class MockHandler:
    """Mock handler for prompt runner that provides the required attributes."""
    def __init__(self, site="Thing", item_type="Thing"):
        self.site = site
        self.item_type = item_type
        self.query = ""
        self.prev_queries = []
        self.decontextualized_query = ""
        self.top_k = 3
        self.tool = MockTool()
        self.tools = MockTools()
        self.state = MockState()

class MockState:
    """Mock state object for prompt runner."""
    def is_decontextualization_done(self):
        return False
        
class MockTool:
    """Mock tool object for prompt filling."""
    def __init__(self):
        self.description = ""

class MockTools:
    """Mock tools object for prompt filling.""" 
    def __init__(self):
        self.description = ""

@dataclass
class Tool:
    name: str
    path: str
    description: str
    method: str  # local, url, or mcp
    arguments: Dict[str, str]  # argument name -> description
    examples: List[str]
    schema_type: str  # schema.org type (Recipe, Movie, Product, Restaurant, etc.)

@dataclass
class ToolScore:
    tool: Tool
    score: int
    explanation: Optional[str] = None
    extracted_params: Optional[Dict[str, Any]] = None

class QueryRouter:
    """Router for selecting appropriate tools based on user queries."""
    
    def __init__(self, tools_xml_path: str):
        """Initialize router with tools XML file path."""
        self.tools_xml_path = tools_xml_path
        self.tools: List[Tool] = []
        self.handler = MockHandler()
        self.prompt_runner = PromptRunner(self.handler)
        self._load_tools()
    
    def _load_tools(self):
        """Load tools from XML file at initialization."""
        try:
            tree = ET.parse(self.tools_xml_path)
            root = tree.getroot()
            
            logger.debug(f"Root element: {root.tag}")
            
            # Find all schema.org type elements (Recipe, Movie, Product, Restaurant, etc.)
            for schema_elem in root:
                # Skip text nodes, comments, and other non-element nodes
                if not hasattr(schema_elem, 'tag'):
                    continue
                    
                schema_type = schema_elem.tag
                logger.debug(f"Processing schema type: {schema_type}")
                
                # Find all Tool elements within this schema type
                tools_in_schema = schema_elem.findall('Tool')
                logger.debug(f"Found {len(tools_in_schema)} tools in {schema_type}")
                
                for tool_elem in tools_in_schema:
                    name = tool_elem.get('name', '')
                    path = tool_elem.findtext('path', '').strip()
                    description = tool_elem.findtext('description', '').strip()
                    method = tool_elem.findtext('method', '').strip()
                    
                    # Parse arguments
                    arguments = {}
                    for arg_elem in tool_elem.findall('argument'):
                        arg_name = arg_elem.get('name', '')
                        arg_desc = arg_elem.text or ''
                        arguments[arg_name] = arg_desc.strip()
                    
                    # Parse examples
                    examples = [ex.text.strip() for ex in tool_elem.findall('example') if ex.text]
                    
                    tool = Tool(
                        name=name,
                        path=path,
                        description=description,
                        method=method,
                        arguments=arguments,
                        examples=examples,
                        schema_type=schema_type
                    )
                    self.tools.append(tool)
                    logger.debug(f"Added tool: {name} ({schema_type})")
                
            logger.info(f"Loaded {len(self.tools)} tools from {self.tools_xml_path}")
            
        except Exception as e:
            logger.error(f"Error loading tools from {self.tools_xml_path}: {e}")
            raise
    
    async def independent_tool_ranking(self, query: str, top_k: int = 3) -> List[ToolScore]:
        """
        Independent Tool Ranking: Score each tool individually and return top k.
        
        Args:
            query: The user's decontextualized query
            top_k: Number of top tools to return (default 3)
            
        Returns:
            List of ToolScore objects ranked by score
        """
        logger.info(f"Running independent tool ranking for query: {query}")
        
        tool_scores = []
        
        # Score all tools in parallel
        tasks = []
        for tool in self.tools:
            task = asyncio.create_task(self._score_individual_tool(query, tool))
            tasks.append((tool, task))
        
        # Wait for all scoring tasks to complete
        for tool, task in tasks:
            try:
                result = await task
                logger.debug(f"Tool '{tool.name}' LLM result: {result}")
                score = int(result.get("score", 0))
                justification = result.get("justification", "")
                
                # Extract additional parameters based on tool type
                extracted_params = {}
                if tool.name == "search" and "search_query" in result:
                    extracted_params["search_query"] = result.get("search_query")
                elif tool.name == "details" and "item_name" in result:
                    extracted_params["item_name"] = result.get("item_name")
                elif tool.name == "compare" and "item1" in result and "item2" in result:
                    extracted_params["item1"] = result.get("item1")
                    extracted_params["item2"] = result.get("item2")
                
                tool_scores.append(ToolScore(tool=tool, score=score, explanation=justification, extracted_params=extracted_params))
            except Exception as e:
                logger.error(f"Error scoring tool {tool.name}: {e}")
                tool_scores.append(ToolScore(tool=tool, score=0, explanation=f"Error: {str(e)}"))
        
        # Sort by score descending and return top k
        tool_scores.sort(key=lambda x: x.score, reverse=True)
        return tool_scores[:top_k]
    
    async def _score_individual_tool(self, query: str, tool: Tool) -> dict:
        """Score a single tool for the given query."""
        
        # Construct tool description with examples
        tool_desc = f"Tool: {tool.name}\n"
        tool_desc += f"Schema Type: {tool.schema_type}\n"
        tool_desc += f"Description: {tool.description}\n"
        tool_desc += f"Method: {tool.method}\n"
        
        if tool.arguments:
            tool_desc += "Arguments:\n"
            for arg_name, arg_desc in tool.arguments.items():
                tool_desc += f"  - {arg_name}: {arg_desc}\n"
        
        if tool.examples:
            tool_desc += "Example use cases:\n"
            for example in tool.examples:
                tool_desc += f"  - {example}\n"
        
        # Set handler attributes for prompt filling
        self.handler.query = query
        self.handler.tool.description = tool_desc
        
        # Choose the appropriate prompt based on tool name
        prompt_name = self._get_prompt_name_for_tool(tool.name)
        
        try:
            response = await self.prompt_runner.run_prompt(prompt_name, level="high", timeout=8)
            if response and "score" in response:
                return response  # Return the full response with score, justification, and extracted parameters
            else:
                logger.warning(f"No valid response from {prompt_name} for tool {tool.name}")
                return {"score": 0, "justification": "No response from LLM"}
        except Exception as e:
            logger.error(f"Error getting score for tool {tool.name}: {e}")
            return {"score": 0, "justification": f"Error: {str(e)}"}
    
    def _get_prompt_name_for_tool(self, tool_name: str) -> str:
        """Get the appropriate prompt name based on the tool name."""
        if tool_name == "search":
            return "SearchToolScoringPrompt"
        elif tool_name == "details":
            return "DetailsToolScoringPrompt" 
        elif tool_name == "compare":
            return "CompareToolScoringPrompt"
        else:
            return "ToolScoringPrompt"  # Default prompt for other tools
    
    async def collective_tool_ranking(self, query: str, top_k: int = 3) -> List[ToolScore]:
        """
        Collective Tool Ranking: Present all tools to LLM and ask for ranking.
        
        Args:
            query: The user's decontextualized query
            top_k: Number of top tools to return (default 3)
            
        Returns:
            List of ToolScore objects ranked by LLM
        """
        logger.info(f"Running collective tool ranking for query: {query}")
        
        # Construct prompt with all tools
        tools_desc = "Available tools:\n\n"
        
        for i, tool in enumerate(self.tools, 1):
            tools_desc += f"Tool {i}: {tool.name}\n"
            tools_desc += f"Schema Type: {tool.schema_type}\n"
            tools_desc += f"Description: {tool.description}\n"
            tools_desc += f"Method: {tool.method}\n"
            
            if tool.arguments:
                tools_desc += "Arguments:\n"
                for arg_name, arg_desc in tool.arguments.items():
                    tools_desc += f"  - {arg_name}: {arg_desc}\n"
            
            if tool.examples:
                tools_desc += "Example use cases:\n"
                for example in tool.examples:
                    tools_desc += f"  - {example}\n"
            tools_desc += "\n"
        
        # Set handler attributes for prompt filling
        self.handler.query = query
        self.handler.top_k = top_k
        self.handler.tools.description = tools_desc
        
        try:
            response = await self.prompt_runner.run_prompt("ToolRankingPrompt", level="low", timeout=12)
            
            if not response or "rankings" not in response:
                logger.warning("No valid rankings in response from ToolRankingPrompt")
                return await self.approach_1_individual_scoring(query, top_k)
            
            # Parse response into ToolScore objects
            tool_scores = []
            rankings = response.get("rankings", [])
            
            for ranking in rankings[:top_k]:
                if isinstance(ranking, dict):
                    tool_name = ranking.get("tool_name", "")
                    score = int(ranking.get("score", 0))
                    explanation = ranking.get("explanation", "")
                    
                    # Find the tool by name
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    if tool:
                        tool_scores.append(ToolScore(tool=tool, score=score, explanation=explanation))
                    else:
                        logger.warning(f"Tool '{tool_name}' not found in loaded tools")
            
            return tool_scores
            
        except Exception as e:
            logger.error(f"Error in collective tool ranking: {e}")
            # Fallback to independent ranking
            return await self.independent_tool_ranking(query, top_k)


    def get_tools_by_type(self, schema_type: str) -> List[Tool]:
        """Get all tools that match the specified schema type. Falls back to Thing if type not found."""
        type_tools = [tool for tool in self.tools if tool.schema_type == schema_type]
        
        # If no tools found for the specific type, fall back to Thing
        if not type_tools:
            logger.info(f"No tools found for schema type '{schema_type}', falling back to Thing")
            type_tools = [tool for tool in self.tools if tool.schema_type == "Thing"]
        
        return type_tools
    
    async def independent_tool_ranking_by_type(self, query: str, schema_type: str, top_k: int = 3) -> List[ToolScore]:
        """Run independent tool ranking on tools of a specific type only."""
        type_tools = self.get_tools_by_type(schema_type)
        if not type_tools:
            logger.warning(f"No tools found for schema type: {schema_type}")
            return []
        
        logger.info(f"Running independent tool ranking for query: {query} on {len(type_tools)} {schema_type} tools")
        logger.debug(f"Found {len(type_tools)} tools for schema type '{schema_type}'")
        
        tool_scores = []
        
        # Score all tools in parallel
        tasks = []
        for tool in type_tools:
            task = asyncio.create_task(self._score_individual_tool(query, tool))
            tasks.append((tool, task))
        
        # Wait for all scoring tasks to complete
        for tool, task in tasks:
            try:
                result = await task
                logger.debug(f"Tool '{tool.name}' LLM result: {result}")
                score = int(result.get("score", 0))
                justification = result.get("justification", "")
                
                # Extract additional parameters based on tool type
                extracted_params = {}
                if tool.name == "search" and "search_query" in result:
                    extracted_params["search_query"] = result.get("search_query")
                elif tool.name == "details" and "item_name" in result:
                    extracted_params["item_name"] = result.get("item_name")
                elif tool.name == "compare" and "item1" in result and "item2" in result:
                    extracted_params["item1"] = result.get("item1")
                    extracted_params["item2"] = result.get("item2")
                
                tool_scores.append(ToolScore(tool=tool, score=score, explanation=justification, extracted_params=extracted_params))
            except Exception as e:
                logger.error(f"Error scoring tool {tool.name}: {e}")
                tool_scores.append(ToolScore(tool=tool, score=0, explanation=f"Error: {str(e)}"))
        
        # Sort by score descending and return top k
        tool_scores.sort(key=lambda x: x.score, reverse=True)
        return tool_scores[:top_k]
    
    async def collective_tool_ranking_by_type(self, query: str, schema_type: str, top_k: int = 3) -> List[ToolScore]:
        """Run collective tool ranking on tools of a specific type only."""
        type_tools = self.get_tools_by_type(schema_type)
        if not type_tools:
            logger.warning(f"No tools found for schema type: {schema_type}")
            return []
        
        logger.info(f"Running collective tool ranking for query: {query} on {len(type_tools)} {schema_type} tools")
        
        # Construct prompt with tools of this type only
        tools_desc = f"Available {schema_type} tools:\n\n"
        
        for i, tool in enumerate(type_tools, 1):
            tools_desc += f"Tool {i}: {tool.name}\n"
            tools_desc += f"Schema Type: {tool.schema_type}\n"
            tools_desc += f"Description: {tool.description}\n"
            tools_desc += f"Method: {tool.method}\n"
            
            if tool.arguments:
                tools_desc += "Arguments:\n"
                for arg_name, arg_desc in tool.arguments.items():
                    tools_desc += f"  - {arg_name}: {arg_desc}\n"
            
            if tool.examples:
                tools_desc += "Example use cases:\n"
                for example in tool.examples:
                    tools_desc += f"  - {example}\n"
            tools_desc += "\n"
        
        # Set handler attributes for prompt filling
        self.handler.query = query
        self.handler.top_k = top_k
        self.handler.tools.description = tools_desc
        
        try:
            response = await self.prompt_runner.run_prompt("ToolRankingPrompt", level="low", timeout=12)
            
            if not response or "rankings" not in response:
                logger.warning("No valid rankings in response from ToolRankingPrompt")
                return await self.independent_tool_ranking_by_type(query, schema_type, top_k)
            
            # Parse response into ToolScore objects
            tool_scores = []
            rankings = response.get("rankings", [])
            
            for ranking in rankings[:top_k]:
                if isinstance(ranking, dict):
                    tool_name = ranking.get("tool_name", "")
                    score = int(ranking.get("score", 0))
                    explanation = ranking.get("explanation", "")
                    
                    # Find the tool by name within this type
                    tool = next((t for t in type_tools if t.name == tool_name), None)
                    if tool:
                        tool_scores.append(ToolScore(tool=tool, score=score, explanation=explanation))
                    else:
                        logger.warning(f"Tool '{tool_name}' not found in {schema_type} tools")
            
            return tool_scores
            
        except Exception as e:
            logger.error(f"Error in collective tool ranking for {schema_type}: {e}")
            # Fallback to independent ranking for this type
            return await self.independent_tool_ranking_by_type(query, schema_type, top_k)


class ToolRouterModule(PromptRunner):
    """Module that integrates tool routing into the NLWeb pipeline."""
    
    STEP_NAME = "ToolRouter"
    
    def __init__(self, handler):
        super().__init__(handler)
        self.handler.state.start_precheck_step(self.STEP_NAME)
        
        # Initialize the router with test_tools.xml
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tools_xml_path = os.path.join(current_dir, "test_tools.xml")
        self.router = QueryRouter(tools_xml_path)
        
        # Store routing results
        self.tool_scores: List[ToolScore] = []
        self.selected_tools: List[str] = []
        self.extracted_parameters = {}
        
    async def do(self):
        """Execute tool routing using independent tool ranking."""
        try:
            logger.info(f"Starting tool routing for query: {self.handler.query}")
            
            # Wait for decontextualization to complete
            await self.handler.state.wait_for_decontextualization()
            
            # Use the decontextualized query if available, otherwise use original query
            query = self.handler.decontextualized_query or self.handler.query
            
            # Get the item type (schema type) for tool filtering
            schema_type = self._get_schema_type()
            
            # Run independent tool ranking
            logger.debug(f"Running independent tool ranking for schema_type: {schema_type} with query: '{query}'")
            
            self.tool_scores = await self.router.independent_tool_ranking_by_type(
                query, schema_type, top_k=3
            )
            
            logger.debug(f"Got {len(self.tool_scores)} tool scores back")
            
            # Process results
            await self._process_tool_scores()
            
            # Send routing results as a message
            await self._send_routing_message()
            
            # Check if fast track should be aborted based on tool routing results
            self.handler.state.abort_fast_track_if_needed()
            
            logger.info(f"Tool routing completed. Selected tools: {self.selected_tools}")
            
        except Exception as e:
            logger.error(f"Error in tool routing: {e}")
        finally:
            await self.handler.state.precheck_step_done(self.STEP_NAME)
    
    def _get_schema_type(self) -> str:
        """Get the schema type from item_type, defaulting to Thing."""
        item_type = getattr(self.handler, 'item_type', 'Thing')
        
        # Extract schema type from item_type if it's in format "{namespace}type"
        if isinstance(item_type, str) and '}' in item_type:
            schema_type = item_type.split('}')[1]
        else:
            schema_type = str(item_type)
        
        # Map common types
        type_mapping = {
            'Recipe': 'Recipe',
            'Movie': 'Movie', 
            'Product': 'Product',
            'Restaurant': 'Restaurant'
        }
        
        return type_mapping.get(schema_type, 'Thing')
    
    async def _process_tool_scores(self):
        """Process tool scores and extract information."""
        if not self.tool_scores:
            logger.warning("No tool scores received from router")
            return
        
        # Extract tool names and parameters
        for tool_score in self.tool_scores:
            self.selected_tools.append(tool_score.tool.name)
            
            # Store extracted parameters by tool name
            if tool_score.extracted_params:
                self.extracted_parameters[tool_score.tool.name] = tool_score.extracted_params
        
        # Store results in handler for other modules to access
        self.handler.tool_routing_results = {
            'tool_scores': self.tool_scores,
            'selected_tools': self.selected_tools,
            'extracted_parameters': self.extracted_parameters,
            'top_tool': self.tool_scores[0] if self.tool_scores else None
        }
        logger.debug(f"ToolRouter stored {len(self.tool_scores)} tool scores in handler")
        
        # Log tool scores at debug level
        if self.tool_scores:
            logger.debug("Router results:")
            for i, tool_score in enumerate(self.tool_scores):
                logger.debug(f"  Tool {i+1}: {tool_score.tool.name} (Score: {tool_score.score})")
                logger.debug(f"    Explanation: {tool_score.explanation}")
                if tool_score.extracted_params:
                    logger.debug(f"    Extracted Params: {tool_score.extracted_params}")
            
            top_tool = self.tool_scores[0] if self.tool_scores else None
            if top_tool:
                logger.info(f"Selected tool: {top_tool.tool.name} with score {top_tool.score}")
        else:
            logger.warning("No tool scores generated!")
    
    async def _send_routing_message(self):
        """Send tool routing results as a message."""
        if not self.tool_scores:
            return
        
        # Prepare message with top 3 tools
        tools_info = []
        for i, tool_score in enumerate(self.tool_scores[:3]):
            tool_info = {
                'rank': i + 1,
                'name': tool_score.tool.name,
                'score': tool_score.score,
                'justification': tool_score.explanation or '',
                'schema_type': tool_score.tool.schema_type
            }
            
            # Add extracted parameters
            if tool_score.extracted_params:
                tool_info['extracted_params'] = tool_score.extracted_params
            
            tools_info.append(tool_info)
        
        message = {
            "message_type": "tool_routing",
            "tools": tools_info,
            "query": self.handler.decontextualized_query or self.handler.query,
            "schema_type": self._get_schema_type()
        }
        
        await self.handler.send_message(message)


def main():
    """Test function for the router."""
    import sys
    import os
    
    if len(sys.argv) < 3:
        print("Usage: python router.py <schema_type> <query>")
        print("Example: python router.py Recipe 'Find vegetarian pasta recipes'")
        print("Example: python router.py Restaurant 'Find Italian restaurants near me'")
        print("Available types: Recipe, Movie, Product, Restaurant")
        return
    
    schema_type = sys.argv[1]
    query = sys.argv[2]
    
    # Always use test_tools.xml from the same directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    tools_xml_path = os.path.join(current_dir, "test_tools.xml")
    
    async def test_router():
        try:
            # Initialize router
            router = QueryRouter(tools_xml_path)
            print(f"Loaded {len(router.tools)} total tools")
            
            # Get tools for the specified type
            type_tools = router.get_tools_by_type(schema_type)
            if not type_tools:
                print(f"No tools found for schema type: {schema_type} or Thing")
                print("Available types:", set(tool.schema_type for tool in router.tools))
                return
            
            # Check if we fell back to Thing
            actual_type = type_tools[0].schema_type if type_tools else schema_type
            if actual_type != schema_type:
                print(f"Schema type '{schema_type}' not found, using '{actual_type}' tools")
            
            print(f"Found {len(type_tools)} tools for type '{actual_type}'")
            print(f"Query: {query}\n")
            
            # Test independent tool ranking
            print(f"=== Independent Tool Ranking ({actual_type}) ===")
            independent_results = await router.independent_tool_ranking_by_type(query, schema_type)
            
            for i, tool_score in enumerate(independent_results, 1):
                print(f"{i}. {tool_score.tool.name} (Score: {tool_score.score})")
                print(f"   Schema Type: {tool_score.tool.schema_type}")
                print(f"   Description: {tool_score.tool.description}")
                print(f"   Method: {tool_score.tool.method}")
                if tool_score.explanation:
                    print(f"   Justification: {tool_score.explanation}")
                if tool_score.extracted_params:
                    print(f"   Extracted Parameters: {tool_score.extracted_params}")
                print()
            
            # Test collective tool ranking
            print(f"=== Collective Tool Ranking ({actual_type}) ===")
            collective_results = await router.collective_tool_ranking_by_type(query, schema_type)
            
            for i, tool_score in enumerate(collective_results, 1):
                print(f"{i}. {tool_score.tool.name} (Score: {tool_score.score})")
                print(f"   Schema Type: {tool_score.tool.schema_type}")
                print(f"   Description: {tool_score.tool.description}")
                print(f"   Method: {tool_score.tool.method}")
                if tool_score.explanation:
                    print(f"   Explanation: {tool_score.explanation}")
                print()
                
        except Exception as e:
            print(f"Error: {e}")
            logger.error(f"Test error: {e}")
    
    # Run the async test
    asyncio.run(test_router())

if __name__ == "__main__":
    main()