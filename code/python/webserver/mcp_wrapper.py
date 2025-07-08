# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the code for the MCP handler implementing standard MCP protocol.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
import traceback
import asyncio
from core.baseHandler import NLWebHandler
from webserver.StreamingWrapper import HandleRequest, SendChunkWrapper
from misc.logger.logger import get_logger, LogLevel
from core.config import CONFIG  # Import CONFIG for site validation
# from core.router import ToolSelector  # Not needed for basic MCP

# Assuming logger is available
logger = get_logger(__name__)

# MCP Protocol version
MCP_PROTOCOL_VERSION = "2024-11-05"

class MCPHandler:
    """Handler for standard MCP protocol requests"""
    
    def __init__(self):
        self.initialized = False
        self.capabilities = {
            "tools": {}
        }
        self._tools_cache = None
    
    async def handle_request(self, request_data, query_params, send_response, send_chunk):
        """
        Handle a JSON-RPC 2.0 MCP request
        
        Args:
            request_data: Parsed JSON request data
            query_params: URL query parameters
            send_response: Function to send response headers
            send_chunk: Function to send response body
        """
        # Extract JSON-RPC fields
        jsonrpc = request_data.get("jsonrpc", "2.0")
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")
        
        # Check if this is a notification (no id field)
        is_notification = request_id is None
        
        logger.info(f"MCP request: method={method}, id={request_id}, is_notification={is_notification}")
        print(f"=== MCP REQUEST: method={method}, id={request_id}, initialized={self.initialized} ===")
        
        try:
            # Route based on method
            if method == "initialize":
                result = await self.handle_initialize(params)
                print(f"=== INITIALIZE COMPLETE, sending response ===")
            elif method == "initialized" or method == "notifications/initialized":
                # This is a notification, no response needed
                self.initialized = True
                logger.info("MCP server initialized")
                print(f"=== SERVER MARKED AS INITIALIZED ===")
                if not is_notification:
                    result = {"status": "ok"}
                else:
                    return  # No response for notifications
            elif method == "tools/list":
                # Temporarily disable initialization check for debugging
                # if not self.initialized:
                #     raise Exception("Server not initialized")
                logger.info(f"tools/list called, initialized={self.initialized}")
                result = await self.handle_tools_list(params)
            elif method == "tools/call":
                print(f"=== TOOLS/CALL: initialized={self.initialized} ===")
                if not self.initialized:
                    raise Exception("Server not initialized")
                result = await self.handle_tools_call(params, query_params)
            else:
                # Unknown method
                raise Exception(f"Method not found: {method}")
            
            # Send successful response
            response = {
                "jsonrpc": jsonrpc,
                "id": request_id,
                "result": result
            }
            
        except Exception as e:
            # Send error response
            logger.error(f"MCP error handling {method}: {str(e)}")
            response = {
                "jsonrpc": jsonrpc,
                "id": request_id,
                "error": {
                    "code": -32603,  # Internal error
                    "message": str(e)
                }
            }
        
        # Send the response
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(response).encode('utf-8'), end_response=True)
    
    async def handle_initialize(self, params):
        """Handle initialize request"""
        client_version = params.get("protocolVersion", "")
        client_capabilities = params.get("capabilities", {})
        client_info = params.get("clientInfo", {})
        
        logger.info(f"MCP Initialize request from {client_info.get('name', 'unknown')} v{client_info.get('version', 'unknown')}")
        
        # Return server capabilities
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": self.capabilities,
            "serverInfo": {
                "name": "nlweb-mcp-server",
                "version": "1.0.0"
            },
            "instructions": "NLWeb MCP Server - Query and analyze information from configured data sources"
        }
    
    async def handle_tools_list(self, params):
        """Handle tools/list request"""
        # Get available tools from the router
        available_tools = []
        
        # Add the main ask/query tool
        available_tools.append({
            "name": "ask_nlweb",
            "description": "Query NLWeb to search and analyze information from configured data sources",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or search query"
                    },
                    "site": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of sites to search. If not provided, searches all configured sites"
                    },
                    "generate_mode": {
                        "type": "string",
                        "enum": ["list", "generate", "summarize"],
                        "description": "The type of response to generate",
                        "default": "list"
                    }
                },
                "required": ["query"]
            }
        })
        
        # Add tool listing capability
        available_tools.append({
            "name": "list_sites",
            "description": "List all available sites that can be queried",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        })
        
        # TODO: Add additional NLWeb tools here when router integration is ready
        
        return {"tools": available_tools}
    
    async def handle_tools_call(self, params, query_params):
        """Handle tools/call request"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"MCP tool call: {tool_name} with args: {arguments}")
        print(f"=== TOOL CALL: {tool_name} ===")
        print(f"Arguments: {json.dumps(arguments, indent=2)}")
        
        if tool_name == "ask_nlweb":
            # Handle the main query tool
            query = arguments.get("query", "")
            sites = arguments.get("site", [])
            generate_mode = arguments.get("generate_mode", "list")
            
            # Update query params with MCP arguments
            # Make sure to format values as lists (like URL parameters)
            query_params["query"] = [query] if query else []
            if sites:
                query_params["site"] = sites if isinstance(sites, list) else [sites]
            query_params["generate_mode"] = [generate_mode] if generate_mode else ["list"]
            
            print(f"=== QUERY PARAMS BEING PASSED ===")
            print(f"query_params: {query_params}")
            
            # Create a response accumulator
            response_content = []
            
            # Create a wrapper class that provides write_stream method
            class ChunkCapture:
                async def write_stream(self, data, end_response=False):
                    # Convert data to string
                    if isinstance(data, dict):
                        chunk = json.dumps(data)
                    elif isinstance(data, bytes):
                        chunk = data.decode('utf-8')
                    else:
                        chunk = str(data)
                    response_content.append(chunk)
            
            capture_chunk = ChunkCapture()
            
            # Process the query using NLWebHandler
            handler = NLWebHandler(query_params, capture_chunk)
            result = await handler.runQuery()
            
            # Join all chunks
            full_response = ''.join(response_content)
            
            # Return MCP-formatted response
            return {
                "content": [
                    {
                        "type": "text",
                        "text": full_response
                    }
                ]
            }
        
        elif tool_name == "list_sites":
            # Get sites from retriever like WebServer does
            try:
                from core.retriever import get_vector_db_client
                
                # Create a retriever client
                retriever = get_vector_db_client(query_params=query_params)
                
                # Get the list of sites
                sites = await retriever.get_sites()
                
                # Format the response
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"sites": sites}, indent=2)
                        }
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting sites: {str(e)}")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error retrieving sites: {str(e)}"
                        }
                    ]
                }
        
        else:
            raise Exception(f"Unknown tool: {tool_name}")


# Global MCP handler instance
mcp_handler = MCPHandler()

async def handle_mcp_request(query_params, body, send_response, send_chunk, streaming=False):
    """
    Handle an MCP request following the standard MCP protocol
    
    Args:
        query_params (dict): URL query parameters
        body (bytes): Request body
        send_response (callable): Function to send response headers
        send_chunk (callable): Function to send response body
        streaming (bool, optional): Whether to use streaming response
    """
    try:
        # Parse the request body as JSON
        if body:
            try:
                request_data = json.loads(body)
                print(f"\n=== INCOMING MCP REQUEST ===")
                print(f"Body: {json.dumps(request_data, indent=2)}")
                print(f"===========================\n")
                
                # Validate JSON-RPC format
                if "jsonrpc" not in request_data:
                    request_data["jsonrpc"] = "2.0"
                
                # Handle the request
                await mcp_handler.handle_request(request_data, query_params, send_response, send_chunk)
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in MCP request: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,  # Parse error
                        "message": f"Parse error: {str(e)}"
                    }
                }
                await send_response(200, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps(error_response).encode('utf-8'), end_response=True)
        else:
            logger.error("Empty MCP request body")
            print("Empty MCP request body")
            await send_response(400, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps({
                "type": "function_response",
                "status": "error",
                "error": "Empty request body"
            }), end_response=True)
            
    except Exception as e:
        logger.error(f"Error processing MCP request: {e}", exc_info=True)
        print(f"Error processing MCP request: {e}\n{traceback.format_exc()}")
        await send_response(500, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps({
            "type": "function_response",
            "status": "error",
            "error": f"Internal server error: {str(e)}"
        }), end_response=True)

async def handle_ask_function(function_call, query_params, send_response, send_chunk, streaming, request_id=None):
    """Handle the 'ask' function and its aliases"""
    try:
        # Parse function arguments - handle different formats
        arguments = function_call.get("arguments", {})
        
        # If arguments is a string, try to parse it
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                # If not valid JSON, treat as a query string
                arguments = {"query": arguments}
        elif not isinstance(arguments, dict):
            # Convert to dict if needed
            arguments = {"query": str(arguments)}
        
        # Extract the query parameter (required)
        # Check different common parameter names
        query = None
        for param_name in ["query", "question", "q", "text", "input"]:
            if param_name in arguments:
                query = arguments.get(param_name)
                break
        
        if not query:
            # Return error for missing query parameter
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,  # Invalid request
                    "message": "Invalid request: Empty body"
                }
            }
            await send_response(400, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
            return
        
        # Initialize query_params if it doesn't exist
        if query_params is None:
            query_params = {}
        
        # Add the query to query_params for NLWebHandler
        query_params["query"] = [query]
        
        # Add optional parameters if they exist in the arguments
        optional_params = {
            "site": "site",
            "query_id": "query_id", 
            "prev_query": "prev_query", 
            "context_url": "context_url"
        }
        
        for arg_name, param_name in optional_params.items():
            if arg_name in arguments:
                query_params[param_name] = [arguments[arg_name]]
        
        # Check if streaming was specified in the arguments
        if "streaming" in arguments:
            streaming = arguments["streaming"] in [True, "true", "True", "1", 1]
        elif "stream" in arguments:
            streaming = arguments["stream"] in [True, "true", "True", "1", 1]
            
        # Validate site parameters
        validated_query_params = handle_site_parameter(query_params)
        
        if not streaming:
            # Non-streaming response - process request and return complete response
            result = await NLWebHandler(validated_query_params, None).runQuery()
            
            # Add chatbot instructions to the result
            result = add_chatbot_instructions(result)
            
            # Format the response according to protocol
            if request_id is not None:
                # JSON-RPC format for MCP
                mcp_response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2)
                            }
                        ]
                    }
                }
            else:
                # Legacy format
                mcp_response = {
                    "type": "function_response",
                    "status": "success",
                    "response": result
                }
            
            # Send the response
            await send_response(200, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response).encode('utf-8'), end_response=True)
    
    except Exception as e:
        logger.error(f"Error in handle_ask_function: {str(e)}")
        print(f"Error in handle_ask_function: {str(e)}")
        raise

async def handle_initialize_request(request_data, send_response, send_chunk):
    """Handle MCP initialize request"""
    try:
        # Return capabilities
        response = {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "logging": {}
                },
                "serverInfo": {
                    "name": "nlweb-mcp-server",
                    "version": "1.0.0"
                }
            }
        }
        
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(response), end_response=True)
        
    except Exception as e:
        logger.error(f"Error in handle_initialize_request: {str(e)}")
        error_response = {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(error_response), end_response=True)

async def handle_tools_list_request(request_data, send_response, send_chunk):
    """Handle MCP tools/list request"""
    try:
        # Define available tools
        tools = [
            {
                "name": "ask",
                "description": "Ask a question to search the knowledge base",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The question to ask"
                        },
                        "site": {
                            "type": "string",
                            "description": "Optional: Specific site to search within"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_sites",
                "description": "Get a list of available sites",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
        
        response = {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "result": {
                "tools": tools
            }
        }
        
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(response), end_response=True)
        
    except Exception as e:
        logger.error(f"Error in handle_tools_list_request: {str(e)}")
        error_response = {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(error_response), end_response=True)

async def handle_list_tools_function(send_response, send_chunk):
    """Handle the 'list_tools' function to return available tools"""
    try:
        # Define the list of available tools
        available_tools = [
            {
                "name": "ask",
                "description": "Ask a question and get an answer from the knowledge base",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The question to ask"
                        },
                        "site": {
                            "type": "string",
                            "description": "Optional: Specific site to search within"
                        },
                        "streaming": {
                            "type": "boolean",
                            "description": "Optional: Whether to stream the response"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "ask_nlw",
                "description": "Alternative name for the ask function",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The question to ask"
                        },
                        "site": {
                            "type": "string",
                            "description": "Optional: Specific site to search within"
                        },
                        "streaming": {
                            "type": "boolean",
                            "description": "Optional: Whether to stream the response"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "list_prompts",
                "description": "List available prompts that can be used with NLWeb",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_prompt",
                "description": "Get a specific prompt by ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt_id": {
                            "type": "string",
                            "description": "ID of the prompt to retrieve"
                        }
                    },
                    "required": ["prompt_id"]
                }
            },
            {
                "name": "get_sites",
                "description": "Get a list of available sites",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
        
        # Format the response according to MCP protocol
        mcp_response = {
            "type": "function_response",
            "status": "success",
            "response": {
                "tools": available_tools
        logger.error(f"Error in handle_mcp_request: {str(e)}")
        logger.error(traceback.format_exc())
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,  # Internal error
                "message": f"Internal error: {str(e)}"
            }
        }
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(mcp_response), end_response=True)
        
    except Exception as e:
        logger.error(f"Error in handle_list_tools_function: {str(e)}")
        print(f"Error in handle_list_tools_function: {str(e)}")
        raise

async def handle_list_prompts_function(send_response, send_chunk):
    """Handle the 'list_prompts' function to return available prompts"""
    try:
        # Define the list of available prompts (can be loaded from config or database)
        available_prompts = [
            {
                "id": "default",
                "name": "Default Prompt",
                "description": "Standard prompt for general queries"
            },
            {
                "id": "technical",
                "name": "Technical Prompt",
                "description": "Prompt optimized for technical questions"
            },
            {
                "id": "creative",
                "name": "Creative Prompt",
                "description": "Prompt optimized for creative writing and brainstorming"
            }
        ]
        
        # Format the response according to MCP protocol
        mcp_response = {
            "type": "function_response",
            "status": "success",
            "response": {
                "prompts": available_prompts
            }
        }
        
        # Send the response
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(mcp_response), end_response=True)
        
    except Exception as e:
        logger.error(f"Error in handle_list_prompts_function: {str(e)}")
        print(f"Error in handle_list_prompts_function: {str(e)}")
        raise

async def handle_get_prompt_function(function_call, send_response, send_chunk):
    """Handle the 'get_prompt' function to retrieve a specific prompt"""
    try:
        # Parse function arguments
        arguments_str = function_call.get("arguments", "{}")
        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            arguments = {}
        
        # Extract required parameters
        prompt_id = arguments.get("prompt_id")
        
        if not prompt_id:
            # Return error for missing prompt_id parameter
            error_response = {
                "type": "function_response",
                "status": "error",
                "error": "Missing required parameter: prompt_id"
            }
            await send_response(400, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
            return
        
        # Example prompt data (in a real implementation, this would be loaded from a database or config)
        prompts = {
            "default": {
                "id": "default",
                "name": "Default Prompt",
                "description": "Standard prompt for general queries",
                "prompt_text": "You are a helpful assistant. Answer the following question: {{query}}"
            },
            "technical": {
                "id": "technical",
                "name": "Technical Prompt",
                "description": "Prompt optimized for technical questions",
                "prompt_text": "You are a technical expert. Provide detailed technical information for: {{query}}"
            },
            "creative": {
                "id": "creative",
                "name": "Creative Prompt",
                "description": "Prompt optimized for creative writing and brainstorming",
                "prompt_text": "You are a creative writing assistant. Create engaging and imaginative content for: {{query}}"
            }
        }
        
        if prompt_id not in prompts:
            # Return error for unknown prompt ID
            error_response = {
                "type": "function_response",
                "status": "error",
                "error": f"Unknown prompt ID: {prompt_id}"
            }
            await send_response(404, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
            return
        
        # Format the response according to MCP protocol
        mcp_response = {
            "type": "function_response",
            "status": "success",
            "response": prompts[prompt_id]
        }
        
        # Send the response
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(mcp_response), end_response=True)
        
    except Exception as e:
        logger.error(f"Error in handle_get_prompt_function: {str(e)}")
        print(f"Error in handle_get_prompt_function: {str(e)}")
        raise

async def handle_get_sites_function(send_response, send_chunk):
    """Handle the 'get_sites' function to return available sites"""
    try:
        # Get allowed sites from config
        allowed_sites = CONFIG.get_allowed_sites()
        
        # Create site information
        site_info = []
        for site in allowed_sites:
            site_info.append({
                "id": site,
                "name": site.capitalize(),  # Simple name formatting, can be enhanced
                "description": f"Site: {site}"  # Basic description, should be enhanced
            })
        
        # Format the response according to MCP protocol
        mcp_response = {
            "type": "function_response",
            "status": "success",
            "response": {
                "sites": site_info
            }
        }
        
        # Send the response
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(mcp_response), end_response=True)
        
    except Exception as e:
        logger.error(f"Error in handle_get_sites_function: {str(e)}")
        print(f"Error in handle_get_sites_function: {str(e)}")
        raise

async def handle_get_sites_mcp(request_id, send_response, send_chunk):
    """Handle MCP tools/call for get_sites tool"""
    try:
        # Get allowed sites from config
        allowed_sites = CONFIG.get_allowed_sites()
        
        # Create site information
        site_info = []
        for site in allowed_sites:
            site_info.append({
                "id": site,
                "name": site.capitalize(),  # Simple name formatting, can be enhanced
                "description": f"Site: {site}"  # Basic description, should be enhanced
            })
        
        # Format the response according to JSON-RPC protocol for MCP
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"sites": site_info}, indent=2)
                    }
                ]
            }
        }
        
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(response), end_response=True)
        
    except Exception as e:
        logger.error(f"Error in handle_get_sites_mcp: {str(e)}")
        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(error_response), end_response=True)
