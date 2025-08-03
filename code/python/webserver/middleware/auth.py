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
    
    # Extract user ID from token for testing
    # E2E tests use format: "Bearer e2e_token_{user_id}" or "Bearer e2e_{identifier}"
    user_id = 'authenticated_user'  # default
    user_name = 'User'
    
    if auth_token.startswith('e2e_'):
        # Extract user info from E2E test tokens
        parts = auth_token.split('_')
        if len(parts) >= 2:
            # Handle formats like "e2e_test_single_user" or "e2e_creator_token"
            if len(parts) == 3 and parts[1] in ['test', 'token']:
                user_id = parts[2]
            elif len(parts) == 3:
                user_id = f"{parts[1]}_{parts[2]}"
            else:
                user_id = parts[1]
            user_name = user_id.replace('_', ' ').title()
    elif auth_token.startswith('test_token_'):
        # Integration test format
        user_id = auth_token.replace('test_token_', '')
        user_name = f"Test User {user_id}"
    
    request['user'] = {
        'id': user_id,
        'name': user_name,
        'authenticated': True,
        'token': auth_token
    }
    
    # Continue to handler
    return await handler(request)