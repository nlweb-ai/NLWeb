# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the code for the MCP handler.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
import traceback
import asyncio
from core.baseHandler import NLWebHandler
from webserver.StreamingWrapper import HandleRequest, SendChunkWrapper
from utils.logger import get_logger, LogLevel
from config.config import CONFIG  # Import CONFIG for site validation

# Assuming logger is available
logger = get_logger(__name__)

def handle_site_parameter(query_params):
    """
    Handle site parameter with configuration validation.
    
    Args:
        query_params (dict): Query parameters from request
        
    Returns:
        dict: Modified query parameters with valid site parameter(s)
    """
    # Create a copy of query_params to avoid modifying the original
    result_params = query_params.copy()
    logger.debug(f"Query params: {query_params}")
    
    # Get allowed sites from config
    allowed_sites = CONFIG.get_allowed_sites()
    sites = []
    if "site" in query_params and len(query_params["site"]) > 0:
        sites = query_params["site"]
        logger.debug(f"Sites: {sites}")
        
    # Check if site parameter exists in query params
    if len(sites) > 0:
        if isinstance(sites, list):
            # Validate each site
            valid_sites = []
            for site in sites:
                if CONFIG.is_site_allowed(site):
                    valid_sites.append(site)
                else:
                    logger.warning(f"Site '{site}' is not in allowed sites list")
            
            if valid_sites:
                result_params["site"] = valid_sites
            else:
                # No valid sites provided, use default from config
                result_params["site"] = allowed_sites
        else:
            # Single site
            if CONFIG.is_site_allowed(sites):
                result_params["site"] = [sites]
            else:
                logger.warning(f"Site '{sites}' is not in allowed sites list")
                result_params["site"] = allowed_sites
    else:
        # No site parameter provided, use all allowed sites from config
        result_params["site"] = allowed_sites
    
    return result_params

def add_chatbot_instructions(response):
    """
    Add instructions for the chatbot on how to format the response
    
    Args:
        response (dict): The response dictionary
    
    Returns:
        dict: The response with added chatbot instructions
    """
    if isinstance(response, dict) and "results" in response:
        # Get instructions from config
        instructions = CONFIG.get_chatbot_instructions("search_results")
        
        # Create a new field for chatbot instructions
        response["chatbot_instructions"] = instructions
    return response

class MCPFormatter:
    """Formatter for MCP streaming responses"""
    
    def __init__(self, send_chunk):
        self.send_chunk = send_chunk
        self.closed = False
        self._write_lock = asyncio.Lock()  # Add lock for thread-safe operations
    
    async def write_stream(self, message, end_response=False):
        if self.closed:
            return
        
        async with self._write_lock:  # Ensure thread-safe writes
            try:
                # Format according to MCP protocol based on message type
                if isinstance(message, dict):
                    message_type = message.get("message_type")
                    
                    if message_type == "result_batch" and "results" in message:
                        # For result batches, add chatbot instructions
                        message_with_instructions = message.copy()
                        message_with_instructions["chatbot_instructions"] = CONFIG.get_chatbot_instructions("search_results")
                        # Format them as a partial response that
                        # the MCP client can display
                        results_json = json.dumps(message_with_instructions, indent=2)
                        mcp_event = {
                            "type": "function_stream_event",
                            "content": {
                                "partial_response": f"Results: {results_json}\n\n"
                            }
                        }
                    else:
                        # Convert any other dictionary message to a JSON string for display
                        msg_json = json.dumps(message, indent=2)
                        mcp_event = {
                            "type": "function_stream_event",
                            "content": {
                                "partial_response": f"{msg_json}\n\n"
                            }
                        }
                elif isinstance(message, str):
                    # Already a string, format as partial_response
                    mcp_event = {
                        "type": "function_stream_event",
                        "content": {"partial_response": message}
                    }
                else:
                    # Convert any other type to string
                    mcp_event = {
                        "type": "function_stream_event",
                        "content": {"partial_response": str(message)}
                    }
                
                # Send the event
                data_message = f"data: {json.dumps(mcp_event)}\n\n"
                await self.send_chunk(data_message, end_response=False)
                
                if end_response:
                    # Send final completion event
                    final_event = {
                        "type": "function_stream_end",
                        "status": "success"
                    }
                    final_message = f"data: {json.dumps(final_event)}\n\n"
                    await self.send_chunk(final_message, end_response=True)
                    self.closed = True
                    
            except Exception as e:
                logger.error(f"Error in MCPFormatter.write_stream: {str(e)}")
                print(f"Error in MCPFormatter.write_stream: {str(e)}")
                self.closed = True

async def handle_mcp_request(query_params, body, send_response, send_chunk, streaming=False):
    """
    Handle an MCP request by processing it with NLWebHandler
    
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
                
                # Extract the function call details
                function_call = request_data.get("function_call", {})
                function_name = function_call.get("name")
                
                # Handle different function types
                if function_name == "ask" or function_name == "ask_nlw" or function_name == "query" or function_name == "search":
                    # Original ask functionality (handle multiple common function names)
                    await handle_ask_function(function_call, query_params, send_response, send_chunk, streaming)
                
                elif function_name == "list_tools":
                    # Function to list available tools
                    await handle_list_tools_function(send_response, send_chunk)
                
                elif function_name == "list_prompts":
                    # Function to list available prompts
                    await handle_list_prompts_function(send_response, send_chunk)
                
                elif function_name == "get_prompt":
                    # Function to get a specific prompt
                    await handle_get_prompt_function(function_call, send_response, send_chunk)
                
                elif function_name == "get_sites":
                    # Function to get available sites
                    await handle_get_sites_function(send_response, send_chunk)
                
                else:
                    # Return error for unsupported functions
                    error_response = {
                        "type": "function_response",
                        "status": "error",
                        "error": f"Unknown function: {function_name}"
                    }
                    await send_response(400, {'Content-Type': 'application/json'})
                    await send_chunk(json.dumps(error_response), end_response=True)
                    return
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in MCP request: {e}")
                print(f"Invalid JSON in MCP request: {e}")
                await send_response(400, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps({
                    "type": "function_response",
                    "status": "error",
                    "error": f"Invalid JSON: {str(e)}"
                }), end_response=True)
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

async def handle_ask_function(function_call, query_params, send_response, send_chunk, streaming):
    """Handle the 'ask' function and its aliases"""
    try:
        # Parse function arguments - try to handle different formats
        arguments_str = function_call.get("arguments", "{}")
        try:
            # Try to parse as JSON
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            # If not valid JSON, treat as a string
            arguments = {"query": arguments_str}
        
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
                "type": "function_response",
                "status": "error",
                "error": "Missing required parameter: query"
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
            
            # Format the response according to MCP protocol
            mcp_response = {
                "type": "function_response",
                "status": "success",
                "response": result
            }
            
            # Send the response
            await send_response(200, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(mcp_response), end_response=True)
        else:
            # Streaming response - set up SSE headers
            response_headers = {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'  # Disable proxy buffering
            }
            
            # Send SSE headers
            await send_response(200, response_headers)
            await send_chunk(": keep-alive\n\n", end_response=False)
            
            # Create formatter for MCP streaming responses
            mcp_formatter = MCPFormatter(send_chunk)
            
            # Mark as streaming
            validated_query_params["streaming"] = ["True"]
            
            try:
                # Call NLWebHandler with the formatter
                await NLWebHandler(validated_query_params, mcp_formatter).runQuery()
            except Exception as e:
                logger.error(f"Error in streaming request: {str(e)}")
                print(f"Error in streaming request: {str(e)}")
                
                # Try to send an error response if possible
                if not mcp_formatter.closed:
                    error_event = {
                        "type": "function_stream_end",
                        "status": "error",
                        "error": f"Error processing streaming request: {str(e)}"
                    }
                    error_message = f"data: {json.dumps(error_event)}\n\n"
                    await send_chunk(error_message, end_response=True)
    except Exception as e:
        logger.error(f"Error in handle_ask_function: {str(e)}")
        print(f"Error in handle_ask_function: {str(e)}")
        raise

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
            }
        }
        
        # Send the response
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