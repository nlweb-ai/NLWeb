# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Conversation Search Handler for searching through conversation history.
Used when site=conv_history.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import json
from misc.logger.logging_config_helper import get_configured_logger
# from core.embedding import get_embedding  # May be needed for future vector search
from core.conversation_history import get_storage_client
from core.ranking import Ranking

logger = get_configured_logger("conversation_search")


class ConversationRanking(Ranking):
    """Custom ranking for conversations that includes user_id in results."""
    
    def __init__(self, handler, items):
        super().__init__(handler, items, ranking_type=Ranking.CONVERSATION_SEARCH)
    
    async def send_answers(self, force=False):
        """Override to add user_id to each result."""
        json_results = []
        
        for result in self.results:
            if not result:
                continue
                
            if self.shouldSend(result) or force:
                item_data = {
                    "@type": "Item",
                    "url": result["url"],
                    "name": result["name"],
                    "site": result["site"],
                    "siteUrl": result["site"],
                    "score": result["ranking"]["score"],
                    "description": result["ranking"]["description"],
                    "schema_object": result["schema_object"]
                }
                
                # Add user_id from the map if available
                if hasattr(self.handler, '_conv_user_id_map'):
                    user_id = self.handler._conv_user_id_map.get(result["url"])
                    if user_id:
                        item_data["user_id"] = user_id
                
                json_results.append(item_data)
                result["sent"] = True
            
        if json_results:  # Only attempt to send if there are results
            # Wait for pre checks to be done using event
            await self.handler.pre_checks_done_event.wait()
            
            # if we got here, prechecks are done. check once again for fast track abort
            if self.ranking_type == Ranking.FAST_TRACK and self.handler.state.should_abort_fast_track():
                logger.info("Fast track aborted after pre-checks")
                return
            
            try:
                # Final safety check before sending
                if self.num_results_sent + len(json_results) > self.NUM_RESULTS_TO_SEND:
                    # Trim the results to not exceed the limit
                    allowed_count = self.NUM_RESULTS_TO_SEND - self.num_results_sent
                    json_results = json_results[:allowed_count]
                    logger.warning(f"Trimmed results to {len(json_results)} to stay within limit of {self.NUM_RESULTS_TO_SEND}")
                
                to_send = {"message_type": "result", "content": json_results}
                asyncio.create_task(self.handler.send_message(to_send))
                self.num_results_sent += len(json_results)
                logger.info(f"Sent {len(json_results)} results with user_id, total sent: {self.num_results_sent}/{self.NUM_RESULTS_TO_SEND}")
            except (BrokenPipeError, ConnectionResetError) as e:
                logger.error(f"Client disconnected while sending answers: {str(e)}")
                self.handler.connection_alive_event.clear()
            except Exception as e:
                logger.error(f"Error sending answers: {str(e)}")
                self.handler.connection_alive_event.clear()


class ConversationSearchHandler():
    """Handler for searching through conversation history."""
    
    def __init__(self, params, handler):
        """
        Initialize the conversation search handler.
        
        Args:
            params: Parameters from tool routing including search query
            handler: The parent handler instance
        """
        self.handler = handler
        self.params = params
        self.search_query = params.get('search_query', '')
        
    async def do(self):
        """Main entry point following NLWeb module pattern."""
        try:
            if not self.search_query:
                await self._send_no_results_message()
                return
                
            # Extract search_all_users parameter from handler query params
            search_all_users = False
            if hasattr(self.handler, 'query_params') and self.handler.query_params:
                search_all_users_param = self.handler.query_params.get('search_all_users', [])
                if search_all_users_param:
                    search_all_users_value = search_all_users_param[0] if isinstance(search_all_users_param, list) else search_all_users_param
                    # Handle both string 'true'/'false' and boolean values
                    search_all_users = str(search_all_users_value).lower() in ['true', '1', 'yes']
            
            # Extract user_id from handler query params
            user_id = None
            if not search_all_users:
                # Only restrict by user_id if not searching all users
                if hasattr(self.handler, 'query_params') and self.handler.query_params:
                    user_id_list = self.handler.query_params.get('user_id', [])
                    if user_id_list:
                        user_id = user_id_list[0] if isinstance(user_id_list, list) else user_id_list
            
            logger.info(f"Searching conversation history. Query: {self.search_query}, Search all users: {search_all_users}, User ID: {user_id}")
            
            # Send intermediate message
            asyncio.create_task(self.handler.send_message({
                "message_type": "intermediate_message",
                "message": f"Searching conversation history for: {self.search_query}"
            }))
            
            # Step 1: Compute embedding on the query (currently unused but may be needed for vector search)
            # query_embedding = await get_embedding(self.search_query)
            
            # Step 2: Issue vector search to conversation storage backend
            storage_client = await get_storage_client()
            
            # Use the search_conversations method which does hybrid search (text + vector)
            conversation_results = await storage_client.search_conversations(
                query=self.search_query,
                user_id=user_id,
                site=None,  # Search across all sites
                limit=50    # Get top 50 results for ranking
            )
            
            if not conversation_results:
                await self._send_no_results_message()
                return
            
            # Convert conversation results to format expected by Ranking
            # Create items in the 4-tuple format (url, json_str, name, site)
            items_for_ranking = []
            # Also store user_id mapping for later
            user_id_map = {}
            for conv in conversation_results:
                # Create the conversation JSON object with specified fields
                conversation_data = {
                    "@type": "Conversation",
                    "conversation_id": conv.conversation_id,
                    "user_prompt": conv.user_prompt,
                    "description": conv.summary if conv.summary else conv.user_prompt,
                    "messages": conv.response,  # The response contains the messages
                    "time_of_creation": conv.time_of_creation.isoformat() if hasattr(conv.time_of_creation, 'isoformat') else str(conv.time_of_creation)  # Convert datetime to string
                }
                
                # Store user_id separately for later injection
                conversation_url = f"conversation://{conv.conversation_id}"
                user_id_map[conversation_url] = conv.user_id
                
                # Create the 4-tuple item format
                # (url, json_str, name, site)
                item = (
                    conversation_url,  # url
                    json.dumps(conversation_data),  # json_str with the conversation data
                    conv.user_prompt,  # name (using user_prompt as title)
                    conv.site  # site
                )
                items_for_ranking.append(item)
            
            # Step 3: Rank the results using conversation-specific ranking
            # Set the handler's query to the search query for ranking
            original_query = self.handler.query
            self.handler.query = self.search_query
            
            # Store the user_id map in the handler for the ranking to use
            self.handler._conv_user_id_map = user_id_map
            
            # Use the Ranking class with CONVERSATION_SEARCH type
            ranking = ConversationRanking(self.handler, items_for_ranking)
            await ranking.do()
            
            # Clean up
            if hasattr(self.handler, '_conv_user_id_map'):
                del self.handler._conv_user_id_map
            
            # Restore original query
            self.handler.query = original_query
            
        except Exception as e:
            logger.error(f"Exception during conversation search: {e}")
            await self._send_no_results_message()
    
    async def _send_no_results_message(self):
        """Send message when no matching conversations are found."""
        message = {
            "message_type": "no_results",
            "message": f"No conversations found matching: {self.search_query}"
        }
        
        asyncio.create_task(self.handler.send_message(message))
    
    async def _send_placeholder_message(self, user_id):
        """Temporary placeholder message until implementation is complete."""
        message = {
            "message_type": "placeholder",
            "message": f"Conversation search for '{self.search_query}' - implementation pending",
            "user_id": user_id,
            "query": self.search_query
        }
        
        asyncio.create_task(self.handler.send_message(message))