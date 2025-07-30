#!/usr/bin/env python3
"""
StreamableHTTP handler for MCP that maintains persistent connections
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class StreamableMCPHandler:
    """
    MCP handler that supports StreamableHTTP transport with persistent connections
    """
    
    def __init__(self):
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.initialized = False
        
    async def handle_streamable_connection(self, reader, writer):
        """
        Handle a persistent StreamableHTTP connection for MCP
        """
        connection_id = f"{writer.get_extra_info('peername')}"
        logger.info(f"New StreamableHTTP connection: {connection_id}")
        
        try:
            while True:
                # Read HTTP request line
                request_line = await reader.readline()
                if not request_line:
                    break
                    
                request_line = request_line.decode('utf-8').strip()
                if not request_line:
                    continue
                    
                logger.debug(f"Request line: {request_line}")
                parts = request_line.split(' ')
                if len(parts) < 3:
                    continue
                    
                method, path, protocol = parts[0], parts[1], parts[2]
                
                # Read headers
                headers = {}
                while True:
                    header_line = await reader.readline()
                    if not header_line or header_line == b'\r\n':
                        break
                    header_line = header_line.decode('utf-8').strip()
                    if ':' in header_line:
                        key, value = header_line.split(':', 1)
                        headers[key.lower().strip()] = value.strip()
                
                # Read body if present
                body = None
                if 'content-length' in headers:
                    content_length = int(headers['content-length'])
                    body = await reader.read(content_length)
                    body = body.decode('utf-8')
                
                # Handle the request based on path
                if path == '/mcp' and method == 'POST':
                    await self.handle_mcp_message(body, writer)
                elif path == '/mcp/sse' and method == 'GET':
                    # Server-sent events endpoint for server-to-client messages
                    await self.handle_sse_connection(writer)
                else:
                    # Send 404
                    response = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"
                    writer.write(response.encode('utf-8'))
                    await writer.drain()
                    
        except asyncio.CancelledError:
            logger.info(f"Connection {connection_id} cancelled")
        except Exception as e:
            logger.error(f"Error in connection {connection_id}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            if connection_id in self.connections:
                del self.connections[connection_id]
            logger.info(f"Connection {connection_id} closed")
    
    async def handle_mcp_message(self, body: str, writer):
        """
        Handle a single MCP message in the StreamableHTTP format
        """
        try:
            # Parse JSON-RPC request
            request = json.loads(body)
            method = request.get('method')
            params = request.get('params', {})
            request_id = request.get('id')
            
            logger.info(f"MCP request: {method} (id={request_id})")
            
            # Process the request
            result = None
            error = None
            
            if method == 'initialize':
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "prompts": {"listChanged": True}
                    },
                    "serverInfo": {
                        "name": "nlweb-streamable-mcp",
                        "version": "1.0.0"
                    }
                }
                self.initialized = True
                
            elif method == 'initialized':
                # This is a notification, no response needed
                if request_id is None:
                    return
                result = {"status": "ok"}
                
            elif method == 'tools/list':
                result = {
                    "tools": [
                        {
                            "name": "ask_nlweb",
                            "description": "Query NLWeb for information",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                    "site": {"type": "string"},
                                    "generate_mode": {"type": "string", "enum": ["list", "summarize", "generate"]}
                                },
                                "required": ["query"]
                            }
                        }
                    ]
                }
            else:
                error = {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            
            # Build response
            response_data = {
                "jsonrpc": "2.0",
                "id": request_id
            }
            
            if error:
                response_data["error"] = error
            else:
                response_data["result"] = result
            
            # Send HTTP response with Connection: keep-alive
            response_body = json.dumps(response_data)
            response = f"HTTP/1.1 200 OK\r\n"
            response += f"Content-Type: application/json\r\n"
            response += f"Content-Length: {len(response_body)}\r\n"
            response += f"Connection: keep-alive\r\n"
            response += f"\r\n"
            response += response_body
            
            writer.write(response.encode('utf-8'))
            await writer.drain()
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }
            response_body = json.dumps(error_response)
            response = f"HTTP/1.1 200 OK\r\n"
            response += f"Content-Type: application/json\r\n"
            response += f"Content-Length: {len(response_body)}\r\n"
            response += f"Connection: keep-alive\r\n"
            response += f"\r\n"
            response += response_body
            writer.write(response.encode('utf-8'))
            await writer.drain()
    
    async def handle_sse_connection(self, writer):
        """
        Handle server-sent events connection for server-initiated messages
        """
        # Send SSE headers
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: text/event-stream\r\n"
        response += "Cache-Control: no-cache\r\n"
        response += "Connection: keep-alive\r\n"
        response += "\r\n"
        
        writer.write(response.encode('utf-8'))
        await writer.drain()
        
        # Keep connection open for server-initiated messages
        # This would be used for notifications, progress updates, etc.
        try:
            while True:
                # Send heartbeat every 30 seconds
                writer.write(b":keepalive\n\n")
                await writer.drain()
                await asyncio.sleep(30)
        except:
            pass

async def run_streamable_mcp_server(host='localhost', port=8001):
    """
    Run the StreamableHTTP MCP server
    """
    handler = StreamableMCPHandler()
    
    server = await asyncio.start_server(
        handler.handle_streamable_connection,
        host, port
    )
    
    addr = server.sockets[0].getsockname()
    logger.info(f'StreamableHTTP MCP server running on http://{addr[0]}:{addr[1]}/mcp')
    
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_streamable_mcp_server())