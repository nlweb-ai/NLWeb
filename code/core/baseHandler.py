# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the base class for all handlers.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from retrieval.retriever import get_vector_db_client
import asyncio
import pre_retrieval.decontextualize as decontextualize
import pre_retrieval.analyze_query as analyze_query
import pre_retrieval.memory as memory   
import core.ranking as ranking
import pre_retrieval.required_info as required_info
import traceback
import pre_retrieval.relevance_detection as relevance_detection
import core.fastTrack as fastTrack
import core.post_ranking as post_ranking
from core.state import NLWebHandlerState
from utils.utils import get_param, siteToItemType, log
from utils.logger import get_logger, LogLevel
from utils.logging_config_helper import get_configured_logger

logger = get_configured_logger("nlweb_handler")

VERSION_NUMBER = "0.1"

class NLWebHandler:

    def __init__(self, query_params, http_handler): 
        logger.info("Initializing NLWebHandler")
        print(f"http_handler: {http_handler}")
        self.http_handler = http_handler
        self.query_params = query_params

        # the site that is being queried
        self.site = get_param(query_params, "site", str, "all")  

        # the query that the user entered
        self.query = get_param(query_params, "query", str, "")

        # the previous queries that the user has entered
        self.prev_queries = get_param(query_params, "prev", list, [])

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
        self.fastTrackWorked = False
        self.sites_in_embeddings_sent = False

        # this is the value that will be returned to the user. 
        # it will be a dictionary with the message type as the key and the value being
        # the value of the message.
        self.return_value = {}

        self.versionNumberSent = False
        
        logger.info(f"NLWebHandler initialized with parameters:")
        logger.debug(f"site: {self.site}, query: {self.query}")
        logger.debug(f"model: {self.model}, streaming: {self.streaming}")
        logger.debug(f"generate_mode: {self.generate_mode}, query_id: {self.query_id}")
        logger.debug(f"context_url: {self.context_url}")
        logger.debug(f"Previous queries: {self.prev_queries}")
        
        log(f"NLWebHandler initialized with site: {self.site}, query: {self.query}, prev_queries: {self.prev_queries}, mode: {self.generate_mode}, query_id: {self.query_id}, context_url: {self.context_url}")
    
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
        logger.debug(f"Sending message of type: {message.get('message_type', 'unknown')}")
        async with self._send_lock:  # Protect send operation with lock
            # Check connection before sending
            if not self.connection_alive_event.is_set():
                logger.debug("Connection lost, not sending message")
                return
                
            if (self.streaming and self.http_handler is not None):
                message["query_id"] = self.query_id
                if not self.versionNumberSent:
                    self.versionNumberSent = True
                    version_number_message = {"message_type": "version_number", "version_number": {VERSION_NUMBER}}
                  #  await self.http_handler.write_stream(version_number_message)
                    
                try:
                    await self.http_handler.write_stream(message)
                    logger.debug(f"Message streamed successfully")
                except Exception as e:
                    logger.error(f"Error streaming message: {e}")
                    self.connection_alive_event.clear()  # Use event instead of flag
            else:
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

    async def runQuery(self):
        logger.info(f"Starting query execution for query_id: {self.query_id}")
        try:
            await self.prepare()
            if (self.query_done):
                logger.info(f"Query done prematurely")
                log(f"query done prematurely")
                return self.return_value
            if (not self.fastTrackWorked):
                logger.info(f"Fast track did not work, proceeding with normal ranking")
                log(f"Going to get ranked answers")
                await self.get_ranked_answers()
                log(f"ranked answers done")
            await self.post_ranking_tasks()
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
        
        try:
            logger.debug(f"Running {len(tasks)} preparation tasks concurrently")
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"Error during preparation tasks: {e}")
        finally:
            self.pre_checks_done_event.set()  # Signal completion regardless of errors
            self.state.set_pre_checks_done()
         
        # Wait for retrieval to be done
        if not self.retrieval_done_event.is_set():
            logger.info("Retrieval not done by fast track, performing regular retrieval")
            client = get_vector_db_client(query_params=self.query_params)
            items = await client.search(self.decontextualized_query, self.site)
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

    async def post_ranking_tasks(self):
        logger.info("Starting post-ranking tasks")
        await post_ranking.PostRanking(self).do()
        logger.info("Post-ranking tasks completed")