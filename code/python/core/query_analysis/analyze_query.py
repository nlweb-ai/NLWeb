# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the methods for analyzing the query to determine the 
type of item being sought, whether there are multiple types of items being
sought, etc.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from core.prompts import PromptRunner

import asyncio
from core.config import CONFIG

from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("analyze_query")


class DetectItemType(PromptRunner):
    ITEM_TYPE_PROMPT_NAME = "DetectItemTypePrompt"
    STEP_NAME = "DetectItemType"

    def __init__(self, handler):
        super().__init__(handler)
        # Use async version
        self.handler.state.start_precheck_step(self.STEP_NAME)

    async def do(self):
        if not CONFIG.is_analyze_query_enabled():
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            logger.info("Analyze query is disabled in config, skipping DetectItemType")
            return
        # Check if item_type is already set to Statistics from site mapping
        current_item_type = getattr(self.handler, 'item_type', '')
        if isinstance(current_item_type, str) and '}' in current_item_type:
            current_item_type = current_item_type.split('}')[1]
            
        if current_item_type == "Statistics":
            logger.info(f"Item type already set to Statistics from site mapping, skipping DetectItemType")
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            return {"item_type": "Statistics"}
            
        response = await self.run_prompt(self.ITEM_TYPE_PROMPT_NAME, level="low")
        if (response):
            logger.debug(f"DetectItemType response: {response}")
            self.handler.item_type = response['item_type']
        else:
            logger.warning("No response from DetectItemTypePrompt, item_type will not be set")
        await self.handler.state.precheck_step_done(self.STEP_NAME)
        return response

class DetectMultiItemTypeQuery(PromptRunner):
    MULTI_ITEM_TYPE_QUERY_PROMPT_NAME = "DetectMultiItemTypeQueryPrompt"
    STEP_NAME = "DetectMultiItemTypeQuery"

    def __init__(self, handler):
        super().__init__(handler)
        self.handler.state.start_precheck_step(self.STEP_NAME)

    async def do(self):
        if not CONFIG.is_analyze_query_enabled():
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            logger.info("Analyze query is disabled in config, skipping DetectMultiItemTypeQuery")
            return
        response = await self.run_prompt(self.MULTI_ITEM_TYPE_QUERY_PROMPT_NAME, level="low")
        logger.debug(f"DetectMultiItemTypeQuery response: {response}")
        await self.handler.state.precheck_step_done(self.STEP_NAME)
        return response

class DetectQueryType(PromptRunner):
    DETECT_QUERY_TYPE_PROMPT_NAME = "DetectQueryTypePrompt"
    STEP_NAME = "DetectQueryType"

    def __init__(self, handler):
        super().__init__(handler)
        self.handler.state.start_precheck_step(self.STEP_NAME)

    async def do(self):
        if not CONFIG.is_analyze_query_enabled():
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            logger.info("Analyze query is disabled in config, skipping DetectQueryType")
            return
        response = await self.run_prompt(self.DETECT_QUERY_TYPE_PROMPT_NAME, level="low")
        logger.debug(f"DetectQueryType response: {response}")
        await self.handler.state.precheck_step_done(self.STEP_NAME)
        return response
