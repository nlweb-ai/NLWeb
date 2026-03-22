"""Static file serving routes for aiohttp server"""

from aiohttp import web
import logging
import os
from pathlib import Path
from core.config import CONFIG

logger = logging.getLogger(__name__)


def setup_static_routes(app: web.Application):
    """Setup static file serving routes"""
    
    config = app.get('config', {})
    static_dir = config.get('static_directory', '../static')
    
    # Convert to absolute path
    base_path = Path(__file__).parent.parent.parent.parent.parent
    static_path = base_path / static_dir.lstrip('../')
    
    if not static_path.exists():
        logger.warning(f"Static directory not found at {static_path}")
        # Try alternate path
        static_path = Path(__file__).parent.parent / 'static'
        if not static_path.exists():
            logger.error("Could not find static directory")
            return
    
    logger.info(f"Serving static files from: {static_path}")
    
    # Serve index.html for root path
    app.router.add_get('/', index_handler)
    
    # Serve static files
    app.router.add_static(
        '/static/', 
        path=static_path,
        name='static',
        show_index=False,
        follow_symlinks=False
    )
    
    # Serve HTML files
    html_path = static_path / 'html'
    if html_path.exists():
        app.router.add_static(
            '/html/', 
            path=html_path,
            name='html',
            show_index=False,
            follow_symlinks=False
        )
    
    # Store static path in app for use in handlers
    app['static_path'] = static_path


async def index_handler(request: web.Request) -> web.Response:
    """Serve homepage file specified in config for root path"""

    static_path = request.app.get('static_path')
    if not static_path:
        return web.Response(text="Static files not configured", status=500)

    # Get homepage from config, default to 'static/index.html' if not set
    homepage = getattr(CONFIG, 'homepage', 'static/index.html')

    # Remove 'static/' prefix if present since we're already in the static directory
    if homepage.startswith('static/'):
        homepage = homepage[7:]  # Remove 'static/' prefix

    homepage_file = static_path / homepage

    if not homepage_file.exists():
        logger.error(f"Homepage file not found at {homepage_file}")
        # Fall back to index.html if configured homepage doesn't exist
        fallback_file = static_path / 'index.html'
        if fallback_file.exists():
            logger.warning(f"Using fallback index.html instead of configured homepage: {homepage}")
            homepage_file = fallback_file
        else:
            return web.Response(text=f"Homepage file '{homepage}' not found", status=404)

    return web.FileResponse(
        homepage_file,
        headers={
            'Cache-Control': 'no-cache',
            'Content-Type': 'text/html; charset=utf-8'
        }
    )