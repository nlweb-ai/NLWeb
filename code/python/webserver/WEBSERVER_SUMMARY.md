# Webserver Directory Summary

## Overview
The webserver directory contains the aiohttp-based HTTP server implementation for NLWeb, providing REST APIs, WebSocket support, OAuth authentication, and static file serving.

## Core Components

### Main Server (`aiohttp_server.py`)
- **AioHTTPServer class**: Main server implementation
  - Handles configuration loading from YAML files
  - SSL/TLS support with configurable certificates
  - Azure App Service compatibility
  - Creates and manages aiohttp application lifecycle
  - Port: 8000 (default), configurable via environment

### Request Handlers

#### API Routes (`routes/api.py`)
- `/ask` - Main query endpoint supporting streaming and non-streaming responses
  - `ask_handler`: Processes natural language queries
  - `handle_streaming_ask`: Server-sent events for streaming responses
  - `handle_regular_ask`: Standard JSON responses
- `/who` - User identification endpoint
- `/sites` - Available data sources endpoint

#### Chat Routes (`routes/chat.py`)
- `/api/chat/conversation` - Conversation management
  - `create_conversation_handler`: Create new conversations
  - `list_conversations_handler`: List user's conversations
  - `get_conversation_handler`: Get specific conversation details
- `/api/chat/conversation/{id}/join` - Join existing conversation
- `/api/chat/conversation/{id}/leave` - Leave conversation
- `/api/chat/share/{share_link}` - Join via share link
- `/ws/chat` - WebSocket endpoint for real-time chat
  - `websocket_handler`: Manages WebSocket connections
  - Handles message routing, participant management
  - Supports reconnection with session recovery

#### OAuth Routes (`routes/oauth.py`)
- `/api/oauth/config` - OAuth provider configuration
- `/api/oauth/login` - Initiate OAuth flow
- `/api/oauth/callback` - OAuth provider callback
- `/api/oauth/token` - Token exchange and refresh
- `/api/oauth/validate` - Token validation
- `/api/oauth/logout` - User logout
- Supports: Google, Facebook, Microsoft, GitHub

#### MCP Routes (`routes/mcp.py`)
- `/mcp` - Model Context Protocol endpoint
  - Handles both streaming and regular responses
  - Integrates with MCPHandler for query processing

#### Static Routes (`routes/static.py`)
- Serves frontend files from static directory
- Special handling for:
  - `/` - Main index page
  - `/multi-chat-index.html` - Multi-chat interface
  - `/fp-chat-interface.html` - Main chat interface
  - Static assets (JS, CSS, images)

#### Health Routes (`routes/health.py`)
- `/health` - Basic health check
- `/ready` - Readiness probe with dependency checks

#### Conversation Routes (`routes/conversation.py`)
- `/api/conversation/{id}` - Get conversation details
- `/api/conversations/user/{user_id}` - Get user's conversations

### Middleware

#### Authentication (`middleware/auth.py`)
- `auth_middleware`: JWT token validation
- Protects API endpoints
- Extracts user context from tokens
- Whitelist for public endpoints

#### CORS (`middleware/cors.py`)
- `cors_middleware`: Cross-origin resource sharing
- Configurable allowed origins
- Handles preflight requests

#### Error Handling (`middleware/error_handler.py`)
- `error_middleware`: Global error handling
- Structured error responses
- Logging of exceptions

#### Logging (`middleware/logging_middleware.py`)
- `logging_middleware`: Request/response logging
- Performance metrics
- Debug information

#### Streaming (`middleware/streaming.py`)
- `streaming_middleware`: SSE support
- Handles streaming responses
- Chunk management

### Wrappers and Utilities

#### MCP Wrapper (`mcp_wrapper.py`)
- **MCPHandler class**: Model Context Protocol handler
  - Integrates with core processing engine
  - Manages query parameters and context
  - Handles streaming and regular responses
  - Error handling and retry logic

#### Streaming Wrapper (`aiohttp_streaming_wrapper.py`)
- **AioHttpStreamingWrapper class**: SSE implementation
  - Server-sent events formatting
  - Chunk sending with proper headers
  - Connection management
  - Error recovery

## Key Features

### WebSocket Support
- Real-time bidirectional communication
- Message types: query, response, participant updates
- Connection state management
- Automatic reconnection support
- Session persistence

### Streaming Responses
- Server-sent events (SSE) for long-running queries
- Chunked transfer encoding
- Progress updates during processing
- Graceful connection handling

### Security
- JWT authentication
- OAuth 2.0 integration
- CORS protection
- SSL/TLS support
- Request size limits

### Configuration
- YAML-based configuration
- Environment variable overrides
- Development/production modes
- Azure App Service compatibility

## Integration Points

### With Core Module
- Imports processing engine from `core/`
- Uses configuration from `core/config.py`
- Integrates with conversation manager

### With Methods Module
- Calls query processing methods
- Handles response formatting
- Error propagation

### With Frontend
- Serves static files
- WebSocket communication
- RESTful API endpoints
- SSE streaming

## Error Handling
- Global exception catching
- Structured error responses
- Client-friendly error messages
- Detailed logging for debugging
- Graceful degradation

## Performance Considerations
- Connection pooling
- Async/await throughout
- Configurable timeouts
- Request size limits
- Resource cleanup

## Dependencies
- aiohttp: Web server framework
- PyYAML: Configuration parsing
- PyJWT: Token handling
- aiohttp-cors: CORS support
- SSL support for HTTPS

## Entry Point
Main entry: `aiohttp_server.py:main()`
- Creates server instance
- Loads configuration
- Sets up routes and middleware
- Starts event loop