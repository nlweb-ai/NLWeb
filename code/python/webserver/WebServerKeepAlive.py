"""
WebServer keep-alive patch - adds HTTP/1.1 keep-alive support to handle_client
"""
import asyncio
import urllib.parse
import time
from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG

logger = get_configured_logger("webserver")

async def handle_client_with_keepalive(reader, writer, fulfill_request):
    """Handle a client connection with HTTP/1.1 keep-alive support."""
    connection_id = f"client_{int(time.time()*1000)}"
    keep_alive = True
    request_count = 0
    
    try:
        while keep_alive:
            request_count += 1
            request_id = f"{connection_id}_req{request_count}"
            connection_alive = True
            
            try:
                # Set a timeout for reading the request
                request_line = await asyncio.wait_for(reader.readline(), timeout=30.0)
                if not request_line:
                    # Connection closed by client
                    break
                
                # Debug logging to see what we're receiving
                logger.debug(f"[{request_id}] Raw request bytes: {request_line[:100]}")
                
                try:
                    request_line = request_line.decode('utf-8', errors='replace').rstrip('\r\n')
                except Exception as decode_error:
                    logger.error(f"[{request_id}] Failed to decode request line: {decode_error}")
                    writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                    await writer.drain()
                    break
                    
                words = request_line.split()
                if len(words) < 2:
                    # Bad request
                    logger.warning(f"[{request_id}] Bad request: {request_line}")
                    writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                    await writer.drain()
                    break
                    
                method, path = words[0], words[1]
                http_version = words[2] if len(words) > 2 else "HTTP/1.0"
                logger.debug(f"[{request_id}] {method} {path} {http_version}")
                
                # Parse headers
                headers = {}
                while True:
                    try:
                        header_line = await reader.readline()
                        if not header_line or header_line == b'\r\n':
                            break
                        
                        try:
                            hdr = header_line.decode('utf-8', errors='replace').rstrip('\r\n')
                        except Exception as decode_error:
                            logger.error(f"[{request_id}] Failed to decode header: {decode_error}")
                            continue
                            
                        if ":" not in hdr:
                            continue
                        name, value = hdr.split(":", 1)
                        headers[name.strip().lower()] = value.strip()
                    except (ConnectionResetError, BrokenPipeError) as e:
                        connection_alive = False
                        keep_alive = False
                        break
                
                if not connection_alive:
                    break
                
                # Check if client wants keep-alive
                connection_header = headers.get('connection', '').lower()
                if http_version == "HTTP/1.1":
                    # HTTP/1.1 defaults to keep-alive unless Connection: close
                    keep_alive = connection_header != 'close'
                else:
                    # HTTP/1.0 defaults to close unless Connection: keep-alive
                    keep_alive = connection_header == 'keep-alive'
                
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
                        logger.debug(f"[{request_id}] Read body of {len(body) if body else 0} bytes")
                    except (ValueError, ConnectionResetError, BrokenPipeError) as e:
                        logger.error(f"[{request_id}] Error reading body: {e}")
                        connection_alive = False
                        keep_alive = False
                        break
                    except Exception as e:
                        logger.error(f"[{request_id}] Unexpected error reading body: {e}")
                        connection_alive = False
                        keep_alive = False
                        break
                
                # Track if this response should close the connection
                response_should_close = False
                
                # Create a streaming response handler
                async def send_response(status_code, response_headers, end_response=False):
                    """Send HTTP status and headers to the client."""
                    nonlocal connection_alive, keep_alive, response_should_close
                    
                    if not connection_alive:
                        return
                        
                    try:
                        status_line = f"HTTP/1.1 {status_code}\r\n"
                        writer.write(status_line.encode('utf-8'))
                        
                        # Add CORS headers if enabled
                        if CONFIG.server.enable_cors and 'origin' in headers:
                            response_headers['Access-Control-Allow-Origin'] = '*'
                            response_headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                            response_headers['Access-Control-Allow-Headers'] = 'Content-Type'
                        
                        # Check if response headers indicate connection should close
                        response_connection = response_headers.get('Connection', '').lower()
                        if response_connection == 'close':
                            keep_alive = False
                            response_should_close = True
                        elif keep_alive and response_connection != 'keep-alive':
                            # Add keep-alive header if not present and we want to keep alive
                            response_headers['Connection'] = 'keep-alive'
                        
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
                        keep_alive = False
                    except Exception as e:
                        connection_alive = False
                        keep_alive = False
                
                # Create a streaming content sender
                async def send_chunk(chunk, end_response=False):
                    """Send a chunk of data to the client."""
                    nonlocal connection_alive, keep_alive
                    
                    if not connection_alive:
                        return
                        
                    if not hasattr(send_response, 'headers_sent') or not send_response.headers_sent:
                        logger.warning(f"[{request_id}] Headers must be sent before content")
                        return
                        
                    if hasattr(send_response, 'ended') and send_response.ended:
                        logger.warning(f"[{request_id}] Response has already been ended")
                        return
                        
                    try:
                        writer.write(chunk)
                        if end_response:
                            send_response.ended = True
                            # Don't close keep-alive connections
                            if response_should_close:
                                keep_alive = False
                        await writer.drain()
                    except (ConnectionResetError, BrokenPipeError) as e:
                        logger.warning(f"[{request_id}] Client disconnected during send_chunk")
                        connection_alive = False
                        keep_alive = False
                    except Exception as e:
                        logger.error(f"[{request_id}] Error in send_chunk: {str(e)}")
                        connection_alive = False
                        keep_alive = False
                
                # Handle the request (correct parameter order)
                await fulfill_request(method, path, headers, query_params, body, send_response, send_chunk)
                
                # If headers weren't sent, send a default response
                if not hasattr(send_response, 'headers_sent') or not send_response.headers_sent:
                    await send_response(200, {'Content-Type': 'text/plain'})
                    await send_chunk(b"OK", end_response=True)
                
                # Log request completion
                logger.info(f"[{request_id}] Request completed, keep_alive={keep_alive}")
                
            except asyncio.TimeoutError:
                logger.debug(f"[{connection_id}] Timeout waiting for request, closing connection")
                keep_alive = False
            except Exception as e:
                logger.error(f"[{request_id}] Error handling request: {str(e)}", exc_info=True)
                keep_alive = False
                
    except Exception as e:
        logger.error(f"[{connection_id}] Critical error handling connection: {str(e)}", exc_info=True)
    finally:
        # Close the connection in a controlled manner
        try:
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            logger.debug(f"[{connection_id}] Connection closed after {request_count} requests")
        except Exception as e:
            logger.warning(f"[{connection_id}] Error closing connection: {str(e)}")