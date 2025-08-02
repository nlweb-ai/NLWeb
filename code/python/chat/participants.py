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
            # Build context from chat history
            nlweb_context = self.context_builder.build_context(context, message)
            
            # Prepare query parameters for NLWebHandler
            query_params = {
                "query": [message.content],
                "user_id": [message.sender_id],
                "generate_mode": ["list"],  # Default mode
            }
            
            # Add context to query params
            if nlweb_context["prev_queries"]:
                query_params["prev_queries"] = [json.dumps(nlweb_context["prev_queries"])]
            
            if nlweb_context["last_answers"]:
                query_params["last_answers"] = [json.dumps(nlweb_context["last_answers"])]
            
            # Capture response chunks
            response_chunks = []
            
            class ChunkCapture:
                async def write_stream(self, data, end_response=False):
                    # Capture chunk
                    if isinstance(data, dict):
                        chunk = json.dumps(data)
                    elif isinstance(data, bytes):
                        chunk = data.decode('utf-8')
                    else:
                        chunk = str(data)
                    
                    response_chunks.append(chunk)
                    
                    # Stream to callback if provided
                    if stream_callback:
                        await stream_callback(chunk)
            
            chunk_capture = ChunkCapture()
            
            # Call NLWebHandler directly - it's a class that needs to be instantiated
            # This follows the same pattern as MCP integration
            
            # If nlweb_handler is a class, instantiate it
            if isinstance(self.nlweb_handler, type):
                handler = self.nlweb_handler(query_params, chunk_capture)
                # Run query with timeout
                await asyncio.wait_for(
                    handler.runQuery(),
                    timeout=self.config.timeout
                )
            else:
                # For testing, nlweb_handler might be a mock function
                await asyncio.wait_for(
                    self.nlweb_handler(query_params, chunk_capture),
                    timeout=self.config.timeout
                )
            
            # If NLWeb produced a response, create a chat message
            if response_chunks:
                full_response = ''.join(response_chunks)
                
                # Create response message
                return ChatMessage(
                    message_id=f"nlweb_{datetime.utcnow().timestamp()}",
                    conversation_id=message.conversation_id,
                    sequence_id=0,  # Will be assigned by conversation manager
                    sender_id=self.participant_id,
                    sender_name="NLWeb Assistant",
                    content=full_response,
                    message_type=MessageType.NLWEB_RESPONSE,
                    timestamp=datetime.utcnow(),
                    status=MessageStatus.DELIVERED,
                    metadata={
                        "responding_to": message.sender_id,
                        "context_messages": len(context)
                    }
                )
            
            # NLWeb decided not to respond
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