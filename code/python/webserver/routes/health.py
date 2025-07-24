"""Health check routes for aiohttp server"""

from aiohttp import web
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

# Server start time
SERVER_START_TIME = time.time()


def setup_health_routes(app: web.Application):
    """Setup health check routes"""
    app.router.add_get('/health', health_check)
    app.router.add_get('/ready', readiness_check)


async def health_check(request: web.Request) -> web.Response:
    """Basic health check endpoint"""
    
    uptime = time.time() - SERVER_START_TIME
    
    return web.json_response({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'uptime_seconds': round(uptime, 2),
        'version': '2.0.0',  # TODO: Get from config or package
        'mode': request.app['config'].get('mode', 'unknown')
    })


async def readiness_check(request: web.Request) -> web.Response:
    """Readiness check - verifies all dependencies are available"""
    
    checks = {}
    all_ready = True
    
    # Check static files
    static_path = request.app.get('static_path')
    if static_path and static_path.exists():
        checks['static_files'] = True
    else:
        checks['static_files'] = False
        all_ready = False
    
    # Check client session
    if request.app.get('client_session'):
        checks['http_client'] = True
    else:
        checks['http_client'] = False
        all_ready = False
    
    # TODO: Add more checks as needed
    # - Database connectivity
    # - External API availability
    # - Cache connectivity
    
    status_code = 200 if all_ready else 503
    
    return web.json_response({
        'status': 'ready' if all_ready else 'not_ready',
        'checks': checks,
        'timestamp': datetime.utcnow().isoformat()
    }, status=status_code)