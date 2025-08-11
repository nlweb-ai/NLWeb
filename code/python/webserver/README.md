# NLWeb Webserver

This directory contains the web server implementation for the NLWeb application, providing both traditional WSGI and modern async HTTP server capabilities.

## Directory Structure

```
webserver/
├── middleware/           # Request/response middleware components
│   ├── auth.py          # Authentication middleware
│   ├── cors.py          # CORS (Cross-Origin Resource Sharing) middleware
│   ├── error_handler.py # Global error handling middleware
│   ├── logging_middleware.py # Request/response logging middleware
│   └── streaming.py     # SSE (Server-Sent Events) streaming support
│
├── routes/              # HTTP route handlers
│   ├── api.py          # Main API endpoints (/sites, /stream, etc.)
│   ├── health.py       # Health check endpoints
│   ├── mcp.py          # MCP (Model Control Plane) endpoints
│   └── static.py       # Static file serving routes
│
├── aiohttp_server.py           # Modern async HTTP server using aiohttp
├── aiohttp_streaming_wrapper.py # SSE streaming wrapper for aiohttp
├── WebServer.py                # Legacy WSGI server implementation
├── StreamingWrapper.py         # Legacy SSE streaming wrapper
├── mcp_wrapper.py              # MCP integration wrapper
└── static_file_handler.py      # Static file serving utilities
```

## Components

### Servers

- **aiohttp_server.py**: The main async HTTP server built on aiohttp framework. Provides high-performance async request handling with support for WebSockets and SSE.

- **WebServer.py**: Legacy WSGI-based server implementation using Flask. Being phased out in favor of the aiohttp implementation.

### Middleware

The middleware layer handles cross-cutting concerns:

- **auth.py**: Handles authentication and authorization
- **cors.py**: Manages CORS headers for cross-origin requests
- **error_handler.py**: Provides centralized error handling and formatting
- **logging_middleware.py**: Logs all incoming requests and outgoing responses
- **streaming.py**: Enables Server-Sent Events for real-time streaming

### Routes

Route modules define the API endpoints:

- **api.py**: Core API endpoints including:
  - `/sites` - List available sites/agents
  - `/stream` - SSE streaming endpoint for real-time responses
  - `/sites/stream` - Combined sites listing with streaming support

- **health.py**: System health monitoring endpoints

- **mcp.py**: Model Control Plane integration endpoints for advanced model management

- **static.py**: Serves static files (HTML, CSS, JavaScript) for the web UI

### Utilities

- **static_file_handler.py**: Helper functions for serving static files with proper MIME types
- **mcp_wrapper.py**: Abstraction layer for MCP protocol integration
- **StreamingWrapper.py** / **aiohttp_streaming_wrapper.py**: Handle SSE protocol implementation for streaming responses

## Usage

The server is typically started via:

```bash
# Using the modern aiohttp server
python python/app-aiohttp.py

# Or directly
python -m webserver.aiohttp_server
```

## Configuration

The server respects various environment variables:

- `HOST`: Server bind address (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `USE_AIOHTTP`: Whether to use aiohttp server (default: true)

## Migration Status

The codebase is transitioning from Flask/WSGI to aiohttp for better async support and performance. Both implementations currently coexist to ensure backward compatibility during the migration period.