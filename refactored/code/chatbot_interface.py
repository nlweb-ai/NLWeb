from typing import Any, Dict
import json
import os
import sys
import asyncio
import argparse
import httpx

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    ErrorData,
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)

# Default server settings
DEFAULT_SERVER_URL = "http://localhost:8000"
DEFAULT_ENDPOINT = "/mcp"

async def forward_to_nlweb(function_name: str, arguments: Dict[str, Any], server_url: str, endpoint: str) -> Dict[str, Any]:
    """Forward a request to the NLWeb MCP endpoint"""
    nlweb_mcp_url = f"{server_url}{endpoint}"
    try:
        # Format the request in MCP format
        payload = {
            "function_call": {
                "name": function_name,
                "arguments": json.dumps(arguments)
            }
        }
        
        # Print some debug info to stderr (won't interfere with stdio protocol)
        print(f"Forwarding to {nlweb_mcp_url}: {function_name}", file=sys.stderr)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                nlweb_mcp_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Error from server: {response.status_code} - {response.text}", file=sys.stderr)
                return {
                    "error": f"Server error: {response.status_code} - {response.text}"
                }
            
            result = response.json()
            return result
            
    except Exception as e:
        print(f"Request failed: {str(e)}", file=sys.stderr)
        return {
            "error": f"Request failed: {str(e)}"
        }

async def serve(server_url: str = DEFAULT_SERVER_URL, endpoint: str = DEFAULT_ENDPOINT) -> None:
    """
    Run the simplified MCP server that forwards requests to NLWeb
    
    Args:
        server_url: The NLWeb server URL
        endpoint: The NLWeb server endpoint
    """
    print(f"Starting NLWeb MCP interface - connecting to {server_url}{endpoint}", file=sys.stderr)
    server = Server("nlweb-interface")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Forward list_tools request to NLWeb"""
        result = await forward_to_nlweb("list_tools", {}, server_url, endpoint)
        
        if "error" in result:
            # Fallback to default if server is unavailable
            return [
                Tool(
                    name="ask_nlw",
                    description="Connects with the NLWeb server to answer questions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The query string to send to the NLWeb server"
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]
        
        # Extract tools from the response
        try:
            tools = result.get("response", {}).get("tools", [])
            return [Tool(
                name=tool["name"],
                description=tool["description"],
                inputSchema=tool["parameters"]
            ) for tool in tools]
        except (KeyError, TypeError) as e:
            print(f"Error processing tools: {str(e)}", file=sys.stderr)
            # Fallback to default
            return [
                Tool(
                    name="ask_nlw",
                    description="Connects with the NLWeb server to answer questions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The query string to send to the NLWeb server"
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        """Forward list_prompts request to NLWeb"""
        result = await forward_to_nlweb("list_prompts", {}, server_url, endpoint)
        
        if "error" in result:
            # Fallback to default if server is unavailable
            return [
                Prompt(
                    name="ask_nlw",
                    description="Connects with the NLWeb server to answer questions",
                    arguments=[
                        PromptArgument(
                            name="query", 
                            description="query string in english", 
                            required=True
                        )
                    ]
                )
            ]
        
        # Extract prompts from the response
        try:
            prompts = result.get("response", {}).get("prompts", [])
            return [Prompt(
                name=prompt["id"],
                description=prompt["description"],
                arguments=[
                    PromptArgument(
                        name="query", 
                        description="query string in english", 
                        required=True
                    )
                ]
            ) for prompt in prompts]
        except (KeyError, TypeError) as e:
            print(f"Error processing prompts: {str(e)}", file=sys.stderr)
            # Fallback to default
            return [
                Prompt(
                    name="ask_nlw",
                    description="Connects with the NLWeb server to answer questions",
                    arguments=[
                        PromptArgument(
                            name="query", 
                            description="query string in english", 
                            required=True
                        )
                    ]
                )
            ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Forward tool calls to NLWeb"""
        result = await forward_to_nlweb(name, arguments, server_url, endpoint)
        
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        
        # Extract response from the result
        try:
            response_data = result.get("response", {})
            # Convert to string if it's not already
            if isinstance(response_data, (dict, list)):
                response_text = json.dumps(response_data, indent=2)
            else:
                response_text = str(response_data)
            
            return [TextContent(type="text", text=response_text)]
        except Exception as e:
            print(f"Error processing tool response: {str(e)}", file=sys.stderr)
            return [TextContent(type="text", text=f"Error processing response: {str(e)}")]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
        """Forward get_prompt to NLWeb"""
        if not arguments:
            arguments = {}
            
        # Add the prompt name as prompt_id if not present
        if "prompt_id" not in arguments:
            arguments["prompt_id"] = name
        
        result = await forward_to_nlweb("get_prompt", arguments, server_url, endpoint)
        
        if "error" in result:
            return GetPromptResult(
                description=f"Failed to get prompt {arguments.get('prompt_id', name)}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=f"Error: {result['error']}")
                    )
                ]
            )
        
        # Extract prompt from the response
        try:
            prompt_data = result.get("response", {})
            prompt_text = prompt_data.get("prompt_text", f"Prompt for {name}")
            
            return GetPromptResult(
                description=f"Prompt: {prompt_data.get('name', name)}",
                messages=[
                    PromptMessage(
                        role="user", 
                        content=TextContent(type="text", text=prompt_text)
                    )
                ]
            )
        except Exception as e:
            print(f"Error processing prompt: {str(e)}", file=sys.stderr)
            return GetPromptResult(
                description=f"Error getting prompt {name}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=f"Error: {str(e)}")
                    )
                ]
            )

    # Run the server
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)

# Main entry point when script is executed directly
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Claude interface for NLWeb")
    parser.add_argument("--server", default=DEFAULT_SERVER_URL, help="NLWeb server URL")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="NLWeb server endpoint")
    
    args = parser.parse_args()
    
    # Run the server with the specified parameters
    asyncio.run(serve(args.server, args.endpoint))