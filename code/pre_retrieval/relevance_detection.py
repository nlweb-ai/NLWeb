# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the methods for detecting if the query is irrelevant to the site.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from prompts.prompt_runner import PromptRunner


# NOTE : RelevanceDetection is turned off as a default, for now. 
# Turn it on by changing the value of the following variable.

RELEVANCE_DETECTION_ENABLED = False

class RelevanceDetection(PromptRunner):

    RELEVANCE_PROMPT_NAME = "DetectIrrelevantQueryPrompt"
    STEP_NAME = "Relevance"
    
    def __init__(self, handler):
        super().__init__(handler)
        self.handler.state.start_precheck_step(self.STEP_NAME)

    async def do(self):
        if not RELEVANCE_DETECTION_ENABLED:
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            return

        if (self.handler.site == 'all' or self.handler.site == 'nlws'):
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            return
        response = await self.run_prompt(self.RELEVANCE_PROMPT_NAME, level="high")
        if (not response):
            await self.handler.state.precheck_step_done(self.STEP_NAME)
            return
        self.site_is_irrelevant_to_query = response["site_is_irrelevant_to_query"]
        self.explanation_for_irrelevance = response["explanation_for_irrelevance"]
        if (self.site_is_irrelevant_to_query == "True"):
            message = {"message_type": "site_is_irrelevant_to_query", "message": self.explanation_for_irrelevance}
            self.handler.query_is_irrelevant = True
            self.handler.query_done = True
            self.handler.abort_fast_track_event.set()  # Use event instead of flag
            await self.handler.send_message(message)
        else:
            self.handler.query_is_irrelevant = False
        await self.handler.state.precheck_step_done(self.STEP_NAME)
