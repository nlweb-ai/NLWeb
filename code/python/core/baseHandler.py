# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the base class for all handlers.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from core.retriever import search
import asyncio
import importlib
import core.query_analysis.decontextualize as decontextualize
import core.query_analysis.analyze_query as analyze_query
import core.query_analysis.memory as memory   
import core.ranking as ranking
import core.query_analysis.required_info as required_info
import traceback
import core.query_analysis.relevance_detection as relevance_detection
import core.fastTrack as fastTrack
import core.post_ranking as post_ranking
import core.router as router
import methods.accompaniment as accompaniment
import methods.recipe_substitution as substitution
from core.state import NLWebHandlerState
from core.utils.utils import get_param, siteToItemType, log
from misc.logger.logger import get_logger, LogLevel
from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG
from core.storage import add_conversation

logger = get_configured_logger("nlweb_handler")

API_VERSION = "0.1"

class NLWebHandler:

    def __init__(self, query_params, http_handler): 
        import time
        logger.info("Initializing NLWebHandler")
        self.http_handler = http_handler
        self.query_params = query_params
        
        # Track initialization time for time-to-first-result
        self.init_time = time.time()
        self.first_result_sent = False

        # the site that is being queried
        self.site = get_param(query_params, "site", str, "all")  
        
        # Parse comma-separated sites
        if self.site and isinstance(self.site, str) and "," in self.site:
            self.site = [s.strip() for s in self.site.split(",") if s.strip()]

        # the query that the user entered
        self.query = get_param(query_params, "query", str, "")

        # the previous queries that the user has entered
        self.prev_queries = get_param(query_params, "prev", list, [])

        # the last answers (title and url) from previous queries
        self.last_answers = get_param(query_params, "last_ans", list, [])

        # the model that is being used
        self.model = get_param(query_params, "model", str, "gpt-4o-mini")

        # the request may provide a fully decontextualized query, in which case 
        # we don't need to decontextualize the latest query.
        self.decontextualized_query = get_param(query_params, "decontextualized_query", str, "") 

        # the url of the page on which the query was entered, in case that needs to be 
        # used to decontextualize the query. Typically left empty
        self.context_url = get_param(query_params, "context_url", str, "")

        # this allows for the request to specify an arbitrary string as background/context
        self.context_description = get_param(query_params, "context_description", str, "")

        # this is the query id which is useful for some bookkeeping
        self.query_id = get_param(query_params, "query_id", str, "")

        # OAuth user ID for conversation storage
        self.oauth_id = get_param(query_params, "oauth_id", str, "")
        
        # Thread ID for conversation grouping
        self.thread_id = get_param(query_params, "thread_id", str, "")

        streaming = get_param(query_params, "streaming", str, "True")
        self.streaming = streaming not in ["False", "false", "0"]

        # should we just list the results or try to summarize the results or use the results to generate an answer
        # Valid values are "none","summarize" and "generate"
        self.generate_mode = get_param(query_params, "generate_mode", str, "none")
        # the items that have been retrieved from the vector database, could be before decontextualization.
        # See below notes on fasttrack
        self.retrieved_items = []

        # the final set of items retrieved from vector database, after decontextualization, etc.
        # items from these will be returned. If there is no decontextualization required, this will
        # be the same as retrieved_items
        self.final_retrieved_items = []

        # the final ranked answers that will be returned to the user (or have already been streamed)
        self.final_ranked_answers = []

        # whether the query has been done. Can happen if it is determined that we don't have enough
        # information to answer the query, or if the query is irrelevant.
        self.query_done = False

        # whether the query is irrelevant. e.g., how many angels on a pinhead asked of seriouseats.com
        self.query_is_irrelevant = False

        # whether the query requires decontextualization
        self.requires_decontextualization = False

        # the type of item that is being sought. e.g., recipe, movie, etc.
        self.item_type = siteToItemType(self.site)

        # required item type from request parameter
        self.required_item_type = get_param(query_params, "required_item_type", str, None)

        # tool routing results

        self.tool_routing_results = []

        # the state of the handler. This is a singleton that holds the state of the handler.
        self.state = NLWebHandlerState(self)

        # Synchronization primitives - replace flags with proper async primitives
        self.pre_checks_done_event = asyncio.Event()
        self.retrieval_done_event = asyncio.Event()
        self.connection_alive_event = asyncio.Event()
        self.connection_alive_event.set()  # Initially alive
        self.abort_fast_track_event = asyncio.Event()
        self._state_lock = asyncio.Lock()
        self._send_lock = asyncio.Lock()
        
        self.fastTrackRanker = None
        self.headersSent = False  # Track if headers have been sent
        self.fastTrackWorked = False
        self.sites_in_embeddings_sent = False

        # this is the value that will be returned to the user. 
        # it will be a dictionary with the message type as the key and the value being
        # the value of the message.
        self.return_value = {}

        self.versionNumberSent = False
        self.headersSent = False
        
        logger.info(f"NLWebHandler initialized with parameters:")
        logger.debug(f"site: {self.site}, query: {self.query}")
        logger.debug(f"model: {self.model}, streaming: {self.streaming}")
        logger.debug(f"generate_mode: {self.generate_mode}, query_id: {self.query_id}")
        logger.debug(f"context_url: {self.context_url}")
        logger.debug(f"Previous queries: {self.prev_queries}")
        logger.debug(f"Last answers: {self.last_answers}")
        
        # log(f"NLWebHandler initialized with site: {self.site}, query: {self.query}, prev_queries: {self.prev_queries}, mode: {self.generate_mode}, query_id: {self.query_id}, context_url: {self.context_url}")

    @property 
    def is_connection_alive(self):
        return self.connection_alive_event.is_set()
        
    @is_connection_alive.setter
    def is_connection_alive(self, value):
        if value:
            self.connection_alive_event.set()
        else:
            self.connection_alive_event.clear()

   

    async def send_message(self, message):
        import time
        logger.debug(f"Sending message of type: {message.get('message_type', 'unknown')}")
        async with self._send_lock:  # Protect send operation with lock
            # Check connection before sending
            if not self.connection_alive_event.is_set():
                logger.debug("Connection lost, not sending message")
                return
                
            if (self.streaming and self.http_handler is not None):
                message["query_id"] = self.query_id

                
                # Check if this is the first result_batch and add time-to-first-result header
                if message.get("message_type") == "result_batch" and not self.first_result_sent:
                    self.first_result_sent = True
                    time_to_first_result = time.time() - self.init_time
                    
                    # Send time-to-first-result as a header message
                    ttfr_message = {
                        "message_type": "header",
                        "header_name": "time-to-first-result",
                        "header_value": f"{time_to_first_result:.3f}s",
                        "query_id": self.query_id
                    }
                    try:
                        await self.http_handler.write_stream(ttfr_message)
                        logger.info(f"Sent time-to-first-result header: {time_to_first_result:.3f}s")
                    except Exception as e:
                        logger.error(f"Error sending time-to-first-result header: {e}")
                
                # Send headers on first message if not already sent
                if not self.headersSent:
                    self.headersSent = True

                    
                    # Send version number first
                    if not self.versionNumberSent:
                        self.versionNumberSent = True
                        version_number_message = {"message_type": "api_version", "api_version": API_VERSION, "query_id": self.query_id}
                        try:
                            await self.http_handler.write_stream(version_number_message)
                            logger.info(f"Sent API version: {API_VERSION}")
                        except Exception as e:
                            logger.error(f"Error sending API version: {e}")
                    
                    # Send headers from config as messages
                    if hasattr(CONFIG.nlweb, 'headers') and CONFIG.nlweb.headers:
                        logger.info(f"Sending headers: {CONFIG.nlweb.headers}")
                        for header_key, header_value in CONFIG.nlweb.headers.items():
                            header_message = {
                                "message_type": header_key,
                                "content": header_value,
                                "query_id": self.query_id
                            }
                            try:
                                await self.http_handler.write_stream(header_message)
                                logger.info(f"Sent header message: {header_key} = {header_value}")
                            except Exception as e:
                                logger.error(f"Error sending header {header_key}: {e}")
                                self.connection_alive_event.clear()
                                return
                    else:
                        logger.warning("No headers found in CONFIG.nlweb.headers")
                    
                    # Send API keys from config as messages
                    if hasattr(CONFIG.nlweb, 'api_keys') and CONFIG.nlweb.api_keys:
                        logger.info(f"API keys in config: {list(CONFIG.nlweb.api_keys.keys())}")
                        for key_name, key_value in CONFIG.nlweb.api_keys.items():
                            logger.info(f"Processing API key '{key_name}': value exists = {bool(key_value)}")
                            if key_value:  # Only send if key has a value
                                api_key_message = {
                                    "message_type": "api_key",
                                    "key_name": key_name,
                                    "key_value": key_value,
                                    "query_id": self.query_id
                                }
                                try:
                                    await self.http_handler.write_stream(api_key_message)
                                    logger.info(f"Sent API key configuration for: {key_name} (length: {len(key_value)})")
                                except Exception as e:
                                    logger.error(f"Error sending API key {key_name}: {e}")
                                    self.connection_alive_event.clear()
                                    return
                            else:
                                logger.warning(f"API key '{key_name}' has no value, skipping")
                    else:
                        logger.info("No API keys configured in CONFIG.nlweb")
                
                try:
                    await self.http_handler.write_stream(message)
                    logger.debug(f"Message streamed successfully")
                except Exception as e:
                    logger.error(f"Error streaming message: {e}")
                    self.connection_alive_event.clear()  # Use event instead of flag
            else:
                # Add headers to non-streaming response if not already added
                if not self.headersSent:
                    self.headersSent = True
                    try:
                        # Get configured headers from CONFIG and add them to return_value
                        headers = CONFIG.get_headers()
                        for header_key, header_value in headers.items():
                            self.return_value[header_key] = {"message": header_value}
                            logger.debug(f"Header '{header_key}' added to return value")
                    except Exception as e:
                        logger.error(f"Error adding headers to return value: {e}")
                
                val = {}
                message_type = message["message_type"]
                if (message_type == "result_batch"):
                    val = message["results"]
                    for result in val:
                        if "results" not in self.return_value:
                            self.return_value["results"] = []
                        self.return_value["results"].append(result)
                    logger.debug(f"Added {len(val)} results to return value")
                else:
                    for key in message:
                        if (key != "message_type"):
                            val[key] = message[key]
                    self.return_value[message["message_type"]] = val
                logger.debug(f"Message added to return value store")
                
                # Also add headers to return value in non-streaming mode if not already sent
                if not self.headersSent:
                    self.headersSent = True
                    if hasattr(CONFIG.nlweb, 'headers') and CONFIG.nlweb.headers:
                        for header_key, header_value in CONFIG.nlweb.headers.items():
                            self.return_value[header_key] = header_value


    async def runQuery(self):
        logger.info(f"Starting query execution for query_id: {self.query_id}")
        try:
            await self.prepare()
            if (self.query_done):
                logger.info(f"Query done prematurely")
                log(f"query done prematurely")
                return self.return_value
            if (not self.fastTrackWorked):
                logger.info(f"Fast track did not work, proceeding with routing logic")
                await self.route_query_based_on_tools()
            
            # Check if query is done regardless of whether FastTrack worked
            if (self.query_done):
                logger.info(f"Query completed by tool handler")
                return self.return_value
                
            await self.post_ranking_tasks()
            
            # Store conversation if user is authenticated
            if self.oauth_id and self.thread_id:
                logger.info(f"Storing conversation for oauth_id: {self.oauth_id}, thread_id: {self.thread_id}")
                try:
                    
                    # Prepare the response summary
                    response = ""
                    if self.final_ranked_answers:
                        # Create a summary of the top results
                        results = []
                        for answer in self.final_ranked_answers[:5]:  # Top 5 results
                            if isinstance(answer, dict):
                                name = answer.get('name', '')
                                url = answer.get('url', '')
                                if name and url:
                                    results.append(f"- {name}: {url}")
                        response = "\n".join(results) if results else "No results found"
                    else:
                        response = "No results found"
                    
                    # Store the conversation
                    await add_conversation(
                        user_id=self.oauth_id,
                        site=self.site,
                        thread_id=self.thread_id,
                        user_prompt=self.query,
                        response=response
                    )
                    logger.info(f"Stored conversation for user {self.oauth_id} in thread {self.thread_id}")
                except Exception as e:
                    logger.error(f"Error storing conversation: {e}")
                    # Don't fail the request if storage fails
            
            self.return_value["query_id"] = self.query_id
            logger.info(f"Query execution completed for query_id: {self.query_id}")
            return self.return_value
        except Exception as e:
            logger.exception(f"Error in runQuery: {e}")
            log(f"Error in runQuery: {e}")
            traceback.print_exc()
            raise
    
    async def prepare(self):
        logger.info("Starting preparation phase")
        tasks = []
        
        logger.debug("Creating preparation tasks")
        tasks.append(asyncio.create_task(fastTrack.FastTrack(self).do()))
        tasks.append(asyncio.create_task(analyze_query.DetectItemType(self).do()))
        tasks.append(asyncio.create_task(analyze_query.DetectMultiItemTypeQuery(self).do()))
        tasks.append(asyncio.create_task(analyze_query.DetectQueryType(self).do()))
        tasks.append(asyncio.create_task(self.decontextualizeQuery().do()))
        tasks.append(asyncio.create_task(relevance_detection.RelevanceDetection(self).do()))
        tasks.append(asyncio.create_task(memory.Memory(self).do()))
        tasks.append(asyncio.create_task(required_info.RequiredInfo(self).do()))
        tasks.append(asyncio.create_task(router.ToolSelector(self).do()))
        
        try:
            logger.debug(f"Running {len(tasks)} preparation tasks concurrently")
            if CONFIG.should_raise_exceptions():
                # In testing/development mode, raise exceptions to fail tests properly
                await asyncio.gather(*tasks)
            else:
                # In production mode, catch exceptions to avoid crashing
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"Error during preparation tasks: {e}")
            if CONFIG.should_raise_exceptions():
                raise  # Re-raise in testing/development mode
        finally:
            self.pre_checks_done_event.set()  # Signal completion regardless of errors
            self.state.set_pre_checks_done()
         
        # Wait for retrieval to be done
        logger.info(f"Checking retrieval_done_event for site: {self.site}")
        if not self.retrieval_done_event.is_set():
            # Skip retrieval for sites without embeddings
            if "datacommons" in self.site:
                logger.info("Skipping retrieval for DataCommons - no embeddings")
                self.final_retrieved_items = []
                self.retrieval_done_event.set()
            else:
                logger.info("Retrieval not done by fast track, performing regular retrieval")
                items = await search(
                    self.decontextualized_query, 
                    self.site,
                    query_params=self.query_params
                )
                self.final_retrieved_items = items
                logger.debug(f"Retrieved {len(items)} items from database")
                self.retrieval_done_event.set()
        
        logger.info("Preparation phase completed")

    def decontextualizeQuery(self):
        logger.info("Determining decontextualization strategy")
        if (len(self.prev_queries) < 1):
            logger.debug("No context or previous queries - using NoOpDecontextualizer")
            self.decontextualized_query = self.query
            return decontextualize.NoOpDecontextualizer(self)
        elif (self.decontextualized_query != ''):
            logger.debug("Decontextualized query already provided - using NoOpDecontextualizer")
            return decontextualize.NoOpDecontextualizer(self)
        elif (len(self.prev_queries) > 0):
            logger.debug(f"Using PrevQueryDecontextualizer with {len(self.prev_queries)} previous queries")
            return decontextualize.PrevQueryDecontextualizer(self)
        elif (len(self.context_url) > 4 and len(self.prev_queries) == 0):
            logger.debug(f"Using ContextUrlDecontextualizer with context URL: {self.context_url}")
            return decontextualize.ContextUrlDecontextualizer(self)
        else:
            logger.debug("Using FullDecontextualizer with both context URL and previous queries")
            return decontextualize.FullDecontextualizer(self)
    
    async def get_ranked_answers(self):
        try:
            logger.info(f"Starting ranking process on {len(self.final_retrieved_items)} items")
            log(f"Getting ranked answers on {len(self.final_retrieved_items)} items")
            await ranking.Ranking(self, self.final_retrieved_items, ranking.Ranking.REGULAR_TRACK).do()
            logger.info("Ranking process completed")
            return self.return_value
        except Exception as e:
            logger.exception(f"Error in get_ranked_answers: {e}")
            log(f"Error in get_ranked_answers: {e}")
            traceback.print_exc()
            raise

    async def route_query_based_on_tools(self):
        """Route the query based on tool selection results."""
        logger.info("Routing query based on tool selection")

        # Check if we have tool routing results
        if not hasattr(self, 'tool_routing_results') or not self.tool_routing_results:
            logger.debug("No tool routing results available, defaulting to search")
            await self.get_ranked_answers()
            return

        top_tool = self.tool_routing_results[0] 
        tool = top_tool['tool']
        tool_name = tool.name
        params = top_tool['result']
        log(f"Selected tool: {tool_name}")
        
        # Check if tool has a handler class defined
        if tool.handler_class:
            try:
                logger.info(f"Routing to {tool_name} functionality via {tool.handler_class}")
                
                # For non-search tools, clear any items that FastTrack might have populated
                if tool_name != "search":
                    self.final_retrieved_items = []
                    self.retrieved_items = []
                
                # Dynamic import of handler module and class
                module_path, class_name = tool.handler_class.rsplit('.', 1)
                module = importlib.import_module(module_path)
                handler_class = getattr(module, class_name)
                
                # Instantiate and execute handler
                handler_instance = handler_class(params, self)
                
                # Standard handler pattern with do() method
                await handler_instance.do()
                    
            except Exception as e:
                logger.error(f"Error loading handler for tool {tool_name}: {e}")
                # Fall back to search
                await self.get_ranked_answers()
        else:
            # Default behavior for tools without handlers (like search)
            if tool_name == "search":
                logger.info("Routing to search functionality")
                await self.get_ranked_answers()
            else:
                logger.info(f"No handler defined for tool: {tool_name}, defaulting to search")
                await self.get_ranked_answers()


    async def post_ranking_tasks(self):
        logger.info("Starting post-ranking tasks")
        await post_ranking.PostRanking(self).do()
        logger.info("Post-ranking tasks completed")
