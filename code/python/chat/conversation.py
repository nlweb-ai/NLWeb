"""
Conversation orchestration and management.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import time

from chat.schemas import (
    ChatMessage,
    MessageType,
    MessageStatus,
    ParticipantType,
    QueueFullError
)
from chat.participants import BaseParticipant
from chat.storage import ChatStorageInterface
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
        self.storage: Optional[ChatStorageInterface] = None
        self.metrics = ChatMetrics()
        
        # Broadcast callback for mode changes
        self.broadcast_callback: Optional[Callable] = None
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Running state
        self._running = True
    
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
        message: ChatMessage,
        require_ack: bool = False
    ) -> ChatMessage:
        """
        Process an incoming message.
        
        Args:
            message: The message to process
            require_ack: Whether to require delivery acknowledgments
            
        Returns:
            The message with assigned sequence ID and delivery status
            
        Raises:
            QueueFullError: If conversation queue is full
        """
        async with self._lock:
            # Check conversation exists
            if message.conversation_id not in self._conversations:
                raise ValueError(f"Unknown conversation: {message.conversation_id}")
            
            conv_state = self._conversations[message.conversation_id]
            
            # Check queue limit
            if conv_state.message_count >= self.queue_size_limit:
                # Try to drop oldest NLWeb jobs first
                if not self._try_drop_nlweb_jobs(conv_state):
                    raise QueueFullError(
                        conversation_id=message.conversation_id,
                        queue_size=conv_state.message_count,
                        limit=self.queue_size_limit
                    )
            
            # Assign sequence ID
            if self.storage:
                sequence_id = await self.storage.get_next_sequence_id(message.conversation_id)
                conv_state.message_count = sequence_id
            else:
                # For testing without storage
                conv_state.message_count += 1
                sequence_id = conv_state.message_count
            
            # Create message with sequence ID
            sequenced_message = ChatMessage(
                message_id=message.message_id,
                conversation_id=message.conversation_id,
                sequence_id=sequence_id,
                sender_id=message.sender_id,
                sender_name=message.sender_name,
                content=message.content,
                message_type=message.message_type,
                timestamp=message.timestamp,
                status=MessageStatus.PENDING,
                metadata=message.metadata
            )
            
            # Deliver to all participants immediately
            delivery_acks = await self._deliver_to_participants(
                sequenced_message,
                conv_state,
                require_ack
            )
            
            # Update message status
            final_metadata = sequenced_message.metadata.copy() if sequenced_message.metadata else {}
            if require_ack:
                final_metadata['delivery_acks'] = delivery_acks
                
            sequenced_message = ChatMessage(
                message_id=sequenced_message.message_id,
                conversation_id=sequenced_message.conversation_id,
                sequence_id=sequenced_message.sequence_id,
                sender_id=sequenced_message.sender_id,
                sender_name=sequenced_message.sender_name,
                content=sequenced_message.content,
                message_type=sequenced_message.message_type,
                timestamp=sequenced_message.timestamp,
                status=MessageStatus.DELIVERED,
                metadata=final_metadata
            )
            
            # Trigger async persistence
            if self.storage:
                asyncio.create_task(self._persist_message(sequenced_message))
            
            # Update conversation state
            conv_state.updated_at = datetime.utcnow()
            
            # Track metrics
            self.metrics.update_queue_depth(message.conversation_id, conv_state.message_count)
            
            # Broadcast to WebSocket connections
            if self.websocket_manager:
                await self.websocket_manager.broadcast_message(
                    message.conversation_id,
                    {
                        'type': 'message',
                        'message': sequenced_message.to_dict()
                    }
                )
            
            return sequenced_message
    
    async def _deliver_to_participants(
        self,
        message: ChatMessage,
        conv_state: ConversationState,
        require_ack: bool = False
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
            except Exception as e:
                logger.error(f"Failed to get context: {e}")
        
        # Deliver to all participants except sender
        for participant_id, participant in conv_state.participants.items():
            if participant_id != message.sender_id:
                # Create delivery task
                task = self._deliver_to_participant(
                    message,
                    participant,
                    participant_id,
                    context,
                    conv_state
                )
                delivery_tasks.append((participant_id, task))
        
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
        message: ChatMessage,
        participant: BaseParticipant,
        participant_id: str,
        context: List[ChatMessage],
        conv_state: ConversationState
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
            else:
                logger.info(f"ConversationManager calling human participant {participant_id} for message {message.message_id}")
            
            # Process message - pass websocket manager for streaming
            response = await participant.process_message(message, context, self.websocket_manager)
            
            # If participant generated a response, process it
            if response:
                # Process the response as a new message
                await self.process_message(response)
            
            # Remove from active jobs if AI
            if participant_info.participant_type == ParticipantType.AI:
                conv_state.active_nlweb_jobs.discard(f"{message.message_id}_{participant_id}")
                
        except Exception as e:
            logger.error(f"Failed to deliver to {participant_id}: {e}")
            # Remove from active jobs on failure too
            conv_state.active_nlweb_jobs.discard(f"{message.message_id}_{participant_id}")
            raise
    
    async def _persist_message(self, message: ChatMessage) -> None:
        """
        Persist message to storage (async after delivery).
        
        Args:
            message: The message to persist
        """
        try:
            await self.storage.store_message(message)
        except Exception as e:
            logger.error(f"Failed to persist message {message.message_id}: {e}")
    
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
                "timestamp": datetime.utcnow().isoformat()
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
        # Clean up any resources if needed