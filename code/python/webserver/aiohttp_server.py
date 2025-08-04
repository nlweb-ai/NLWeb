#!/usr/bin/env python3
import logging    
# We need to set up logging at the very beginning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

import asyncio
import ssl
import sys
import os
from pathlib import Path
from aiohttp import web
import yaml
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check operating system to optimize port reuse
reuse_port_supported = sys.platform != "win32"  # True for Linux/macOS, False for Windows


logger = logging.getLogger(__name__)


class AioHTTPServer:
    """Main aiohttp server implementation for NLWeb"""
    
    def __init__(self, config_path: str = "config/config_webserver.yaml"):
        self.config = self._load_config(config_path)
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        base_path = Path(__file__).parent.parent.parent.parent
        config_file = base_path / config_path
        
        if not config_file.exists():
            logger.warning(f"Config file not found at {config_file}, using defaults")
            return self._get_default_config()
            
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            
        # Override with environment variables
        config['port'] = int(os.environ.get('PORT', config.get('port', 8000)))
        
        # Azure App Service specific
        if os.environ.get('WEBSITE_SITE_NAME'):
            config['server']['host'] = '0.0.0.0'
            logger.info("Running in Azure App Service mode")
            
        return config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'port': 8000,
            'static_directory': '../static',
            'mode': 'development',
            'server': {
                'host': '0.0.0.0',
                'enable_cors': True,
                'max_connections': 100,
                'timeout': 30,
                'ssl': {
                    'enabled': False,
                    'cert_file_env': 'SSL_CERT_FILE',
                    'key_file_env': 'SSL_KEY_FILE'
                }
            }
        }
    
    def _setup_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Setup SSL context if enabled"""
        ssl_config = self.config.get('server', {}).get('ssl', {})
        
        if not ssl_config.get('enabled', False):
            return None
            
        cert_file = os.environ.get(ssl_config.get('cert_file_env', 'SSL_CERT_FILE'))
        key_file = os.environ.get(ssl_config.get('key_file_env', 'SSL_KEY_FILE'))
        
        if not cert_file or not key_file:
            logger.warning("SSL enabled but certificate files not found")
            return None
            
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)
        
        # Configure for modern TLS
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        
        return ssl_context
    
    async def create_app(self) -> web.Application:
        """Create and configure the aiohttp application"""
        # Create application with proper settings
        app = web.Application(
            client_max_size=1024**2 * 10,  # 10MB max request size
        )
        
        # Store config in app for access in handlers
        app['config'] = self.config
        
        # Setup middleware
        from .middleware import setup_middleware
        setup_middleware(app)
        
        # Setup routes
        from .routes import setup_routes
        setup_routes(app)
        
        # Setup startup and cleanup handlers
        app.on_startup.append(self._on_startup)
        app.on_cleanup.append(self._on_cleanup)
        app.on_shutdown.append(self._on_shutdown)
        
        # Setup client session for outgoing requests
        app['client_session'] = None
        
        return app
    
    async def _on_startup(self, app: web.Application):
        """Initialize resources on startup"""
        import aiohttp
        
        # Create shared client session
        timeout = aiohttp.ClientTimeout(total=30)
        app['client_session'] = aiohttp.ClientSession(timeout=timeout)
        
        logger.info(f"Server starting on {self.config['server']['host']}:{self.config['port']}")
        logger.info(f"Mode: {self.config['mode']}")
        logger.info(f"CORS enabled: {self.config['server']['enable_cors']}")
    
    async def _on_cleanup(self, app: web.Application):
        """Cleanup resources"""
        if app['client_session']:
            await app['client_session'].close()
    
    async def _on_shutdown(self, app: web.Application):
        """Graceful shutdown"""
        logger.info("Server shutting down gracefully...")
    
    async def start(self):
        """Start the server"""
        self.app = await self.create_app()
        
        # Create runner
        self.runner = web.AppRunner(
            self.app,
            keepalive_timeout=75,  # Match aiohttp default
            access_log_format='%a %t "%r" %s %b "%{Referer}i" "%{User-Agent}i"'
        )
        
        await self.runner.setup()
        
        # Setup SSL
        ssl_context = self._setup_ssl_context()
        
        # Create site
        self.site = web.TCPSite(
            self.runner,
            self.config['server']['host'],
            self.config['port'],
            ssl_context=ssl_context,
            backlog=128,
            reuse_address=True,
            reuse_port=reuse_port_supported    # Reuse port is not supported by default on Windows and will cause issues
        )
        
        await self.site.start()
        
        protocol = "https" if ssl_context else "http"
        logger.info(f"Server started at {protocol}://{self.config['server']['host']}:{self.config['port']}")
        
        # Keep server running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
    
    async def stop(self):
        """Stop the server gracefully"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        if self.app:
            await self.app.cleanup()


async def main():
    """Main entry point"""
    
    # Suppress verbose HTTP client logging from OpenAI SDK
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    
    # Suppress Azure SDK HTTP logging
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
    
    # Create and start server
    server = AioHTTPServer()
    
    try:
        await server.start()
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())