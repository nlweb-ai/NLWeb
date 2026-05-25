"""Logging middleware for aiohttp server"""

import time

from aiohttp import web


@web.middleware
async def logging_middleware(request: web.Request, handler):
    """Track request timing and add response headers"""

    start_time = time.time()
    request['start_time'] = start_time

    try:
        response = await handler(request)
        duration = time.time() - start_time
        response.headers['X-Response-Time'] = f"{duration:.3f}s"
        return response
    except web.HTTPException:
        raise
    except Exception:
        raise
