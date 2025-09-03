# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Simplified WHO ranking for site selection.
"""

from core.utils.utils import log
from core.llm import ask_llm
import asyncio
import json
from core.utils.json_utils import trim_json
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("who_ranking_engine")


class WhoRanking:
    
    EARLY_SEND_THRESHOLD = 59
    NUM_RESULTS_TO_SEND = 10

    def __init__(self, handler, items, level="high"):
        logger.info(f"Initializing WHO Ranking with {len(items)} items")
        self.handler = handler
        self.level = level  # Always use high level for WHO ranking
        self.items = items
        self.num_results_sent = 0
        self.rankedAnswers = []

    def get_ranking_prompt(self, query, site_description):
        """Construct the WHO ranking prompt with the given query and site description."""
        prompt = f"""Assign a score between 0 and 100 to the following site based on how relevant the site may be to answering the user's question.

The user's question is: {query}

The site's description is: {site_description}

Additionally, if this site is relevant (score > 50), provide an optimized query that should be sent to this specific site. The query should be tailored to:
- Match the site's specific domain and expertise
- Extract the most relevant information from that site
- Be more specific than the original query when appropriate

For example, if the user asks "I need to make bread" and the site is about:
- Kitchen equipment: rewrite to "bread making equipment" or "bread baking tools"
- Ingredients/groceries: rewrite to "bread ingredients" or "flour yeast for bread"
- Recipes: keep as "bread recipes" or just "bread"

If the original query is already well-suited for the site, use the original query."""
        
        response_structure = {
            "score": "integer between 0 and 100",
            "description": "short description of why this site is relevant",
            "query": "the optimized query to send to this site (only if score > 50)"
        }
        
        return prompt, response_structure

    async def rankItem(self, url, json_str, name, site):
        """Rank a single site for relevance to the query."""
        try:
            description = trim_json(json_str)
            prompt, ans_struc = self.get_ranking_prompt(self.handler.query, description)
            ranking = await ask_llm(prompt, ans_struc, level=self.level, query_params=self.handler.query_params)
            
            # Ensure ranking has required fields (handle LLM failures/timeouts)
            if not ranking or not isinstance(ranking, dict):
                ranking = {"score": 0, "description": "Failed to rank", "query": self.handler.query}
            if "score" not in ranking:
                ranking["score"] = 0
            if "query" not in ranking:
                ranking["query"] = self.handler.query
            
            # Log the LLM score
            print(f"LLM Score: {site} - {name}: {ranking.get('score', 0)} - {ranking.get('description', 'No description')}")
            
            # Handle both string and dictionary inputs for json_str
            schema_object = json_str if isinstance(json_str, dict) else json.loads(json_str)
            
            # Store the result
            ansr = {
                'url': url,
                'site': site,
                'name': name,
                'ranking': ranking,
                'schema_object': schema_object,
                'sent': False,
            }
            
            # Send immediately if high score
            if ranking.get("score", 0) > self.EARLY_SEND_THRESHOLD:
                logger.info(f"High score site: {name} (score: {ranking['score']}) - sending early")
                await self.sendAnswers([ansr])
            
            self.rankedAnswers.append(ansr)
            logger.debug(f"Site {name} added to ranked answers")
        
        except Exception as e:
            logger.error(f"Error in rankItem for {name}: {str(e)}")
            logger.debug(f"Full error trace: ", exc_info=True)
            # Still add the item with a zero score so we don't lose it completely
            try:
                schema_object = json_str if isinstance(json_str, dict) else json.loads(json_str)
                ansr = {
                    'url': url,
                    'site': site,
                    'name': name,
                    'ranking': {"score": 0, "description": f"Error: {str(e)}", "query": self.handler.query},
                    'schema_object': schema_object,
                    'sent': False,
                }
                self.rankedAnswers.append(ansr)
            except:
                pass  # Skip this item entirely if we can't even create a basic record

    async def sendAnswers(self, answers, force=False):
        """Send ranked sites to the client."""
        json_results = []
        
        for result in answers:
            # Stop if we've already sent enough
            if self.num_results_sent + len(json_results) >= self.NUM_RESULTS_TO_SEND:
                logger.info(f"Stopping at {len(json_results)} results to avoid exceeding limit of {self.NUM_RESULTS_TO_SEND}")
                break
            
            # Extract site type from schema_object
            schema_obj = result.get("schema_object", {})
            site_type = schema_obj.get("@type", "Website")
            
            result_item = {
                "@type": site_type,  # Use the actual site type
                "url": result["url"],
                "name": result["name"],
                "score": result["ranking"]["score"]
            }
            
            # Always include query field (required for WHO ranking)
            if "query" in result["ranking"]:
                result_item["query"] = result["ranking"]["query"]
            else:
                # Fallback to original query if no custom query provided
                result_item["query"] = self.handler.query
            
            json_results.append(result_item)
            result["sent"] = True
        
        if json_results:
            to_send = {"message_type": "result", "content": json_results}
            asyncio.create_task(self.handler.send_message(to_send))
            self.num_results_sent += len(json_results)
            logger.info(f"Sent {len(json_results)} results, total sent: {self.num_results_sent}/{self.NUM_RESULTS_TO_SEND}")

    async def do(self):
        """Main execution method - rank all sites concurrently."""
        logger.info(f"Starting WHO ranking process with {len(self.items)} sites")
        
        # Create tasks for all sites
        tasks = []
        for url, json_str, name, site in self.items:
            tasks.append(asyncio.create_task(self.rankItem(url, json_str, name, site)))
        
        # Wait for all ranking tasks to complete
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error during ranking tasks: {str(e)}")
        
        # Filter and sort final results
        filtered = [r for r in self.rankedAnswers if r.get('ranking', {}).get('score', 0) > 50]
        ranked = sorted(filtered, key=lambda x: x.get('ranking', {}).get("score", 0), reverse=True)
        self.handler.final_ranked_answers = ranked[:self.NUM_RESULTS_TO_SEND]
        
        logger.info(f"Filtered to {len(filtered)} results with score > 50")
        
        # Print final ranked results
        print("\n=== Final WHO Ranking Results ===")
        for i, result in enumerate(ranked[:10]):  # Show top 10
            score = result.get('ranking', {}).get('score', 0)
            site = result.get('site', 'unknown')
            name = result.get('name', 'unknown')
            desc = result.get('ranking', {}).get('description', 'No description')
            print(f"{i+1}. [{score}] {site} - {name}: {desc}")
        
        # Send any remaining results that haven't been sent
        results_to_send = [r for r in ranked if not r['sent']][:self.NUM_RESULTS_TO_SEND - self.num_results_sent]
        
        if results_to_send:
            logger.info(f"Sending final batch of {len(results_to_send)} results")
            await self.sendAnswers(results_to_send, force=True)