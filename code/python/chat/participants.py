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
                
            # Log message details for debugging
            logger.info(f"Context message: type={msg.message_type}, sender_id={msg.sender_id}, content_preview={msg.content[:50] if msg.content else 'None'}")
            
            if msg.message_type == MessageType.TEXT:
                # Human message
                human_messages.append(msg)
            elif msg.message_type == MessageType.NLWEB_RESPONSE:
                # NLWeb response
                nlweb_messages.append(msg)
        
        # Log what we found
        logger.info(f"Found {len(human_messages)} human messages and {len(nlweb_messages)} NLWeb messages in context")
        
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
            logger.info(f"NLWebParticipant processing message: {message.content[:100]}")
            logger.info(f"NLWebParticipant received context with {len(context)} messages")
            
            # Build context from chat history  
            nlweb_context = self.context_builder.build_context(context, message)
            logger.info(f"NLWebParticipant built context: prev_queries={len(nlweb_context.get('prev_queries', []))}, last_answers={len(nlweb_context.get('last_answers', []))}")
            
            # Prepare query parameters for NLWebHandler
            query_params = {
                "query": [message.content],
                "user_id": [message.sender_id],
                "generate_mode": ["list"],  # Default mode
                "streaming": ["true"],  # Enable streaming
            }
            
            # Check if message has metadata with sites
            if hasattr(message, 'metadata') and message.metadata:
                if 'sites' in message.metadata and message.metadata['sites']:
                    # Convert sites array to comma-separated string for 'site' param
                    sites = message.metadata['sites']
                    if isinstance(sites, list) and len(sites) > 0:
                        query_params["site"] = [",".join(sites)]
                
                # Also check for generate_mode in metadata
                if 'generate_mode' in message.metadata:
                    query_params["generate_mode"] = [message.metadata['generate_mode']]
            logger.info(f"NLWebParticipant initial query_params: {query_params}")
            
            # Check for context in message metadata first (from client)
            if hasattr(message, 'metadata') and message.metadata:
                if 'prev_queries' in message.metadata and message.metadata['prev_queries']:
                    # Use client-provided context - use correct param name "prev"
                    query_params["prev"] = [json.dumps(message.metadata['prev_queries'])]
                    logger.info(f"NLWebParticipant using client prev_queries: {message.metadata['prev_queries']}")
                elif nlweb_context["prev_queries"]:
                    # Fall back to server-built context
                    query_params["prev"] = [json.dumps(nlweb_context["prev_queries"])]
                    logger.info(f"NLWebParticipant using server prev_queries: {nlweb_context['prev_queries']}")
                
                if 'last_answers' in message.metadata and message.metadata['last_answers']:
                    # Use client-provided context - use correct param name "last_ans"
                    query_params["last_ans"] = [json.dumps(message.metadata['last_answers'])]
                    logger.info(f"NLWebParticipant using client last_answers: {len(message.metadata['last_answers'])} answers")
                elif nlweb_context["last_answers"]:
                    # Fall back to server-built context
                    query_params["last_ans"] = [json.dumps(nlweb_context["last_answers"])]
                    logger.info(f"NLWebParticipant using server last_answers: {nlweb_context['last_answers']}")
            else:
                # No metadata, use server-built context
                if nlweb_context["prev_queries"]:
                    query_params["prev"] = [json.dumps(nlweb_context["prev_queries"])]
                    logger.info(f"NLWebParticipant adding prev_queries: {nlweb_context['prev_queries']}")
                
                if nlweb_context["last_answers"]:
                    query_params["last_ans"] = [json.dumps(nlweb_context["last_answers"])]
                    logger.info(f"NLWebParticipant adding last_answers: {nlweb_context['last_answers']}")
            
            logger.info(f"NLWebParticipant final query_params being sent to NLWebHandler: {query_params}")
            
            # Track if we've sent any response and collect content
            response_sent = False
            conversation_id = message.conversation_id
            websocket_manager = stream_callback  # stream_callback is the websocket manager
            collected_content = []  # Collect all streamed content
            collected_results = []  # Collect all results
            
            class ChunkCapture:
                async def write_stream(self, data, end_response=False):
                    nonlocal response_sent
                    
                    # Stream directly to WebSocket if we have a manager
                    if websocket_manager:
                        response_sent = True
                        
                        # Send the streaming data exactly as the client expects it
                        # The client expects data with message_type at the top level
                        await websocket_manager.broadcast_message(conversation_id, data)
                    
                    # Collect content for creating a ChatMessage later
                    if isinstance(data, dict):
                        if data.get('message_type') == 'summary' and data.get('message'):
                            collected_content.append(data['message'])
                        elif data.get('message_type') == 'result_batch' and data.get('results'):
                            collected_results.extend(data['results'])
                        elif data.get('message_type') == 'asking_sites' and data.get('message'):
                            collected_content.append(f"Searching: {data['message']}")
                    
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
            
            # If we streamed the response, create a ChatMessage for storage
            if response_sent:
                # Send a completion message just like HTTP streaming
                if websocket_manager:
                    completion_message = {
                        'message_type': 'complete'
                    }
                    await websocket_manager.broadcast_message(conversation_id, completion_message)
                
                # Create a ChatMessage from collected content
                if collected_content or collected_results:
                    # Format the content
                    content_parts = []
                    
                    # Add text content
                    if collected_content:
                        content_parts.append('\n'.join(collected_content))
                    
                    # Add results as formatted text
                    if collected_results:
                        content_parts.append('\n\nResults:')
                        for i, result in enumerate(collected_results[:10], 1):  # Limit to first 10
                            if isinstance(result, dict):
                                name = result.get('name', 'Untitled')
                                url = result.get('url', '')
                                if url:
                                    content_parts.append(f"{i}. [{name}]({url})")
                                else:
                                    content_parts.append(f"{i}. {name}")
                    
                    # Create the response message
                    response_message = ChatMessage(
                        message_id=f"msg_{message.message_id}_response",
                        conversation_id=conversation_id,
                        sequence_id=0,  # Will be assigned by process_message
                        sender_id=self.participant_id,
                        sender_name="NLWeb Assistant",
                        content='\n'.join(content_parts),
                        message_type=MessageType.NLWEB_RESPONSE,
                        timestamp=datetime.utcnow(),
                        metadata={
                            'sites': query_params.get('site', ['all']),
                            'mode': query_params.get('generate_mode', ['list'])[0],
                            'results_count': len(collected_results)
                        }
                    )
                    
                    logger.info(f"NLWebParticipant returning ChatMessage with {len(collected_content)} content parts and {len(collected_results)} results")
                    return response_message
                
                return None  # No content collected
            
            # If no streaming happened, return None (NLWeb didn't respond)
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