"""Authentication middleware for aiohttp server"""

from aiohttp import web
import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS: Set[str] = {
    '/',
    '/health',
    '/ready',
    '/oauth/callback',
    '/api/oauth/config',
    '/who',
    '/sites',
    # Static files
    '/static',
    '/html',
    # Allow public access to ask endpoint for now (can be changed)
    '/ask'
}


@web.middleware
async def auth_middleware(request: web.Request, handler):
    """Handle authentication for protected endpoints"""
    
    # Check if path is public
    path = request.path
    
    # Check exact matches and path prefixes
    is_public = (
        path in PUBLIC_ENDPOINTS or
        path.startswith('/static/') or
        path.startswith('/html/') or
        path == '/favicon.ico'
    )
    
    if is_public:
        # Public endpoint, no auth required
        return await handler(request)
    
    # Check for authentication token
    auth_token = None
    
    # Check Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        auth_token = auth_header[7:]
    
    # Check cookie (for web UI)
    if not auth_token:
        auth_cookie = request.cookies.get('auth_token')
        if auth_cookie:
            auth_token = auth_cookie
    
    # Check query parameter (for SSE connections that can't set headers)
    if not auth_token and request.method == 'GET':
        auth_token = request.query.get('auth_token')
    
    # For now, we'll allow requests without tokens in development mode
    config = request.app.get('config', {})
    mode = config.get('mode', 'production')
    
    if not auth_token and mode == 'development':
        logger.debug(f"No auth token for {path}, allowing in development mode")
        request['user'] = {'id': 'dev_user', 'authenticated': False}
        return await handler(request)
    
    if not auth_token:
        logger.warning(f"No auth token provided for protected endpoint: {path}")
        return web.json_response(
            {'error': 'Authentication required', 'type': 'auth_required'},
            status=401,
            headers={'WWW-Authenticate': 'Bearer'}
        )
    
    # TODO: Validate token with OAuth provider or JWT validation
    # For now, we'll just store the token in the request
    request['auth_token'] = auth_token
    request['user'] = {
        'id': 'authenticated_user',
        'authenticated': True,
        'token': auth_token
    }
    
    # Continue to handler
    return await handler(request)