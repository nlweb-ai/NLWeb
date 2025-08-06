# WebSocket handler refactored for multiple conversations
async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """
    WebSocket endpoint for real-time chat.
    
    GET /chat/ws
    
    Single WebSocket connection per client that can handle multiple conversations.
    Messages include conversation_id to route to appropriate conversation.
    """
    print(f"\n{'='*80}")
    print(f"WEBSOCKET CONNECTION REQUEST")
    print(f"{'='*80}")
    
    # [Authentication code remains the same - lines 976-1065]
    
    # Create WebSocket response
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    
    # Create connection without conversation_id (will be set when joining conversations)
    connection = WebSocketConnection(
        websocket=ws,
        participant_id=user_id,
        conversation_id=None,  # Not tied to any conversation yet
        participant_name=user_name
    )
    
    # Track active conversations for this connection
    active_conversations = set()
    
    try:
        print(f"\n=== WEBSOCKET CONNECTION SETUP ===")
        
        # Send connection confirmation
        print(f"Sending connection confirmation to {user_id}")
        await ws.send_json({
            'type': 'connected',
            'participant_id': user_id
        })
        
        # Handle incoming messages
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                print(f"\n=== RAW WEBSOCKET MESSAGE ===")
                print(f"Raw data: {msg.data[:200]}")
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get('type')
                    print(f"Parsed type: {msg_type}")
                    
                    # Handle join conversation request
                    if msg_type == 'join':
                        conversation_id = data.get('conversation_id')
                        if not conversation_id:
                            await ws.send_json({'type': 'error', 'message': 'conversation_id required'})
                            continue
                            
                        print(f"User {user_id} joining conversation {conversation_id}")
                        
                        # Create participant instance
                        human = HumanParticipant(
                            user_id=user_id,
                            user_name=user_name
                        )
                        
                        # Add participant through conversation manager
                        conv_manager.add_participant(conversation_id, human)
                        
                        # Add to WebSocket manager
                        connection.conversation_id = conversation_id  # Update connection's conversation
                        await ws_manager.add_connection(conversation_id, connection)
                        active_conversations.add(conversation_id)
                        
                        # Add AI participant if not already present
                        conv_state = conv_manager._conversations.get(conversation_id)
                        has_ai_participant = False
                        if conv_state:
                            for participant in conv_state.participants.values():
                                if hasattr(participant, 'participant_type') and participant.participant_type == 'nlweb':
                                    has_ai_participant = True
                                    break
                        
                        if not has_ai_participant:
                            nlweb_handler = request.app.get('nlweb_handler')
                            if nlweb_handler:
                                config = ParticipantConfig(
                                    timeout=20,
                                    human_messages_context=5,
                                    nlweb_messages_context=1
                                )
                                nlweb = NLWebParticipant(nlweb_handler, config)
                                conv_manager.add_participant(conversation_id, nlweb)
                        
                        # Send participant list
                        await ws_manager._send_participant_list(conversation_id, connection)
                        
                        # Broadcast participant join
                        await ws_manager.broadcast_participant_update(
                            conversation_id=conversation_id,
                            action="join",
                            participant_id=user_id,
                            participant_name=user_name,
                            participant_type="human"
                        )
                        
                        # Send conversation history
                        recent_messages = await storage_client.get_conversation_messages(
                            conversation_id=conversation_id,
                            limit=50
                        )
                        
                        browser_messages = [msg.to_dict() for msg in recent_messages]
                        
                        await ws.send_json({
                            'type': 'conversation_history',
                            'conversation_id': conversation_id,
                            'messages': browser_messages
                        })
                        
                        continue
                    
                    # Handle leave conversation request
                    if msg_type == 'leave':
                        conversation_id = data.get('conversation_id')
                        if conversation_id in active_conversations:
                            conv_manager.remove_participant(conversation_id, user_id)
                            await ws_manager.remove_connection(conversation_id, user_id)
                            active_conversations.remove(conversation_id)
                            
                            await ws_manager.broadcast_participant_update(
                                conversation_id=conversation_id,
                                action="leave",
                                participant_id=user_id,
                                participant_name=user_name,
                                participant_type="human"
                            )
                        continue
                    
                    # Handle message
                    if msg_type == 'message':
                        conversation_id = data.get('conversation_id')
                        if not conversation_id:
                            await ws.send_json({'type': 'error', 'message': 'conversation_id required for messages'})
                            continue
                            
                        if conversation_id not in active_conversations:
                            await ws.send_json({'type': 'error', 'message': 'Must join conversation before sending messages'})
                            continue
                        
                        print(f"\n=== WEBSOCKET MESSAGE RECEIVED ===")
                        print(f"User ID: {user_id}")
                        print(f"Conversation ID: {conversation_id}")
                        print(f"Content: {data.get('content', '')[:100]}")
                        logger.info(f"WebSocket received message from {user_id} in {conversation_id}: {data.get('content', '')[:100]}")
                        
                        # Extract site and mode from the WebSocket message
                        site = data.get('site', 'all')
                        sites = [site] if isinstance(site, str) else site
                        mode = data.get('mode', 'list')
                        
                        logger.info(f"WebSocket extracted: site={site}, sites={sites}, mode={mode}")
                        
                        # Extract any additional metadata
                        additional_metadata = data.get('metadata', {})
                        
                        # Create chat message using the clean interface
                        message = ConversationManager.create_message(
                            conversation_id=conversation_id,
                            sender_id=user_id,
                            sender_name=user.get('name', 'User'),
                            content=data.get('content', ''),
                            sites=sites,
                            mode=mode,
                            metadata=additional_metadata
                        )
                        
                        logger.info(f"Processing message {message.message_id} through ConversationManager")
                        
                        # Process through conversation manager
                        try:
                            processed_msg = await conv_manager.process_message(message)
                            logger.info(f"Message processed successfully")
                            
                            # Send acknowledgment
                            await ws.send_json({
                                'type': 'message_ack',
                                'message_id': processed_msg.message_id
                            })
                            
                        except QueueFullError as e:
                            await ws.send_json({
                                'type': 'error',
                                'error': 'queue_full',
                                'message': 'Conversation queue is full. Please wait.',
                                'code': 429
                            })
                    
                    elif msg_type == 'ping':
                        await ws.send_json({'type': 'pong'})
                        
                except json.JSONDecodeError:
                    await ws.send_json({
                        'type': 'error',
                        'error': 'invalid_json',
                        'message': 'Invalid JSON format'
                    })
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await ws.send_json({
                        'type': 'error',
                        'error': 'processing_error',
                        'message': str(e)
                    })
                    
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f'WebSocket error: {ws.exception()}')
                
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}", exc_info=True)
        
    finally:
        # Clean up all active conversations on disconnect
        for conversation_id in active_conversations:
            try:
                conv_manager.remove_participant(conversation_id, user_id)
                await ws_manager.remove_connection(conversation_id, user_id)
                
                # Broadcast leave to remaining participants
                await ws_manager.broadcast_participant_update(
                    conversation_id=conversation_id,
                    action="leave",
                    participant_id=user_id,
                    participant_name=user_name,
                    participant_type="human"
                )
            except Exception as e:
                logger.error(f"Error cleaning up conversation {conversation_id}: {e}")
        
        print(f"WebSocket connection closed for {user_id}")
        
    return ws