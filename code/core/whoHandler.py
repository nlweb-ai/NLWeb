from core.baseHandler import NLWebHandler

# Who handler is work in progress for answering questions about who
# might be able to answer a given query



class WhoHandler (NLWebHandler) :

    def __init__(self, query_params, http_handler): 
        super().__init__(query_params, http_handler)
                            
    async def runQuery(self):
        try:
            await self.decontextualizeQuery().do()
            items = await self.retrieve_items(self.decontextualized_query).do()
            sites_in_embeddings = {}
            for url, json_str, name, site in items:
                sites_in_embeddings[site] = sites_in_embeddings.get(site, 0) + 1
            sites = sorted(sites_in_embeddings.items(), key=lambda x: x[1], reverse=True)[:5]
            message = {"message_type": "result", "results": str(sites)}
            await self.sendMessage(message)
            return message
        except Exception as e:
            traceback.print_exc()

    