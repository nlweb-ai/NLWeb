"""OAuth routes for authentication"""

from aiohttp import web
import aiohttp
import logging
import json
import jwt
import secrets
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import os
from pathlib import Path
from core.config import CONFIG

logger = logging.getLogger(__name__)


def setup_oauth_routes(app: web.Application):
    """Setup OAuth routes"""
    logger.info("Setting up OAuth routes")
    app.router.add_get('/api/oauth/config', oauth_config_handler)
    app.router.add_get('/oauth/{provider}', oauth_login_handler)
    app.router.add_get('/oauth/callback/{provider}', oauth_callback_handler)
    app.router.add_post('/api/oauth/token', oauth_token_handler)
    app.router.add_post('/api/oauth/logout', oauth_logout_handler)
    app.router.add_get('/api/oauth/validate', oauth_validate_handler)
    logger.info(f"OAuth providers available in CONFIG: {list(CONFIG.oauth_providers.keys()) if hasattr(CONFIG, 'oauth_providers') else 'None'}")


async def oauth_config_handler(request: web.Request) -> web.Response:
    """
    Get OAuth configuration for enabled providers.
    
    Returns:
        200: {
            "google": {
                "enabled": true,
                "client_id": "...",
                "auth_url": "...",
                "redirect_uri": "...",
                "scope": "..."
            },
            ...
        }
    """
    try:
        # Use the global CONFIG which has OAuth providers loaded
        oauth_providers = CONFIG.oauth_providers if hasattr(CONFIG, 'oauth_providers') else {}
        
        # Build response with enabled providers and their config
        response = {}
        base_url = f"{request.scheme}://{request.host}"
        
        for provider_name, provider_config in oauth_providers.items():
            response[provider_name] = {
                "enabled": True,
                "client_id": provider_config.get("client_id"),
                "auth_url": provider_config.get("auth_url"),
                "redirect_uri": f"{base_url}/oauth/callback/{provider_name}",
                "scope": provider_config.get("scope")
            }
            
        logger.info(f"OAuth config requested, returning {len(response)} providers: {list(response.keys())}")
        return web.json_response(response)
        
    except Exception as e:
        logger.error(f"Error getting OAuth config: {e}")
        return web.json_response({})


async def oauth_login_handler(request: web.Request) -> web.Response:
    """Handle OAuth login redirect"""
    provider = request.match_info['provider']
    
    # Check if provider is configured
    oauth_providers = CONFIG.oauth_providers if hasattr(CONFIG, 'oauth_providers') else {}
    if provider not in oauth_providers:
        return web.json_response(
            {'error': f'OAuth provider {provider} not configured'},
            status=400
        )
    
    provider_config = oauth_providers[provider]
    
    # Build OAuth authorization URL
    base_url = f"{request.scheme}://{request.host}"
    redirect_uri = f"{base_url}/oauth/callback/{provider}"
    
    # Create state parameter for CSRF protection
    state = secrets.token_urlsafe(32)
    request.app['oauth_states'] = getattr(request.app, 'oauth_states', {})
    request.app['oauth_states'][state] = {
        'provider': provider,
        'created_at': time.time()
    }
    
    # Build authorization URL based on provider
    auth_params = {
        'client_id': provider_config['client_id'],
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': provider_config['scope']
    }
    
    if provider == 'google':
        auth_params.update({
            'response_type': 'code',
            'access_type': 'online',
            'prompt': 'select_account'
        })
    elif provider == 'github':
        # GitHub uses minimal parameters
        pass
    elif provider == 'microsoft':
        auth_params.update({
            'response_type': 'code',
            'prompt': 'select_account'
        })
    elif provider == 'facebook':
        auth_params.update({
            'response_type': 'code'
        })
    
    # Build URL with parameters
    auth_url = provider_config['auth_url']
    params = '&'.join([f"{k}={v}" for k, v in auth_params.items()])
    full_auth_url = f"{auth_url}?{params}"
    
    # Redirect to OAuth provider
    return web.Response(
        status=302,
        headers={'Location': full_auth_url}
    )


async def oauth_callback_handler(request: web.Request) -> web.Response:
    """Handle OAuth callback - serves the callback HTML page"""
    provider = request.match_info['provider']
    
    # Serve the oauth-callback.html file
    try:
        static_dir = Path(__file__).parent.parent.parent.parent.parent / 'static'
        callback_file = static_dir / 'oauth-callback.html'
        
        if not callback_file.exists():
            logger.error(f"OAuth callback HTML file not found at {callback_file}")
            return web.Response(
                text='OAuth callback page not found',
                status=404
            )
        
        with open(callback_file, 'r') as f:
            html_content = f.read()
        
        # Return the HTML page
        return web.Response(
            text=html_content,
            content_type='text/html'
        )
        
    except Exception as e:
        logger.error(f"Error serving OAuth callback page: {e}")
        return web.Response(
            text='Internal server error',
            status=500
        )


async def oauth_token_handler(request: web.Request) -> web.Response:
    """
    Exchange OAuth authorization code for access token.
    
    POST /api/oauth/token
    {
        "code": "authorization_code",
        "provider": "github",
        "redirect_uri": "http://localhost:8000/oauth/callback/github"
    }
    """
    try:
        data = await request.json()
        code = data.get('code')
        provider = data.get('provider')
        redirect_uri = data.get('redirect_uri')
        
        if not all([code, provider, redirect_uri]):
            return web.json_response(
                {'error': 'Missing required parameters'},
                status=400
            )
        
        # Get provider configuration
        oauth_providers = CONFIG.oauth_providers if hasattr(CONFIG, 'oauth_providers') else {}
        if provider not in oauth_providers:
            return web.json_response(
                {'error': f'OAuth provider {provider} not configured'},
                status=400
            )
        
        provider_config = oauth_providers[provider]
        
        # Exchange code for token
        async with aiohttp.ClientSession() as session:
            token_data = {
                'client_id': provider_config['client_id'],
                'client_secret': provider_config['client_secret'],
                'code': code,
                'redirect_uri': redirect_uri
            }
            
            # Provider-specific token exchange
            if provider == 'google':
                token_data['grant_type'] = 'authorization_code'
            elif provider == 'github':
                # GitHub wants Accept header for JSON response
                headers = {'Accept': 'application/json'}
            elif provider == 'microsoft':
                token_data['grant_type'] = 'authorization_code'
            elif provider == 'facebook':
                token_data['grant_type'] = 'authorization_code'
            
            # Make token exchange request
            headers = getattr(locals(), 'headers', {})
            async with session.post(
                provider_config['token_url'],
                data=token_data,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Token exchange failed for {provider}: {error_text}")
                    return web.json_response(
                        {'error': 'Token exchange failed'},
                        status=400
                    )
                
                # Parse token response
                if provider == 'github':
                    # GitHub returns form-encoded by default unless Accept: application/json
                    if 'json' in resp.headers.get('Content-Type', ''):
                        token_response = await resp.json()
                    else:
                        text = await resp.text()
                        token_response = dict(x.split('=') for x in text.split('&'))
                else:
                    token_response = await resp.json()
                
                access_token = token_response.get('access_token')
                if not access_token:
                    logger.error(f"No access token in response from {provider}")
                    return web.json_response(
                        {'error': 'No access token received'},
                        status=400
                    )
            
            # Get user info
            user_info = await get_user_info(session, provider, access_token, provider_config)
            
            if not user_info:
                return web.json_response(
                    {'error': 'Failed to get user information'},
                    status=400
                )
            
            # Create JWT token for our application
            jwt_payload = {
                'user_id': user_info.get('id'),
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'provider': provider,
                'exp': int((datetime.utcnow() + timedelta(seconds=CONFIG.oauth_token_expiration)).timestamp()),
                'iat': int(datetime.utcnow().timestamp())
            }
            
            # Use session secret for JWT
            jwt_secret = CONFIG.oauth_session_secret
            app_token = jwt.encode(jwt_payload, jwt_secret, algorithm='HS256')
            
            # Return success response
            return web.json_response({
                'access_token': app_token,
                'token_type': 'Bearer',
                'expires_in': CONFIG.oauth_token_expiration,
                'user_info': user_info
            })
            
    except Exception as e:
        logger.error(f"Error in OAuth token exchange: {e}", exc_info=True)
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )


async def get_user_info(session: aiohttp.ClientSession, provider: str, access_token: str, provider_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get user information from OAuth provider"""
    try:
        headers = {'Authorization': f'Bearer {access_token}'}
        
        if provider == 'github':
            # GitHub uses different header format
            headers = {'Authorization': f'token {access_token}'}
        
        # Get basic user info
        async with session.get(provider_config['userinfo_url'], headers=headers) as resp:
            if resp.status != 200:
                logger.error(f"Failed to get user info from {provider}: {resp.status}")
                return None
            
            user_data = await resp.json()
        
        # Normalize user info across providers
        user_info = {}
        
        if provider == 'google':
            user_info = {
                'id': user_data.get('id'),
                'email': user_data.get('email'),
                'name': user_data.get('name'),
                'picture': user_data.get('picture')
            }
        elif provider == 'github':
            user_info = {
                'id': str(user_data.get('id')),
                'email': user_data.get('email'),
                'name': user_data.get('name') or user_data.get('login'),
                'picture': user_data.get('avatar_url')
            }
            
            # GitHub may not return email in user endpoint
            if not user_info['email'] and provider_config.get('emails_url'):
                async with session.get(provider_config['emails_url'], headers=headers) as resp:
                    if resp.status == 200:
                        emails = await resp.json()
                        primary_email = next((e['email'] for e in emails if e.get('primary')), None)
                        if primary_email:
                            user_info['email'] = primary_email
        
        elif provider == 'microsoft':
            user_info = {
                'id': user_data.get('id'),
                'email': user_data.get('mail') or user_data.get('userPrincipalName'),
                'name': user_data.get('displayName'),
                'picture': None  # Microsoft Graph doesn't return photo URL directly
            }
        elif provider == 'facebook':
            user_info = {
                'id': user_data.get('id'),
                'email': user_data.get('email'),
                'name': user_data.get('name'),
                'picture': user_data.get('picture', {}).get('data', {}).get('url')
            }
        
        return user_info
        
    except Exception as e:
        logger.error(f"Error getting user info from {provider}: {e}")
        return None


async def oauth_validate_handler(request: web.Request) -> web.Response:
    """
    Validate OAuth token.
    
    GET /api/oauth/validate
    Headers: Authorization: Bearer <token>
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return web.json_response(
                {'valid': False, 'error': 'Invalid authorization header'},
                status=401
            )
        
        token = auth_header[7:]
        
        # Validate JWT token
        try:
            jwt_secret = CONFIG.oauth_session_secret
            payload = jwt.decode(token, jwt_secret, algorithms=['HS256'])
            
            # Check if token is expired
            if payload.get('exp') < time.time():
                return web.json_response(
                    {'valid': False, 'error': 'Token expired'},
                    status=401
                )
            
            # Token is valid
            return web.json_response({
                'valid': True,
                'user_info': {
                    'id': payload.get('user_id'),
                    'email': payload.get('email'),
                    'name': payload.get('name'),
                    'provider': payload.get('provider')
                }
            })
            
        except jwt.InvalidTokenError as e:
            return web.json_response(
                {'valid': False, 'error': 'Invalid token'},
                status=401
            )
            
    except Exception as e:
        logger.error(f"Error validating token: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )


async def oauth_logout_handler(request: web.Request) -> web.Response:
    """Handle logout"""
    # For JWT tokens, logout is handled client-side by removing the token
    # Server can optionally maintain a blacklist of revoked tokens
    return web.json_response({"success": True, "message": "Logged out successfully"})