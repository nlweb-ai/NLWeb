"""
Chat system data models and schemas.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Set, Dict, Any, Optional, List
import uuid


class MessageType(Enum):
    """Types of messages in the chat system"""
    CONVERSATION_START = "conversation_start"
    USER_INPUT = "user_input"
    NLW_RESPONSE = "nlw_response"
    USER_JOINING = "user_joining"
    USER_LEAVING = "user_leaving"


class MessageStatus(Enum):
    """Status of a message"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    PROCESSING = "processing"


class ParticipantType(Enum):
    """Types of participants in a conversation"""
    HUMAN = "human"
    AI = "ai"


@dataclass
class ChatMessage:
    """
    Unified chat message format matching browser localStorage.
    Content can be any JSON-serializable object (string, dict, list, etc.)
    """
    message_id: str
    conversation_id: str
    content: Any  # Can be string, dict, list - any JSON-serializable object
    message_type: str  # "user", "assistant", "system", "join", "leave", "nlweb", etc.
    timestamp: int  # milliseconds since epoch
    sender_info: Dict[str, str]  # {id: str, name: str}
    site: Optional[str] = None  # Site for NLWeb queries
    mode: Optional[str] = None  # Mode for NLWeb queries (list, summarize, generate)
    prev_queries: Optional[List[Dict[str, Any]]] = None  # Previous queries for context
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization"""
        result = {
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "content": self.content,
            "message_type": self.message_type,
            "timestamp": self.timestamp,
            "sender_info": self.sender_info
        }
        if self.site is not None:
            result["site"] = self.site
        if self.mode is not None:
            result["mode"] = self.mode
        if self.prev_queries is not None:
            result["prev_queries"] = self.prev_queries
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """Create ChatMessage from dictionary.
        For NLWeb and other messages, stores the entire message dict as content."""
        
        # Extract required fields
        message_id = data.get("message_id", f"msg_{uuid.uuid4().hex[:12]}")
        conversation_id = data.get("conversation_id")
        message_type = data.get("message_type")
        timestamp = data.get("timestamp")
        sender_info = data.get("sender_info")
        
        # Validate required fields
        if not all([conversation_id, message_type, timestamp, sender_info]):
            raise ValueError(f"Missing required fields. Got: conversation_id={conversation_id}, "
                           f"message_type={message_type}, timestamp={timestamp}, sender_info={sender_info}")
        
        # For NLWeb messages that don't have a 'content' field, use the entire message as content
        if "content" in data:
            content = data["content"]
        else:
            # Store the entire message structure for NLWeb messages
            content = data
        
        return cls(
            message_id=message_id,
            conversation_id=conversation_id,
            content=content,
            message_type=message_type,
            timestamp=timestamp,
            sender_info=sender_info,
            site=data.get("site"),
            mode=data.get("mode"),
            prev_queries=data.get("prev_queries")
        )


@dataclass
class ParticipantInfo:
    """
    Information about a conversation participant.
    """
    participant_id: str
    name: str
    participant_type: ParticipantType
    joined_at: int  # Unix timestamp in milliseconds
    
    def is_human(self) -> bool:
        """Check if participant is human"""
        return self.participant_type == ParticipantType.HUMAN
    
    def is_ai(self) -> bool:
        """Check if participant is AI"""
        return self.participant_type == ParticipantType.AI
    
    def __eq__(self, other):
        """Equality based on participant_id"""
        if isinstance(other, ParticipantInfo):
            return self.participant_id == other.participant_id
        return False
    
    def __hash__(self):
        """Hash based on participant_id for use in sets"""
        return hash(self.participant_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "participant_id": self.participant_id,
            "name": self.name,
            "participant_type": self.participant_type.value,
            "joined_at": self.joined_at  # Already in milliseconds
        }


@dataclass
class Conversation:
    """
    Represents a conversation with multiple participants.
    Supports multiple human participants and AI agents.
    """
    conversation_id: str
    created_at: datetime
    active_participants: Set[ParticipantInfo]
    queue_size_limit: int
    messages: List[ChatMessage] = field(default_factory=list)  # Sequential list of all messages
    message_count: int = 0
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate that active_participants contains ParticipantInfo objects."""
        if self.active_participants:
            for p in self.active_participants:
                if not isinstance(p, ParticipantInfo):
                    raise TypeError(
                        f"active_participants must contain ParticipantInfo objects, "
                        f"got {type(p).__name__}: {p}"
                    )
    
    def get_human_participants(self) -> List[ParticipantInfo]:
        """Get all human participants"""
        return [p for p in self.active_participants if p.is_human()]
    
    def get_ai_participants(self) -> List[ParticipantInfo]:
        """Get all AI participants"""
        return [p for p in self.active_participants if p.is_ai()]
    
    def add_participant(self, participant: ParticipantInfo):
        """Add a participant to the conversation"""
        if not isinstance(participant, ParticipantInfo):
            raise TypeError(f"Expected ParticipantInfo, got {type(participant)}: {participant}")
        
        self.active_participants.add(participant)
        self.updated_at = datetime.utcnow()
    
    def remove_participant(self, participant_id: str):
        """Remove a participant from the conversation"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== Conversation.remove_participant called on {self.conversation_id} ===")
        logger.info(f"  Removing participant ID: {participant_id}")
        logger.info(f"  Active participants before: {self.active_participants}")
        
        self.active_participants = {
            p for p in self.active_participants 
            if p.participant_id != participant_id
        }
        self.updated_at = datetime.utcnow()
        
        logger.info(f"  Active participants after: {self.active_participants}")
        logger.info(f"=== Participant removed from {self.conversation_id} ===\n")
    
    def increment_message_count(self):
        """Increment the message count"""
        self.message_count += 1
        self.updated_at = datetime.utcnow()
    
    def check_queue_limit(self):
        """
        Check if queue is full and raise QueueFullError if so.
        Should be called before adding a new message.
        """
        if self.message_count >= self.queue_size_limit:
            raise QueueFullError(
                conversation_id=self.conversation_id,
                queue_size=self.message_count,
                limit=self.queue_size_limit
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation to dictionary for serialization"""
        return {
            "conversation_id": self.conversation_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "participants": [p.to_dict() for p in self.active_participants],
            "queue_size_limit": self.queue_size_limit,
            "message_count": self.message_count,
            "participant_count": len(self.active_participants),
            "metadata": self.metadata or {}
        }
    
    def create_participant_event(self, participant: ParticipantInfo, event_type: str) -> ChatMessage:
        """
        Create a system message for participant join/leave events.
        """
        import time
        
        if event_type == "join":
            content = f"{participant.name} has joined the conversation"
            msg_type = "join"
        elif event_type == "leave":
            content = f"{participant.name} has left the conversation"
            msg_type = "leave"
        else:
            raise ValueError(f"Unknown event type: {event_type}")
        
        return ChatMessage(
            message_id=f"msg_{uuid.uuid4().hex[:12]}",
            conversation_id=self.conversation_id,
            content=content,
            message_type=msg_type,
            timestamp=int(time.time() * 1000),  # milliseconds
            sender_info={
                "id": "system",
                "name": "System"
            }
        )
    


class QueueFullError(Exception):
    """
    Raised when a conversation's message queue is full.
    Used for backpressure control.
    """
    def __init__(self, conversation_id: str, queue_size: int, limit: int):
        self.conversation_id = conversation_id
        self.queue_size = queue_size
        self.limit = limit
        super().__init__(
            f"Queue full for conversation {conversation_id}: {queue_size}/{limit} messages"
        )