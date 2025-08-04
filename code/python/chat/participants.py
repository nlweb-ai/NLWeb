"""
Chat participants including NLWeb integration.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

from chat.schemas import (
    ChatMessage,
    MessageType,
    MessageStatus,
    ParticipantInfo,
    ParticipantType,
    QueueFullError
)

logger = logging.getLogger(__name__)


@dataclass
class ParticipantConfig:
    """Configuration for participants"""
    timeout: int = 20  # seconds
    human_messages_context: int = 5
    nlweb_messages_context: int = 1


class BaseParticipant(ABC):
    """Base class for all chat participants"""
    
    @abstractmethod
    async def process_message(
        self, 
        message: ChatMessage, 
        context: List[ChatMessage],
        stream_callback: Optional[Callable] = None
    ) -> Optional[ChatMessage]:
        """
        Process an incoming message.
        
        Args:
            message: The message to process
            context: Previous messages for context
            stream_callback: Optional callback for streaming responses
            
        Returns:
            Response message if any, None otherwise
        """
        pass
    
    @abstractmethod
    def get_participant_info(self) -> ParticipantInfo:
        """Get participant information"""
        pass


class HumanParticipant(BaseParticipant):
    """Represents a human participant in the chat"""
    
    def __init__(self, user_id: str, user_name: str):
        self.user_id = user_id
        self.user_name = user_name
        self.joined_at = datetime.utcnow()
    
    async def process_message(
        self, 
        message: ChatMessage, 
        context: List[ChatMessage],
        stream_callback: Optional[Callable] = None
    ) -> Optional[ChatMessage]:
        """Humans don't process messages, they send them"""
        return None
    
    def get_participant_info(self) -> ParticipantInfo:
        """Get participant information"""
        return ParticipantInfo(
            participant_id=self.user_id,
            name=self.user_name,
            participant_type=ParticipantType.HUMAN,
            joined_at=self.joined_at
        )


class NLWebContextBuilder:
    """Builds context for NLWeb from chat history"""
    
    def __init__(self, config: Dict[str, Any]):
        self.human_messages_limit = config.get("human_messages", 5)
        self.nlweb_messages_limit = config.get("nlweb_messages", 1)
    
    def build_context(
        self, 
        messages: List[ChatMessage],
        current_message: Optional[ChatMessage] = None
    ) -> Dict[str, Any]:
        """
        Build context for NLWeb from chat messages.
        
        Args:
            messages: List of previous messages
            current_message: The current message being processed
            
        Returns:
            Context dict with prev_queries and last_answers
        """
        context = {
            "prev_queries": [],
            "last_answers": []
        }
        
        # Separate human and NLWeb messages
        human_messages = []
        nlweb_messages = []
        
        for msg in messages:
            # Skip current message if provided
            if current_message and msg.message_id == current_message.message_id:
                continue
                
            if msg.message_type == MessageType.TEXT:
                # Human message
                human_messages.append(msg)
            elif msg.message_type == MessageType.NLWEB_RESPONSE:
                # NLWeb response
                nlweb_messages.append(msg)
        
        # Take last N human messages
        recent_human_messages = human_messages[-self.human_messages_limit:]
        
        # Build prev_queries with user_id
        for msg in recent_human_messages:
            context["prev_queries"].append({
                "query": msg.content,
                "user_id": msg.sender_id,
                "timestamp": msg.timestamp.isoformat()
            })
        
        # Take last N NLWeb messages
        recent_nlweb_messages = nlweb_messages[-self.nlweb_messages_limit:]
        
        # Build last_answers
        for msg in recent_nlweb_messages:
            answer_data = {
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            if msg.metadata:
                answer_data["metadata"] = msg.metadata
            context["last_answers"].append(answer_data)
        
        # Add current query info if provided
        if current_message and current_message.message_type == MessageType.TEXT:
            context["current_query"] = current_message.content
            context["current_user_id"] = current_message.sender_id
        
        return context


class NLWebParticipant(BaseParticipant):
    """
    Wraps NLWebHandler to participate in chat conversations.
    Does NOT modify NLWebHandler in any way.
    """
    
    def __init__(self, nlweb_handler, config: ParticipantConfig):
        """
        Initialize NLWeb participant.
        
        Args:
            nlweb_handler: Existing NLWebHandler instance (used as-is)
            config: Participant configuration
        """
        self.nlweb_handler = nlweb_handler
        self.config = config
        self.participant_id = "nlweb_1"
        self.joined_at = datetime.utcnow()
        
        # Context builder
        self.context_builder = NLWebContextBuilder({
            "human_messages": config.human_messages_context,
            "nlweb_messages": config.nlweb_messages_context
        })
    
    async def process_message(
        self, 
        message: ChatMessage, 
        context: List[ChatMessage],
        stream_callback: Optional[Callable] = None
    ) -> Optional[ChatMessage]:
        """
        Process a message through NLWebHandler.
        NLWeb decides internally whether to respond.
        
        Args:
            message: The message to process
            context: Previous messages for context
            stream_callback: Optional callback for streaming responses
            
        Returns:
            Response message if NLWeb responds, None otherwise
        """
        try:
            print(f"=== NLWebParticipant.process_message() CALLED ===")
            print(f"Message content: {message.content[:100]}")
            print(f"Message sender: {message.sender_id}")
            logger.info(f"NLWebParticipant processing message: {message.content[:100]}")
            
            # Build context from chat history  
            nlweb_context = self.context_builder.build_context(context, message)
            
            # Prepare query parameters for NLWebHandler
            query_params = {
                "query": [message.content],
                "user_id": [message.sender_id],
                "generate_mode": ["list"],  # Default mode
            }
            
            # Check if message has metadata with sites
            if hasattr(message, 'metadata') and message.metadata:
                print(f"Message metadata: {message.metadata}")
                if 'sites' in message.metadata and message.metadata['sites']:
                    # Convert sites array to comma-separated string for 'site' param
                    sites = message.metadata['sites']
                    if isinstance(sites, list) and len(sites) > 0:
                        query_params["site"] = [",".join(sites)]
                        print(f"Added site param from metadata: {query_params['site']}")
                
                # Also check for generate_mode in metadata
                if 'generate_mode' in message.metadata:
                    query_params["generate_mode"] = [message.metadata['generate_mode']]
            
            print(f"Query params prepared: {query_params}")
            logger.info(f"NLWebParticipant query_params: {query_params}")
            
            # Add context to query params
            if nlweb_context["prev_queries"]:
                query_params["prev_queries"] = [json.dumps(nlweb_context["prev_queries"])]
            
            if nlweb_context["last_answers"]:
                query_params["last_answers"] = [json.dumps(nlweb_context["last_answers"])]
            
            # Track if we've sent any response
            response_sent = False
            conversation_id = message.conversation_id
            websocket_manager = stream_callback  # stream_callback is the websocket manager
            
            class ChunkCapture:
                async def write_stream(self, data, end_response=False):
                    nonlocal response_sent
                    print(f"=== ChunkCapture.write_stream() CALLED ===")
                    print(f"Data type: {type(data)}")
                    print(f"Data preview: {str(data)[:200]}")
                    print(f"End response: {end_response}")
                    
                    # Stream directly to WebSocket if we have a manager
                    if websocket_manager:
                        response_sent = True
                        # Send the raw data exactly like HTTP streaming does
                        print(f"=== Streaming chunk to WebSocket ===")
                        await websocket_manager.broadcast_message(conversation_id, data)
                    
                    # Also keep the chunk for fallback
                    if isinstance(data, dict):
                        chunk = json.dumps(data)
                    elif isinstance(data, bytes):
                        chunk = data.decode('utf-8')
                    else:
                        chunk = str(data)
            
            chunk_capture = ChunkCapture()
            
            # Call NLWebHandler directly - it's a class that needs to be instantiated
            # This follows the same pattern as MCP integration
            
            # If nlweb_handler is a class, instantiate it
            if isinstance(self.nlweb_handler, type):
                print(f"=== NLWebParticipant creating NLWebHandler instance ===")
                print(f"Handler class: {self.nlweb_handler}")
                logger.info(f"NLWebParticipant instantiating NLWebHandler with query_params")
                handler = self.nlweb_handler(query_params, chunk_capture)
                print(f"=== NLWebParticipant calling handler.runQuery() ===")
                logger.info(f"NLWebParticipant calling handler.runQuery()")
                # Run query with timeout
                await asyncio.wait_for(
                    handler.runQuery(),
                    timeout=self.config.timeout
                )
                print(f"=== NLWebParticipant handler.runQuery() COMPLETED ===")
                logger.info(f"NLWebParticipant handler.runQuery() completed")
            else:
                print(f"=== NLWebParticipant calling mock handler function ===")
                logger.info(f"NLWebParticipant calling mock handler function")
                # For testing, nlweb_handler might be a mock function
                await asyncio.wait_for(
                    self.nlweb_handler(query_params, chunk_capture),
                    timeout=self.config.timeout
                )
            
            # If we streamed the response, we're done
            if response_sent:
                print(f"=== Response was streamed via WebSocket ===")
                # Send a completion message just like HTTP streaming
                if websocket_manager:
                    completion_message = {
                        'message_type': 'complete'
                    }
                    await websocket_manager.broadcast_message(conversation_id, completion_message)
                return None  # No need to return a ChatMessage since we streamed
            
            # If no streaming happened, return None (NLWeb didn't respond)
            print(f"=== No response from NLWeb ===")
            return None
            
        except asyncio.TimeoutError:
            logger.warning(f"NLWeb timeout processing message from {message.sender_id}")
            raise
        except QueueFullError:
            # Handle queue full gracefully
            logger.info("Queue full, dropping NLWeb response")
            return None
        except Exception as e:
            logger.error(f"Error in NLWeb processing: {e}")
            return None
    
    def get_participant_info(self) -> ParticipantInfo:
        """Get participant information"""
        return ParticipantInfo(
            participant_id=self.participant_id,
            name="NLWeb Assistant",
            participant_type=ParticipantType.AI,
            joined_at=self.joined_at
        )