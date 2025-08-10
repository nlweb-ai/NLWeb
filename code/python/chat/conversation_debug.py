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
        print(f"[ConvMgr] ===== ENTERING process_message =====")
        print(f"[ConvMgr] Message ID: {message.message_id}")
        print(f"[ConvMgr] Sender: {message.sender_name} (ID: {message.sender_id})")
        print(f"[ConvMgr] Type: {message.message_type}")
        print(f"[ConvMgr] Conversation: {message.conversation_id}")
        print(f"[ConvMgr] Known conversations: {list(self._conversations.keys())}")
        
        try:
            print(f"[ConvMgr] Step 1: Acquiring lock...")
            async with self._lock:
                print(f"[ConvMgr] Step 2: Lock acquired")
                # Check conversation exists
                print(f"[ConvMgr] Step 3: Checking if conversation exists...")
                if message.conversation_id not in self._conversations:
                    print(f"[ConvMgr] ERROR: Unknown conversation: {message.conversation_id}")
                    print(f"[ConvMgr] Known conversations: {list(self._conversations.keys())}")
                    raise ValueError(f"Unknown conversation: {message.conversation_id}")
                
                print(f"[ConvMgr] Step 4: Conversation found!")
                conv_state = self._conversations[message.conversation_id]
                print(f"[ConvMgr] Step 5: Got conversation state with {conv_state.message_count} messages")
                logger.info(f"Processing message for conversation {message.conversation_id} with {conv_state.message_count} existing messages")
                
                # Check queue limit
                print(f"[ConvMgr] Step 6: Checking queue limit ({conv_state.message_count} vs {self.queue_size_limit})...")
                if conv_state.message_count >= self.queue_size_limit:
                    print(f"[ConvMgr] Step 6a: Queue full, trying to drop NLWeb jobs...")
                    # Try to drop oldest NLWeb jobs first
                    if not self._try_drop_nlweb_jobs(conv_state):
                        print(f"[ConvMgr] Step 6b: Could not drop jobs, raising QueueFullError")
                        raise QueueFullError(
                            conversation_id=message.conversation_id,
                            queue_size=conv_state.message_count,
                            limit=self.queue_size_limit
                        )
            
                # Assign sequence ID
                print(f"[ConvMgr] Step 7: Assigning sequence ID...")
                if self.storage:
                    print(f"[ConvMgr] Step 7a: Getting sequence ID from storage")
                    sequence_id = await self.storage.get_next_sequence_id(message.conversation_id)
                    conv_state.message_count = sequence_id
                    print(f"[ConvMgr] Step 7b: Got sequence ID: {sequence_id}")
                else:
                    # For testing without storage
                    print(f"[ConvMgr] Step 7c: No storage, using in-memory counter")
                    conv_state.message_count += 1
                    sequence_id = conv_state.message_count
                    print(f"[ConvMgr] Step 7d: In-memory sequence ID: {sequence_id}")
            
                # Create message with sequence ID
                print(f"[ConvMgr] Step 8: Creating sequenced message...")
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
                print(f"[ConvMgr] Step 9: Sequenced message created with seq_id={sequence_id}")
            
                # Deliver to all participants immediately
                print(f"[ConvMgr] Step 10: Delivering to participants...")
                delivery_acks = await self._deliver_to_participants(
                    sequenced_message,
                    conv_state,
                    require_ack
                )
                print(f"[ConvMgr] Step 11: Delivery complete, got {len(delivery_acks)} acks")
            
                # Update message status
                print(f"[ConvMgr] Step 12: Updating message status...")
                final_metadata = sequenced_message.metadata.copy() if sequenced_message.metadata else {}
                if require_ack:
                    print(f"[ConvMgr] Step 12a: Adding delivery acks to metadata")
                    final_metadata['delivery_acks'] = delivery_acks
                    
                print(f"[ConvMgr] Step 13: Creating final message with DELIVERED status...")
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
                print(f"[ConvMgr] Step 14: Final message created")
            
                # Trigger async persistence
                print(f"[ConvMgr] Step 15: Checking storage backend...")
                if self.storage:
                    print(f"[ConvMgr] Step 15a: Storage available, creating async persist task")
                    asyncio.create_task(self._persist_message(sequenced_message))
                    print(f"[ConvMgr] Step 15b: Async persist task created")
                else:
                    print(f"[ConvMgr] Step 15c: WARNING: No storage backend available!")
            
                # Update conversation state
                print(f"[ConvMgr] Step 16: Updating conversation state...")
                conv_state.updated_at = datetime.utcnow()
                print(f"[ConvMgr] Step 17: Conversation state updated")
            
                # Track metrics
                print(f"[ConvMgr] Step 18: Tracking metrics...")
                self.metrics.update_queue_depth(message.conversation_id, conv_state.message_count)
                print(f"[ConvMgr] Step 19: Metrics tracked")
            
                # Broadcast to WebSocket connections (exclude sender to avoid echo)
                print(f"[ConvMgr] Step 20: Checking WebSocket manager...")
                if self.websocket_manager:
                    print(f"[ConvMgr] Step 20a: Broadcasting to WebSocket connections...")
                    await self.websocket_manager.broadcast_message(
                        message.conversation_id,
                        sequenced_message.to_dict(),  # Send message directly, no wrapping
                        exclude_user_id=message.sender_id  # Exclude the sender
                    )
                    print(f"[ConvMgr] Step 20b: WebSocket broadcast complete")
                else:
                    print(f"[ConvMgr] Step 20c: No WebSocket manager available")
                
                print(f"[ConvMgr] Step 21: Returning sequenced message")
                return sequenced_message
        except Exception as e:
            print(f"[ConvMgr] ERROR in process_message: {e}")
            print(f"[ConvMgr] Exception type: {type(e)}")
            import traceback
            print(f"[ConvMgr] Traceback: {traceback.format_exc()}")
            raise