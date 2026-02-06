"""
Chat participants including NLWeb integration.
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

from chat.schemas import (
    ParticipantInfo,
    ParticipantType,
    QueueFullError
)
from core.schemas import (
    Message,
    MessageType,
    MessageStatus
)
from core.conversation_history import add_conversation
from core.llm import ask_llm
from core.embedding import get_embedding

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
        message: Message, 
        context: List[Message],
        stream_callback: Optional[Callable] = None
    ) -> Optional[Message]:
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
        self.joined_at = int(time.time() * 1000)
    
    async def process_message(
        self, 
        message: Message, 
        context: List[Message],
        stream_callback: Optional[Callable] = None
    ) -> Optional[Message]:
        """Humans don't process messages, they send them"""
        return None
    
    def get_participant_info(self) -> ParticipantInfo:
        """Get participant information"""
        return ParticipantInfo(
            participant_id=self.user_id,
            name=self.user_name,
            participant_type=ParticipantType.HUMAN,
            joined_at=self.joined_at  # Already in milliseconds
        )


class NLWebContextBuilder:
    """Builds context for NLWeb from chat history"""
    
    def __init__(self, config: Dict[str, Any]):
        self.human_messages_limit = config.get("human_messages", 5)
        self.nlweb_messages_limit = config.get("nlweb_messages", 1)
    
    def build_context(
        self, 
        messages: List[Message],
        current_message: Optional[Message] = None
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
                "user_id": msg.sender_info.get('id'),
                "timestamp": datetime.fromtimestamp(msg.timestamp / 1000).isoformat()
            })
        
        # Note: last_answers is empty since NLWeb doesn't create stored messages
        
        # Add current query info if provided
        if current_message and current_message.message_type == 'user':
            context["current_query"] = current_message.content
            context["current_user_id"] = current_message.sender_info.get('id')
        
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
        self.joined_at = int(time.time() * 1000)
        
        # Context builder
        self.context_builder = NLWebContextBuilder({
            "human_messages": config.human_messages_context,
            "nlweb_messages": config.nlweb_messages_context
        })

    def _extract_query_texts(self, prev_queries):
        """
        Extract just the query text from previous queries.
        Handles both simple string lists and complex nested structures.
        """
        if not prev_queries:
            return []

        query_texts = []

        for item in prev_queries:
            if isinstance(item, str):
                query_texts.append(item)
            elif isinstance(item, dict):
                # Extract query from dict structure
                if 'query' in item:
                    if isinstance(item['query'], dict) and 'query' in item['query']:
                        query_texts.append(item['query']['query'])
                    elif isinstance(item['query'], str):
                        query_texts.append(item['query'])
            elif isinstance(item, list):
                # Recursively extract from list
                query_texts.extend(self._extract_query_texts(item))

        return query_texts

    def _extract_query_params(self, message):
        """
        Extract query parameters from a message object.

        Args:
            message: ChatMessage object with content

        Returns:
            Dictionary of query parameters for NLWebHandler
        """
        import json

        # Debug: Print entire message
        print(f"\n=== EXTRACT_QUERY_PARAMS DEBUG ===")
        print(f"Full message object: {message}")
        if hasattr(message, '__dict__'):
            print(f"Message attributes: {message.__dict__}")
            # Check if there are any additional fields at message level
            for key, value in message.__dict__.items():
                if key not in ['message_id', 'sender_type', 'message_type', 'conversation_id',
                              'timestamp', 'content', 'sender_info', 'metadata']:
                    print(f"Extra field at message level: {key}={value}")

        query_params = {}

        # Get content from message
        content = message.content if hasattr(message, 'content') else {}
        print(f"Extracted content: {content}")
        print(f"Content type: {type(content)}")

        if isinstance(content, dict):
            # Add all parameters from content
            for key, value in content.items():
                if key == 'prev_queries':
                    # Special case: Extract just the query texts from prev_queries
                    query_texts = self._extract_query_texts(value)
                    query_params["prev"] = query_texts  # Pass as list of strings
                else:
                    # All other parameters pass through as-is (including 'db', 'query', 'site', 'mode', etc.)
                    query_params[key] = [value] if not isinstance(value, list) else value

        # Extract user info from sender_info
        if hasattr(message, 'sender_info') and message.sender_info:
            query_params["user_id"] = [message.sender_info.get('id', '')]
            query_params["oauth_id"] = [message.sender_info.get('id', '')]

        # Add conversation tracking
        if hasattr(message, 'conversation_id') and message.conversation_id:
            query_params["conversation_id"] = [message.conversation_id]

        # Add streaming flag (always true for WebSocket/chat)
        query_params["streaming"] = ["true"]

        print(f"Final query_params: {query_params}")
        print(f"=== END EXTRACT_QUERY_PARAMS DEBUG ===\n")

        return query_params

    async def process_message(
        self, 
        message: Message, 
        context: List[Message],
        stream_callback: Optional[Callable] = None
    ) -> Optional[Message]:
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
            # Track if we've sent any response
            response_sent = False
            conversation_id = message.conversation_id
            websocket_manager = stream_callback  # stream_callback can be websocket manager or SSE wrapper
            
            class ChunkCapture:
                async def write_stream(self, data, end_response=False):
                    nonlocal response_sent
                    
                    # Stream directly if we have a manager/wrapper (async)
                    if websocket_manager:
                        response_sent = True
                        
                        # Send the streaming data asynchronously (non-blocking)
                        # The client expects data with message_type at the top level
                        asyncio.create_task(websocket_manager.broadcast_message(conversation_id, data))
            
            chunk_capture = ChunkCapture()

            # Extract query parameters from message
            query_params = self._extract_query_params(message)

            # Create handler directly with query_params
            handler = self.nlweb_handler(query_params, chunk_capture)
            results = await handler.runQuery()
            
            # If we streamed the response, create a message for storage
            if response_sent:
                # No longer send complete message - end-nlweb-response is sent by handler

                # Store the conversation exchange
                # Handle both dict and string sender_info
                if isinstance(message.sender_info, dict):
                    user_id = message.sender_info.get('id')
                else:
                    user_id = message.sender_info
                await self.storeConversationExchange(handler, user_id, conversation_id)
        
            
        except asyncio.TimeoutError:
            sender_id = message.sender_info.get('id') if isinstance(message.sender_info, dict) else message.sender_info
            logger.warning(f"NLWeb timeout processing message from {sender_id}")
            raise
        except QueueFullError:
            # Handle queue full gracefully
            logger.info("Queue full, dropping NLWeb response")
            return None
        except Exception as e:
            logger.error(f"Error in NLWeb processing: {e}")
            return None
    
    async def storeConversationExchange(self, handler, user_id, conversation_id):
        """Store the conversation exchange."""
        try:
            # Don't store conversation history searches in the conversation history
            if hasattr(handler, 'site') and handler.site == 'conv_history':
                logger.info("Skipping storage for conversation history search")
                return

            # Check if handler has any ranked answers to store
            if not hasattr(handler, 'final_ranked_answers') or not handler.final_ranked_answers:
                return

            # Serialize the ranked answers as the response
            response = json.dumps([
                {
                    'name': item.get('name', ''),
                    'url': item.get('url', ''),
                    'ranking': item.get('ranking', {}),
                }
                for item in handler.final_ranked_answers
            ])
            summary_array = []

            # Create summary array from final_ranked_answers
            # Each item is a dict with 'name', 'url', 'ranking', 'schema_object'
            for item in handler.final_ranked_answers:
                title = item.get('name', '')
                # Extract description from schema_object if available
                schema_obj = item.get('schema_object', {})
                description = ''
                if isinstance(schema_obj, dict):
                    description = schema_obj.get('description', '')

                summary_array.append({
                    'title': title,
                    'description': description
                })

            decontextualized_query = handler.decontextualized_query if hasattr(handler, 'decontextualized_query') else handler.query

            # In summarize mode, handler.summary is already available as a string
            if hasattr(handler, 'summary') and handler.summary:
                summary_result = {
                    'summary': handler.summary,
                    'main_topics': []
                }
                # Still generate the embedding
                embedding_text = " ".join([
                    f"{item['title']} {item['description']}"
                    for item in summary_array
                    if item['title'] or item['description']
                ])
                try:
                    embedding = await get_embedding(
                        text=embedding_text[:2000],
                        timeout=10
                    )
                except Exception as e:
                    logger.error(f"Error generating embedding: {e}")
                    embedding = None
            else:
                # Generate summary and embedding in parallel
                summary_result, embedding = await self.createSummaryAndEmbedding(summary_array, decontextualized_query)

            # Store the conversation with summary and embedding
            await add_conversation(
                user_id=user_id,
                site=handler.site if hasattr(handler, 'site') else 'all',
                message_id=None,  # Let storage generate a message_id
                user_prompt=decontextualized_query,
                response=response,
                conversation_id=conversation_id,  # This is the frontend's conversation ID
                embedding=embedding,
                summary=summary_result.get('summary') if summary_result else None,
                main_topics=summary_result.get('main_topics') if summary_result else None,
                participants=summary_result.get('participants') if summary_result else None
            )
            logger.info(f"Stored conversation with summary for user {user_id} in conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
            # Don't fail the request if storage fails
    
    async def createSummaryAndEmbedding(self, summary_array, decontextualized_query):
        """
        Create a summary using LLM and generate embedding from the summary array.
        Both calls happen in parallel for efficiency.
        
        Args:
            summary_array: List of dicts with 'title' and 'description' keys
            decontextualized_query: The processed/decontextualized query string
            
        Returns:
            Tuple of (summary_result, embedding)
        """
        try:
            # Define the prompt directly
            prompt_str = f"""You are tasked with creating a concise, informative summary of search results from a conversation.
          
The user's query was: {decontextualized_query}

You will receive a list of search results returned for this query, each with a title and description.
Create a summary that:
1. Captures the main themes and topics covered across all results
2. Highlights the most relevant and useful information
3. Is concise yet comprehensive (2-3 sentences)
4. Maintains factual accuracy without speculation
5. Relates the findings back to the user's original query

In the summary, don't explicitly refer to "the search results"

The search results are:
{json.dumps(summary_array, indent=2)}

Create a summary that would be useful for understanding what information was found in response to the user's query."""

            # Define the expected response structure
            ans_struc = {
                "summary": "A concise 2-3 sentence summary of the search results",
                "main_topics": ["topic1", "topic2", "topic3"]
            }
            
            # Convert summary array to text for embedding
            embedding_text = " ".join([
                f"{item['title']} {item['description']}" 
                for item in summary_array 
                if item['title'] or item['description']
            ])
            
            # Make parallel calls to LLM and embedding service
            llm_task = ask_llm(
                prompt=prompt_str,
                schema=ans_struc,
                level="low",
                timeout=10
            )
            
            embedding_task = get_embedding(
                text=embedding_text[:2000],  # Limit text length for embedding
                timeout=10
            )
            
            # Wait for both tasks to complete
            summary_result, embedding = await asyncio.gather(
                llm_task,
                embedding_task,
                return_exceptions=True
            )
            
            # Handle exceptions from either task
            if isinstance(summary_result, Exception):
                logger.error(f"Error generating summary: {summary_result}")
                summary_result = None
            
            if isinstance(embedding, Exception):
                logger.error(f"Error generating embedding: {embedding}")
                embedding = None
            
            return summary_result, embedding
            
        except Exception as e:
            logger.error(f"Error in createSummaryAndEmbedding: {e}")
            return None, None
    
    def get_participant_info(self) -> ParticipantInfo:
        """Get participant information"""
        return ParticipantInfo(
            participant_id=self.participant_id,
            name="NLWeb Assistant",
            participant_type=ParticipantType.AI,
            joined_at=self.joined_at  # Already in milliseconds
        )