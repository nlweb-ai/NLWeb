"""
Core message and conversation schemas for NLWeb system.
Provides standardized data structures and serialization utilities.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional, Union, List
from enum import Enum
import uuid


class SenderType(str, Enum):
    """Who sent the message."""
    USER = "user"
    ASSISTANT = "assistant" 
    SYSTEM = "system"


class MessageStatus(str, Enum):
    """Status of message delivery/processing."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    PROCESSING = "processing"


class MessageType(str, Enum):
    """Type/purpose of the message content."""
    # User interactions
    QUERY = "query"  # Also covers USER_INPUT
    
    # Results and responses
    RESULT = "result"
    NLWS = "nlws"  # Generated answers (also covers NLW_RESPONSE)
    
    # Status and progress
    STATUS = "status"
    INTERMEDIATE = "intermediate_message"
    
    # Errors
    ERROR = "error"
    
    # Specific content types
    ITEM_DETAILS = "item_details"
    STATISTICS = "statistics_result"
    CHART = "chart_result"
    COMPARISON = "compare_items"
    SUBSTITUTION = "substitution_suggestions"
    ENSEMBLE = "ensemble_result"
    
    # Multi-site operations
    SITE_QUERYING = "site_querying"
    SITE_COMPLETE = "site_complete"
    SITE_ERROR = "site_error"
    MULTI_SITE_COMPLETE = "multi_site_complete"
    
    # System messages
    NO_RESULTS = "no_results"
    COMPLETE = "complete"
    TOOL_SELECTION = "tool_selection"
    
    # Chat-specific events
    CONVERSATION_START = "conversation_start"
    USER_JOINING = "user_joining"
    USER_LEAVING = "user_leaving"
    JOIN = "join"
    LEAVE = "leave"


@dataclass
class UserQuery:
    """User query content structure."""
    query: str
    site: Optional[str] = None
    mode: Optional[str] = None
    prev_queries: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, omitting None values."""
        result = {"query": self.query}
        if self.site is not None:
            result["site"] = self.site
        if self.mode is not None:
            result["mode"] = self.mode
        if self.prev_queries is not None:
            result["prev_queries"] = self.prev_queries
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserQuery':
        """Create UserQuery from dictionary."""
        return cls(
            query=data.get("query", ""),
            site=data.get("site"),
            mode=data.get("mode"),
            prev_queries=data.get("prev_queries")
        )


@dataclass
class Message:
    """
    Core message structure for all communication.
    Separates WHO sent it (sender_type) from WHAT it contains (message_type).
    """
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_type: SenderType = SenderType.USER
    message_type: MessageType = MessageType.QUERY
    conversation_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    content: Union[str, UserQuery, Dict[str, Any], List[Any]] = ""
    sender_info: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        result = {
            "message_id": self.message_id,
            "sender_type": self.sender_type.value if isinstance(self.sender_type, SenderType) else self.sender_type,
            "message_type": self.message_type.value if isinstance(self.message_type, MessageType) else self.message_type,
            "timestamp": self.timestamp
        }
        
        # Handle content serialization
        if isinstance(self.content, UserQuery):
            result["content"] = self.content.to_dict()
        elif isinstance(self.content, (str, dict, list)):
            result["content"] = self.content
        else:
            result["content"] = str(self.content)
        
        # Add optional fields
        if self.conversation_id is not None:
            result["conversation_id"] = self.conversation_id
        if self.sender_info is not None:
            result["sender_info"] = self.sender_info
        if self.metadata is not None:
            result["metadata"] = self.metadata
            
        return result
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create Message from dictionary."""
        # Determine content type
        content = data.get("content", "")
        sender_type = data.get("sender_type", "user")
        message_type = data.get("message_type", "query")
        
        # If content is a dict with 'query' field and sender is user, treat as UserQuery
        if isinstance(content, dict) and "query" in content and sender_type == "user":
            content = UserQuery.from_dict(content)
        
        # Convert string types to enums if valid
        if isinstance(sender_type, str):
            try:
                sender_type = SenderType(sender_type)
            except ValueError:
                # Keep as string if not a valid enum value
                pass
        
        if isinstance(message_type, str):
            try:
                message_type = MessageType(message_type)
            except ValueError:
                # Keep as string if not a valid enum value
                pass
        
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            sender_type=sender_type,
            message_type=message_type,
            conversation_id=data.get("conversation_id"),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            content=content,
            sender_info=data.get("sender_info"),
            metadata=data.get("metadata")
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Create Message from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class ConversationEntry:
    """
    Represents a single conversation entry (one exchange between user and assistant).
    Used for storing conversation history in the database.
    """
    user_id: str                    # User ID (if logged in) or anonymous ID
    site: str                       # Site context for the conversation
    message_id: str                 # Message ID to group related messages in a conversation
    user_prompt: str                # The user's question/prompt
    response: Union[str, List[Message]]  # The assistant's response (legacy str or Message list)
    time_of_creation: datetime      # Timestamp of creation
    conversation_id: str            # Unique ID for this conversation entry
    embedding: Optional[List[float]] = None  # Embedding vector for the conversation
    summary: Optional[str] = None   # LLM-generated summary of the conversation
    main_topics: Optional[List[str]] = None  # Main topics identified in the conversation
    participants: Optional[List[Dict[str, Any]]] = None  # List of participants in the conversation
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        # Handle response field - convert Message objects to dicts if needed
        if isinstance(self.response, list) and self.response and isinstance(self.response[0], Message):
            response_data = [msg.to_dict() for msg in self.response]
        else:
            response_data = self.response
            
        return {
            "user_id": self.user_id,
            "site": self.site,
            "message_id": self.message_id,
            "user_prompt": self.user_prompt,
            "response": response_data,
            "time_of_creation": self.time_of_creation.isoformat(),
            "conversation_id": self.conversation_id,
            "embedding": self.embedding,
            "summary": self.summary,
            "main_topics": self.main_topics,
            "participants": self.participants
        }
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON format for API responses."""
        # Handle response field - convert Message objects to dicts if needed
        if isinstance(self.response, list) and self.response and isinstance(self.response[0], Message):
            response_data = [msg.to_dict() for msg in self.response]
        else:
            response_data = self.response
            
        return {
            "id": self.conversation_id,
            "user_prompt": self.user_prompt,
            "response": response_data,
            "time": self.time_of_creation.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationEntry':
        """Create from dictionary."""
        # Handle datetime conversion
        if isinstance(data.get("time_of_creation"), str):
            data["time_of_creation"] = datetime.fromisoformat(data["time_of_creation"])
        
        # Handle response field - convert dicts to Message objects if it's a list
        response = data.get("response")
        if isinstance(response, list) and response and isinstance(response[0], dict):
            try:
                data["response"] = [Message.from_dict(msg) for msg in response]
            except:
                # If conversion fails, keep as is
                pass
                
        return cls(**data)


# Convenience functions for creating common message types

def create_user_message(query: str, site: Optional[str] = None, mode: Optional[str] = None,
                       sender_info: Optional[Dict[str, Any]] = None,
                       handler=None, send: bool = True) -> Message:
    """
    Create a user message with UserQuery content.
    
    Args:
        query: The user's query text
        site: Optional site filter
        mode: Optional query mode
        sender_info: Optional sender information
        handler: Handler instance (provides conversation_id and send capability)
        send: If True and handler provided, automatically send the message
    
    Returns:
        The created Message object
    """
    user_query = UserQuery(query=query, site=site, mode=mode)
    message = Message(
        sender_type=SenderType.USER,
        message_type=MessageType.QUERY,
        content=user_query,
        conversation_id=handler.conversation_id if handler and hasattr(handler, 'conversation_id') else None,
        sender_info=sender_info
    )
    
    if send and handler:
        import asyncio
        asyncio.create_task(handler.send_message(message.to_dict()))
    
    return message


def create_assistant_result(results: List[Dict[str, Any]], 
                           handler=None, 
                           metadata: Optional[Dict[str, Any]] = None,
                           send: bool = True) -> Message:
    """
    Create an assistant message with search results.
    
    Args:
        results: List of search results
        handler: Handler instance (provides conversation_id and send capability)
        metadata: Optional metadata
        send: If True and handler provided, automatically send the message
    
    Returns:
        The created Message object
    """
    message = Message(
        sender_type=SenderType.ASSISTANT,
        message_type=MessageType.RESULT,
        content=results,
        conversation_id=handler.conversation_id if handler and hasattr(handler, 'conversation_id') else None,
        metadata=metadata
    )
    
    if send and handler:
        import asyncio
        asyncio.create_task(handler.send_message(message.to_dict()))
    
    return message


def create_assistant_answer(answer: str, 
                           handler=None,
                           items: Optional[List[Dict[str, Any]]] = None,
                           send: bool = True) -> Message:
    """
    Create an assistant message with generated answer.
    
    Args:
        answer: The generated answer text
        handler: Handler instance (provides conversation_id and send capability)
        items: Optional list of supporting items
        send: If True and handler provided, automatically send the message
    
    Returns:
        The created Message object
    """
    content = {"answer": answer, "@type": "GeneratedAnswer"}
    if items:
        content["items"] = items
    
    message = Message(
        sender_type=SenderType.ASSISTANT,
        message_type=MessageType.NLWS,
        content=content,
        conversation_id=handler.conversation_id if handler and hasattr(handler, 'conversation_id') else None
    )
    
    if send and handler:
        import asyncio
        asyncio.create_task(handler.send_message(message.to_dict()))
    
    return message


def create_status_message(status_text: str, 
                         handler=None,
                         sender_type: SenderType = SenderType.SYSTEM,
                         send: bool = True) -> Message:
    """
    Create a status/intermediate message.
    
    Args:
        status_text: The status message text
        handler: Handler instance (provides conversation_id and send capability)
        sender_type: Who is sending the status (default: SYSTEM)
        send: If True and handler provided, automatically send the message
    
    Returns:
        The created Message object
    """
    message = Message(
        sender_type=sender_type,
        message_type=MessageType.INTERMEDIATE,
        content=status_text,
        conversation_id=handler.conversation_id if handler and hasattr(handler, 'conversation_id') else None
    )
    
    if send and handler:
        import asyncio
        asyncio.create_task(handler.send_message(message.to_dict()))
    
    return message


def create_error_message(error_text: str, 
                        handler=None,
                        metadata: Optional[Dict[str, Any]] = None,
                        send: bool = True) -> Message:
    """
    Create an error message.
    
    Args:
        error_text: The error message text
        handler: Handler instance (provides conversation_id and send capability)
        metadata: Optional error metadata
        send: If True and handler provided, automatically send the message
    
    Returns:
        The created Message object
    """
    message = Message(
        sender_type=SenderType.SYSTEM,
        message_type=MessageType.ERROR,
        content=error_text,
        conversation_id=handler.conversation_id if handler and hasattr(handler, 'conversation_id') else None,
        metadata=metadata
    )
    
    if send and handler:
        import asyncio
        asyncio.create_task(handler.send_message(message.to_dict()))
    
    return message


def create_complete_message(handler=None,
                           sender_info: Optional[Dict[str, Any]] = None,
                           send: bool = True) -> Message:
    """
    Create a completion message.
    
    Args:
        handler: Handler instance (provides conversation_id and send capability)
        sender_info: Optional sender information
        send: If True and handler provided, automatically send the message
    
    Returns:
        The created Message object
    """
    message = Message(
        sender_type=SenderType.SYSTEM,
        message_type=MessageType.COMPLETE,
        content="",
        conversation_id=handler.conversation_id if handler and hasattr(handler, 'conversation_id') else None,
        sender_info=sender_info or {"id": "system", "name": "NLWeb"}
    )
    
    if send and handler:
        import asyncio
        asyncio.create_task(handler.send_message(message.to_dict()))
    
    return message


# Legacy compatibility function
def create_legacy_message(message_type: str, content: Any,
                         conversation_id: Optional[str] = None,
                         sender_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a message in the legacy format for backward compatibility.
    Returns a dict with the old structure where message_type conflates sender and type.
    """
    message = {
        "message_type": message_type,
        "content": content
    }
    
    if conversation_id:
        message["conversation_id"] = conversation_id
    if sender_info:
        message["sender_info"] = sender_info
        
    return message