"""
In-memory storage implementation for chat system.
Used for development and testing.
"""

from typing import Dict, List, Optional
import asyncio
import json
from pathlib import Path

from chat.schemas import ChatMessage
from chat.storage import SimpleChatStorageInterface


class MemoryStorage(SimpleChatStorageInterface):
    """
    Simple in-memory implementation of chat storage.
    Stores messages in a list and persists to JSONL file.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize memory storage.
        
        Args:
            config: Storage configuration
        """
        print(f"\n=== MEMORY STORAGE INIT ===")
        print(f"Config: {config}")
        self.config = config
        # Note: queue_size_limit not used in simple storage
        
        # Storage configuration
        self.enable_storage = config.get('enable_storage', True)  # Default to True - storage enabled for upload endpoint
        self.persist_to_disk = config.get('persist_to_disk', True)
        self.storage_path = Path(config.get('storage_path', 'data/chat_storage'))
        
        # Storage structures
        self._messages: List[ChatMessage] = []
        
        # Load existing data from disk if available
        if self.persist_to_disk:
            # Create storage directory if it doesn't exist
            print(f"Creating storage directory: {self.storage_path}")
            self.storage_path.mkdir(parents=True, exist_ok=True)
            print(f"Storage directory exists: {self.storage_path.exists()}")
            # Load data synchronously during init
            asyncio.create_task(self._load_from_disk())
    
    async def store_message(self, message: ChatMessage) -> None:
        """
        Store a message - simply append to list and file.
        
        Args:
            message: The message to store
        """
        print(f"[STORAGE] Storage called for message {message.message_id}, enabled={self.enable_storage}")
        
        if not self.enable_storage:
            return  # Skip storage if disabled
        
        # Append message
        self._messages.append(message)
        
        # Append to disk immediately
        if self.persist_to_disk:
            await self._append_message_to_disk(message)
    
    async def get_conversation_messages(
        self, 
        conversation_id: str, 
        limit: int = 100,
        after_sequence_id: Optional[int] = None
    ) -> List[ChatMessage]:
        """
        Get messages for a conversation - filter from the list.
        
        Args:
            conversation_id: The conversation ID
            limit: Maximum number of messages to return
            after_sequence_id: Ignored in simple implementation
            
        Returns:
            List of messages in order they were added
        """
        # Filter messages for this conversation
        conv_messages = [m for m in self._messages if m.conversation_id == conversation_id]
        
        # Apply limit (return most recent messages)
        if len(conv_messages) > limit:
            conv_messages = conv_messages[-limit:]
        
        return conv_messages
    
    async def clear_all(self) -> None:
        """
        Clear all data from memory storage.
        Used for test cleanup.
        """
        self._messages.clear()
        
        # Clear persisted data
        if self.persist_to_disk:
            msg_file = self.storage_path / 'messages.jsonl'
            if msg_file.exists():
                # Clear the file by opening in write mode
                with open(msg_file, 'w') as f:
                    pass  # Empty file
    
    async def _append_message_to_disk(self, message: ChatMessage) -> None:
        """Append message to messages.jsonl file"""
        try:
            msg_file = self.storage_path / 'messages.jsonl'
            
            # Write the message as-is using to_dict()
            with open(msg_file, 'a') as f:
                f.write(json.dumps(message.to_dict()) + '\n')
                
        except Exception as e:
            print(f"ERROR appending message to disk: {e}")
    
    async def _load_from_disk(self) -> None:
        """Load persisted state from disk"""
        if not self.persist_to_disk:
            return
            
        print(f"\n=== LOADING FROM DISK ===")
        print(f"Storage path: {self.storage_path}")
        
        try:
            # Load messages from JSONL file
            msg_file = self.storage_path / 'messages.jsonl'
            if msg_file.exists():
                self._messages = []
                with open(msg_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:  # Skip empty lines
                            msg_data = json.loads(line)
                            message = ChatMessage.from_dict(msg_data)
                            self._messages.append(message)
                
                print(f"Loaded {len(self._messages)} messages")
            
            print("Load complete")
            
        except Exception as e:
            print(f"ERROR loading from disk: {e}")
            # Don't fail if loading fails, just start fresh