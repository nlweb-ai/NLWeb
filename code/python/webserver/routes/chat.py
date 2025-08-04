"""Chat API routes for multi-participant conversations"""

from aiohttp import web
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from chat.websocket import WebSocketManager, WebSocketConnection
from chat.conversation import ConversationManager
from chat.participants import HumanParticipant, NLWebParticipant, ParticipantConfig
from chat.storage import ChatStorageClient
from chat.schemas import (
    ChatMessage,
    Conversation,
    ParticipantInfo,
    ParticipantType,
    MessageType,
    QueueFullError
)

logger = logging.getLogger(__name__)


def setup_chat_routes(app: web.Application):
    """Setup chat API routes"""
    # Conversation management
    app.router.add_post('/chat/create', create_conversation_handler)
    app.router.add_get('/chat/my-conversations', list_conversations_handler)
    app.router.add_get('/chat/conversations/{id}', get_conversation_handler)
    app.router.add_post('/chat/{id}/join', join_conversation_handler)
    app.router.add_delete('/chat/{id}/leave', leave_conversation_handler)
    
    # Share link endpoints (using conversation ID as the share token)
    app.router.add_post('/chat/join/{conv_id}', join_via_share_link_handler)
    
    # WebSocket endpoint
    app.router.add_get('/chat/ws/{conv_id}', websocket_handler)
    
    # Health check
    app.router.add_get('/health/chat', chat_health_handler)


async def create_conversation_handler(request: web.Request) -> web.Response:
    """
    Create a new multi-participant conversation.
    
    POST /chat/create
    {
        "title": "Optional conversation title",
        "participants": [
            {"user_id": "alice_123", "name": "Alice"},
            {"user_id": "bob_456", "name": "Bob"}
        ],
        "enable_ai": true  // Whether to add NLWeb participant
    }
    
    Returns:
        201: {
            "conversation_id": "conv_uuid",
            "created_at": "2024-01-15T10:30:00Z",
            "participants": [...],
            "websocket_url": "/chat/ws/conv_uuid"
        }
        400: Bad request (invalid participants)
        401: Unauthorized (removed - now supports anonymous)
        429: Too many conversations
    """
    try:
        # Get authenticated user or create anonymous user
        user = request.get('user')
        logger.info(f"Create conversation - user from request: {user}")
        
        if not user or not user.get('authenticated'):
            # Create anonymous user
            import random
            anon_id = f"anon_{random.randint(1000, 9999)}"
            user = {
                'id': anon_id,
                'name': f'Anonymous {anon_id[-4:]}',
                'authenticated': False,
                'is_anonymous': True
            }
            logger.info(f"Created anonymous user: {user['id']}")
        
        # Parse request body
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {'error': 'Invalid JSON in request body'},
                status=400
            )
        
        # Get title or use default
        title = data.get('title', 'New Conversation')
        
        # Get participants or create default with current user
        participants = data.get('participants', [])
        if not participants:
            # Add current user as the only participant
            participants = [{
                'user_id': user.get('id'),
                'name': user.get('name', 'User')
            }]
        
        # Validate each participant has required fields
        for i, p in enumerate(participants):
            if not isinstance(p, dict):
                return web.json_response(
                    {'error': f'Participant {i} must be an object'},
                    status=400
                )
            if 'user_id' not in p:
                return web.json_response(
                    {'error': f'Participant {i} missing required field: user_id'},
                    status=400
                )
            if 'name' not in p:
                return web.json_response(
                    {'error': f'Participant {i} missing required field: name'},
                    status=400
                )
        
        # Always ensure requesting user is included as a participant
        requesting_user_id = user.get('id')
        requesting_user_name = user.get('name', 'User')
        
        # Remove any duplicate of the requesting user
        participants = [p for p in participants if p.get('user_id') != requesting_user_id]
        
        # Add requesting user as first participant
        participants.insert(0, {
            'user_id': requesting_user_id,
            'name': requesting_user_name
        })
        
        # Validate participant count
        if len(participants) > 10:  # Reasonable limit
            return web.json_response(
                {'error': 'Maximum 10 participants allowed'},
                status=400
            )
        
        # Create conversation
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        
        # Get managers from app
        conv_manager: ConversationManager = request.app['conversation_manager']
        storage_client: ChatStorageClient = request.app['chat_storage']
        
        # Create conversation in storage
        conversation = Conversation(
            conversation_id=conversation_id,
            created_at=datetime.utcnow(),
            active_participants=set(),
            queue_size_limit=1000,
            message_count=0,
            metadata={
                'title': title,
                'sites': data.get('sites', []),
                'mode': data.get('mode', 'list')
            }
        )
        
        # Add human participants
        for p in participants:
            participant_info = ParticipantInfo(
                participant_id=p['user_id'],
                name=p['name'],
                participant_type=ParticipantType.HUMAN,
                joined_at=datetime.utcnow()
            )
            conversation.add_participant(participant_info)
            
            # Create participant instance
            human = HumanParticipant(
                user_id=p['user_id'],
                user_name=p['name']
            )
            conv_manager.add_participant(conversation_id, human)
        
        # Add AI participant if enabled
        if data.get('enable_ai', True):
            # Get NLWeb handler from app
            nlweb_handler = request.app.get('nlweb_handler')
            logger.info(f"NLWeb handler available: {nlweb_handler is not None}")
            if nlweb_handler:
                config = ParticipantConfig(
                    timeout=20,
                    human_messages_context=5,
                    nlweb_messages_context=1
                )
                nlweb = NLWebParticipant(nlweb_handler, config)
                conv_manager.add_participant(conversation_id, nlweb)
                
                # Add to conversation
                ai_info = nlweb.get_participant_info()
                conversation.add_participant(ai_info)
                logger.info(f"Added NLWeb participant to conversation {conversation_id}")
            else:
                logger.warning("NLWeb handler not found in app - AI responses disabled")
        
        # Store conversation
        await storage_client.create_conversation(conversation)
        
        # Return response
        return web.json_response({
            'conversation_id': conversation_id,
            'title': title,
            'created_at': conversation.created_at.isoformat(),
            'participants': [
                {
                    'id': p.participant_id,
                    'name': p.name,
                    'type': p.participant_type.value
                }
                for p in conversation.active_participants
            ],
            'websocket_url': f"/chat/ws/{conversation_id}"
        }, status=201)
        
    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )


async def list_conversations_handler(request: web.Request) -> web.Response:
    """
    List conversations for the authenticated user.
    
    GET /chat/my-conversations?limit=20&offset=0
    
    Returns:
        200: {
            "conversations": [
                {
                    "conversation_id": "conv_abc123",
                    "title": "Team Discussion",
                    "created_at": "2024-01-15T10:30:00Z",
                    "last_message_at": "2024-01-15T11:45:00Z",
                    "participant_count": 3,
                    "unread_count": 5
                }
            ],
            "total": 42,
            "limit": 20,
            "offset": 0
        }
        401: Unauthorized
    """
    try:
        # Get authenticated user
        user = request.get('user')
        if not user or not user.get('authenticated'):
            return web.json_response(
                {'error': 'Authentication required'},
                status=401
            )
        
        # Get pagination parameters
        limit = min(int(request.query.get('limit', '20')), 100)
        offset = max(int(request.query.get('offset', '0')), 0)
        
        # Get storage client
        storage_client: ChatStorageClient = request.app['chat_storage']
        
        # Get user's conversations
        user_id = user.get('id')
        conversations = await storage_client.get_user_conversations(
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        # Format response
        formatted_conversations = []
        for conv in conversations:
            formatted_conversations.append({
                'conversation_id': conv.conversation_id,
                'title': conv.metadata.get('title', 'Untitled Chat') if conv.metadata else 'Untitled Chat',
                'created_at': conv.created_at.isoformat(),
                'last_message_at': conv.updated_at.isoformat() if hasattr(conv, 'updated_at') and conv.updated_at else None,
                'participant_count': len(conv.active_participants),
                'unread_count': 0  # TODO: Implement unread tracking
            })
        
        return web.json_response({
            'conversations': formatted_conversations,
            'total': len(formatted_conversations),  # TODO: Get actual total from storage
            'limit': limit,
            'offset': offset
        })
        
    except ValueError as e:
        return web.json_response(
            {'error': f'Invalid parameter: {str(e)}'},
            status=400
        )
    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )


async def get_conversation_handler(request: web.Request) -> web.Response:
    """
    Get specific conversation with messages.
    
    GET /chat/conversations/{id}
    
    Returns full conversation object with messages and participants.
    Only accessible to current participants.
    
    Returns:
        200: Full conversation object
        401: Unauthorized
        404: Conversation not found or user not a participant
    """
    try:
        # Extract conversation_id from URL
        conversation_id = request.match_info['id']
        
        # Get user info from auth
        user = request.get('user')
        if not user or not user.get('authenticated'):
            return web.json_response(
                {'error': 'Authentication required'},
                status=401
            )
        
        user_id = user.get('id')
        
        # Get managers from app
        storage_client: ChatStorageClient = request.app['chat_storage']
        ws_manager: WebSocketManager = request.app.get('websocket_manager')
        
        # Retrieve conversation from storage
        conversation = await storage_client.get_conversation(conversation_id)
        if not conversation:
            return web.json_response(
                {'error': 'Conversation not found'},
                status=404
            )
        
        
        # Verify user is a participant
        participant_ids = {p.participant_id for p in conversation.active_participants}
        if user_id not in participant_ids:
            return web.json_response(
                {'error': 'Conversation not found'},  # Don't reveal existence
                status=404
            )
        
        # Get recent messages (last 100)
        messages = await storage_client.get_conversation_messages(
            conversation_id=conversation_id,
            limit=100
        )
        
        # Get online status for participants
        online_participant_ids = set()
        if ws_manager and conversation_id in ws_manager._connections:
            online_participant_ids = {
                conn.participant_id 
                for conn in ws_manager._connections[conversation_id].values()
            }
        
        # Build participant list with online status
        participants = []
        for p in conversation.active_participants:
            # Debug: Check what type p is
            if isinstance(p, str):
                logger.error(f"Participant is string instead of ParticipantInfo: {p}")
                continue
            participants.append({
                'participantId': p.participant_id,
                'displayName': p.name,
                'type': p.participant_type.value,
                'joinedAt': p.joined_at.isoformat(),
                'isOnline': p.participant_id in online_participant_ids
            })
        
        # Build message list
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                'id': msg.message_id,
                'sequence_id': msg.sequence_id,
                'sender_id': msg.sender_id,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'type': msg.message_type.value,
                'status': msg.status.value
            })
        
        # Build response matching test expectations
        response_data = {
            'id': conversation.conversation_id,
            'title': conversation.metadata.get('title', 'Untitled Chat') if conversation.metadata else 'Untitled Chat',
            'sites': conversation.metadata.get('sites', []) if conversation.metadata else [],
            'mode': conversation.metadata.get('mode', 'list') if conversation.metadata else 'list',
            'participants': participants,
            'messages': formatted_messages,
            'created_at': conversation.created_at.isoformat(),
            'updated_at': conversation.updated_at.isoformat() if hasattr(conversation, 'updated_at') else conversation.created_at.isoformat()
        }
        
        # Add additional metadata if present
        if conversation.metadata:
            # Add any additional fields from metadata
            for key in ['status', 'ended_at']:
                if key in conversation.metadata:
                    response_data[key] = conversation.metadata[key]
        
        # Add summary statistics
        response_data['participant_count'] = len(conversation.active_participants)
        response_data['message_count'] = conversation.message_count
        response_data['unread_count'] = 0  # TODO: Implement unread tracking
        
        # Add last message preview if messages exist
        if formatted_messages:
            last_message = formatted_messages[-1]
            response_data['last_message_preview'] = last_message['content'][:100]
            response_data['last_message_at'] = last_message['timestamp']
        
        return web.json_response(response_data)
        
    except Exception as e:
        logger.error(f"Error getting conversation: {e}", exc_info=True)
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )


async def join_conversation_handler(request: web.Request) -> web.Response:
    """
    Join an existing conversation.
    
    POST /chat/{id}/join
    {
        "participant": {
            "participantId": "user456",
            "displayName": "New User",
            "email": "user@example.com"
        }
    }
    
    Returns:
        200: {
            "success": true,
            "conversation": { /* full conversation object */ }
        }
        401: Unauthorized
        404: Conversation not found
        409: Already a participant
        429: Participant limit reached
    """
    try:
        # Extract conversation_id from URL path
        conversation_id = request.match_info['id']
        
        # Get authenticated user
        user = request.get('user')
        if not user or not user.get('authenticated'):
            return web.json_response(
                {'error': 'Authentication required'},
                status=401
            )
        
        # Parse request body
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {'error': 'Invalid JSON in request body'},
                status=400
            )
        
        # Get participant info from request
        participant_data = data.get('participant', {})
        if not participant_data:
            return web.json_response(
                {'error': 'Participant information required'},
                status=400
            )
        
        # Get managers from app
        conv_manager: ConversationManager = request.app['conversation_manager']
        storage_client: ChatStorageClient = request.app['chat_storage']
        ws_manager: WebSocketManager = request.app['websocket_manager']
        
        # Verify conversation exists
        conversation = await storage_client.get_conversation(conversation_id)
        if not conversation:
            return web.json_response(
                {'error': 'Conversation not found'},
                status=404
            )
        
        # Validate participant data - support both old and new format
        participant_id = participant_data.get('user_id') or participant_data.get('participantId', user.get('id'))
        participant_name = participant_data.get('name') or participant_data.get('displayName', user.get('name', 'User'))
        
        if not participant_id:
            return web.json_response(
                {'error': 'Participant user_id is required'},
                status=400
            )
        
        # Check if user is already a participant
        existing_participant_ids = {p.participant_id for p in conversation.active_participants}
        
        if participant_id in existing_participant_ids:
            return web.json_response(
                {
                    'error': 'Already a participant in this conversation',
                    'code': 'ALREADY_MEMBER'
                },
                status=409
            )
        
        # Check participant limit
        if len(conversation.active_participants) >= conv_manager.max_participants:
            return web.json_response(
                {
                    'error': f'Conversation is at maximum capacity ({conv_manager.max_participants} participants)',
                    'code': 'CAPACITY_REACHED'
                },
                status=429
            )
        
        # Create participant info
        participant_info = ParticipantInfo(
            participant_id=participant_id,
            name=participant_name,
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        # Add to conversation object
        conversation.add_participant(participant_info)
        
        # Create HumanParticipant instance
        human = HumanParticipant(
            user_id=participant_id,
            user_name=participant_info.name
        )
        
        # Add participant through conversation manager
        conv_manager.add_participant(conversation_id, human)
        
        # Update conversation in storage
        await storage_client.update_conversation(conversation)
        
        # Broadcast participant update to all WebSocket connections
        participant_update = {
            'type': 'participant_joined',
            'conversation_id': conversation_id,
            'participant': {
                'id': participant_info.participant_id,
                'name': participant_info.name,
                'type': participant_info.participant_type.value,
                'joined_at': participant_info.joined_at.isoformat()
            },
            'participant_count': len(conversation.active_participants),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Broadcast to all connections in the conversation
        await ws_manager.broadcast_to_conversation(conversation_id, participant_update)
        
        # Get updated conversation with messages for response
        messages = await storage_client.get_conversation_messages(
            conversation_id=conversation_id,
            limit=50
        )
        
        # Return success with full conversation object
        return web.json_response({
            'success': True,
            'conversation': {
                'id': conversation.conversation_id,
                'title': conversation.metadata.get('title', 'Untitled Chat') if conversation.metadata else 'Untitled Chat',
                'sites': conversation.metadata.get('sites', []) if conversation.metadata else [],
                'mode': conversation.metadata.get('mode', 'list') if conversation.metadata else 'list',
                'participants': [
                    {
                        'participantId': p.participant_id,
                        'displayName': p.name,
                        'type': p.participant_type.value,
                        'joinedAt': p.joined_at.isoformat(),
                        'isOnline': p.participant_id in [c.participant_id 
                                                        for c in ws_manager._connections.get(conversation_id, {}).values()]
                    }
                    for p in conversation.active_participants
                ],
                'messages': [
                    {
                        'id': msg.message_id,
                        'sequence_id': msg.sequence_id,
                        'sender_id': msg.sender_id,
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat(),
                        'type': msg.message_type.value,
                        'status': msg.status.value
                    }
                    for msg in messages
                ],
                'created_at': conversation.created_at.isoformat(),
                'updated_at': conversation.updated_at.isoformat() if hasattr(conversation, 'updated_at') else None,
                'participant_count': len(conversation.active_participants),
                'message_count': conversation.message_count
            }
        })
        
    except ValueError as e:
        logger.error(f"Participant limit error: {e}")
        return web.json_response(
            {'error': str(e)},
            status=429
        )
    except Exception as e:
        logger.error(f"Error joining conversation: {e}", exc_info=True)
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )


async def leave_conversation_handler(request: web.Request) -> web.Response:
    """
    Leave a conversation.
    
    DELETE /chat/{id}/leave
    
    Returns:
        200: {
            "success": true,
            "message": "Successfully left conversation"
        }
        401: Unauthorized
        404: Not a participant or conversation not found
    """
    try:
        # Extract conversation_id from URL
        conversation_id = request.match_info['id']
        
        # Get authenticated user from auth context
        user = request.get('user')
        if not user or not user.get('authenticated'):
            return web.json_response(
                {'error': 'Authentication required'},
                status=401
            )
        
        # Get user ID
        user_id = user.get('id')
        
        # Get managers from app
        conv_manager: ConversationManager = request.app['conversation_manager']
        storage_client: ChatStorageClient = request.app['chat_storage']
        ws_manager: WebSocketManager = request.app['websocket_manager']
        
        # Verify conversation exists
        conversation = await storage_client.get_conversation(conversation_id)
        if not conversation:
            return web.json_response(
                {'error': 'Conversation not found'},
                status=404
            )
        
        # Verify user is a participant
        participant_ids = {p.participant_id for p in conversation.active_participants}
        if user_id not in participant_ids:
            return web.json_response(
                {
                    'error': 'You are not a participant in this conversation',
                    'code': 'NOT_PARTICIPANT'
                },
                status=404
            )
        
        # Get participant info before removal for broadcast
        leaving_participant = None
        for p in conversation.active_participants:
            if p.participant_id == user_id:
                leaving_participant = p
                break
        
        # Remove participant from conversation object
        conversation.active_participants = {
            p for p in conversation.active_participants 
            if p.participant_id != user_id
        }
        
        # Remove participant through conversation manager
        conv_manager.remove_participant(conversation_id, user_id)
        
        # Update conversation in storage
        await storage_client.update_conversation(conversation)
        
        # Close any WebSocket connections for this user/conversation
        if conversation_id in ws_manager._connections:
            connections_to_close = []
            for conn in ws_manager._connections[conversation_id].values():
                if conn.participant_id == user_id:
                    connections_to_close.append(conn)
            
            # Close connections
            for conn in connections_to_close:
                try:
                    await conn.websocket.close(code=1000, message=b'Left conversation')
                    await ws_manager.remove_connection(conversation_id, user_id)
                except Exception as e:
                    logger.warning(f"Error closing WebSocket for {user_id}: {e}")
        
        # Check if this was the last participant
        remaining_participants = len(conversation.active_participants)
        
        if remaining_participants > 0:
            # Broadcast participant_left update to remaining participants
            participant_update = {
                'type': 'participant_left',
                'conversation_id': conversation_id,
                'participant': {
                    'id': leaving_participant.participant_id,
                    'name': leaving_participant.name,
                    'type': leaving_participant.participant_type.value
                },
                'participant_count': remaining_participants,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Broadcast to all remaining connections
            await ws_manager.broadcast_to_conversation(conversation_id, participant_update)
        else:
            # Last participant left - consider marking conversation as inactive
            logger.info(f"Last participant left conversation {conversation_id}")
            # Optionally: Mark conversation as inactive in storage
            conversation.metadata = conversation.metadata or {}
            conversation.metadata['status'] = 'inactive'
            conversation.metadata['ended_at'] = datetime.utcnow().isoformat()
            await storage_client.update_conversation(conversation)
        
        # Return success response
        return web.json_response({
            'success': True,
            'message': 'Successfully left conversation',
            'conversation_id': conversation_id,
            'remaining_participants': remaining_participants
        })
        
    except Exception as e:
        logger.error(f"Error leaving conversation: {e}", exc_info=True)
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )


async def join_via_share_link_handler(request: web.Request) -> web.Response:
    """
    Join a conversation via share link.
    
    POST /chat/join/{conv_id}
    {
        "participant": {
            "user_id": "user123",
            "name": "John Doe"
        }
    }
    
    The conversation ID in the URL acts as the share token.
    Anyone with the link can join the conversation.
    
    Returns:
        200: Success with full conversation details
        401: Unauthorized (no auth token)
        404: Conversation not found
        409: Already a participant
    """
    try:
        # Get conversation ID from URL
        conversation_id = request.match_info['conv_id']
        
        # Get authenticated user
        user = request.get('user')
        if not user or not user.get('authenticated'):
            return web.json_response(
                {'error': 'Authentication required'},
                status=401
            )
        
        # Parse request body
        try:
            data = await request.json()
        except json.JSONDecodeError:
            data = {}  # Use defaults if no body provided
        
        # Get participant info
        participant_data = data.get('participant', {})
        user_id = participant_data.get('user_id', user.get('id'))
        user_name = participant_data.get('name', user.get('name', 'User'))
        
        # Get managers from app
        conv_manager: ConversationManager = request.app['conversation_manager']
        storage_client: ChatStorageClient = request.app['chat_storage']
        ws_manager: WebSocketManager = request.app['websocket_manager']
        
        # Verify conversation exists
        conversation = await storage_client.get_conversation(conversation_id)
        if not conversation:
            return web.json_response(
                {'error': 'Invalid share link - conversation not found'},
                status=404
            )
        
        # Check if already a participant
        existing_participant_ids = {p.participant_id for p in conversation.active_participants}
        if user_id in existing_participant_ids:
            # Already a member - return success with conversation details
            messages = await storage_client.get_conversation_messages(
                conversation_id=conversation_id,
                limit=50
            )
            
            return web.json_response({
                'success': True,
                'already_member': True,
                'conversation': {
                    'id': conversation.conversation_id,
                    'title': conversation.metadata.get('title', 'Untitled Chat') if conversation.metadata else 'Untitled Chat',
                    'participants': [
                        {
                            'participantId': p.participant_id,
                            'displayName': p.name,
                            'type': p.participant_type.value
                        }
                        for p in conversation.active_participants
                    ],
                    'message_count': conversation.message_count
                }
            })
        
        # Add new participant
        participant_info = ParticipantInfo(
            participant_id=user_id,
            name=user_name,
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        # Add to conversation
        conversation.add_participant(participant_info)
        
        # Create HumanParticipant instance
        human = HumanParticipant(
            user_id=user_id,
            user_name=user_name
        )
        
        # Add participant through conversation manager
        conv_manager.add_participant(conversation_id, human)
        
        # Update conversation in storage
        await storage_client.update_conversation(conversation)
        
        # Broadcast participant joined event
        participant_update = {
            'type': 'participant_joined',
            'conversation_id': conversation_id,
            'participant': {
                'id': participant_info.participant_id,
                'name': participant_info.name,
                'type': participant_info.participant_type.value,
                'joined_at': participant_info.joined_at.isoformat()
            },
            'participant_count': len(conversation.active_participants),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await ws_manager.broadcast_to_conversation(conversation_id, participant_update)
        
        # Get recent messages
        messages = await storage_client.get_conversation_messages(
            conversation_id=conversation_id,
            limit=50
        )
        
        # Return success with conversation details
        return web.json_response({
            'success': True,
            'conversation': {
                'id': conversation.conversation_id,
                'title': conversation.metadata.get('title', 'Untitled Chat') if conversation.metadata else 'Untitled Chat',
                'sites': conversation.metadata.get('sites', []) if conversation.metadata else [],
                'mode': conversation.metadata.get('mode', 'list') if conversation.metadata else 'list',
                'participants': [
                    {
                        'participantId': p.participant_id,
                        'displayName': p.name,
                        'type': p.participant_type.value,
                        'joinedAt': p.joined_at.isoformat()
                    }
                    for p in conversation.active_participants
                ],
                'messages': [
                    {
                        'id': msg.message_id,
                        'sender_id': msg.sender_id,
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat(),
                        'type': msg.message_type.value
                    }
                    for msg in messages
                ],
                'created_at': conversation.created_at.isoformat(),
                'participant_count': len(conversation.active_participants),
                'message_count': conversation.message_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error joining via share link: {e}", exc_info=True)
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """
    WebSocket endpoint for real-time chat.
    
    GET /chat/ws/{conv_id}
    
    Each human participant gets their own WebSocket connection.
    Messages are routed to all participants in the conversation.
    """
    conversation_id = request.match_info['conv_id']
    
    # Get authenticated user or create anonymous user
    user = request.get('user')
    if not user or not user.get('authenticated'):
        # Create anonymous user
        import random
        anon_id = f"anon_{random.randint(1000, 9999)}"
        user = {
            'id': anon_id,
            'name': f'Anonymous {anon_id[-4:]}',
            'authenticated': False,
            'is_anonymous': True
        }
    
    user_id = user.get('id')
    user_name = user.get('name', 'User')
    
    # Get managers
    ws_manager: WebSocketManager = request.app['websocket_manager']
    conv_manager: ConversationManager = request.app['conversation_manager']
    storage_client: ChatStorageClient = request.app['chat_storage']
    
    # Verify conversation exists
    conversation = await storage_client.get_conversation(conversation_id)
    if not conversation:
        return web.Response(text='Conversation not found', status=404)
    
    # Verify user is a participant or add them if they're not
    participant_ids = {p.participant_id for p in conversation.active_participants}
    if user_id not in participant_ids:
        # Add user as participant if not already one
        logger.info(f"Adding user {user_id} to conversation {conversation_id}")
        
        # Create participant info
        participant_info = ParticipantInfo(
            participant_id=user_id,
            name=user_name,
            participant_type=ParticipantType.HUMAN,
            joined_at=datetime.utcnow()
        )
        
        # Add to conversation
        conversation.add_participant(participant_info)
        
        # Create participant instance
        human = HumanParticipant(
            user_id=user_id,
            user_name=user_name
        )
        
        # Add participant through conversation manager
        conv_manager.add_participant(conversation_id, human)
        
        # Update conversation in storage
        await storage_client.update_conversation(conversation)
        
        # Check if AI participant exists, if not add it
        ai_participant_exists = any(
            p.participant_type != ParticipantType.HUMAN 
            for p in conversation.active_participants
        )
        
        if not ai_participant_exists:
            logger.info(f"No AI participant found in conversation {conversation_id}, adding NLWeb participant")
            nlweb_handler = request.app.get('nlweb_handler')
            if nlweb_handler:
                config = ParticipantConfig(
                    timeout=20,
                    human_messages_context=5,
                    nlweb_messages_context=1
                )
                nlweb = NLWebParticipant(nlweb_handler, config)
                conv_manager.add_participant(conversation_id, nlweb)
                
                # Add to conversation
                ai_info = nlweb.get_participant_info()
                conversation.add_participant(ai_info)
                await storage_client.update_conversation(conversation)
                logger.info(f"Added NLWeb participant to existing conversation {conversation_id}")
            else:
                logger.warning("NLWeb handler not available - AI responses will not work")
    
    # Create WebSocket response
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    
    # Create connection with participant name
    connection = WebSocketConnection(
        websocket=ws,
        participant_id=user_id,
        conversation_id=conversation_id,
        participant_name=user_name
    )
    
    try:
        # Add connection to manager (this just stores the connection now)
        await ws_manager.add_connection(conversation_id, connection)
        
        # Send connection confirmation FIRST (proper WebSocket handshake)
        await ws.send_json({
            'type': 'connected',
            'conversation_id': conversation_id,
            'participant_id': user_id,
            'mode': conv_manager.get_conversation_mode(conversation_id).value,
            'input_timeout': conv_manager.get_input_timeout(conversation_id)
        })
        
        # Send current participant list
        await ws_manager._send_participant_list(conversation_id, connection)
        
        # Broadcast participant join to other users
        await ws_manager.broadcast_participant_update(
            conversation_id=conversation_id,
            action="join",
            participant_id=user_id,
            participant_name=user_name,
            participant_type="human"
        )
        
        # Send recent message history
        recent_messages = await storage_client.get_conversation_messages(
            conversation_id=conversation_id,
            limit=50
        )
        
        for msg in reversed(recent_messages):  # Send in chronological order
            await ws.send_json({
                'type': 'message',
                'message': msg.to_dict()
            })
        
        # Handle incoming messages
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    
                    if data.get('type') == 'message':
                        logger.info(f"WebSocket received message from {user_id}: {data.get('content', '')[:100]}")
                        
                        # Extract metadata from the WebSocket message
                        metadata = {}
                        if 'sites' in data:
                            metadata['sites'] = data['sites']
                        if 'mode' in data:
                            metadata['generate_mode'] = data['mode']
                        if 'metadata' in data:
                            # Merge any additional metadata
                            metadata.update(data['metadata'])
                        
                        print(f"=== WebSocket creating ChatMessage ===")
                        print(f"Extracted metadata: {metadata}")
                        
                        # Create chat message
                        message = ChatMessage(
                            message_id=f"msg_{uuid.uuid4().hex[:12]}",
                            conversation_id=conversation_id,
                            sequence_id=0,  # Will be assigned
                            sender_id=user_id,
                            sender_name=user.get('name', 'User'),
                            content=data.get('content', ''),
                            message_type=MessageType.TEXT,
                            timestamp=datetime.utcnow(),
                            metadata=metadata
                        )
                        
                        logger.info(f"Processing message {message.message_id} through ConversationManager")
                        
                        # Process through conversation manager
                        try:
                            processed_msg = await conv_manager.process_message(message)
                            logger.info(f"Message processed successfully, got response with sequence_id: {processed_msg.sequence_id}")
                            
                            # Send acknowledgment
                            await ws.send_json({
                                'type': 'message_ack',
                                'message_id': processed_msg.message_id,
                                'sequence_id': processed_msg.sequence_id
                            })
                            
                        except QueueFullError as e:
                            await ws.send_json({
                                'type': 'error',
                                'error': 'queue_full',
                                'message': 'Conversation queue is full. Please wait.',
                                'code': 429
                            })
                    
                    elif data.get('type') == 'ping':
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
        # Remove connection
        await ws_manager.remove_connection(conversation_id, user_id)
        await ws.close()
    
    return ws


async def chat_health_handler(request: web.Request) -> web.Response:
    """
    Health check for chat system.
    
    GET /health/chat
    
    Returns comprehensive health status of the chat system.
    """
    try:
        # Get managers
        ws_manager: WebSocketManager = request.app.get('websocket_manager')
        conv_manager: ConversationManager = request.app.get('conversation_manager')
        storage_client: ChatStorageClient = request.app.get('chat_storage')
        
        # Collect health data
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'connections': 0,
            'conversations': 0,
            'participants_by_conversation': {},
            'queue_depths': {},
            'storage': 'disconnected'
        }
        
        # Check WebSocket connections
        if ws_manager:
            total_connections = 0
            for conv_id, connections in ws_manager._connections.items():
                total_connections += len(connections)
                health_data['participants_by_conversation'][conv_id] = {
                    'humans': len(connections),
                    'ai_agents': 0  # Will be updated from conv_manager
                }
            health_data['connections'] = total_connections
        
        # Check conversation manager
        if conv_manager:
            health_data['conversations'] = len(conv_manager._conversations)
            
            for conv_id, conv_state in conv_manager._conversations.items():
                # Count participant types
                human_count = 0
                ai_count = 0
                
                for participant in conv_state.participants.values():
                    info = participant.get_participant_info()
                    if info.participant_type == ParticipantType.HUMAN:
                        human_count += 1
                    else:
                        ai_count += 1
                
                # Update or create entry
                if conv_id in health_data['participants_by_conversation']:
                    health_data['participants_by_conversation'][conv_id]['ai_agents'] = ai_count
                else:
                    health_data['participants_by_conversation'][conv_id] = {
                        'humans': human_count,
                        'ai_agents': ai_count
                    }
                
                # Queue depth
                health_data['queue_depths'][conv_id] = conv_state.message_count
        
        # Check storage
        if storage_client:
            try:
                # Simple connectivity check
                await storage_client.get_conversation_messages('test_conv', limit=1)
                health_data['storage'] = 'connected'
            except Exception:
                health_data['storage'] = 'error'
        
        # Determine overall health
        if health_data['storage'] != 'connected':
            health_data['status'] = 'degraded'
        
        return web.json_response(health_data)
        
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return web.json_response({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }, status=500)