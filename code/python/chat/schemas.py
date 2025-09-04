"""
Chat system data models and schemas.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Set, Dict, Any, Optional, List
import uuid

# Import core message schemas
from core.schemas import Message, MessageType, MessageStatus, SenderType

# Use Message directly from core.schemas - no need for ChatMessage
# MessageType, MessageStatus, and SenderType are already defined in core.schemas

class ParticipantType(Enum):
    """Types of participants in a conversation"""
    HUMAN = "human"  # Maps to SenderType.USER
    AI = "ai"  # Maps to SenderType.ASSISTANT


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
    messages: List[Message] = field(default_factory=list)  # Sequential list of all messages
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
    
    def create_participant_event(self, participant: ParticipantInfo, event_type: str) -> Message:
        """
        Create a system message for participant join/leave events.
        """
        
        if event_type == "join":
            content = f"{participant.name} has joined the conversation"
            msg_type = MessageType.JOIN
        elif event_type == "leave":
            content = f"{participant.name} has left the conversation"
            msg_type = MessageType.LEAVE
        else:
            raise ValueError(f"Unknown event type: {event_type}")
        
        return Message(
            message_id=f"msg_{uuid.uuid4().hex[:12]}",
            conversation_id=self.conversation_id,
            content=content,
            sender_type=SenderType.SYSTEM,
            message_type=msg_type,
            timestamp=datetime.utcnow().isoformat(),
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