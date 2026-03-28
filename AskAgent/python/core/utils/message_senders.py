# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Message sending utilities for NLWebHandler.

This module contains helper classes for managing message sending operations,
extracted from NLWebHandler to improve code organization and maintainability.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from core.config import CONFIG
from core.schemas import Message, SenderType, MessageType

API_VERSION = "0.55"


class MessageSender:
    """
    Helper class for sending messages in NLWebHandler.

    This class encapsulates message sending utilities to reduce clutter
    in the main NLWebHandler class.
    """

    def __init__(self, handler):
        """
        Initialize the MessageSender with a reference to the NLWebHandler.

        Args:
            handler: The NLWebHandler instance this sender belongs to.
        """
        self.handler = handler
        self._result_index = 0

    def _is_v055(self):
        """Check if the current request uses v0.55 protocol."""
        return getattr(self.handler, 'protocol_version', None) == '0.55'

    def create_initial_user_message(self):
        """
        Create the initial user query message as a Message object.
        This message represents the user's original query.
        
        Returns:
            Message object containing the user message
        """
        from core.utils.utils import get_param
        from core.schemas import UserQuery
        
        # Create UserQuery for the content
        user_query = UserQuery(
            query=self.handler.query,
            site=self.handler.site,
            mode=self.handler.generate_mode,
            prev_queries=self.handler.prev_queries
        )
        
        # Create the Message object
        user_message = Message(
            message_id=f"{self.handler.handler_message_id}#0",
            conversation_id=self.handler.conversation_id,
            sender_type=SenderType.USER,
            message_type=MessageType.QUERY,
            content=user_query,
            timestamp=datetime.utcnow().isoformat(),
            sender_info={
                "id": self.handler.oauth_id or get_param(self.handler.query_params, "user_id", str, ""),
                "name": get_param(self.handler.query_params, "user_name", str, "User")
            }
        )
        
        return user_message
    
    async def send_time_to_first_result(self):
        """Send time-to-first-result header message."""
        return
        time_to_first_result = time.time() - self.handler.init_time
        
        ttfr_message = {
            "message_type": "header",
            "header_name": "time-to-first-result",
            "header_value": f"{time_to_first_result:.3f}s"
        }
        ttfr_message = self.add_message_metadata(ttfr_message, use_system_sender=True)
        
        try:
            await self.handler.http_handler.write_stream(ttfr_message)
        except Exception as e:
            pass
    
    async def send_api_version(self):
        """Send API version message."""
        return
        
        version_message = {
            "message_type": "api_version",
            "api_version": API_VERSION
        }
        version_message = self.add_message_metadata(version_message, use_system_sender=True)
        
        try:
            await self.handler.http_handler.write_stream(version_message)
            self.handler.versionNumberSent = True
        except Exception as e:
            pass
    
    async def send_begin_response(self):
        """Send begin/start message at the start of query processing."""
        if not (self.handler.streaming and self.handler.http_handler is not None):
            return

        if self._is_v055():
            try:
                await self.handler.http_handler.write_sse_event("start", {
                    "_meta": {
                        "version": "0.55",
                        "response_type": "answer",
                        "mode": self.handler.generate_mode or "list",
                        "site": self.handler.site
                    },
                    "streaming": True
                })
            except Exception:
                pass
            return

        begin_message = {
            "message_type": "begin-nlweb-response",
            "conversation_id": self.handler.conversation_id,
            "query": self.handler.query,
            "timestamp": int(time.time() * 1000)
        }

        try:
            await self.handler.http_handler.write_stream(begin_message)
        except Exception:
            pass
    
    async def send_end_response(self, error=False):
        """
        Send end/complete message at the end of query processing.

        Args:
            error: If True, indicates the query ended with an error
        """
        if not (self.handler.streaming and self.handler.http_handler is not None):
            return

        if self._is_v055():
            complete_data = {"_meta": {"version": "0.55"}}
            if error:
                complete_data["_meta"]["error"] = True
            try:
                await self.handler.http_handler.write_sse_event("complete", complete_data)
            except Exception:
                pass
            return

        end_message = {
            "message_type": "end-nlweb-response",
            "conversation_id": self.handler.conversation_id,
            "timestamp": int(time.time() * 1000)
        }

        if error:
            end_message["error"] = True

        try:
            await self.handler.http_handler.write_stream(end_message)
        except Exception:
            pass
    
    async def send_config_headers(self):
        """Send headers from configuration as messages."""
        return
        
        if not hasattr(CONFIG.nlweb, 'headers') or not CONFIG.nlweb.headers:
            return
        
        for header_key, header_value in CONFIG.nlweb.headers.items():
            header_message = {
                "message_type": header_key,
                "content": header_value
            }
            header_message = self.add_message_metadata(header_message, use_system_sender=True)
            
            try:
                await self.handler.http_handler.write_stream(header_message)
            except Exception as e:
                self.handler.connection_alive_event.clear()
                raise
    
    def store_message(self, message: Union[Dict[str, Any], Message]):
        """
        Store message as Message objects in handler.messages.

        Args:
            message: The message to store (dict or Message object)
        """
        # Convert dict to Message object if needed
        if isinstance(message, dict):
            # Try to create a Message object from the dict
            try:
                message_obj = Message.from_dict(message)
            except:
                # If conversion fails, create a basic Message with the dict as content
                message_obj = Message(
                    sender_type=SenderType.SYSTEM,
                    message_type=message.get("message_type", MessageType.STATUS),
                    content=message.get("content", message),
                    conversation_id=message.get("conversation_id") or getattr(self.handler, 'conversation_id', None)
                )
        else:
            message_obj = message

        # Store the Message object in the messages list
        self.handler.messages.append(message_obj)
    
    async def _send_headers_if_needed(self, is_streaming=True):
        """
        Send headers if they haven't been sent yet.
        Handles both streaming and non-streaming modes.
        
        Args:
            is_streaming: True for streaming mode, False for non-streaming
        """
        if self.handler.headersSent:
            return
            
        self.handler.headersSent = True
        
        if is_streaming:
            # In streaming mode, send headers as messages
            # Send version number first
            if not self.handler.versionNumberSent:
                await self.send_api_version()
            
            # Send headers from config as messages
            await self.send_config_headers()
        else:
            # In non-streaming mode, headers are now sent as messages
            try:
                # Get configured headers from CONFIG and add them as messages
                headers = CONFIG.get_headers()
                for header_key, header_value in headers.items():
                    header_message = {
                        "message_type": header_key,
                        "content": {"message": header_value}
                    }
                    header_message = self.add_message_metadata(header_message, use_system_sender=True)
                    self.store_message(header_message)
            except Exception:
                pass
            
            # Also add nlweb headers if available
            if hasattr(CONFIG.nlweb, 'headers') and CONFIG.nlweb.headers:
                for header_key, header_value in CONFIG.nlweb.headers.items():
                    header_message = {
                        "message_type": header_key,
                        "content": header_value
                    }
                    header_message = self.add_message_metadata(header_message, use_system_sender=True)
                    self.store_message(header_message)
    
    def add_message_metadata(self, message, use_system_sender=False):
        """
        Add standard metadata fields to a message if not already present.
        
        Args:
            message: The message dictionary to add fields to
            use_system_sender: If True, use system sender info instead of nlweb_assistant
            
        Returns:
            The message with standard fields added
        """
        # Add timestamp
        if "timestamp" not in message:
            message["timestamp"] = int(time.time() * 1000)
        
        # Add message_id with counter for uniqueness
        if "message_id" not in message:
            # Increment counter and generate unique ID
            self.handler.message_counter += 1
            message["message_id"] = f"{self.handler.handler_message_id}#{self.handler.message_counter}"
        
        # Add conversation_id
        if "conversation_id" not in message:
            message["conversation_id"] = self.handler.conversation_id
        
        # Add sender_info - use different defaults based on context
        if "sender_info" not in message and "senderInfo" not in message:
            if use_system_sender:
                message["senderInfo"] = {"id": "system", "name": "NLWeb"}
            else:
                message["sender_info"] = {
                    "id": "nlweb_assistant",
                    "name": "NLWeb Assistant"
                }
        
        return message
    
    async def send_message(self, message):
        """Send a message with appropriate metadata and routing."""
        message_type = message.get('message_type', 'unknown')
        message = self.add_message_metadata(message)

        # Always store the message (for both streaming and non-streaming)
        self.store_message(message)

        if (self.handler.streaming and self.handler.http_handler is not None):
            # Streaming mode: send via SSE

            # Check if this is the first result and add time-to-first-result header
            if message.get("message_type") == "result" and not self.handler.first_result_sent:
                self.handler.first_result_sent = True
                await self.send_time_to_first_result()

            # Send headers if not already sent
            await self._send_headers_if_needed(is_streaming=True)

            try:
                if self._is_v055() and message.get("message_type") == "result" and isinstance(message.get("content"), list):
                    # v0.55: emit event: result per item
                    for item in message.get("content", []):
                        await self.handler.http_handler.write_sse_event("result", {
                            "index": self._result_index,
                            "item": item
                        })
                        self._result_index += 1
                elif self._is_v055():
                    # v0.55: other message types sent as unnamed data events
                    await self.handler.http_handler.write_stream(message)
                else:
                    await self.handler.http_handler.write_stream(message)
            except Exception as e:
                self.handler.connection_alive_event.clear()
        else:
            # Non-streaming mode: just store (already done above)
            # Send headers if not already sent
            await self._send_headers_if_needed(is_streaming=False)