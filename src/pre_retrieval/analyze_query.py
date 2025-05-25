# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the methods for analyzing the query to determine the 
type of item being sought, whether there are multiple types of items being
sought, etc.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from prompts.prompt_runner import PromptRunner
import asyncio

class DetectItemType(PromptRunner):
    ITEM_TYPE_PROMPT_NAME = "DetectItemTypePrompt"
    STEP_NAME = "DetectItemType"

    def __init__(self, handler):
        super().__init__(handler)
        # Use async version
        self.handler.state.start_precheck_step(self.STEP_NAME)

    async def do(self):
        response = await self.run_prompt(self.ITEM_TYPE_PROMPT_NAME, level="low")
        if (response):
            self.handler.item_type = response['item_type']
        await self.handler.state.precheck_step_done(self.STEP_NAME)
        return response

class DetectMultiItemTypeQuery(PromptRunner):
    MULTI_ITEM_TYPE_QUERY_PROMPT_NAME = "DetectMultiItemTypeQueryPrompt"
    STEP_NAME = "DetectMultiItemTypeQuery"

    def __init__(self, handler):
        super().__init__(handler)
        self.handler.state.start_precheck_step(self.STEP_NAME)

    async def do(self):
        response = await self.run_prompt(self.MULTI_ITEM_TYPE_QUERY_PROMPT_NAME, level="low")
        await self.handler.state.precheck_step_done(self.STEP_NAME)
        return response

class DetectQueryType(PromptRunner):
    DETECT_QUERY_TYPE_PROMPT_NAME = "DetectQueryTypePrompt"
    STEP_NAME = "DetectQueryType"

    def __init__(self, handler):
        super().__init__(handler)
        self.handler.state.start_precheck_step(self.STEP_NAME)

    async def do(self):
        response = await self.run_prompt(self.DETECT_QUERY_TYPE_PROMPT_NAME, level="low")
        await self.handler.state.precheck_step_done(self.STEP_NAME)
        return response
