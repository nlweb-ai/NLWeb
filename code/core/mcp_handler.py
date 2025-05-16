# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the code for the MCP handler.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
import traceback
from core.baseHandler import NLWebHandler
from webserver.StreamingWrapper import HandleRequest, SendChunkWrapper
import asyncio
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
                
                if function_name != "ask":
                    # Return error for unsupported functions
                    error_response = {
                        "type": "function_response",
                        "status": "error",
                        "error": f"Unknown function: {function_name}"
                    }
                    await send_response(400, {'Content-Type': 'application/json'})
                    await send_chunk(json.dumps(error_response), end_response=True)
                    return
                
                # Parse function arguments
                arguments = json.loads(function_call.get("arguments", "{}"))
                
                # Extract the query parameter (required)
                query = arguments.get("query")
                
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
                if "site" in arguments:
                    query_params["site"] = [arguments["site"]]

                if "query_id" in arguments:
                    query_params["query_id"] = [arguments["query_id"]]
                
                if "prev_query" in arguments:
                    query_params["prev_query"] = [arguments["prev_query"]]
                
                if "context_url" in arguments:
                    query_params["context_url"] = [arguments["context_url"]]
                
                # Check if streaming was specified in the arguments
                if "streaming" in arguments:
                    streaming = arguments["streaming"] in [True, "true", "True", "1", 1]
                    
                # Validate site parameters
                validated_query_params = handle_site_parameter(query_params)
                
                if not streaming:
                    # Non-streaming response - process request and return complete response
                    result = await NLWebHandler(validated_query_params, None).runQuery()
                    
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
                    
                    # Create a custom formatter for MCP streaming responses
                    class MCPFormatter:
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
                                            # For result batches, format them as a partial response that
                                            # the MCP client can display
                                            results_json = json.dumps(message["results"], indent=2)
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
                    
                    # Mark query_params as streaming
                    validated_query_params["streaming"] = ["True"]
                    
                    # Create formatter and directly call NLWebHandler
                    mcp_formatter = MCPFormatter(send_chunk)
                    
                    try:
                        # Call NLWebHandler directly with the formatter
                        await NLWebHandler(validated_query_params, mcp_formatter).runQuery()
                    except Exception as e:
                        logger.error(f"Error in streaming request: {str(e)}")
                        print(f"Error in streaming request: {str(e)}\n{traceback.format_exc()}")
                        
                        # Try to send an error response if possible
                        if not mcp_formatter.closed:
                            error_event = {
                                "type": "function_stream_end",
                                "status": "error",
                                "error": f"Error processing streaming request: {str(e)}"
                            }
                            error_message = f"data: {json.dumps(error_event)}\n\n"
                            await send_chunk(error_message, end_response=True)
                
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