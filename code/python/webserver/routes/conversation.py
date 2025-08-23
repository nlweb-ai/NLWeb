"""Conversation API routes for aiohttp server"""

from aiohttp import web
import logging
from typing import Dict, Any, List
from core.conversation_history import get_conversation_by_id, get_recent_conversations

logger = logging.getLogger(__name__)


def setup_conversation_routes(app: web.Application):
    """Setup conversation API routes"""
    app.router.add_get('/conversation', get_conversation_handler)
    app.router.add_get('/userConversations', get_user_conversations_handler)


async def get_conversation_handler(request: web.Request) -> web.Response:
    """
    Handle /conversation endpoint to retrieve conversation events and participants.
    
    Query Parameters:
        conversation_id: The ID of the conversation to retrieve
    
    Returns:
        JSON response with conversation events and participants
    """
    try:
        # Get conversation_id from query parameters
        conversation_id = request.query.get('conversation_id')
        
        if not conversation_id:
            return web.json_response({
                "error": "Missing required parameter: conversation_id"
            }, status=400)
        
        # Retrieve conversation data from storage
        conversation_data = await get_conversation_by_id(conversation_id)
        
        return web.json_response(conversation_data)
        
    except Exception as e:
        logger.error(f"Error in get_conversation_handler: {e}", exc_info=True)
        return web.json_response({
            "error": f"Internal server error: {str(e)}"
        }, status=500)


async def get_user_conversations_handler(request: web.Request) -> web.Response:
    """
    Handle /userConversations endpoint to retrieve all conversations for a user.
    
    Query Parameters:
        user_id: The ID of the user whose conversations to retrieve
        site: (optional) Filter conversations by site
        limit: (optional) Maximum number of conversations to return (default: 50)
    
    Returns:
        JSON response with user's conversations grouped by thread
    """
    try:
        # Get parameters from query
        user_id = request.query.get('user_id')
        site = request.query.get('site', 'all')  # Default to 'all' if not specified
        limit = int(request.query.get('limit', '50'))  # Default to 50
        
        if not user_id:
            return web.json_response({
                "error": "Missing required parameter: user_id"
            }, status=400)
        
        # Validate limit
        if limit < 1:
            limit = 1
        elif limit > 100:
            limit = 100  # Cap at 100 to prevent excessive data retrieval
        
        # Retrieve user's conversations from storage
        conversations = await get_recent_conversations(user_id, site, limit)
        
        return web.json_response({
            "user_id": user_id,
            "site": site,
            "conversations": conversations
        })
        
    except ValueError as e:
        # Handle invalid limit parameter
        return web.json_response({
            "error": f"Invalid parameter value: {str(e)}"
        }, status=400)
    except Exception as e:
        logger.error(f"Error in get_user_conversations_handler: {e}", exc_info=True)
        return web.json_response({
            "error": f"Internal server error: {str(e)}"
        }, status=500)