# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the code for the streaming wrapper.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""
import time
import asyncio
import ssl
import json
from core.baseHandler import NLWebHandler
from core.generate_answer import GenerateAnswer

# Add SendChunkWrapper class here
class SendChunkWrapper:
    def __init__(self, send_chunk):
        self.send_chunk = send_chunk
        self.closed = False

    async def write(self, chunk, end_response=False):
        if self.closed:
            return
        try:
            if isinstance(chunk, dict):
                message = f"data: {json.dumps(chunk)}\n\n"
                await self.send_chunk(message, end_response)
            else:
                await self.send_chunk(chunk, end_response)
                
            if end_response:
                self.closed = True
        except (ConnectionResetError, BrokenPipeError) as e:
            print(f"Connection lost in write: {str(e)}")
            self.closed = True
        except Exception as e:
            print(f"Error in SendChunkWrapper.write: {str(e)}")
            self.closed = True

    async def write_stream(self, message, end_response=False):
        if self.closed:
            return
            
        try:
            data_message = f"data: {json.dumps(message)}\n\n"
            await self.send_chunk(data_message, end_response)
            if end_response:
                self.closed = True
        except (ConnectionResetError, BrokenPipeError) as e:
            print(f"Connection lost in write_stream: {str(e)}")
            self.closed = True
        except Exception as e:
            print(f"Error in write_stream: {str(e)}")
            self.closed = True

# simple wrapper for handling streaming. Needs to be replaced for any 'real' deployment
class HandleRequest():
    protocol_version = 'HTTP/1.1'
    
    def __init__(self, method, path, headers, query_params, body, send_response, send_chunk_wrapper, generate_mode):
        self.method = method
        self.path = path
        self.headers = headers
        self.query_params = query_params
        self.body = body
        self.send_response = send_response
        self.send_chunk_wrapper = send_chunk_wrapper
        self.connection = None  # Added to maintain compatibility with error handlers
        self.connection_alive = True  # Flag to track connection state
        self.generate_mode = generate_mode
        

    async def do_GET(self):
        request_id = f"req_{int(time.time()*1000)}"
        try:
            await self._start_sse_response()
            
            if not self.connection_alive:
                print(f"[{request_id}] Connection lost before starting query handling")
                return
            if (self.generate_mode == "generate"):
                await GenerateAnswer(self.query_params, self).runQuery()
            else:
                await NLWebHandler(self.query_params, self).runQuery()
            await self.write_stream({"message_type": "complete"})
        except (ssl.SSLError, BrokenPipeError, ConnectionResetError) as conn_err:
            print(f"[{request_id}] Connection error during request handling: {str(conn_err)}")
            self.connection_alive = False
            # Connection errors are expected and don't need to generate an error response
            return
        except Exception as inner_e:
            if self.connection_alive:
                print(f"[{request_id}] Error during request handling: {str(inner_e)}")
                error_msg = f"Error processing request: {str(inner_e)}"
                await self.send_error_response(500, error_msg)
            else:
                print(f"[{request_id}] Error after connection was already lost: {str(inner_e)}")
            return

    
    async def send_error_response(self, status_code, message):
        """Send error response to client if connection is still alive"""
        try:
            headers = {
                'Content-Type': 'text/plain',
                'Connection': 'close'
            }
            headers.update(self._get_cors_headers())
            
            await self.send_response(status_code, headers)
            await self.send_chunk_wrapper.write({"error": message}, end_response=True)
        except (ssl.SSLError, BrokenPipeError, ConnectionResetError) as ssl_err:
            self.connection_alive = False
            print(f"Connection lost while sending error response: {str(ssl_err)}")
        except Exception as e:
            print(f"Critical error during error handling: {str(e)}")
        
    async def write_stream(self, message):
        """
        Asynchronously write a message to the SSE stream.
        
        Args:
            message (str): Message to write to the stream
        """
        if not self.connection_alive:
            return
            
        try:
            await self.send_chunk_wrapper.write(message)
            await asyncio.sleep(0)  # Yield control to allow other tasks to run
        except (ssl.SSLError, BrokenPipeError, ConnectionResetError) as e:
            self.connection_alive = False
            print(f"Connection lost while writing to stream: {str(e)}")
            # Don't re-raise - consumer should check connection_alive flag
        except Exception as e:
            print(f"Error writing to stream: {str(e)}")
            self.connection_alive = False
            # Don't re-raise - consumer should check connection_alive flag

    def _get_cors_headers(self):
        """Return CORS headers as a dictionary"""
        return {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    
    async def _handle_cors_preflight(self):
        print("Handling CORS preflight request")
        headers = self._get_cors_headers()
        await self.send_response(200, headers)

    async def _start_sse_response(self):
        """Setup SSE response headers"""
        try:
            headers = {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
            headers.update(self._get_cors_headers())
            await self.send_response(200, headers)
        except (ssl.SSLError, BrokenPipeError, ConnectionResetError) as e:
            self.connection_alive = False
            print(f"Connection lost before sending headers: {str(e)}")
            raise  # Re-raise to caller