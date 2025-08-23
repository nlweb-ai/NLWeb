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
from datetime import datetime
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
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = "config/config_webserver.yaml"
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
        
        # Initialize chat system components
        await self._initialize_chat_system(app)
        
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
        
        # Shutdown chat system
        if 'conversation_manager' in app:
            await app['conversation_manager'].shutdown()
    
    async def _initialize_chat_system(self, app: web.Application):
        """Initialize chat system components"""
        try:
            from chat.websocket import WebSocketManager
            from chat.conversation import ConversationManager
            from chat.storage import SimpleChatStorageClient
            
            # Initialize WebSocket manager
            app['websocket_manager'] = WebSocketManager(max_connections_per_participant=1)
            
            # Initialize conversation manager
            chat_config = self.config.get('chat', {})
            conv_manager_config = {
                'single_mode_timeout': chat_config.get('single_mode_timeout', 100),
                'multi_mode_timeout': chat_config.get('multi_mode_timeout', 2000),
                'queue_size_limit': chat_config.get('queue_size_limit', 1000),
                'max_participants': chat_config.get('max_participants', 100)
            }
            app['conversation_manager'] = ConversationManager(conv_manager_config)
            
            # Note: Storage is handled through conversation_history API directly
            # No need to initialize a separate storage client
            
            # Store websocket manager in conversation manager
            app['conversation_manager'].websocket_manager = app['websocket_manager']
            
            # Set up WebSocket broadcast callback
            def broadcast_to_conversation(conversation_id: str, message: dict):
                """Broadcast message to all participants in a conversation"""
                ws_manager = app['websocket_manager']
                asyncio.create_task(
                    ws_manager.broadcast_to_conversation(conversation_id, message)
                )
            
            app['conversation_manager'].broadcast_callback = broadcast_to_conversation
            
            # Set up WebSocket manager callbacks
            ws_manager = app['websocket_manager']
            conv_manager = app['conversation_manager']
            
            # Participant verification callback
            async def verify_participant(conversation_id: str, participant_id: str) -> bool:
                """With simple storage, allow all participants"""
                # In simple storage mode, we don't track participants
                # Just allow the connection
                return True
            
            ws_manager.verify_participant_callback = verify_participant
            
            # Get participants callback
            async def get_participants(conversation_id: str) -> Dict[str, Any]:
                """Get current participants for a conversation"""
                # With simple storage, get participants from ConversationManager
                if conversation_id not in conv_manager._conversations:
                    return {"participants": [], "count": 0}
                
                conv_state = conv_manager._conversations[conversation_id]
                
                # Check online status
                online_ids = set()
                if conversation_id in ws_manager._connections:
                    online_ids = set(ws_manager._connections[conversation_id].keys())
                
                # Build participant list from conversation state
                participants = []
                for participant_id, participant in conv_state.participants.items():
                    # Get participant info
                    p_info = participant.get_participant_info()
                    participants.append({
                        "participantId": p_info.participant_id,
                        "displayName": p_info.name,
                        "type": p_info.participant_type.value,
                        "joinedAt": datetime.utcfromtimestamp(p_info.joined_at / 1000).isoformat() + 'Z' if p_info.joined_at else datetime.utcnow().isoformat() + 'Z',
                        "isOnline": p_info.participant_id in online_ids
                    })
                
                return {
                    "participants": participants,
                    "count": len(participants)
                }
            
            ws_manager.get_participants_callback = get_participants
            
            # Set up NLWeb handler class for chat system
            try:
                from core.baseHandler import NLWebHandler
                app['nlweb_handler'] = NLWebHandler
                logger.info("NLWebHandler configured for chat system")
            except ImportError as e:
                logger.error(f"Failed to import NLWebHandler: {e}")
                app['nlweb_handler'] = None
            
            logger.info("Chat system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize chat system: {e}", exc_info=True)
            # Chat is optional, so we don't fail the server startup
    
    async def start(self):
        """Start the server"""
        # Check if port is already in use
        import socket
        port = self.config['port']
        host = self.config['server']['host']
        
        # Try to bind to the port to check if it's available
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            # Try to bind to the port
            if host == '0.0.0.0':
                # Check on localhost since 0.0.0.0 means all interfaces
                sock.bind(('127.0.0.1', port))
            else:
                sock.bind((host, port))
        except OSError as e:
            sock.close()  # Make sure to close the socket on error
            if e.errno == 48:  # Address already in use on macOS
                logger.error(f"Port {port} is already in use!")
                logger.error("Another server instance may be running.")
                logger.error(f"To find the process: lsof -i :{port}")
                logger.error(f"To kill it: kill $(lsof -t -i :{port})")
                raise SystemExit(f"Error: Port {port} is already in use. Please stop the other server or use a different port.")
            elif e.errno == 98:  # Address already in use on Linux
                logger.error(f"Port {port} is already in use!")
                logger.error("Another server instance may be running.")
                logger.error(f"To find the process: netstat -tulpn | grep {port}")
                raise SystemExit(f"Error: Port {port} is already in use. Please stop the other server or use a different port.")
            else:
                # Re-raise other socket errors
                raise
        finally:
            # Always close the socket
            sock.close()
        
        self.app = await self.create_app()
        
        # Create runner
        self.runner = web.AppRunner(
            self.app,
            keepalive_timeout=75,  # Match aiohttp default
            access_log_format='%a %t "%r" %s %b "%{Referer}i" "%{User-Agent}i"'
        )
        
        await self.runner.setup()
        
        # Check platform support for reuse_port
        reuse_port_supported = sys.platform not in ['win32', 'cygwin']
        
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
    
    # Suppress aiohttp access logs
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    
    # Suppress webserver middleware logging
    logging.getLogger("webserver.middleware.logging_middleware").setLevel(logging.WARNING)
    
    # Suppress chat system logging
    logging.getLogger("webserver.routes.chat").setLevel(logging.WARNING)
    logging.getLogger("chat.conversation").setLevel(logging.WARNING)
    logging.getLogger("chat.participants").setLevel(logging.WARNING)
    logging.getLogger("chat.websocket").setLevel(logging.WARNING)
    
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