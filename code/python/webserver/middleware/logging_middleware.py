"""Logging middleware for aiohttp server"""

from aiohttp import web
import logging
import time
import json
from typing import Optional

logger = logging.getLogger(__name__)


@web.middleware
async def logging_middleware(request: web.Request, handler):
    """Log all requests and responses"""
    
    start_time = time.time()
    
    # Extract request info
    request_info = {
        'method': request.method,
        'path': request.path,
        'query': dict(request.query),
        'headers': dict(request.headers),
        'remote': request.remote,
        'scheme': request.scheme,
        'host': request.host
    }
    
    # Log request (exclude sensitive headers)
    safe_headers = {k: v for k, v in request_info['headers'].items() 
                   if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
    
    logger.info(f"Request: {request.method} {request.path}", extra={
        'request_method': request.method,
        'request_path': request.path,
        'request_query': request_info['query'],
        'request_headers': safe_headers,
        'request_remote': request_info['remote']
    })
    
    # Store request start time for use in handlers
    request['start_time'] = start_time
    
    try:
        # Process request
        response = await handler(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"Response: {request.method} {request.path} - {response.status} ({duration:.3f}s)",
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'response_status': response.status,
                'response_duration': duration,
                'response_size': response.content_length or 0
            }
        )
        
        # Add timing header
        response.headers['X-Response-Time'] = f"{duration:.3f}s"
        
        return response
        
    except web.HTTPException as ex:
        # Log HTTP exceptions
        duration = time.time() - start_time
        logger.warning(
            f"HTTP Exception: {request.method} {request.path} - {ex.status} ({duration:.3f}s)",
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'response_status': ex.status,
                'response_duration': duration,
                'error_reason': ex.reason
            }
        )
        raise
        
    except Exception as e:
        # Log other exceptions
        duration = time.time() - start_time
        logger.error(
            f"Exception: {request.method} {request.path} - 500 ({duration:.3f}s)",
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'response_status': 500,
                'response_duration': duration,
                'error_type': type(e).__name__,
                'error_message': str(e)
            }
        )
        raise