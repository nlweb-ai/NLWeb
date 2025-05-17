# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains a simple web server, that should be replaced as appropriate.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import json
import os
import sys
import time
import traceback
import urllib.parse
from core.whoHandler import WhoHandler
from core.mcp_handler import handle_mcp_request
from utils.utils import get_param
from webserver.StreamingWrapper import HandleRequest, SendChunkWrapper
from core.generate_answer import GenerateAnswer
from webserver.static_file_handler import send_static_file
from config.config import CONFIG
from core.baseHandler import NLWebHandler
from utils.logging_config_helper import get_configured_logger

# Initialize module logger
logger = get_configured_logger("webserver")

async def handle_client(reader, writer, fulfill_request):
    """Handle a client connection by parsing the HTTP request and passing it to fulfill_request."""
    request_id = f"client_{int(time.time()*1000)}"
    connection_alive = True
    
    try:
        # Read the request line
        request_line = await reader.readline()
        if not request_line:
            connection_alive = False
            return
            
        request_line = request_line.decode('utf-8', errors='replace').rstrip('\r\n')
        words = request_line.split()
        if len(words) < 2:
            # Bad request
            logger.warning(f"[{request_id}] Bad request: {request_line}")
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            await writer.drain()
            connection_alive = False
            return
            
        method, path = words[0], words[1]
        logger.debug(f"[{request_id}] {method} {path}")
        
        # Parse headers
        headers = {}
        while True:
            try:
                header_line = await reader.readline()
                if not header_line or header_line == b'\r\n':
                    break
                    
                hdr = header_line.decode('utf-8').rstrip('\r\n')
                if ":" not in hdr:
                    continue
                name, value = hdr.split(":", 1)
                headers[name.strip().lower()] = value.strip()
            except (ConnectionResetError, BrokenPipeError) as e:
                connection_alive = False
                return
        
        # Parse query parameters
        if '?' in path:
            path, query_string = path.split('?', 1)
            query_params = {}
            try:
                # Parse query parameters into a dictionary of lists
                for key, values in urllib.parse.parse_qs(query_string).items():
                    query_params[key] = values
            except Exception as e:
                query_params = {}
        else:
            query_params = {}
        
        # Read request body if Content-Length is provided
        body = None
        if 'content-length' in headers:
            try:
                content_length = int(headers['content-length'])
                body = await reader.read(content_length)
            except (ValueError, ConnectionResetError, BrokenPipeError) as e:
                connection_alive = False
                return
        
        # Create a streaming response handler
        async def send_response(status_code, response_headers, end_response=False):
            """Send HTTP status and headers to the client."""
            nonlocal connection_alive
            
            if not connection_alive:
                return
                
            try:
                status_line = f"HTTP/1.1 {status_code}\r\n"
                writer.write(status_line.encode('utf-8'))
                
                # Add CORS headers if enabled
                if CONFIG.server.enable_cors and 'Origin' in headers:
                    response_headers['Access-Control-Allow-Origin'] = '*'
                    response_headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                    response_headers['Access-Control-Allow-Headers'] = 'Content-Type'
                
                # Send headers
                for header_name, header_value in response_headers.items():
                    header_line = f"{header_name}: {header_value}\r\n"
                    writer.write(header_line.encode('utf-8'))
                
                # End headers
                writer.write(b"\r\n")
                await writer.drain()   
                # Signal that we've sent the headers
                send_response.headers_sent = True
                send_response.ended = end_response
            except (ConnectionResetError, BrokenPipeError) as e:
                connection_alive = False
            except Exception as e:
                connection_alive = False
        
        # Create a streaming content sender
        async def send_chunk(chunk, end_response=False):
            """Send a chunk of data to the client."""
            nonlocal connection_alive
            
            if not connection_alive:
                return
                
            if not hasattr(send_response, 'headers_sent') or not send_response.headers_sent:
                logger.warning(f"[{request_id}] Headers must be sent before content")
                return
                
            if hasattr(send_response, 'ended') and send_response.ended:
                logger.warning(f"[{request_id}] Response has already been ended")
                return
                
            try:
                chunk_size = 0
                if chunk:
                    if isinstance(chunk, str):
                        data = chunk.encode('utf-8')
                        chunk_size = len(data)
                        writer.write(data)
                    else:
                        chunk_size = len(chunk)
                        writer.write(chunk)
                    await writer.drain()
                
                send_response.ended = end_response
            except (ConnectionResetError, BrokenPipeError) as e:
                logger.warning(f"[{request_id}] Connection lost while sending chunk: {str(e)}")
                connection_alive = False
            except Exception as e:
                logger.warning(f"[{request_id}] Error sending chunk: {str(e)}")
                connection_alive = False
        
        # Call the user-provided fulfill_request function with streaming capabilities
        if connection_alive:
            try:
                await fulfill_request(
                    method=method,
                    path=urllib.parse.unquote(path),
                    headers=headers,
                    query_params=query_params,
                    body=body,
                    send_response=send_response,
                    send_chunk=send_chunk
                )
            except Exception as e:
                logger.error(f"[{request_id}] Error in fulfill_request: {str(e)}", exc_info=True)
                
                if connection_alive and not (hasattr(send_response, 'headers_sent') and send_response.headers_sent):
                    try:
                        # Send a 500 error if headers haven't been sent yet
                        error_headers = {
                            'Content-Type': 'text/plain',
                            'Connection': 'close'
                        }
                        await send_response(500, error_headers)
                        await send_chunk(f"Internal server error: {str(e)}".encode('utf-8'), end_response=True)
                    except:
                        pass
        
    except Exception as e:
        logger.error(f"[{request_id}] Critical error handling request: {str(e)}", exc_info=True)
    finally:
        # Close the connection in a controlled manner
        try:
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            logger.debug(f"[{request_id}] Connection closed")
        except Exception as e:
            logger.warning(f"[{request_id}] Error closing connection: {str(e)}")

def handle_site_parameter(query_params):
    """
    Handle site parameter with configuration validation.
    
    Args:
        query_params (dict): Query parameters from request
        
    Returns:
        dict: Modified query parameters with valid site parameter(s)
    """
    # Create a copy of query_params to avoid modifying the original
    result_params = query_params.copy()
    logger.debug(f"Query params: {query_params}")
    # Get allowed sites from config
    allowed_sites = CONFIG.get_allowed_sites()
    sites = []
    if "site" in query_params and len(query_params["site"]) > 0:
        sites = query_params["site"]
        logger.debug(f"Sites: {sites}")
    # Check if site parameter exists in query params
    if  len(sites) > 0:
        if isinstance(sites, list):
            # Validate each site
            valid_sites = []
            for site in sites:
                if CONFIG.is_site_allowed(site):
                    valid_sites.append(site)
                else:
                    logger.warning(f"Site '{site}' is not in allowed sites list")
            
            if valid_sites:
                result_params["site"] = valid_sites
            else:
                # No valid sites provided, use default from config
                result_params["site"] = allowed_sites
        else:
            # Single site
            if CONFIG.is_site_allowed(sites):
                result_params["site"] = [sites]
            else:
                logger.warning(f"Site '{sites}' is not in allowed sites list")
                result_params["site"] = allowed_sites
    else:
        # No site parameter provided, use all allowed sites from config
        result_params["site"] = allowed_sites
    
    return result_params

async def start_server(host=None, port=None, fulfill_request=None, use_https=False, 
                 ssl_cert_file=None, ssl_key_file=None):
    """
    Start the HTTP/HTTPS server with the provided request handler.
    """
    import ssl
    
    if fulfill_request is None:
        raise ValueError("fulfill_request function must be provided")
    
    # Use configured values if not provided
    host = host or CONFIG.server.host
    port = port or CONFIG.port
    
    ssl_context = None
    if use_https or CONFIG.is_ssl_enabled():
        # Get SSL files from config if not provided
        ssl_cert_file = ssl_cert_file or CONFIG.get_ssl_cert_path()
        ssl_key_file = ssl_key_file or CONFIG.get_ssl_key_path()
        
        if not ssl_cert_file or not ssl_key_file:
            if CONFIG.is_ssl_enabled():
                raise ValueError("SSL is enabled in config but certificate/key files not found in environment")
            else:
                raise ValueError("SSL certificate and key files must be provided for HTTPS")
        
        # Create SSL context - using configuration from working code
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.maximum_version = ssl.TLSVersion.TLSv1_3
        ssl_context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256')
        ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        
        try:
            ssl_context.load_cert_chain(ssl_cert_file, ssl_key_file)
        except (ssl.SSLError, FileNotFoundError) as e:
            raise ValueError(f"Failed to load SSL certificate: {e}")
    
    # Start server with or without SSL
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, fulfill_request), 
        host, 
        port,
        ssl=ssl_context
    )
    
    addr = server.sockets[0].getsockname()
    protocol = "HTTPS" if (use_https or ssl_context) else "HTTP"
    url_protocol = "https" if (use_https or ssl_context) else "http"
    print(f'Serving {protocol} on {addr[0]} port {addr[1]} ({url_protocol}://{addr[0]}:{addr[1]}/) ...')
    async with server:
        await server.serve_forever()

async def fulfill_request(method, path, headers, query_params, body, send_response, send_chunk):
    '''
    Process an HTTP request and stream the response back.
    
    Args:
        method (str): HTTP method (GET, POST, etc.)
        path (str): URL path
        headers (dict): HTTP headers
        query_params (dict): URL query parameters
        body (bytes or None): Request body
        send_response (callable): Function to send response headers
        send_chunk (callable): Function to send response body chunks
    '''
    try:
        streaming = True
        generate_mode = "none"
        if ("streaming" in query_params):
            strval = get_param(query_params, "streaming", str, "True")
            streaming = strval not in ["False", "false", "0"]

        if ("generate_mode" in query_params):
            generate_mode = get_param(query_params, "generate_mode", str, "none")
           
        if path == "/" or path == "":
            # Serve the home page as /static/index.html
            # First check if the file exists
            try:
                await send_static_file("/static/index.html", send_response, send_chunk)
            except FileNotFoundError:
                # If new_test.html doesn't exist, send a 404 error
                await send_response(404, {'Content-Type': 'text/plain'})
                await send_chunk("Home page not found".encode('utf-8'), end_response=True)
            return
        elif (path.find("html/") != -1) or path.find("static/") != -1 or (path.find("png") != -1):
            await send_static_file(path, send_response, send_chunk)
            return
        elif (path.find("who") != -1):
            retval =  await WhoHandler(query_params, None).runQuery()
            await send_response(200, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(retval), end_response=True)
            return
        elif (path.find("mcp") != -1):
            # Handle MCP health check
            if path == "/mcp/health" or path == "/mcp/healthz":
                await send_response(200, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps({"status": "ok"}), end_response=True)
                return

            # Check if streaming should be used from query parameters
            use_streaming = False
            if ("streaming" in query_params):
                strval = get_param(query_params, "streaming", str, "False")
                use_streaming = strval not in ["False", "false", "0"]
                
            # Handle MCP requests with streaming parameter
            logger.info(f"Routing to MCP handler (streaming={use_streaming})")
            await handle_mcp_request(query_params, body, send_response, send_chunk, streaming=use_streaming)
            return
        elif (path.find("ask") != -1):
            # Handle site parameter validation for ask endpoint
            validated_query_params = handle_site_parameter(query_params)
            
            if (not streaming):
                if (generate_mode == "generate"):
                    retval = await GenerateAnswer(validated_query_params, None).runQuery()
                else:
                    retval = await NLWebHandler(validated_query_params, None).runQuery()
                await send_response(200, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps(retval), end_response=True)
                return
            else:   
                # Set proper headers for server-sent events (SSE)
                response_headers = {
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no'  # Disable proxy buffering
                }
                
                # Send SSE headers
                await send_response(200, response_headers)
                
                # Send initial keep-alive comment to establish connection
                await send_chunk(": keep-alive\n\n", end_response=False)
                
                # Create wrapper for chunk sending
                send_chunk_wrapper = SendChunkWrapper(send_chunk)
                
                # Handle the request with validated query parameters
                hr = HandleRequest(method, path, headers, validated_query_params, 
                                   body, send_response, send_chunk_wrapper, generate_mode)
                await hr.do_GET()
        else:
            # Default handler for unknown paths
            logger.warning(f"No handler found for path: {path}")
            await send_response(404, {'Content-Type': 'text/plain'})
            await send_chunk(f"No handler found for path: {path}".encode('utf-8'), end_response=True)
    except Exception as e:
        logger.error(f"Error in fulfill_request: {e}\n{traceback.format_exc()}")
        raise

def close_logs():
    """Close the log file when the application exits."""
    if hasattr(logging, 'log_file'):
        logging.log_file.close()

# Azure Web App specific: Check for the PORT environment variable
def get_port():
    """Get the port to listen on, using config or environment."""
    if 'PORT' in os.environ:
        port = int(os.environ['PORT'])
        print(f"Using PORT from environment variable: {port}")
        return port
    elif 'WEBSITE_SITE_NAME' in os.environ:
        # Running in Azure App Service
        print("Running in Azure App Service, using default port 8000")
        return 8000  # Azure will redirect requests to this port
    else:
        # Use configured port
        print(f"Using configured port {CONFIG.port}")
        return CONFIG.port

if __name__ == "__main__":
    try:
        port = get_port()
        
        # Check if running in Azure App Service or locally
        is_azure = 'WEBSITE_SITE_NAME' in os.environ
        is_local = not is_azure
        
        if is_azure:
            print(f"Running in Azure App Service: {os.environ.get('WEBSITE_SITE_NAME')}")
            print(f"Home directory: {os.environ.get('HOME')}")
            # List all environment variables
            print("Environment variables:")
            for key, value in os.environ.items():
                print(f"  {key}: {value}")
            use_https = CONFIG.is_ssl_enabled() 
        else:
            print(f"Running on localhost (port {port})")
            use_https = False
        
        if use_https:
            print("Starting HTTPS server")
            # If using command line, use default cert files
            if len(sys.argv) > 1 and sys.argv[1] == "https":
                ssl_cert_file = 'fullchain.pem'
                ssl_key_file = 'privkey.pem'
            else:
                # Use config values
                ssl_cert_file = CONFIG.get_ssl_cert_path()
                ssl_key_file = CONFIG.get_ssl_key_path()
                
            asyncio.run(start_server(
                fulfill_request=fulfill_request,
                use_https=True,
                ssl_cert_file=ssl_cert_file,
                ssl_key_file=ssl_key_file,
                port=port
            ))
        else:
            # Use the detected port
            print(f"Starting HTTP server on port {port}")
            asyncio.run(start_server(port=port, fulfill_request=fulfill_request))
    finally:
        # Make sure to close the log file when the application exits
        close_logs()