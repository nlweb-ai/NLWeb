"""CORS middleware for aiohttp server"""

from aiohttp import web
import logging

logger = logging.getLogger(__name__)


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Handle CORS headers for all requests"""
    
    # Get CORS configuration from app config
    config = request.app.get('config', {})
    cors_enabled = config.get('server', {}).get('enable_cors', True)
    
    if not cors_enabled:
        return await handler(request)
    
    # CORS headers
    cors_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Max-Age': '3600'
    }
    
    # Handle preflight OPTIONS requests
    if request.method == 'OPTIONS':
        return web.Response(
            status=200,
            headers=cors_headers
        )
    
    # Process the request
    try:
        response = await handler(request)
    except web.HTTPException as ex:
        # Add CORS headers to HTTP exceptions
        ex.headers.update(cors_headers)
        raise
    
    # Add CORS headers to successful responses
    response.headers.update(cors_headers)
    
    return response