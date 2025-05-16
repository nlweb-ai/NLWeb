# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the methods for checking if we have the required information.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from utils.logger import get_logger, LogLevel
from prompts.prompt_runner import PromptRunner

# Create a logger for this module
logger = get_logger("required_info")

class RequiredInfo(PromptRunner):
    """For some sites, we will need to make sure that we have enough information, either from the user
       or context, before we process the query. This class is used to check if we have the required information."""

    REQUIRED_INFO_PROMPT_NAME = "RequiredInfoPrompt"
    STEP_NAME = "RequiredInfo"
    
    def __init__(self, handler):
        logger.debug(f"Initializing RequiredInfo for handler: {handler.__class__.__name__}")
        super().__init__(handler)
        self.handler.state.start_precheck_step(self.STEP_NAME)
        logger.info(f"Started precheck step: {self.STEP_NAME}")

    async def do(self):
        logger.info(f"Running required info check with prompt: {self.REQUIRED_INFO_PROMPT_NAME}")
        response = await self.run_prompt(self.REQUIRED_INFO_PROMPT_NAME, level="high")
        
        if response:
            logger.debug(f"Required info prompt response received: {response}")
            self.handler.required_info_found = response["required_info_found"] == "True"
            
            if not self.handler.required_info_found:
                logger.info("Required information not found, will ask user for more details")
                self.handler.query_done = True
                self.handler.abort_fast_track_event.set()  # Use event instead of flag
                
                logger.debug(f"Sending ask_user message: {response['user_question']}")
                await self.handler.send_message({"message_type": "ask_user", "message": response["user_question"]})
                
                logger.info(f"Precheck step complete: {self.STEP_NAME} (missing required info)")
                await self.handler.state.precheck_step_done(self.STEP_NAME)
                return
            else:
                logger.info("Required information found, proceeding with query")
        else:
            logger.warning("No response from required info prompt, assuming info is present")
            self.handler.required_info_found = True
            self.handler.user_question = ""
        
        logger.info(f"Precheck step complete: {self.STEP_NAME} (required info available)")
        await self.handler.state.precheck_step_done(self.STEP_NAME)