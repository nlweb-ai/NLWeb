"""Routes package for aiohttp server"""

from .static import setup_static_routes
from .api import setup_api_routes
from .health import setup_health_routes
from .mcp import setup_mcp_routes
from .a2a import setup_a2a_routes
from .conversation import setup_conversation_routes
from .chat import setup_chat_routes
from .oauth import setup_oauth_routes


def setup_routes(app):
    """Setup all routes for the application"""
    setup_static_routes(app)
    setup_api_routes(app)
    setup_health_routes(app)
    setup_mcp_routes(app)
    setup_a2a_routes(app)
    setup_conversation_routes(app)
    setup_chat_routes(app)
    setup_oauth_routes(app)


__all__ = ['setup_routes']