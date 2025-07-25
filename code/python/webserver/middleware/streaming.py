"""Streaming response middleware for aiohttp server"""

from aiohttp import web
from aiohttp.web import FileResponse
import logging

logger = logging.getLogger(__name__)


@web.middleware
async def streaming_middleware(request: web.Request, handler):
    """Add streaming utilities and headers to request/response"""
    
    # Check if this is an SSE (Server-Sent Events) request
    accept_header = request.headers.get('Accept', '')
    is_sse = (
        'text/event-stream' in accept_header or
        request.query.get('stream', '').lower() in ['true', '1', 'yes']
    )
    
    # Add streaming info to request
    request['is_sse'] = is_sse
    request['is_streaming'] = is_sse  # Can be extended for other streaming types
    
    # Process request
    response = await handler(request)
    
    # If it's a StreamResponse (but not FileResponse), ensure proper headers
    if isinstance(response, web.StreamResponse) and not isinstance(response, web.FileResponse):
        # Disable buffering for streaming responses
        response.headers['X-Accel-Buffering'] = 'no'
        
        # For SSE responses, ensure proper content type
        if is_sse and 'Content-Type' not in response.headers:
            response.headers['Content-Type'] = 'text/event-stream'
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['Connection'] = 'keep-alive'
        
        # Ensure chunked encoding for streaming (but not for FileResponse)
        if not response.prepared:
            response.enable_chunked_encoding()
    
    return response