"""A2A (Agent-to-Agent) protocol routes for aiohttp server"""

from aiohttp import web
import logging
import json
from typing import Dict, Any
from webserver.a2a_wrapper import handle_a2a_request

logger = logging.getLogger(__name__)


def setup_a2a_routes(app: web.Application):
    """Setup A2A routes"""
    # A2A health check endpoints
    app.router.add_get('/a2a/health', a2a_health)
    app.router.add_get('/a2a/healthz', a2a_health)
    
    # Main A2A endpoint
    app.router.add_post('/a2a', a2a_handler)
    app.router.add_get('/a2a', a2a_info)
    
    # A2A with path (for future extensions)
    app.router.add_post('/a2a/{path:.*}', a2a_handler)


async def a2a_health(request: web.Request) -> web.Response:
    """A2A health check endpoint"""
    return web.json_response({
        "status": "ok",
        "protocol": "A2A",
        "version": "1.0.0"
    })


async def a2a_info(request: web.Request) -> web.Response:
    """A2A info endpoint for GET requests"""
    return web.json_response({
        "protocol": "A2A",
        "version": "1.0.0",
        "agent_id": "nlweb-agent",
        "capabilities": ["ask", "list_sites"],
        "description": "NLWeb A2A Agent - Query and analyze information from configured data sources",
        "endpoints": {
            "message": "POST /a2a",
            "health": "GET /a2a/health"
        }
    })


async def a2a_handler(request: web.Request) -> web.Response:
    """Handle A2A requests"""
    
    try:
        # Get query parameters
        query_params = dict(request.query)
        
        # Get body for POST requests
        body = None
        if request.method == 'POST':
            if request.has_body:
                body = await request.read()
        
        # Process A2A request
        response_data = None
        
        # Create response capture functions
        async def send_response(status, headers):
            # Headers handled by web.Response
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
        
        # Call the A2A handler
        await handle_a2a_request(query_params, body, send_response, send_chunk)
        
        # Return the response
        if response_data:
            return web.json_response(response_data)
        else:
            return web.json_response({
                "version": "1.0.0",
                "type": "error",
                "content": {"error": "No response from A2A handler"}
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error in A2A handler: {e}", exc_info=True)
        return web.json_response({
            "version": "1.0.0",
            "type": "error",
            "content": {"error": str(e)}
        }, status=500)