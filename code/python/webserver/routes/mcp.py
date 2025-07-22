"""Model Context Protocol (MCP) routes for aiohttp server"""

from aiohttp import web
import logging
import json
from typing import Dict, Any
from webserver.mcp_wrapper import handle_mcp_request
from core.utils.utils import get_param

logger = logging.getLogger(__name__)


def setup_mcp_routes(app: web.Application):
    """Setup MCP routes"""
    # MCP health check endpoints
    app.router.add_get('/mcp/health', mcp_health)
    app.router.add_get('/mcp/healthz', mcp_health)
    
    # Main MCP endpoint
    app.router.add_post('/mcp', mcp_handler)
    app.router.add_get('/mcp', mcp_handler)
    
    # MCP with path
    app.router.add_post('/mcp/{path:.*}', mcp_handler)
    app.router.add_get('/mcp/{path:.*}', mcp_handler)


async def mcp_health(request: web.Request) -> web.Response:
    """MCP health check endpoint"""
    return web.json_response({"status": "ok"})


async def mcp_handler(request: web.Request) -> web.Response:
    """Handle MCP requests"""
    
    try:
        # Get query parameters
        query_params = dict(request.query)
        
        # Get body for POST requests
        body = None
        if request.method == 'POST':
            if request.has_body:
                body = await request.read()
                # Parse body as JSON if it's JSON
                try:
                    if request.content_type == 'application/json':
                        body_json = json.loads(body)
                        # Merge body parameters into query_params
                        query_params.update(body_json)
                except Exception:
                    # Keep body as raw bytes if not JSON
                    pass
        
        # MCP always uses regular JSON-RPC responses, not SSE
        # The streaming parameter in MCP is for the protocol itself, not HTTP streaming
        return await handle_mcp_regular(request, query_params, body)
            
    except Exception as e:
        logger.error(f"Error in MCP handler: {e}", exc_info=True)
        return web.json_response({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            },
            "id": None
        }, status=500)


async def handle_mcp_streaming(request: web.Request, query_params: Dict[str, Any], body: bytes) -> web.StreamResponse:
    """Handle streaming MCP requests"""
    
    # Create SSE response
    response = web.StreamResponse(
        status=200,
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )
    
    await response.prepare(request)
    
    # Create mock send functions that work with aiohttp
    async def send_response(status, headers):
        # Headers are already set in StreamResponse
        pass
    
    async def send_chunk(data, end_response=False):
        if isinstance(data, str):
            data = data.encode()
        elif isinstance(data, dict):
            data = json.dumps(data).encode()
        
        # For SSE, wrap in data: format
        await response.write(b"data: " + data + b"\n\n")
        
        if end_response:
            await response.write_eof()
    
    # Call the MCP handler
    await handle_mcp_request(query_params, body, send_response, send_chunk, streaming=True)
    
    return response


async def handle_mcp_regular(request: web.Request, query_params: Dict[str, Any], body: bytes) -> web.Response:
    """Handle non-streaming MCP requests"""
    
    response_data = None
    
    # Create mock send functions that capture the response
    async def send_response(status, headers):
        # Status and headers handled by web.Response
        pass
    
    async def send_chunk(data, end_response=False):
        nonlocal response_data
        if isinstance(data, bytes):
            data = data.decode()
        if isinstance(data, str):
            try:
                response_data = json.loads(data)
            except:
                response_data = {"data": data}
    
    # Call the MCP handler
    await handle_mcp_request(query_params, body, send_response, send_chunk, streaming=False)
    
    # Return the response
    if response_data:
        return web.json_response(response_data)
    else:
        return web.json_response({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": "No response from MCP handler"
            },
            "id": None
        })