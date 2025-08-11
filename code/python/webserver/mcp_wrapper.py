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
# from webserver.StreamingWrapper import HandleRequest, SendChunkWrapper  # Removed - using direct handlers
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
        print(f"=== MCP REQUEST: method={method}, id={request_id}, initialized={self.initialized}, handler_id={id(self)} ===")
        
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
                # Remove the initialization check - MCP clients might not send initialize first
                # if not self.initialized:
                #     raise Exception("Server not initialized")
                
                # Check if this is a streaming request
                is_streaming = (
                    query_params.get('streaming') == ['true'] and 
                    params.get("arguments", {}).get("streaming", False)
                )
                
                if is_streaming:
                    # Handle streaming request with SSE
                    await self.handle_streaming_tools_call(params, query_params, send_response, send_chunk)
                    return
                else:
                    # Handle regular request
                    result = await self.handle_tools_call(params, query_params)
            elif method == "notifications/cancelled":
                # Handle cancellation notification
                logger.info(f"Received cancellation for request {params.get('requestId')}: {params.get('reason')}")
                # For notifications, we don't send a response
                return
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
            "name": "ask",
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
    
    async def handle_streaming_tools_call(self, params, query_params, send_response, send_chunk):
        """Handle streaming tools/call request with SSE"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        logger.info(f"MCP streaming tool call: {tool_name}")
        
        if tool_name == "ask":
            # Set SSE headers
            await send_response(200, {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            })
            
            # Handle the main query tool with streaming
            query = arguments.get("query", "")
            sites = arguments.get("site", [])
            generate_mode = arguments.get("generate_mode", "list")
            
            # Update query params
            query_params["query"] = [query] if query else []
            if sites:
                query_params["site"] = sites if isinstance(sites, list) else [sites]
            query_params["generate_mode"] = [generate_mode] if generate_mode else ["list"]
            
            # Create a streaming wrapper that sends SSE events
            class SSEStreamer:
                async def write_stream(self, data, end_response=False):
                    # Convert data to streaming event
                    if isinstance(data, dict):
                        chunk = json.dumps(data)
                    elif isinstance(data, bytes):
                        chunk = data.decode('utf-8')
                    else:
                        chunk = str(data)
                    
                    # Send as SSE event
                    event_data = {
                        "type": "function_stream_event",
                        "content": {"partial_response": chunk}
                    }
                    sse_data = f"data: {json.dumps(event_data)}\n\n"
                    await send_chunk(sse_data.encode('utf-8'), end_response=False)
            
            stream_chunk = SSEStreamer()
            
            try:
                # Process the query using NLWebHandler
                handler = NLWebHandler(query_params, stream_chunk)
                await handler.runQuery()
                
                # Send final event
                final_event = {
                    "type": "function_stream_end",
                    "status": "success"
                }
                sse_data = f"data: {json.dumps(final_event)}\n\n"
                await send_chunk(sse_data.encode('utf-8'), end_response=False)
                
            except Exception as e:
                # Send error event
                error_event = {
                    "type": "function_stream_end",
                    "status": "error",
                    "error": str(e)
                }
                sse_data = f"data: {json.dumps(error_event)}\n\n"
                await send_chunk(sse_data.encode('utf-8'), end_response=False)
            
            # End the stream
            await send_chunk(b"", end_response=True)
        else:
            # Other tools not supported for streaming
            await send_response(400, {'Content-Type': 'application/json'})
            error_response = {"error": "Streaming not supported for this tool"}
            await send_chunk(json.dumps(error_response).encode('utf-8'), end_response=True)

    async def handle_tools_call(self, params, query_params):
        """Handle tools/call request"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"MCP tool call: {tool_name} with args: {arguments}")
        print(f"=== TOOL CALL: {tool_name} ===")
        print(f"Arguments: {json.dumps(arguments, indent=2)}")
        
        if tool_name == "ask":
            # Handle the main query tool
            query = arguments.get("query", "")
            print(f"=== PROCESSING ASK TOOL ===")
            print(f"Query: {query}")
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
            
            # Process the query using NLWebHandler with a timeout
            print(f"=== CREATING NLWebHandler ===")
            print(f"Query params: {query_params}")
            handler = NLWebHandler(query_params, capture_chunk)
            try:
                print(f"=== CALLING handler.runQuery() ===")
                # Add a 10-second timeout for MCP requests
                result = await asyncio.wait_for(handler.runQuery(), timeout=10.0)
                print(f"=== HANDLER RETURNED: {result} ===")
            except asyncio.TimeoutError:
                logger.warning("MCP tool call timed out after 10 seconds")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "Request timed out. The query is taking longer than expected. Please try a simpler query or specify a more specific site."
                        }
                    ],
                    "isError": True
                }
            
            # Join all chunks
            full_response = ''.join(response_content)
            
            # Return MCP-formatted response
            return {
                "content": [
                    {
                        "type": "text",
                        "text": full_response
                    }
                ],
                "isError": False
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
                    ],
                    "isError": False
                }
            except Exception as e:
                logger.error(f"Error getting sites: {str(e)}")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error retrieving sites: {str(e)}"
                        }
                    ],
                    "isError": True
                }
        
        else:
            raise Exception(f"Unknown tool: {tool_name}")


# Global MCP handler instance
mcp_handler = MCPHandler()
print(f"=== GLOBAL MCP HANDLER CREATED: id={id(mcp_handler)} ===")

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
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,  # Invalid request
                    "message": "Invalid request: Empty body"
                }
            }
            await send_response(200, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response).encode('utf-8'), end_response=True)
    
    except Exception as e:
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
        await send_chunk(json.dumps(error_response).encode('utf-8'), end_response=True)
