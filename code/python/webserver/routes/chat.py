"""Chat API routes for multi-participant conversations"""

from aiohttp import web
import asyncio
import logging
import json
import uuid
import time
import random
import base64
import traceback
import aiofiles
import os
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
from core.retriever import get_vector_db_client

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
    app.router.add_get('/chat/join/{conv_id}', join_via_share_link_get_handler)
    
    # WebSocket endpoint - general connection, not tied to specific conversation
    app.router.add_get('/chat/ws', websocket_handler)
    
    # Health check
    app.router.add_get('/health/chat', chat_health_handler)
    
    # Upload endpoint for bulk message storage
    app.router.add_post('/chat/upload', upload_conversation_handler)


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
        # Parse request body first
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {'error': 'Invalid JSON in request body'},
                status=400
            )
        
        # Get authenticated user or create anonymous user
        user = request.get('user')
        logger.info(f"Create conversation - user from request: {user}")
        
        if not user or not user.get('authenticated'):
            # Check if anonymous user ID was provided in request
            anon_id = data.get('anonymous_user_id')
            if not anon_id:
                # Create anonymous user if not provided
                anon_id = f"anon_{random.randint(1000, 9999)}"
            
            user = {
                'id': anon_id,
                'name': f'Anonymous {anon_id[-4:]}',
                'authenticated': False,
                'is_anonymous': True
            }
            logger.info(f"Using anonymous user: {user['id']}")
        
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
                nlweb = NLWebParticipant(nlweb_handler, config, storage_client)
                conv_manager.add_participant(conversation_id, nlweb)
                
                # Add to conversation
                ai_info = nlweb.get_participant_info()
                conversation.add_participant(ai_info)
                logger.info(f"Added NLWeb participant to conversation {conversation_id}")
            else:
                logger.warning("NLWeb handler not found in app - AI responses disabled")
        
        # Store conversation - not needed with simple storage
        # await storage_client.create_conversation(conversation)
        
        # Return response
        return web.json_response({
            'conversation_id': conversation_id,
            'title': title,
            'created_at': conversation.created_at,  # Already in milliseconds
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
                'created_at': conv.created_at,  # Already in milliseconds
                'last_message_at': conv.updated_at if hasattr(conv, 'updated_at') and conv.updated_at else None,
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
                'joinedAt': p.joined_at,  # Already in milliseconds
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
                'timestamp': msg.timestamp,  # Already in milliseconds
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
            'created_at': conversation.created_at,  # Already in milliseconds
            'updated_at': conversation.updated_at if hasattr(conversation, 'updated_at') else conversation.created_at
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
                'joined_at': participant_info.joined_at  # Already in milliseconds
            },
            'participant_count': len(conversation.active_participants),
            'timestamp': int(time.time() * 1000)
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
                        'joinedAt': p.joined_at,  # Already in milliseconds
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
                        'timestamp': msg.timestamp,  # Already in milliseconds
                        'type': msg.message_type.value,
                        'status': msg.status.value
                    }
                    for msg in messages
                ],
                'created_at': conversation.created_at,  # Already in milliseconds
                'updated_at': conversation.updated_at if hasattr(conversation, 'updated_at') else None,
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
                'timestamp': int(time.time() * 1000)
            }
            
            # Broadcast to all remaining connections
            await ws_manager.broadcast_to_conversation(conversation_id, participant_update)
        else:
            # Last participant left - consider marking conversation as inactive
            logger.info(f"Last participant left conversation {conversation_id}")
            # Optionally: Mark conversation as inactive in storage
            conversation.metadata = conversation.metadata or {}
            conversation.metadata['status'] = 'inactive'
            conversation.metadata['ended_at'] = int(time.time() * 1000)  # Milliseconds
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
                'joined_at': participant_info.joined_at  # Already in milliseconds
            },
            'participant_count': len(conversation.active_participants),
            'timestamp': int(time.time() * 1000)
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
                        'joinedAt': p.joined_at  # Already in milliseconds
                    }
                    for p in conversation.active_participants
                ],
                'messages': [
                    {
                        'id': msg.message_id,
                        'sender_id': msg.sender_id,
                        'content': msg.content,
                        'timestamp': msg.timestamp,  # Already in milliseconds
                        'type': msg.message_type.value
                    }
                    for msg in messages
                ],
                'created_at': conversation.created_at,  # Already in milliseconds
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


async def join_via_share_link_get_handler(request: web.Request) -> web.Response:
    """
    Handle GET request to join link - redirect to chat interface.
    
    GET /chat/join/{conv_id}
    
    This handler redirects to the chat interface with the conversation ID
    so the user can join through the UI.
    """
    conv_id = request.match_info['conv_id']
    
    # Redirect to the chat interface with the conversation ID as a parameter
    # The frontend will handle the actual join process
    redirect_url = f"/static/multi-chat-index.html?join={conv_id}"
    
    return web.HTTPFound(location=redirect_url)


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
    
    # Get authenticated user or create anonymous user
    user = request.get('user')
    
    # For WebSocket, also check auth_token in query params
    if not user or not user.get('authenticated'):
        auth_token = request.query.get('auth_token')
        if auth_token:
            # Validate the auth token using same logic as auth middleware
            try:
                # First try email-based base64 token
                try:
                    decoded = base64.b64decode(auth_token).decode('utf-8')
                    token_data = json.loads(decoded)
                    if 'user_id' in token_data:
                        # Email-based auth token
                        user = {
                            'id': token_data['user_id'],
                            'email': token_data.get('email', token_data['user_id']),
                            'name': token_data.get('email', '').split('@')[0],
                            'provider': 'email',
                            'authenticated': True
                        }
                except:
                    # Not a simple base64 token, try JWT format
                    parts = auth_token.split('.')
                    if len(parts) == 3:
                        # JWT format - decode payload
                        payload = parts[1]
                        # Add padding if needed
                        payload += '=' * (4 - len(payload) % 4)
                        decoded = base64.urlsafe_b64decode(payload)
                        claims = json.loads(decoded)
                        
                        user = {
                            'id': claims.get('sub', claims.get('user_id', 'user')),
                            'email': claims.get('email'),
                            'name': claims.get('name', claims.get('email', 'User')),
                            'provider': claims.get('provider', 'oauth'),
                            'authenticated': True
                        }
                        logger.info(f"Decoded JWT token for WebSocket user: {user['id']}")
                    else:
                        # Not JWT either, could be an OAuth access token
                        # Check if user info was passed in query params
                        user_id = request.query.get('user_id')
                        user_name = request.query.get('user_name')
                        provider = request.query.get('provider')
                        
                        if user_id:
                            user = {
                                'id': user_id,
                                'name': user_name or 'User',
                                'provider': provider or 'oauth',
                                'authenticated': True,
                                'token': auth_token
                            }
                            logger.info(f"Using user info from query params for WebSocket: {user['id']}")
                        else:
                            logger.warning(f"Unknown token format with {len(parts)} parts and no user info in query")
            except Exception as e:
                logger.warning(f"Failed to validate auth token: {e}")
    
    if not user or not user.get('authenticated'):
        # Check if anonymous user ID was provided in query params
        anon_id = request.query.get('anon_user_id')
        if not anon_id:
            # Create new anonymous user ID if not provided
            anon_id = f"anon_{random.randint(1000, 9999)}"
        
        user = {
            'id': anon_id,
            'name': f'Anonymous {anon_id[-4:]}',
            'authenticated': False,
            'is_anonymous': True
        }
    
    user_id = user.get('id')
    user_name = user.get('name', 'User')
    print(f"User: {user_name} (ID: {user_id})")
    print(f"User authenticated: {user.get('authenticated', False)}")
    
    # Get managers
    ws_manager: WebSocketManager = request.app['websocket_manager']
    conv_manager: ConversationManager = request.app['conversation_manager']
    storage_client: ChatStorageClient = request.app['chat_storage']
    
    # Create a general WebSocket connection not tied to any conversation
    print(f"Accepting WebSocket connection for user: {user_id}")
    
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
    # Track the actual user ID (may be updated from message data)
    actual_user_id = user_id
    
    try:
        
        # Send connection confirmation
        print(f"Sending connection confirmation to {user_id}")
        await ws.send_json({
            'type': 'connected',
            'participant_id': user_id
        })
        
        # Handle incoming messages
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                print(f"Raw data: {msg.data[:200]}")
                try:
                    data = json.loads(msg.data)
                    print(f"Parsed type: {data.get('type')}")
                    
                    msg_type = data.get('type')
                    
                    # Handle join conversation request
                    if msg_type == 'join':
                        conversation_id = data.get('conversation_id')
                        if not conversation_id:
                            await ws.send_json({'type': 'error', 'message': 'conversation_id required'})
                            continue
                        
                        # Get user details from join message if provided, otherwise use connection details
                        join_user_id = data.get('user_id', user_id)
                        join_user_name = data.get('user_name', user_name)
                        join_user_info = data.get('user_info', {})
                        
                        print(f"User {join_user_id} (name: {join_user_name}) joining conversation {conversation_id}")
                        
                        # Update the connection's participant_id to match the actual user
                        connection.participant_id = join_user_id
                        connection.participant_name = join_user_name
                        
                        # Create participant instance with join details
                        human = HumanParticipant(
                            user_id=join_user_id,
                            user_name=join_user_name
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
                                if isinstance(participant, NLWebParticipant):
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
                                nlweb = NLWebParticipant(nlweb_handler, config, storage_client)
                                conv_manager.add_participant(conversation_id, nlweb)
                        
                        # Send participant list
                        await ws_manager._send_participant_list(conversation_id, connection)
                        
                        # Broadcast participant join with user details to all except the joining user
                        await ws_manager.broadcast_participant_update(
                            conversation_id=conversation_id,
                            action="join",
                            participant_id=join_user_id,
                            participant_name=join_user_name,
                            participant_type="human",
                            exclude_participant=join_user_id  # Don't send to the user who just joined
                        )
                        
                        # Send conversation history by replaying individual events
                        recent_messages = await storage_client.get_conversation_messages(
                            conversation_id=conversation_id,
                            limit=50
                        )
                        
                        # Sort messages by timestamp to ensure correct order
                        recent_messages.sort(key=lambda m: m.timestamp)
                        
                        # Replay conversation history for joining user
                        
                        # Replay each message as individual events in timestamp order
                        for i, msg in enumerate(recent_messages):
                            print(f"\nMessage {i+1}:")
                            print(f"  Type: {msg.message_type}")
                            # Handle content as either string or object
                            if isinstance(msg.content, str):
                                print(f"  Content: {msg.content[:200] if msg.content else 'None'}...")
                            else:
                                print(f"  Content: {str(msg.content)[:200]}...")
                            print(f"  SenderInfo: {msg.senderInfo}")
                            print(f"  Timestamp: {msg.timestamp}")
                            
                            # Construct the message properly based on type
                            if isinstance(msg.content, dict) and 'message_type' in msg.content:
                                # This is an NLWeb message where the entire message was stored as content
                                # Send the content directly as it's the complete original message
                                await ws.send_json(msg.content)
                            else:
                                # This is a regular message - send the full message dict
                                await ws.send_json(msg.to_dict())
                        
                        
                        # Send end-conversation-history message to mark the end of replayed messages
                        end_history_msg = {
                            'type': 'end-conversation-history',
                            'conversation_id': conversation_id,
                            'message_count': len(recent_messages),
                            'timestamp': int(time.time() * 1000)
                        }
                        await ws.send_json(end_history_msg)
                        
                        continue
                    
                    # Handle leave conversation request
                    if msg_type == 'leave':
                        conversation_id = data.get('conversation_id')
                        if conversation_id in active_conversations:
                            # Use the actual user ID that was registered with the connection
                            conv_manager.remove_participant(conversation_id, connection.participant_id)
                            await ws_manager.remove_connection(conversation_id, connection.participant_id)
                            active_conversations.remove(conversation_id)
                            
                            await ws_manager.broadcast_participant_update(
                                conversation_id=conversation_id,
                                action="leave",
                                participant_id=connection.participant_id,
                                participant_name=user_name,
                                participant_type="human"
                            )
                        continue
                    
                    # Handle sites request
                    if msg_type == 'sites_request':
                        print(f"Sites request received from {user_id}")
                        
                        # Get sites from vector DB
                        try:
                            # Create a retriever client
                            retriever = get_vector_db_client(query_params={})
                            
                            # Get the list of sites
                            sites = await retriever.get_sites()
                            
                            # Send sites response
                            await ws.send_json({
                                'type': 'sites_response',
                                'sites': sites
                            })
                            
                            print(f"Sent {len(sites)} sites to {user_id}")
                            
                        except Exception as e:
                            print(f"Error getting sites: {e}")
                            traceback.print_exc()
                            
                            # Fallback to default sites
                            await ws.send_json({
                                'type': 'sites_response',
                                'sites': ['all']
                            })
                        continue
                    
                    # Handle message
                    if msg_type == 'message':
                        conversation_id = data.get('conversation_id')
                        if not conversation_id:
                            await ws.send_json({'type': 'error', 'message': 'conversation_id required for messages'})
                            continue
                            
                        # Auto-join conversation if not already joined
                        if conversation_id not in active_conversations:
                            # Get the real user ID from senderInfo in the message
                            sender_info = data.get('senderInfo', {})
                            actual_user_id = sender_info.get('id', user_id)
                            actual_user_name = sender_info.get('name', user_name)
                            print(f"Auto-joining user {actual_user_id} to conversation {conversation_id}")
                            
                            # Update the connection's participant_id to match the actual user
                            connection.participant_id = actual_user_id
                            
                            # Create participant instance with the actual user ID
                            human = HumanParticipant(
                                user_id=actual_user_id,
                                user_name=actual_user_name
                            )
                            
                            # Add participant through conversation manager
                            conv_manager.add_participant(conversation_id, human)
                            
                            # Add to WebSocket manager
                            connection.conversation_id = conversation_id
                            await ws_manager.add_connection(conversation_id, connection)
                            active_conversations.add(conversation_id)
                            
                            # Add AI participant if not already present
                            conv_state = conv_manager._conversations.get(conversation_id)
                            has_ai_participant = False
                            if conv_state:
                                for participant in conv_state.participants.values():
                                    if isinstance(participant, NLWebParticipant):
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
                                    print(f"[AUTO-JOIN] Creating NLWebParticipant with storage_client: {storage_client is not None}")
                                    nlweb = NLWebParticipant(nlweb_handler, config, storage_client)
                                    conv_manager.add_participant(conversation_id, nlweb)
                        print(f"User ID: {user_id}")
                        print(f"Content: {data.get('content', '')[:100]}")
                        print(f"Type: {data.get('type')}")
                        logger.info(f"WebSocket received message from {user_id}: {data.get('content', '')[:100]}")
                        
                        # Extract site and mode from the WebSocket message
                        # Client sends 'site' (singular), convert to list for compatibility
                        # Just pass the message through - no manipulation!
                        message = ChatMessage.from_dict(data)
                        
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
        print(f"\nERROR in WebSocket handler: {e}")
        logger.error(f"WebSocket handler error: {e}", exc_info=True)
    finally:
        print(f"Cleaning up {len(active_conversations)} active conversations for {user_id}")
        
        # Clean up all active conversations on disconnect
        for conversation_id in active_conversations:
            try:
                print(f"Removing {connection.participant_id} from conversation {conversation_id}")
                conv_manager.remove_participant(conversation_id, connection.participant_id)
                await ws_manager.remove_connection(conversation_id, connection.participant_id)
                
                # Broadcast leave to remaining participants
                await ws_manager.broadcast_participant_update(
                    conversation_id=conversation_id,
                    action="leave",
                    participant_id=connection.participant_id,
                    participant_name=user_name,
                    participant_type="human"
                )
            except Exception as e:
                logger.error(f"Error cleaning up conversation {conversation_id}: {e}")
        
        await ws.close()
        print(f"WebSocket closed for {user_id}")
    
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
            'timestamp': int(time.time() * 1000),
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
            'timestamp': int(time.time() * 1000)
        }, status=500)


async def upload_conversation_handler(request: web.Request) -> web.Response:
    """
    Upload conversation messages directly to storage.
    
    POST /chat/upload
    Body: JSONL format (newline-delimited JSON)
    Each line should be a complete message object with conversation_id
    
    Returns:
        200: {"messages_stored": count}
        400: Bad request (invalid JSON)
        500: Internal server error
    """
    try:
        # Get storage backend
        storage = request.app.get('chat_storage')
        if not storage:
            print("ERROR: Storage backend not available")
            return web.json_response(
                {'error': 'Storage backend not available'},
                status=500
            )
        
        # Read body as text (JSONL format)
        body = await request.text()
        print(f"Received body with {len(body)} characters")
        
        lines = body.strip().split('\n')
        print(f"Processing {len(lines)} lines")
        
        count = 0
        errors = []
        
        # Process each line
        for line_num, line in enumerate(lines, 1):
            if not line:
                continue
                
            try:
                # Parse JSON
                data = json.loads(line)
                
                print(f"Message {line_num}: {data.get('message_id', 'NO_ID')} - "
                      f"Type: {data.get('message_type', 'NO_TYPE')} - "
                      f"Conv: {data.get('conversation_id', 'NO_CONV')} - "
                      f"Content: {str(data.get('content', ''))[:50]}...")
                
                # Convert to ChatMessage using from_dict and store
                # This ensures the message is properly stored in memory
                message = ChatMessage.from_dict(data)
                await storage.store_message(message)
                count += 1
                
            except json.JSONDecodeError as e:
                error_msg = f"Line {line_num}: Invalid JSON - {str(e)}"
                print(f"ERROR: {error_msg}")
                errors.append(error_msg)
            except TypeError as e:
                error_msg = f"Line {line_num}: Invalid message format - {str(e)}"
                print(f"ERROR: {error_msg}")
                errors.append(error_msg)
            except Exception as e:
                error_msg = f"Line {line_num}: {str(e)}"
                print(f"ERROR: {error_msg}")
                errors.append(error_msg)
        
        
        # Return response
        response = {'messages_stored': count}
        if errors:
            response['errors'] = errors[:10]  # Limit to first 10 errors
            
        return web.json_response(response)
        
    except Exception as e:
        logger.error(f"Upload conversation error: {e}", exc_info=True)
        return web.json_response(
            {'error': f'Internal server error: {str(e)}'},
            status=500
        )