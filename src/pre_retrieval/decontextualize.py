# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the classes for the different levels of decontextualization. 

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import retrieval.retriever as retriever
from utils.trim import trim_json
import json
from prompts.prompt_runner import PromptRunner
from utils.logger import get_logger

logger = get_logger("Decontextualizer")

class NoOpDecontextualizer(PromptRunner):
  
    DECONTEXTUALIZE_QUERY_PROMPT_NAME = "NoOpDecontextualizer"
    STEP_NAME = "Decon"

    def __init__(self, handler):
        super().__init__(handler)
        self.handler.state.start_precheck_step(self.STEP_NAME)
    
    async def do(self):
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
        response = await self.run_prompt(self.DECONTEXTUALIZE_QUERY_PROMPT_NAME, level="high")
        logger.info(f"response: {response}")
        if response is None:
            logger.info("No response from decontextualizer")
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
                "type": "decontextualized_query",
                "decontextualized_query": self.handler.decontextualized_query
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
        response = await self.run_prompt(self.DECONTEXTUALIZE_QUERY_PROMPT_NAME, level="high")
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
            return

class FullDecontextualizer(ContextUrlDecontextualizer):
    
    DECONTEXTUALIZE_QUERY_PROMPT_NAME = "FullDecontextualizePrompt"

    def __init__(self, handler):
       super().__init__(handler)
