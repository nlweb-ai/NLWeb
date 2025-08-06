"""
Chat participants including NLWeb integration.
"""

import asyncio
import json
import logging
import time
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
        
        # Only collect human messages since NLWeb doesn't create messages
        human_messages = []
        
        for msg in messages:
            # Skip current message if provided
            if current_message and msg.message_id == current_message.message_id:
                continue
                
            # Log message details for debugging
            logger.info(f"Context message: type={msg.message_type}, sender_id={msg.senderInfo.get('id')}, content_preview={msg.content[:50] if msg.content else 'None'}")
            
            if msg.message_type == 'user':
                # Human message
                human_messages.append(msg)
            # Note: NLWeb doesn't create messages, it only streams responses
        
        # Log what we found
        logger.info(f"Found {len(human_messages)} human messages in context")
        
        # Take last N human messages
        recent_human_messages = human_messages[-self.human_messages_limit:]
        
        # Build prev_queries with user_id
        for msg in recent_human_messages:
            context["prev_queries"].append({
                "query": msg.content,
                "user_id": msg.senderInfo.get('id'),
                "timestamp": datetime.fromtimestamp(msg.timestamp / 1000).isoformat()
            })
        
        # Note: last_answers is empty since NLWeb doesn't create stored messages
        
        # Add current query info if provided
        if current_message and current_message.message_type == 'user':
            context["current_query"] = current_message.content
            context["current_user_id"] = current_message.senderInfo.get('id')
        
        return context


class NLWebParticipant(BaseParticipant):
    """
    Wraps NLWebHandler to participate in chat conversations.
    Does NOT modify NLWebHandler in any way.
    """
    
    def __init__(self, nlweb_handler, config: ParticipantConfig, storage_client):
        """
        Initialize NLWeb participant.
        
        Args:
            nlweb_handler: Existing NLWebHandler instance (used as-is)
            config: Participant configuration
            storage_client: Required storage client for persisting messages
        """
        if not storage_client:
            raise ValueError("storage_client is required for NLWebParticipant")
            
        self.nlweb_handler = nlweb_handler
        self.config = config
        self.storage_client = storage_client
        self.participant_id = "nlweb_1"
        self.joined_at = datetime.utcnow()
        
        print(f"[NLWebParticipant.__init__] Created with storage_client type: {type(storage_client)}")
        
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
            logger.info(f"NLWebParticipant processing message: {message.content[:100]}")
            logger.info(f"NLWebParticipant received context with {len(context)} messages")
            
            # Build context from chat history  
            nlweb_context = self.context_builder.build_context(context, message)
            logger.info(f"NLWebParticipant built context: prev_queries={len(nlweb_context.get('prev_queries', []))}, last_answers={len(nlweb_context.get('last_answers', []))}")
            
            # Prepare query parameters for NLWebHandler
            query_params = {
                "query": [message.content],
                "user_id": [message.senderInfo.get('id')],
                "streaming": ["true"],  # Enable streaming
            }
            
            # Get sites and mode from message metadata
            logger.info(f"NLWebParticipant checking metadata: has metadata={hasattr(message, 'metadata')}, metadata={getattr(message, 'metadata', None)}")
            if hasattr(message, 'metadata') and message.metadata:
                sites = message.metadata.get('sites', ['all'])
                generate_mode = message.metadata.get('generate_mode', 'list')
                logger.info(f"NLWebParticipant using sites from metadata: {sites}, mode: {generate_mode}")
            else:
                sites = ['all']
                generate_mode = 'list'
                logger.info(f"NLWebParticipant using default sites: {sites}, mode: {generate_mode}")
            
            # Set sites and mode in query params
            query_params["site"] = sites if isinstance(sites, list) else [sites]
            query_params["generate_mode"] = [generate_mode]
            logger.info(f"NLWebParticipant initial query_params: {query_params}")
            
            # Use server-built context
            if nlweb_context["prev_queries"]:
                query_params["prev"] = [json.dumps(nlweb_context["prev_queries"])]
                logger.info(f"NLWebParticipant adding prev_queries: {nlweb_context['prev_queries']}")
            
            if nlweb_context["last_answers"]:
                query_params["last_ans"] = [json.dumps(nlweb_context["last_answers"])]
                logger.info(f"NLWebParticipant adding last_answers: {nlweb_context['last_answers']}")
            
            logger.info(f"NLWebParticipant final query_params being sent to NLWebHandler: {query_params}")
            
            # Track if we've sent any response
            response_sent = False
            conversation_id = message.conversation_id
            websocket_manager = stream_callback  # stream_callback is the websocket manager
            
            storage_client = self.storage_client
            
            class ChunkCapture:
                async def write_stream(self, data, end_response=False):
                    nonlocal response_sent
                    
                    # Stream directly to WebSocket if we have a manager
                    if websocket_manager:
                        response_sent = True
                        
                        # Send the streaming data exactly as the client expects it
                        # The client expects data with message_type at the top level
                        await websocket_manager.broadcast_message(conversation_id, data)
                        
                        # ALWAYS store every message to storage for persistence
                        logger.info(f"Attempting to store message with type: {data.get('message_type')}")
                        logger.info(f"Storage client available: {storage_client is not None}")
                        
                        if storage_client:
                            try:
                                # Import required modules
                                from chat.schemas import ChatMessage
                                import json
                                import time
                                import uuid
                                
                                # Generate a unique message ID
                                message_id = f"msg_{uuid.uuid4().hex[:12]}"
                                
                                # Create a ChatMessage for storage
                                storage_message = ChatMessage(
                                    message_id=message_id,
                                    conversation_id=conversation_id,
                                    content=json.dumps(data),  # Store the full streaming data
                                    message_type='assistant_stream',  # Mark as streaming data
                                    timestamp=int(time.time() * 1000),
                                    senderInfo={
                                        'id': 'nlweb_assistant',
                                        'name': 'NLWeb Assistant'
                                    },
                                    metadata={
                                        'stream_type': data.get('message_type', 'unknown'),
                                        'sites': query_params.get('sites', []),
                                        'mode': query_params.get('mode', 'unknown')
                                    }
                                )
                                
                                # Store the message
                                await storage_client.store_message(storage_message)
                                logger.info(f"Successfully stored assistant_stream message of type: {data.get('message_type')}")
                                print(f"[STORAGE] Stored assistant message: type={data.get('message_type')}, conversation={conversation_id}")
                                
                            except Exception as e:
                                logger.error(f"Failed to store streaming message: {e}")
                                import traceback
                                logger.error(f"Traceback: {traceback.format_exc()}")
                        else:
                            logger.warning("Storage client is None - cannot store message!")
                            print(f"[STORAGE ERROR] Storage client is None for conversation {conversation_id}!")
            
            chunk_capture = ChunkCapture()
            
            # Call NLWebHandler directly - it's a class that needs to be instantiated
            # This follows the same pattern as MCP integration
            
            # If nlweb_handler is a class, instantiate it
            if isinstance(self.nlweb_handler, type):
                logger.info(f"NLWebParticipant instantiating NLWebHandler with query_params")
                handler = self.nlweb_handler(query_params, chunk_capture)
                logger.info(f"NLWebParticipant calling handler.runQuery()")
                # Run query with timeout
                await asyncio.wait_for(
                    handler.runQuery(),
                    timeout=self.config.timeout
                )
                logger.info(f"NLWebParticipant handler.runQuery() completed")
            else:
                logger.info(f"NLWebParticipant calling mock handler function")
                # For testing, nlweb_handler might be a mock function
                await asyncio.wait_for(
                    self.nlweb_handler(query_params, chunk_capture),
                    timeout=self.config.timeout
                )
            
            # If we streamed the response, create a message for storage
            if response_sent:
                # Send a completion message just like HTTP streaming
                if websocket_manager:
                    completion_message = {
                        'message_type': 'complete'
                    }
                    await websocket_manager.broadcast_message(conversation_id, completion_message)
                
                # NLWebParticipant only streams - it doesn't create messages
                return None
            
            # If no streaming happened, return None (NLWeb didn't respond)
            return None
            
        except asyncio.TimeoutError:
            logger.warning(f"NLWeb timeout processing message from {message.senderInfo.get('id')}")
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