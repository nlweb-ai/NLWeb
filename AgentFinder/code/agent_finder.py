"""
Web server with REST and MCP endpoints for WHO handler.
"""
import os
import json
import asyncio
import sys
from pathlib import Path
from typing import Optional
from aiohttp import web

import who_handler

# Server configuration
PORT = int(os.getenv("WHO_SERVER_PORT", "8080"))
HOST = os.getenv("WHO_SERVER_HOST", "0.0.0.0")

# MCP Protocol version
MCP_PROTOCOL_VERSION = "2024-11-05"


# ========== REST ENDPOINTS ==========

async def who_endpoint(request: web.Request) -> web.Response:
    """REST endpoint for WHO queries - supports both GET and POST"""
    try:
        # Support both GET and POST requests
        if request.method == "GET":
            # Get query from URL parameters
            query = request.query.get("query", "").strip()
        else:
            # Parse JSON request body for POST
            data = await request.json()
            query = data.get("query", "").strip()

        if not query:
            return web.json_response(
                {"error": "Query parameter is required"},
                status=400
            )

        print(f"REST request ({request.method}): {query[:100]}")

        # Process query
        results = await who_handler.who_query(query)

        # Return with same wrapper structure as MCP
        return web.json_response({
            "content": [{
                "type": "text",
                "text": json.dumps(results, indent=2)
            }],
            "isError": False
        })

    except json.JSONDecodeError:
        return web.json_response(
            {"error": "Invalid JSON in request body"},
            status=400
        )
    except Exception as e:
        print(f"Error in WHO endpoint: {e}")
        return web.json_response(
            {"error": "Internal server error"},
            status=500
        )


# ========== MCP ENDPOINTS ==========

async def mcp_endpoint(request: web.Request) -> web.Response:
    """MCP protocol endpoint supporting JSON-RPC 2.0"""
    try:
        # Parse JSON-RPC request
        data = await request.json()
        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")
        jsonrpc = data.get("jsonrpc", "2.0")

        print(f"MCP request: method={method}, id={request_id}")

        # Check if this is a notification (no id)
        is_notification = request_id is None

        result = None
        error = None

        # Route MCP methods
        if method == "initialize":
            result = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "who-standalone",
                    "version": "1.0.0"
                },
                "instructions": "WHO Handler - Find the most relevant sites to answer your queries"
            }

        elif method == "initialized" or method == "notifications/initialized":
            # Notification that client is ready
            if not is_notification:
                result = {"status": "ok"}
            else:
                # Notifications don't get responses
                return web.Response(status=204)

        elif method == "tools/list":
            result = {
                "tools": [{
                    "name": "who",
                    "description": "Find the most relevant sites to answer a query",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The question to find relevant sites for"
                            }
                        },
                        "required": ["query"]
                    }
                }]
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name == "who":
                query = arguments.get("query", "").strip()

                if not query:
                    error = {
                        "code": -32602,  # Invalid params
                        "message": "Query parameter is required"
                    }
                else:
                    print(f"MCP tool call: who query='{query[:100]}'")

                    # Process the query
                    try:
                        results = await who_handler.who_query(query)

                        # Format response for MCP - just return the results array
                        result = {
                            "content": [{
                                "type": "text",
                                "text": json.dumps(results, indent=2)
                            }],
                            "isError": False
                        }
                    except Exception as e:
                        print(f"Error processing query: {e}")
                        result = {
                            "content": [{
                                "type": "text",
                                "text": "Error processing query. Please try again."
                            }],
                            "isError": True
                        }
            else:
                error = {
                    "code": -32601,  # Method not found
                    "message": f"Unknown tool: {tool_name}"
                }

        elif method == "notifications/cancelled":
            # Handle cancellation notification
            request_id_to_cancel = params.get("requestId")
            reason = params.get("reason", "Unknown")
            print(f"Received cancellation for request {request_id_to_cancel}: {reason}")
            # Notifications don't get responses
            return web.Response(status=204)

        else:
            error = {
                "code": -32601,  # Method not found
                "message": f"Method not found: {method}"
            }

        # Build JSON-RPC response
        response = {"jsonrpc": jsonrpc}

        if error:
            response["error"] = error
        else:
            response["result"] = result

        # Include id for non-notifications
        if not is_notification:
            response["id"] = request_id

        return web.json_response(response)

    except json.JSONDecodeError:
        return web.json_response({
            "jsonrpc": "2.0",
            "error": {
                "code": -32700,  # Parse error
                "message": "Parse error: Invalid JSON"
            },
            "id": None
        })
    except Exception as e:
        print(f"Error in MCP endpoint: {e}")
        return web.json_response({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,  # Internal error
                "message": "Internal server error"
            },
            "id": data.get("id") if "data" in locals() else None
        })


# ========== STATIC FILE SERVING ==========

async def index_page(request: web.Request) -> web.Response:
    """Serve the index.html page"""
    try:
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        index_path = script_dir / "index.html"

        if not index_path.exists():
            return web.Response(
                text="index.html not found. Please ensure index.html is in the same directory as server.py",
                status=404
            )

        # Read and serve the HTML file
        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        return web.Response(
            text=html_content,
            content_type='text/html',
            charset='utf-8'
        )
    except Exception as e:
        # Log error internally but don't expose to users
        logger.error(f"Error serving index page", exc_info=False)
        # Don't expose internal error details to users
        return web.Response(
            text="Error loading page. Please try again later.",
            status=500
        )


# ========== ADMIN ENDPOINTS ==========

async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint"""
    try:
        # Get handler stats
        stats = await who_handler.get_stats()

        return web.json_response({
            "status": "healthy",
            "stats": stats
        })
    except Exception as e:
        print(f"Health check error: {e}")
        return web.json_response({
            "status": "unhealthy",
            "error": "Service unavailable"
        }, status=503)


async def stats_endpoint(request: web.Request) -> web.Response:
    """Statistics endpoint"""
    try:
        stats = await who_handler.get_stats()
        return web.json_response(stats)
    except Exception as e:
        print(f"Stats endpoint error: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def clear_cache_endpoint(request: web.Request) -> web.Response:
    """Clear all caches"""
    try:
        await who_handler.clear_caches()
        return web.json_response({"status": "Caches cleared"})
    except Exception as e:
        print(f"Clear cache error: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


# ========== MIDDLEWARE ==========

@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Add CORS headers to responses"""
    response = await handler(request)

    # Add CORS headers
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

    return response


@web.middleware
async def error_middleware(request: web.Request, handler):
    """Global error handler"""
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as e:
        print(f"Unhandled error: {e}")
        import traceback
        traceback.print_exc()
        # Don't expose exception details to users
        return web.json_response({
            "error": "Internal server error"
        }, status=500)


# ========== APP LIFECYCLE ==========

async def startup(app: web.Application):
    """Initialize handler on startup"""
    print(f"Starting WHO server on {HOST}:{PORT}")
    print("Initializing handler...")

    # Initialize the handler (creates connections, etc.)
    await who_handler.get_handler()

    print("Server ready to accept requests")


async def cleanup(app: web.Application):
    """Cleanup on shutdown"""
    print("Shutting down server...")
    await who_handler.cleanup()
    print("Server shutdown complete")


# ========== APPLICATION SETUP ==========

def create_app() -> web.Application:
    """Create the web application"""
    app = web.Application(middlewares=[error_middleware, cors_middleware])

    # Static pages
    app.router.add_get("/", index_page)
    app.router.add_get("/index.html", index_page)

    # REST endpoints (support both GET and POST)
    app.router.add_post("/who", who_endpoint)
    app.router.add_get("/who", who_endpoint)

    # MCP endpoints
    app.router.add_post("/mcp", mcp_endpoint)

    # Admin endpoints
    app.router.add_get("/health", health_check)
    app.router.add_get("/stats", stats_endpoint)
    app.router.add_post("/clear-cache", clear_cache_endpoint)

    # Lifecycle hooks
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    return app


# ========== MAIN ==========

if __name__ == "__main__":
    # Print configuration
    print("=" * 60)
    print("WHO Standalone Server")
    print("=" * 60)
    print(f"Web UI: http://{HOST}:{PORT}/")
    print(f"REST endpoint: POST http://{HOST}:{PORT}/who")
    print(f"MCP endpoint: POST http://{HOST}:{PORT}/mcp")
    print(f"Health check: GET http://{HOST}:{PORT}/health")
    print(f"Statistics: GET http://{HOST}:{PORT}/stats")
    print("=" * 60)

    # Create and run application
    app = create_app()

    # Run the server - let aiohttp handle signals properly
    try:
        web.run_app(
            app,
            host=HOST,
            port=PORT,
            access_log=None,  # Disable access logs for performance
            print=None  # Suppress aiohttp startup message (we have our own)
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"\nServer error: {e}")
        sys.exit(1)