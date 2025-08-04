# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file is used to rewrite complex queries into simpler keyword queries
for traditional keyword-based search engines.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from core.prompts import PromptRunner
import asyncio
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("query_rewrite")


class QueryRewrite(PromptRunner):
    
    QUERY_REWRITE_PROMPT_NAME = "QueryRewrite"
    STEP_NAME = "QueryRewrite"
    
    def __init__(self, handler):
        super().__init__(handler)
        self.handler.state.start_precheck_step(self.STEP_NAME)
        
    async def do(self):
        """
        Rewrite the decontextualized query into simpler keyword queries.
        The results are stored in handler.rewritten_queries.
        """
        logger.info(f"Starting query rewrite for: {self.handler.decontextualized_query}")
        
        try:
            # Run the query rewrite prompt
            response = await self.run_prompt(self.QUERY_REWRITE_PROMPT_NAME, level="high")
            
            if not response:
                logger.warning("No response from QueryRewrite prompt, using original query")
                self.handler.rewritten_queries = [self.handler.decontextualized_query]
                await self.handler.state.precheck_step_done(self.STEP_NAME)
                return
            
            # Extract the rewritten queries from the response
            rewritten_queries = response.get("rewritten_queries", [])
            query_count = response.get("query_count", 0)
            
            # Validate the response
            if not rewritten_queries or not isinstance(rewritten_queries, list):
                logger.warning("Invalid response from QueryRewrite prompt, using original query")
                self.handler.rewritten_queries = [self.handler.decontextualized_query]
            else:
                # Filter out any empty queries and ensure they are strings
                valid_queries = [q for q in rewritten_queries if q and isinstance(q, str) and q.strip()]
                
                if not valid_queries:
                    logger.warning("No valid rewritten queries, using original query")
                    self.handler.rewritten_queries = [self.handler.decontextualized_query]
                else:
                    # Limit to 5 queries maximum
                    self.handler.rewritten_queries = valid_queries[:5]
                    logger.info(f"Generated {len(self.handler.rewritten_queries)} rewritten queries: {self.handler.rewritten_queries}")
            
            # Send a message to the client about the rewritten queries
            if hasattr(self.handler, 'rewritten_queries') and len(self.handler.rewritten_queries) > 1:
                message = {
                    "message_type": "query_rewrite",
                    "original_query": self.handler.decontextualized_query,
                    "rewritten_queries": self.handler.rewritten_queries,
                    "query_id": self.handler.query_id
                }
                await self.handler.send_message(message)
                
        except Exception as e:
            logger.error(f"Error during query rewrite: {e}")
            # On error, fall back to using the original query
            self.handler.rewritten_queries = [self.handler.decontextualized_query]
            
        finally:
            # Always mark the step as done
            await self.handler.state.precheck_step_done(self.STEP_NAME)