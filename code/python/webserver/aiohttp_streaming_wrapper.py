# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Streaming wrapper for aiohttp server implementation.
This provides compatibility between the existing handlers and aiohttp's streaming response.
"""

import time
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from aiohttp import web

logger = logging.getLogger(__name__)


class AioHttpStreamingWrapper:
    """
    Wrapper to make aiohttp StreamResponse compatible with existing NLWeb handlers.
    Provides the same interface as the original HandleRequest class.
    """
    
    protocol_version = 'HTTP/1.1'
    
    def __init__(self, request: web.Request, response: web.StreamResponse, query_params: Dict[str, Any]):
        self.request = request
        self.response = response
        self.query_params = query_params
        self.connection_alive = True
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # Extract compatibility attributes from request
        self.method = request.method
        self.path = request.path
        self.headers = dict(request.headers)
        self.body = None  # Will be set if needed
        
        # For compatibility with existing handlers
        self.generate_mode = query_params.get('generate_mode', 'none')
        
    async def start_heartbeat(self):
        """Start sending SSE keepalive messages"""
        try:
            while self.connection_alive:
                await asyncio.sleep(30)  # Send keepalive every 30 seconds
                if self.connection_alive:
                    await self.write_keepalive()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")
    
    async def write_keepalive(self):
        """Send SSE keepalive comment"""
        if not self.connection_alive:
            return
            
        try:
            await self.response.write(b": keepalive\n\n")
        except Exception:
            self.connection_alive = False
    
    async def write_stream(self, message: Dict[str, Any], end_response: bool = False):
        """
        Write a message to the SSE stream in a format compatible with existing handlers.
        
        Args:
            message: Message dictionary to send
            end_response: Whether this is the last message
        """
        if not self.connection_alive:
            return
            
        try:
            # Check if connection is still alive
            if self.request.transport and self.request.transport.is_closing():
                self.connection_alive = False
                return
            
            # Format as SSE
            data = f"data: {json.dumps(message)}\n\n"
            await self.response.write(data.encode())
            
            # Yield control
            await asyncio.sleep(0)
            
            if end_response:
                self.connection_alive = False
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()
                    
        except Exception as e:
            logger.debug(f"Error writing to stream: {e}")
            self.connection_alive = False
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
    
    async def sendMessage(self, message: Dict[str, Any]):
        """
        Send a message - compatibility method for existing handlers.
        """
        await self.write_stream(message)
    
    async def send_error_response(self, status_code: int, message: str):
        """Send error response - for compatibility"""
        error_data = {
            "message_type": "error",
            "error": message,
            "status": status_code
        }
        await self.write_stream(error_data, end_response=True)
    
    def _get_cors_headers(self):
        """Get CORS headers - for compatibility"""
        return {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }
    
    async def prepare_response(self):
        """Prepare the streaming response"""
        if not self.response.prepared:
            await self.response.prepare(self.request)
            
        # Start heartbeat task
        self.heartbeat_task = asyncio.create_task(self.start_heartbeat())
    
    async def finish_response(self):
        """Clean up the response"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.connection_alive and not self.response._eof_sent:
            try:
                await self.response.write_eof()
            except Exception:
                pass
        
        self.connection_alive = False


class AioHttpSendChunkWrapper:
    """
    Wrapper for send_chunk functionality compatible with aiohttp.
    """
    
    def __init__(self, response: web.StreamResponse, request: web.Request):
        self.response = response
        self.request = request
        self.closed = False
    
    async def write(self, chunk, end_response=False):
        """Write chunk to response"""
        if self.closed:
            return
            
        try:
            # Check connection status
            if self.request.transport and self.request.transport.is_closing():
                self.closed = True
                return
            
            if isinstance(chunk, dict):
                # Format as SSE data
                message = f"data: {json.dumps(chunk)}\n\n"
                await self.response.write(message.encode())
            elif isinstance(chunk, str):
                await self.response.write(chunk.encode())
            elif isinstance(chunk, bytes):
                await self.response.write(chunk)
            else:
                # Convert to string
                await self.response.write(str(chunk).encode())
            
            if end_response:
                self.closed = True
                if not self.response._eof_sent:
                    await self.response.write_eof()
                    
        except Exception as e:
            logger.debug(f"Error in write: {e}")
            self.closed = True
    
    async def write_stream(self, message, end_response=False):
        """Write SSE formatted message"""
        if self.closed:
            return
            
        try:
            data_message = f"data: {json.dumps(message)}\n\n"
            await self.response.write(data_message.encode())
            
            if end_response:
                self.closed = True
                if not self.response._eof_sent:
                    await self.response.write_eof()
                    
        except Exception as e:
            logger.debug(f"Error in write_stream: {e}")
            self.closed = True