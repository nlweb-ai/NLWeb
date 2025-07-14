# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the classes for the different levels of decontextualization. 

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import core.retriever as retriever
from core.utils.trim import trim_json
import json
from core.prompts import PromptRunner
from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG

logger = get_configured_logger("decontextualizer")

class NoOpDecontextualizer(PromptRunner):
  
    DECONTEXTUALIZE_QUERY_PROMPT_NAME = "NoOpDecontextualizer"
    STEP_NAME = "Decon"

    def __init__(self, handler):
        super().__init__(handler)
        self.handler.state.start_precheck_step(self.STEP_NAME)
    
    async def do(self):
        # Check if decontextualization is enabled in config
        if not CONFIG.is_decontextualize_enabled():
            logger.info("Decontextualization is disabled in config, skipping")
            self.handler.decontextualized_query = self.handler.query
            self.handler.requires_decontextualization = False
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            return
        
        self.handler.decontextualized_query = self.handler.query
        self.handler.requires_decontextualization = False
        await self.handler.state.precheck_step_done(self.STEP_NAME)
        logger.info("Decontextualization not required")
        return
    
class PrevQueryDecontextualizer(NoOpDecontextualizer):

    DECONTEXTUALIZE_QUERY_PROMPT_NAME = "PrevQueryDecontextualizer"
  
    def __init__(self, handler):
        super().__init__(handler)

    async def do(self):
        # Check if decontextualization is enabled in config
        if not CONFIG.is_decontextualize_enabled():
            logger.info("Decontextualization is disabled in config, skipping")
            self.handler.decontextualized_query = self.handler.query
            self.handler.requires_decontextualization = False
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            return
        
        response = await self.run_prompt(self.DECONTEXTUALIZE_QUERY_PROMPT_NAME, 
                                         level="high", verbose=False)
        logger.info(f"response: {response}")
        if response is None:
            logger.info("No response from decontextualizer")
            self.handler.requires_decontextualization = False
            self.handler.decontextualized_query = self.handler.query
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            return
        elif "requires_decontextualization" not in response:
            error_msg = f"Missing 'requires_decontextualization' key in response: {response}"
            logger.error(error_msg)
            if CONFIG.should_raise_exceptions():
                raise KeyError(f"Decontextualization failed: {error_msg}")
            else:
                # Fallback in production mode
                self.handler.requires_decontextualization = False
                self.handler.decontextualized_query = self.handler.query
                await self.handler.state.precheck_step_done(self.STEP_NAME)
                return
        elif (response["requires_decontextualization"] == "True"):
            self.handler.requires_decontextualization = True
            self.handler.abort_fast_track_event.set()  # Use event instead of flag
            self.handler.decontextualized_query = response["decontextualized_query"]
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            message = {
                "message_type": "decontextualized_query",
                "decontextualized_query": self.handler.decontextualized_query,
                "original_query": self.handler.query
            }
            logger.info(f"Sending decontextualized query: {self.handler.decontextualized_query}")
            await self.handler.send_message(message)
        else:
            logger.info("No decontextualization required despite previous query")
            self.handler.decontextualized_query = self.handler.query
            await self.handler.state.precheck_step_done(self.STEP_NAME)
        return

class ContextUrlDecontextualizer(PrevQueryDecontextualizer):
    
    DECONTEXTUALIZE_QUERY_PROMPT_NAME = "DecontextualizeContextPrompt"
     
    def __init__(self, handler):    
        super().__init__(handler)
        self.context_url = handler.context_url
        self.retriever = self.retriever()

    def retriever(self):
        return retriever.DBItemRetriever(self.handler)  

    async def do(self):
        # Check if decontextualization is enabled in config
        if not CONFIG.is_decontextualize_enabled():
            logger.info("Decontextualization is disabled in config, skipping")
            self.handler.decontextualized_query = self.handler.query
            self.handler.requires_decontextualization = False
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            return
        
        response = await self.run_prompt(self.DECONTEXTUALIZE_QUERY_PROMPT_NAME, level="high", verbose=False)
        if response is None:
            self.handler.requires_decontextualization = False
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            return
        await self.retriever.do()
        item = self.retriever.handler.context_item
        if (item is None):
            self.handler.requires_decontextualization = False
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            return
        else:
            (url, schema_json, name, site) = item
            self.context_description = json.dumps(trim_json(schema_json))
            self.handler.context_description = self.context_description
            response = await self.run_prompt(self.DECONTEXTUALIZE_QUERY_PROMPT_NAME, verbose=True)
            self.handler.requires_decontextualization = True
            self.handler.abort_fast_track_event.set()  # Use event instead of flag
            self.handler.decontextualized_query = response["decontextualized_query"]
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            
            # Send decontextualized query message if it's different from the original
            if self.handler.decontextualized_query != self.handler.query:
                message = {
                    "message_type": "decontextualized_query",
                    "decontextualized_query": self.handler.decontextualized_query,
                    "original_query": self.handler.query
                }
                logger.info(f"Sending decontextualized query: {self.handler.decontextualized_query}")
                await self.handler.send_message(message)
            return

class FullDecontextualizer(ContextUrlDecontextualizer):
    
    DECONTEXTUALIZE_QUERY_PROMPT_NAME = "FullDecontextualizePrompt"

    def __init__(self, handler):
       super().__init__(handler)
