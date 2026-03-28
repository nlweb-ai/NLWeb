# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Cricket Query Handler for answering cricket statistics and match-related questions.
Integrates with the cricket statistics API to provide real-time cricket information.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
from misc.logger.logging_config_helper import get_configured_logger
from methods.cricketLens import query_cricket_stats
from core.schemas import create_status_message, create_error_message, Message, SenderType, MessageType

logger = get_configured_logger("cricket_query")


class CricketQueryHandler():
    """Handler for cricket statistics and match queries."""
    
    def __init__(self, params, handler):
        """
        Initialize the cricket query handler.
        
        Args:
            params: Parameters from tool routing including the cricket query
            handler: The parent handler instance
        """
        self.handler = handler
        self.params = params
        self.cricket_query = params.get('search_query', '')
        
    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
            if not self.cricket_query:
                await self._send_no_results_message()
                return
            
            # Send intermediate message
            create_status_message(
                f"Searching cricket statistics for: {self.cricket_query}",
                handler=self.handler
            )
            
            # Query the cricket API - returns formatted string
            formatted_response = await query_cricket_stats(self.cricket_query)
            
            if not formatted_response:
                await self._send_no_results_message()
                return
            
            # Check for error messages in the response
            if formatted_response.startswith("Error:"):
                logger.error(f"Cricket API error: {formatted_response}")
                await self._send_error_message()
                return
            
            # Send the formatted response as a result
            await self._send_cricket_result(formatted_response)
            
        except Exception as e:
            logger.error(f"Exception during cricket query: {e}")
            await self._send_error_message()
    
    async def _send_cricket_result(self, formatted_response: str):
        """
        Send cricket statistics result to the client.
        
        Args:
            formatted_response: Formatted table string for display
        """
        # Create a simple title based on the query
        title = f"Cricket Statistics: {self.cricket_query}"
        
        # Create a result object in the format expected by frontend
        result_object = {
            "@type": "CricketStatistics",
            "name": title,
            "url": f"cricket://{self.cricket_query}",
            "description": formatted_response,
            "site": "CricketLens",
            "score": 100,
            "metadata": {
                "source": "CricketLens",
                "query": self.cricket_query,
                "has_tables": True
            }
        }
        
        # Send as array of results like other handlers
        result_message = {
            "message_type": "result",
            "content": [result_object]
        }
        
        await self.handler.send_message(result_message)
        
        # Also send a completion message
        completion_msg = Message(
            sender_type=SenderType.SYSTEM,
            message_type="completion",
            content="Cricket statistics retrieved successfully",
            conversation_id=self.handler.conversation_id if hasattr(self.handler, 'conversation_id') else None
        )
        await self.handler.send_message(completion_msg.to_dict())
    
    async def _send_no_results_message(self):
        """Send message when no cricket data is found."""
        # Create no_results message
        message = Message(
            sender_type=SenderType.SYSTEM,
            message_type=MessageType.NO_RESULTS,
            content=f"No cricket statistics found for: {self.cricket_query}",
            conversation_id=self.handler.conversation_id if hasattr(self.handler, 'conversation_id') else None
        )
        asyncio.create_task(self.handler.send_message(message.to_dict()))
    
    async def _send_error_message(self):
        """Send error message when API call fails."""
        # Create error message and auto-send
        create_error_message(
            "Unable to retrieve cricket statistics. Please try again later.",
            handler=self.handler
        )