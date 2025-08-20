from core.baseHandler import NLWebHandler
import traceback
import core.ranking

# Who handler is work in progress for answering questions about who
# might be able to answer a given query


from core.retriever import search
import core.ranking as ranking
from misc.logger.logging_config_helper import get_configured_logger
import asyncio

logger = get_configured_logger("who_handler")

class WhoHandler (NLWebHandler) :

    def __init__(self, query_params, http_handler): 
        # Force site to 'endpoints' for who queries
        query_params['site'] = 'nlweb_sites'
        super().__init__(query_params, http_handler)

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
            print(f"--- Who retrieval complete: {len(items)} items retrieved")
            
            # Wait for decontextualization to complete with timeout
            self.state.set_pre_checks_done()
            self.fastTrackRanker = ranking.Ranking(self, items, ranking.Ranking.WHO_RANKING)
            await self.fastTrackRanker.do()
            logger.info("Who ranking completed")
            print("--- Who ranking complete")
            return self.return_value  
                
        except Exception as e:
            raise
        