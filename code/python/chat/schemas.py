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
    TEXT = "text"
    SYSTEM = "system"
    NLWEB_RESPONSE = "nlweb_response"
    ERROR = "error"


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


@dataclass(frozen=True)
class ChatMessage:
    """
    Immutable chat message with server-assigned sequence ID for ordering.
    """
    message_id: str
    conversation_id: str
    sequence_id: int  # Server-assigned for strict ordering
    sender_id: str  # Unique identifier for sender (user_123, nlweb_1, etc.)
    sender_name: str  # Display name
    content: str
    message_type: MessageType
    timestamp: datetime
    status: MessageStatus = MessageStatus.DELIVERED
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization"""
        return {
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "sequence_id": self.sequence_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "content": self.content,
            "message_type": self.message_type.value,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "metadata": self.metadata or {}
        }


@dataclass
class ParticipantInfo:
    """
    Information about a conversation participant.
    """
    participant_id: str
    name: str
    participant_type: ParticipantType
    joined_at: datetime
    
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
            "joined_at": self.joined_at.isoformat()
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
            "active_participants": [p.to_dict() for p in self.active_participants],
            "queue_size_limit": self.queue_size_limit,
            "message_count": self.message_count,
            "metadata": self.metadata or {}
        }
    
    def create_participant_event(self, participant: ParticipantInfo, event_type: str) -> ChatMessage:
        """
        Create a system message for participant join/leave events.
        """
        if event_type == "join":
            content = f"{participant.name} has joined the conversation"
            metadata = {
                "event_type": "participant_join",
                "participant_id": participant.participant_id,
                "participant_name": participant.name,
                "participant_type": participant.participant_type.value
            }
        elif event_type == "leave":
            content = f"{participant.name} has left the conversation"
            metadata = {
                "event_type": "participant_leave",
                "participant_id": participant.participant_id,
                "participant_name": participant.name,
                "participant_type": participant.participant_type.value
            }
        else:
            raise ValueError(f"Unknown event type: {event_type}")
        
        return ChatMessage(
            message_id=f"msg_{uuid.uuid4().hex[:12]}",
            conversation_id=self.conversation_id,
            sequence_id=0,  # Will be assigned by server
            sender_id="system",
            sender_name="System",
            content=content,
            message_type=MessageType.SYSTEM,
            timestamp=datetime.utcnow(),
            metadata=metadata
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