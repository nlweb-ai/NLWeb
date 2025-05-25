# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains code for the 'generate answer' path, which provides
a flow that is more similar to RAG.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
from core.baseHandler import NLWebHandler
from llm.llm import ask_llm
from prompts.prompt_runner import PromptRunner
import retrieval.retriever as retriever
from prompts.prompts import find_prompt, fill_ranking_prompt
from utils.trim import trim_json, trim_json_hard
from utils.logging_config_helper import get_configured_logger
from utils.utils import log
import pre_retrieval.analyze_query as analyze_query
import pre_retrieval.relevance_detection as relevance_detection
import pre_retrieval.memory as memory
import pre_retrieval.required_info as required_info
import json
import traceback


logger = get_configured_logger("generate_answer")


class GenerateAnswer(NLWebHandler):

    GATHER_ITEMS_THRESHOLD = 55

    RANKING_PROMPT_NAME = "RankingPromptForGenerate"
    SYNTHESIZE_PROMPT_NAME = "SynthesizePromptForGenerate"
    DESCRIPTION_PROMPT_NAME = "DescriptionPromptForGenerate"

    def __init__(self, query_params, handler):
        super().__init__(query_params, handler)
        self.items = []
        self._results_lock = asyncio.Lock()  # Add lock for thread-safe operations
        logger.info(f"GenerateAnswer initialized with query_params: {query_params}")
        log(f"GenerateAnswer query_params: {query_params}")

    async def runQuery(self):
        try:
            logger.info(f"Starting query execution for query_id: {self.query_id}")
            await self.prepare()
            if (self.query_done):
                logger.info("Query done prematurely")
                return self.return_value
            await self.get_ranked_answers()
            self.return_value["query_id"] = self.query_id
            logger.info(f"Query execution completed for query_id: {self.query_id}")
            return self.return_value
        except Exception as e:
            logger.exception(f"Error in runQuery: {e}")
            traceback.print_exc()
            raise
    
    async def prepare(self):
        # runs the tasks that need to be done before retrieval, ranking, etc.
        logger.info("Starting preparation phase")
        tasks = []
        
        # Adding all necessary preparation tasks
        tasks.append(asyncio.create_task(analyze_query.DetectItemType(self).do()))
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
            
        logger.info("Preparation phase completed")
   
    async def rankItem(self, url, json_str, name, site):
        if not self.connection_alive_event.is_set():
            logger.warning("Connection lost, skipping item ranking")
            return
            
        try:
            logger.debug(f"Ranking item: {name} from {site}")
            prompt_str, ans_struc = find_prompt(site, self.item_type, self.RANKING_PROMPT_NAME)
            description = trim_json_hard(json_str)
            prompt = fill_ranking_prompt(prompt_str, self, description)
            logger.debug(f"Sending ranking request to LLM for item: {name}")
            ranking = await ask_llm(prompt, ans_struc, level="low")
            logger.debug(f"Received ranking score: {ranking.get('score', 'N/A')} for item: {name}")
            ansr = {
                'url': url,
                'site': site,
                'name': name,
                'ranking': ranking,
                'schema_object': json.loads(json_str),
                'sent': False,
            }
            
            if (ranking["score"] > self.GATHER_ITEMS_THRESHOLD):
                logger.info(f"High score item: {name} (score: {ranking['score']})")
                async with self._results_lock:  # Thread-safe append
                    self.final_ranked_answers.append(ansr)
                    
        except Exception as e:
            logger.error(f"Error in rankItem: {e}")
            logger.debug("Full error trace: ", exc_info=True)

    async def get_ranked_answers(self):
        logger.info("Starting retrieval and ranking process")
        try:
            # Wait for retrieval to be done if not already
            logger.info("Retrieving items for query")
            client = retriever.get_vector_db_client(query_params=self.query_params)
            top_embeddings = await client.search(self.decontextualized_query, self.site)
            self.items = top_embeddings  # Store all retrieved items
            logger.debug(f"Retrieved {len(top_embeddings)} items from database")
            # Rank each item
            tasks = []
            for url, json_str, name, site in top_embeddings:
                tasks.append(asyncio.create_task(self.rankItem(url, json_str, name, site)))
            
            
            logger.debug(f"Running {len(tasks)} ranking tasks concurrently")
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Synthesize the answer from ranked items
            logger.info("Ranking completed, synthesizing answer")
            await self.synthesizeAnswer()
            
        except Exception as e:
            logger.exception(f"Error in get_ranked_answers: {e}")
            raise

    async def getDescription(self, url, json_str, query, answer, name, site):
        try:
            logger.debug(f"Getting description for item: {name}")
            description = await PromptRunner(self).run_prompt(self.DESCRIPTION_PROMPT_NAME)
            logger.debug(f"Got description for item: {name}")
            return (url, name, site, description["description"], json_str)
        except Exception as e:
            logger.error(f"Error getting description for {name}: {str(e)}")
            logger.debug("Full error trace: ", exc_info=True)
            raise

    async def synthesizeAnswer(self): 
        if not self.connection_alive_event.is_set():
            logger.warning("Connection lost, skipping answer synthesis")
            return
            
        try:
            logger.info("Starting answer synthesis")
            
            # Check if we have any ranked answers to work with
            if not self.final_ranked_answers:
                logger.warning("No ranked answers found, sending empty response")
                message = {
                    "message_type": "nlws", 
                    "answer": "I couldn't find relevant information to answer your question.", 
                    "items": []
                }
                await self.send_message(message)
                return
                
            response = await PromptRunner(self).run_prompt(self.SYNTHESIZE_PROMPT_NAME, timeout=100, verbose=True)
            logger.debug(f"Synthesis response received")
            
            json_results = []
            description_tasks = []
            answer = response["answer"]
            
            # Create initial message with just the answer
            message = {"message_type": "nlws", "answer": answer, "items": json_results}
            logger.info("Sending initial answer")
            await self.send_message(message)
            
            # Process each URL mentioned in the response
            if "urls" in response and response["urls"]:
                for url in response["urls"]:
                    # Find the matching item in our items list
                    matching_items = [item for item in self.items if item[0] == url]
                    if not matching_items:
                        logger.warning(f"URL {url} referenced in response not found in items")
                        continue
                        
                    item = matching_items[0]
                    (url, json_str, name, site) = item
                    logger.debug(f"Creating description task for item: {name}")
                    t = asyncio.create_task(self.getDescription(url, json_str, self.decontextualized_query, answer, name, site))
                    description_tasks.append(t)
                    
                if description_tasks:
                    logger.info(f"Waiting for {len(description_tasks)} description tasks to complete")
                    desc_answers = await asyncio.gather(*description_tasks, return_exceptions=True)
                    
                    for result in desc_answers:
                        if isinstance(result, Exception):
                            logger.error(f"Error getting description: {result}")
                            continue
                            
                        url, name, site, description, json_str = result
                        logger.debug(f"Adding result for {name} to final message")
                        json_results.append({
                            "url": url,
                            "name": name,
                            "description": description,
                            "site": site,
                            "schema_object": json.loads(json_str),
                        })
                        
                    # Update message with descriptions
                    message = {"message_type": "nlws", "answer": answer, "items": json_results}
                    logger.info(f"Sending final answer with {len(json_results)} item descriptions")
                    await self.send_message(message)
            else:
                logger.warning("No URLs found in synthesis response")
                
        except Exception as e:
            logger.exception(f"Error in synthesizeAnswer: {e}")
            if self.connection_alive_event.is_set():
                try:
                    error_msg = {"message_type": "nlws", "answer": "I encountered an error while generating your answer. Please try again.", "items": []}
                    await self.send_message(error_msg)
                except:
                    pass
            raise