from core.baseHandler import NLWebHandler
from core.retriever import search
import core.ranking as ranking
from misc.logger.logging_config_helper import get_configured_logger

# Who handler is work in progress for answering questions about who
# might be able to answer a given query

logger = get_configured_logger("who_handler")

class WhoHandler (NLWebHandler) :

    def __init__(self, query_params, http_handler): 
        # Force site to 'endpoints' for who queries
        query_params['site'] = 'nlweb_sites'
        super().__init__(query_params, http_handler)
    
    async def send_message(self, message):
        """Override send_message to ensure URLs point to /ask endpoint with site parameter."""
        # Check if message contains results with URLs
        if isinstance(message, dict):
            # Handle messages with 'content' field (results)
            if 'content' in message and isinstance(message['content'], list):
                for result in message['content']:
                    if 'url' in result:
                        url = result['url']
                        # If URL doesn't start with http:// or https://, convert to /ask endpoint
                        if not url.startswith(('http://', 'https://')):
                            # Use the URL value as the site parameter for /ask endpoint
                            result['url'] = f"http://localhost:8000/ask?site={url}"
                            logger.debug(f"Modified URL from '{url}' to '{result['url']}'")
            
            # Handle single result messages
            elif 'url' in message:
                url = message['url']
                if not url.startswith(('http://', 'https://')):
                    message['url'] = f"http://localhost:8000/ask?site={url}"
                    logger.debug(f"Modified URL from '{url}' to '{message['url']}'")
        
        # Call parent class's send_message with modified message
        await super().send_message(message)

    async def runQuery(self):

        try:        
            items = await search(
                self.query, 
                self.site,
                query_params=self.query_params,
                handler=self
            )
            self.final_retrieved_items = items
            logger.info(f"Who ranking retrieved {len(items)} items")
            logger.debug(f"Who retrieval complete: {len(items)} items retrieved")
            
            # Wait for decontextualization to complete with timeout
            self.state.set_pre_checks_done()
            self.fastTrackRanker = ranking.Ranking(self, items, ranking.Ranking.WHO_RANKING)
            await self.fastTrackRanker.do()
            logger.info("Who ranking completed")
            logger.debug("Who ranking complete")
            return self.return_value  
                
        except Exception as e:
            raise
        