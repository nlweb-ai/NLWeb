# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Basic A2A (Agent-to-Agent) protocol handler for NLWeb.
Provides agent communication capabilities similar to MCP but with agent-oriented messaging.
"""

import json
import asyncio
import uuid
from typing import Dict, Any, Optional
from core.baseHandler import NLWebHandler
from misc.logger.logger import get_logger

logger = get_logger(__name__)

# A2A Protocol version
A2A_PROTOCOL_VERSION = "1.0.0"


class A2AHandler:
    """Basic handler for A2A protocol requests"""
    
    def __init__(self):
        self.agent_id = f"nlweb-agent-{uuid.uuid4().hex[:8]}"
        self.registered_agents = {}
        
    async def handle_message(self, message_data: Dict[str, Any], query_params: Dict, 
                            send_response, send_chunk) -> None:
        """
        Handle an A2A message
        
        Args:
            message_data: Parsed message data with from, to, type, content
            query_params: URL query parameters
            send_response: Function to send response headers
            send_chunk: Function to send response body
        """
        from_agent = message_data.get("from", "unknown")
        to_agent = message_data.get("to", "nlweb")
        message_type = message_data.get("type", "query")
        content = message_data.get("content", {})
        message_id = message_data.get("id", str(uuid.uuid4()))
        
        logger.info(f"A2A message: from={from_agent}, to={to_agent}, type={message_type}")
        
        try:
            if message_type == "query":
                # Handle query message - main use case
                result = await self.handle_query(content, query_params, from_agent)
                response = {
                    "version": A2A_PROTOCOL_VERSION,
                    "id": message_id,
                    "from": self.agent_id,
                    "to": from_agent,
                    "type": "response",
                    "content": result
                }
                
            elif message_type == "register":
                # Simple agent registration
                agent_info = {
                    "agent_id": from_agent,
                    "capabilities": content.get("capabilities", ["ask"])
                }
                self.registered_agents[from_agent] = agent_info
                
                response = {
                    "version": A2A_PROTOCOL_VERSION,
                    "id": message_id,
                    "from": self.agent_id,
                    "to": from_agent,
                    "type": "registration_confirmed",
                    "content": {
                        "agent_id": self.agent_id,
                        "capabilities": ["ask", "list_sites"]
                    }
                }
                
            elif message_type == "discover":
                # Return available agents
                response = {
                    "version": A2A_PROTOCOL_VERSION,
                    "id": message_id,
                    "from": self.agent_id,
                    "to": from_agent,
                    "type": "agents",
                    "content": {
                        "agents": list(self.registered_agents.values())
                    }
                }
                
            else:
                # Unknown message type
                response = {
                    "version": A2A_PROTOCOL_VERSION,
                    "id": message_id,
                    "from": self.agent_id,
                    "to": from_agent,
                    "type": "error",
                    "content": {
                        "error": f"Unknown message type: {message_type}"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error handling A2A message: {str(e)}")
            response = {
                "version": A2A_PROTOCOL_VERSION,
                "id": message_id,
                "from": self.agent_id,
                "to": from_agent,
                "type": "error",
                "content": {
                    "error": str(e)
                }
            }
        
        # Send response
        await send_response(200, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(response).encode('utf-8'), end_response=True)
    
    async def handle_query(self, content: Dict[str, Any], query_params: Dict, 
                          from_agent: str) -> Dict[str, Any]:
        """
        Handle a query from an agent using NLWebHandler
        
        Args:
            content: Query content with query, site, generate_mode etc.
            query_params: URL query parameters to pass through
            from_agent: ID of the requesting agent
            
        Returns:
            Query results in A2A format
        """
        query = content.get("query", "")
        sites = content.get("site", content.get("sites", []))
        generate_mode = content.get("generate_mode", "list")
        
        # Update query params with A2A content
        query_params["query"] = [query] if query else []
        if sites:
            query_params["site"] = sites if isinstance(sites, list) else [sites]
        query_params["generate_mode"] = [generate_mode]
        
        logger.info(f"Processing query from {from_agent}: {query}")
        
        # Collect response
        response_chunks = []
        
        class ChunkCollector:
            async def write_stream(self, data, end_response=False):
                if isinstance(data, dict):
                    chunk = json.dumps(data)
                elif isinstance(data, bytes):
                    chunk = data.decode('utf-8')
                else:
                    chunk = str(data)
                response_chunks.append(chunk)
        
        collector = ChunkCollector()
        
        # Process query with NLWebHandler
        try:
            handler = NLWebHandler(query_params, collector)
            await asyncio.wait_for(handler.runQuery(), timeout=30.0)
            
            # Combine chunks into response
            full_response = ''.join(response_chunks)
            
            # Try to parse as JSON for structured response
            try:
                response_data = json.loads(full_response)
            except:
                response_data = {"text": full_response}
            
            return {
                "query": query,
                "content": response_data,
                "status": "success"
            }
            
        except asyncio.TimeoutError:
            logger.warning(f"Query timeout for agent {from_agent}")
            return {
                "query": query,
                "error": "Query timed out after 30 seconds",
                "status": "timeout"
            }
        except Exception as e:
            logger.error(f"Query error for agent {from_agent}: {str(e)}")
            return {
                "query": query,
                "error": str(e),
                "status": "error"
            }


# Global A2A handler instance
a2a_handler = A2AHandler()
logger.info(f"A2A Handler initialized with agent_id: {a2a_handler.agent_id}")


async def handle_a2a_request(query_params: Dict, body: bytes, send_response, send_chunk) -> None:
    """
    Main entry point for A2A requests
    
    Args:
        query_params: URL query parameters
        body: Request body
        send_response: Function to send response headers
        send_chunk: Function to send response body
    """
    try:
        # Parse request body
        if body:
            try:
                message_data = json.loads(body)
                logger.debug(f"A2A request: {json.dumps(message_data, indent=2)}")
                
                # Handle the message
                await a2a_handler.handle_message(message_data, query_params, 
                                                send_response, send_chunk)
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in A2A request: {e}")
                error_response = {
                    "version": A2A_PROTOCOL_VERSION,
                    "type": "error",
                    "content": {"error": f"Invalid JSON: {str(e)}"}
                }
                await send_response(400, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps(error_response).encode('utf-8'), end_response=True)
        else:
            error_response = {
                "version": A2A_PROTOCOL_VERSION,
                "type": "error",
                "content": {"error": "Empty request body"}
            }
            await send_response(400, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response).encode('utf-8'), end_response=True)
            
    except Exception as e:
        logger.error(f"Error in handle_a2a_request: {str(e)}")
        error_response = {
            "version": A2A_PROTOCOL_VERSION,
            "type": "error",
            "content": {"error": f"Internal error: {str(e)}"}
        }
        await send_response(500, {'Content-Type': 'application/json'})
        await send_chunk(json.dumps(error_response).encode('utf-8'), end_response=True)