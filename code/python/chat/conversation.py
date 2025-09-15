"""
Conversation orchestration and management.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from chat.schemas import (
    ParticipantType,
    QueueFullError
)
from core.schemas import (
    Message,
    MessageType,
    MessageStatus
)
from chat.participants import BaseParticipant
from chat.storage import SimpleChatStorageInterface
from chat.metrics import ChatMetrics

logger = logging.getLogger(__name__)


class ConversationMode(Enum):
    """Conversation input mode"""
    SINGLE = "single"  # 1 human + 1 AI
    MULTI = "multi"    # 2+ humans or 3+ total


class MessageDeliveryError(Exception):
    """Error delivering message to participant"""
    def __init__(self, message_id: str, participant_id: str, reason: str):
        self.message_id = message_id
        self.participant_id = participant_id
        self.reason = reason
        super().__init__(f"Failed to deliver message {message_id} to {participant_id}: {reason}")


@dataclass
class ParticipantFailure:
    """Record of a participant failure"""
    participant_id: str
    timestamp: datetime
    error: str
    message_id: Optional[str] = None


@dataclass
class ConversationState:
    """State of a conversation"""
    conversation_id: str
    participants: Dict[str, BaseParticipant] = field(default_factory=dict)
    message_count: int = 0
    mode: ConversationMode = ConversationMode.SINGLE
    failures: List[ParticipantFailure] = field(default_factory=list)
    active_nlweb_jobs: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class ConversationManager:
    """
    Orchestrates conversations between multiple participants.
    Handles message routing, sequencing, and delivery.
    
    This provides a clean interface for both HTTP and WebSocket implementations:
    - process_message(): Main entry point for all messages
    - add_participant(): Add participants to conversations
    - remove_participant(): Remove participants from conversations
    - get_conversation_mode(): Get current conversation mode
    - get_input_timeout(): Get timeout based on mode
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize conversation manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.single_mode_timeout = config.get("single_mode_timeout", 100)  # ms
        self.multi_mode_timeout = config.get("multi_mode_timeout", 2000)  # ms
        self.queue_size_limit = config.get("queue_size_limit", 1000)
        self.max_participants = config.get("max_participants", 100)
        
        # Conversation states
        self._conversations: Dict[str, ConversationState] = {}
        
        # Storage and metrics
        self.storage: Optional[SimpleChatStorageInterface] = None
        self.metrics = ChatMetrics()
        
        # Broadcast callback for mode changes
        self.broadcast_callback: Optional[Callable] = None
        
        # WebSocket manager (set by server)
        self.websocket_manager = None
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Running state
        self._running = True
        
        # Track persistence tasks
        self._persistence_tasks: Set[asyncio.Task] = set()
        
        # Track which conversations are being processed (to prevent deadlock)
        self._processing_messages: Set[str] = set()
    
    def add_participant(self, conversation_id: str, participant: BaseParticipant) -> None:
        """
        Add a participant to a conversation.
        
        Args:
            conversation_id: The conversation ID
            participant: The participant to add
        """
        # Get or create conversation state
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = ConversationState(
                conversation_id=conversation_id
            )
        
        conv_state = self._conversations[conversation_id]
        participant_info = participant.get_participant_info()
        
        # Check participant limit
        if len(conv_state.participants) >= self.max_participants:
            raise ValueError(f"Participant limit ({self.max_participants}) reached")
        
        # Add participant
        conv_state.participants[participant_info.participant_id] = participant
        conv_state.updated_at = datetime.utcnow()
        
        # Check if mode changed
        old_mode = conv_state.mode
        new_mode = self._calculate_mode(conv_state)
        
        if old_mode != new_mode:
            conv_state.mode = new_mode
            self._broadcast_mode_change(conversation_id, new_mode)
    
    def remove_participant(self, conversation_id: str, participant_id: str) -> None:
        """
        Remove a participant from a conversation.
        
        Args:
            conversation_id: The conversation ID
            participant_id: The participant ID to remove
        """
        if conversation_id in self._conversations:
            conv_state = self._conversations[conversation_id]
            
            if participant_id in conv_state.participants:
                del conv_state.participants[participant_id]
                conv_state.updated_at = datetime.utcnow()
                
                # Check if mode changed
                old_mode = conv_state.mode
                new_mode = self._calculate_mode(conv_state)
                
                if old_mode != new_mode:
                    conv_state.mode = new_mode
                    self._broadcast_mode_change(conversation_id, new_mode)
    
    def get_conversation_mode(self, conversation_id: str) -> ConversationMode:
        """Get the current mode of a conversation"""
        if conversation_id in self._conversations:
            return self._conversations[conversation_id].mode
        return ConversationMode.SINGLE
    
    def get_input_timeout(self, conversation_id: str) -> int:
        """Get input timeout based on conversation mode"""
        mode = self.get_conversation_mode(conversation_id)
        return self.single_mode_timeout if mode == ConversationMode.SINGLE else self.multi_mode_timeout
    
    async def process_message(
        self, 
        message: Message,
        require_ack: bool = False,
        stream_callback = None
    ) -> Message:
        """
        Process an incoming message.
        
        Args:
            message: The message to process
            require_ack: Whether to require delivery acknowledgments
            stream_callback: Optional callback for streaming responses (WebSocket manager or SSE wrapper)
            
        Returns:
            The message with assigned sequence ID and delivery status
            
        Raises:
            QueueFullError: If conversation queue is full
        """
        
        # Check if conversation exists BEFORE entering try block
        if message.conversation_id not in self._conversations:
            
            # Conversation must exist before processing messages
            raise ValueError(f"Conversation {message.conversation_id} not found in ConversationManager state")
        
        try:
            # No locking for now - just process the message
            return await self._process_message_internal(message, require_ack, stream_callback)
        except Exception as e:
            raise
    
    async def _process_message_internal(
        self,
        message: Message,
        require_ack: bool = False,
        stream_callback = None
    ) -> Message:
        """
        Internal message processing logic (can be called with or without lock).
        """
        # Check conversation exists
        if message.conversation_id not in self._conversations:
            raise ValueError(f"Unknown conversation: {message.conversation_id}")
        
        conv_state = self._conversations[message.conversation_id]
        logger.debug(f"Processing message for conversation {message.conversation_id} with {conv_state.message_count} existing messages")
        
        # Check queue limit
        if conv_state.message_count >= self.queue_size_limit:
            # Try to drop oldest NLWeb jobs first
            if not self._try_drop_nlweb_jobs(conv_state):
                raise QueueFullError(
                    conversation_id=message.conversation_id,
                    queue_size=conv_state.message_count,
                    limit=self.queue_size_limit
                )
        
        # Update message count (no longer using sequence_id)
        conv_state.message_count += 1
        
        # Message is already in unified format
        sequenced_message = message
        
        # Queue message for storage IMMEDIATELY (async, non-blocking)
        # This ensures user message gets stored with its original timestamp
        if self.storage:
            persist_task = asyncio.create_task(self._persist_message(sequenced_message))
            self._persistence_tasks.add(persist_task)
            persist_task.add_done_callback(lambda t: self._persistence_tasks.discard(t))
        
        # Deliver to participants asynchronously (non-blocking)
        delivery_task = asyncio.create_task(self._deliver_to_participants(
            sequenced_message,
            conv_state,
            require_ack,
            stream_callback
        ))
        
        # Note: We're not awaiting delivery - it happens asynchronously
        
        
        # Update conversation state
        conv_state.updated_at = datetime.utcnow()
        
        # Track metrics
        self.metrics.update_queue_depth(message.conversation_id, conv_state.message_count)
        
        # Broadcast to WebSocket connections asynchronously (non-blocking)
        # IMPORTANT: Don't echo user messages back to the sender
        if self.websocket_manager:
            sender_id = message.sender_info.get('id') if message.sender_info else None
            broadcast_task = asyncio.create_task(
                self.websocket_manager.broadcast_message(
                    message.conversation_id,
                    sequenced_message.to_dict(),  # Send message directly, no wrapping
                    exclude_user_id=sender_id  # Exclude the sender
                )
            )
        
        return sequenced_message
    
    async def _deliver_to_participants(
        self,
        message: Message,
        conv_state: ConversationState,
        require_ack: bool = False,
        stream_callback = None
    ) -> Dict[str, bool]:
        """
        Deliver message to all participants except sender.
        
        Args:
            message: The message to deliver
            conv_state: Conversation state
            require_ack: Whether to track acknowledgments
            
        Returns:
            Dictionary of participant_id -> delivery success
        """
        delivery_acks = {}
        delivery_tasks = []
        
        # Get conversation history for context
        context = []
        if self.storage:
            try:
                # Get recent messages for context
                context = await self.storage.get_conversation_messages(
                    message.conversation_id,
                    limit=20
                )
                logger.info(f"ConversationManager retrieved {len(context)} messages from storage for context")
            except Exception as e:
                logger.error(f"Failed to get context: {e}")
        
        # Deliver to all participants except sender
        for participant_id, participant in conv_state.participants.items():
            if participant_id != message.sender_info.get('id'):
                # Create delivery task for all non-sender participants
                task = self._deliver_to_participant(
                    message,
                    participant,
                    participant_id,
                    context,
                    conv_state,
                    stream_callback
                )
                delivery_tasks.append((participant_id, task))
            elif require_ack:
                # For sender, assume successful delivery
                delivery_acks[participant_id] = True
        
        # Execute all deliveries concurrently
        if delivery_tasks:
            results = await asyncio.gather(
                *[task for _, task in delivery_tasks],
                return_exceptions=True
            )
            
            # Track acknowledgments
            for i, (participant_id, _) in enumerate(delivery_tasks):
                if isinstance(results[i], Exception):
                    delivery_acks[participant_id] = False
                    # Record failure
                    conv_state.failures.append(ParticipantFailure(
                        participant_id=participant_id,
                        timestamp=datetime.utcnow(),
                        error=str(results[i]),
                        message_id=message.message_id
                    ))
                else:
                    delivery_acks[participant_id] = True
        
        return delivery_acks if require_ack else {}
    
    async def _deliver_to_participant(
        self,
        message: Message,
        participant: BaseParticipant,
        participant_id: str,
        context: List[Message],
        conv_state: ConversationState,
        stream_callback = None
    ) -> None:
        """
        Deliver message to a single participant.
        
        Args:
            message: The message to deliver
            participant: The participant
            participant_id: Participant ID
            context: Conversation context
            conv_state: Conversation state
        """
        try:
            participant_info = participant.get_participant_info()
            
            # For AI participants, track as active job
            if participant_info.participant_type == ParticipantType.AI:
                conv_state.active_nlweb_jobs.add(f"{message.message_id}_{participant_id}")
                logger.info(f"ConversationManager calling AI participant {participant_id} for message {message.message_id}")
                
                # Process message - pass stream callback (WebSocket manager or SSE wrapper)
                # Use the provided stream_callback, or fall back to websocket_manager
                callback = stream_callback or self.websocket_manager
                response = await participant.process_message(message, context, callback)
                
                # If participant generated a response, process it
                if response:
                    try:
                        # Process the response as a new message
                        result = await self.process_message(response)
                    except Exception as e:
                        logger.error(f"Failed to process AI response: {e}", exc_info=True)
                
                # Remove from active jobs
                conv_state.active_nlweb_jobs.discard(f"{message.message_id}_{participant_id}")
            else:
                # For human participants, process_message returns None
                # This is kept for consistency but does nothing
                callback = stream_callback or self.websocket_manager
                await participant.process_message(message, context, callback)
                
        except Exception as e:
            logger.error(f"Failed to deliver to {participant_id}: {e}")
            # Remove from active jobs on failure too
            conv_state.active_nlweb_jobs.discard(f"{message.message_id}_{participant_id}")
            raise
    
    async def _persist_message(self, message: Message) -> None:
        """
        Persist message to storage (async after delivery).
        
        Args:
            message: The message to persist
        """
        # Temporarily disabled storage calls
        # try:
        #     await self.storage.store_message(message)
        # except Exception as e:
        #     import traceback
        #     logger.error(f"Failed to persist message {message.message_id}: {e}", exc_info=True)
    
    def _calculate_mode(self, conv_state: ConversationState) -> ConversationMode:
        """
        Calculate conversation mode based on participants.
        
        Args:
            conv_state: Conversation state
            
        Returns:
            The conversation mode
        """
        human_count = 0
        ai_count = 0
        
        for participant in conv_state.participants.values():
            info = participant.get_participant_info()
            if info.participant_type == ParticipantType.HUMAN:
                human_count += 1
            else:
                ai_count += 1
        
        total_count = human_count + ai_count
        
        # Multi mode if 2+ humans or 3+ total participants
        if human_count >= 2 or total_count >= 3:
            return ConversationMode.MULTI
        
        return ConversationMode.SINGLE
    
    def _broadcast_mode_change(self, conversation_id: str, new_mode: ConversationMode) -> None:
        """
        Broadcast mode change to all participants.
        
        Args:
            conversation_id: The conversation ID
            new_mode: The new mode
        """
        if self.broadcast_callback:
            timeout = self.single_mode_timeout if new_mode == ConversationMode.SINGLE else self.multi_mode_timeout
            
            mode_change_msg = {
                "type": "mode_change",
                "conversation_id": conversation_id,
                "mode": new_mode.value,
                "input_timeout": timeout,
                "timestamp": int(time.time() * 1000)
            }
            
            self.broadcast_callback(conversation_id, mode_change_msg)
    
    def _try_drop_nlweb_jobs(self, conv_state: ConversationState) -> bool:
        """
        Try to drop oldest NLWeb processing jobs to make room.
        
        Args:
            conv_state: Conversation state
            
        Returns:
            True if space was made, False otherwise
        """
        if conv_state.active_nlweb_jobs:
            # Drop oldest job
            oldest_job = min(conv_state.active_nlweb_jobs)
            conv_state.active_nlweb_jobs.remove(oldest_job)
            conv_state.message_count -= 1
            logger.info(f"Dropped NLWeb job {oldest_job} to make room")
            return True
        
        return False
    
    def get_participant_failures(self, conversation_id: str) -> List[ParticipantFailure]:
        """Get failures for a conversation"""
        if conversation_id in self._conversations:
            return self._conversations[conversation_id].failures.copy()
        return []
    
    def get_active_nlweb_jobs(self, conversation_id: str) -> List[str]:
        """Get active NLWeb processing jobs"""
        if conversation_id in self._conversations:
            return list(self._conversations[conversation_id].active_nlweb_jobs)
        return []
    
    async def shutdown(self) -> None:
        """Shutdown the conversation manager"""
        self._running = False
        
        # Wait for all persistence tasks to complete
        if self._persistence_tasks:
            try:
                await asyncio.gather(*self._persistence_tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error waiting for persistence tasks: {e}")
    
    @staticmethod
    def create_message(
        conversation_id: str,
        sender_id: str,
        sender_name: str,
        content: str,
        sites: Optional[List[str]] = None,
        mode: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Create a chat message with consistent structure.
        
        This is the clean interface that both HTTP and WebSocket handlers should use
        to create messages with proper metadata including sites and mode.
        
        Args:
            conversation_id: The conversation ID
            sender_id: ID of the sender
            sender_name: Display name of the sender
            content: Message content
            sites: Optional list of sites for this message
            mode: Optional mode (list, summarize, generate)
            metadata: Optional additional metadata
            
        Returns:
            Message with proper structure and metadata
        """
        import uuid
        
        # Build metadata
        msg_metadata = metadata.copy() if metadata else {}
        
        # Add sites if provided
        if sites:
            msg_metadata['sites'] = sites
            
        # Add mode/generate_mode if provided
        if mode:
            msg_metadata['generate_mode'] = mode
        
        logger.info(f"ConversationManager.create_message: sites={sites}, mode={mode}, metadata={msg_metadata}")
            
        return Message(
            message_id=f"msg_{uuid.uuid4().hex[:12]}",
            conversation_id=conversation_id,
            content=content,
            message_type="user",
            timestamp=int(time.time() * 1000),  # milliseconds
            sender_info={
                "id": sender_id,
                "name": sender_name
            },
            metadata=msg_metadata
        )