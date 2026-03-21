"""Error handling middleware for aiohttp server"""

from aiohttp import web
import logging
import traceback
import json
from typing import Dict, Any

logger = logging.getLogger(__name__)


@web.middleware
async def error_middleware(request: web.Request, handler):
    """Handle errors and exceptions uniformly"""
    
    try:
        return await handler(request)
    
    except web.HTTPException:
        # Let aiohttp handle HTTP exceptions normally
        raise
    
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode error: {e}")
        return web.json_response(
            {
                'error': 'Invalid JSON in request body',
                'type': 'json_error',
                'details': str(e)
            },
            status=400
        )
    
    except ValueError as e:
        logger.warning(f"Value error: {e}")
        return web.json_response(
            {
                'error': 'Invalid request parameter',
                'type': 'value_error',
                'details': str(e)
            },
            status=400
        )
    
    except Exception as e:
        # Log the full exception with traceback
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        
        # Get mode from config
        config = request.app.get('config', {})
        mode = config.get('mode', 'production')
        
        # Prepare error response
        error_response: Dict[str, Any] = {
            'error': 'Internal server error',
            'type': 'internal_error'
        }
        
        # In development/testing mode, include more details
        if mode in ['development', 'testing']:
            error_response['details'] = str(e)
            error_response['traceback'] = traceback.format_exc().split('\n')
        
        # In testing mode, re-raise the exception
        if mode == 'testing':
            raise
        
        return web.json_response(error_response, status=500)