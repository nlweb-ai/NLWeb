from core.baseHandler import NLWebHandler
from core.retriever import search
from retrieval_providers.hnswlib_client import HnswlibClient
from core.embedding import get_embedding
from core.whoRanking import WhoRanking
from core.config import CONFIG
from misc.logger.logging_config_helper import get_configured_logger

# Who handler is work in progress for answering questions about who
# might be able to answer a given query

logger = get_configured_logger("who_handler")

class WhoHandler (NLWebHandler) :

    def __init__(self, query_params, http_handler): 
        # Remove site parameter - we'll search all sites
        if 'site' in query_params:
            del query_params['site']
        
        # Check if hnswlib is enabled
        hnswlib_config = CONFIG.retrieval_endpoints.get('hnswlib', {})
        self.use_hnswlib = getattr(hnswlib_config, 'enabled', False)
        
        if self.use_hnswlib:
            # Force hnswlib backend for who queries if enabled
            query_params['retrieval_backend'] = 'hnswlib'
            logger.info("Using hnswlib backend for who query")
        else:
            # Use default retrieval backend
            logger.info("Using default retrieval backend for who query (hnswlib not enabled)")
            
        # Keep prev_queries if provided for context, but don't use 'prev' format
        # The who handler can use previous queries to understand follow-up questions
        if 'prev' in query_params:
            del query_params['prev']
        # Keep prev_queries for context if provided
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
            if self.use_hnswlib:
                # Use cached hnswlib client for who queries
                hnswlib_client = HnswlibClient.get_instance(endpoint_name='hnswlib')
                
                # Search across all sites using search_all_sites
                # Pass model in query_params to use the large embedding model
                items = await hnswlib_client.search_all_sites(
                    self.query,
                    num_results=50,
                    query_params={'model': 'text-embedding-3-large'}
                )
                
                self.final_retrieved_items = items
                logger.info(f"Who ranking retrieved {len(items)} items from hnswlib")
            else:
                # Use the general search method (original path)
                logger.info("Using general search method for who query")
                
                # Search across all available sites
                # Note: This will use whatever retrieval backend is configured as default
                items = await search(
                    self.query, 
                    site=None,  # No specific site - search all
                    query_params=self.query_params,
                    num_results=50
                )
                self.final_retrieved_items = items
                logger.info(f"Who ranking retrieved {len(items)} items from general search")
            
            logger.debug(f"Who retrieval complete: {len(self.final_retrieved_items)} items retrieved")
            
            # Use simplified WHO ranking - no decontextualization needed
            self.ranker = WhoRanking(self, self.final_retrieved_items, level="high")
            await self.ranker.do()
            
            logger.info("Who ranking completed")
            logger.debug("Who ranking complete")
            return self.return_value  
                
        except Exception as e:
            raise
        