# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains code for the 'generate answer' path, which provides
a flow that is more similar to RAG.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import aiohttp
import asyncio
from core.baseHandler import NLWebHandler
from core.llm import ask_llm
from core.prompts import PromptRunner
from core.retriever import search
from core.prompts import find_prompt, fill_prompt
from core.utils.json_utils import trim_json, trim_json_hard
from misc.logger.logging_config_helper import get_configured_logger
from core.utils.utils import log
from typing import Dict, List, Optional, Tuple, Any
import core.query_analysis.analyze_query as analyze_query
import core.query_analysis.relevance_detection as relevance_detection
import core.query_analysis.memory as memory
import core.query_analysis.required_info as required_info
import json
import traceback
import os

logger = get_configured_logger("generate_answer")

class GenerateAnswer(NLWebHandler):

    GATHER_ITEMS_THRESHOLD = 55
    DISTANCE_RANKING_THRESHOLD = 100
     
    RANKING_PROMPT_NAME = "RankingPromptForGenerate"
    DISTANCE_RANKING_PROMPT_NAME = "DistanceRankingPromptForGenerate"

    SYNTHESIZE_PROMPT_NAME_NO_LOCATION = "SynthesizePromptForGenerateNoLocation"
    SYNTHESIZE_PROMPT_NAME = "SynthesizePromptForGenerate"
    DESCRIPTION_PROMPT_NAME = "DescriptionPromptForGenerate"

    def __init__(self, query_params, handler):
        super().__init__(query_params, handler)
        self.items = []
        self._results_lock = asyncio.Lock()  # Add lock for thread-safe operations
        logger.info(f"GenerateAnswer initialized with query_params: {query_params}")
        log(f"GenerateAnswer query_params: {query_params}")

        self.azure_maps_api_key = os.environ["AZURE_MAPS_API_KEY"] 
        self.azure_maps_client_id = os.environ["AZURE_MAPS_CLIENT_ID"] 
        self.azure_maps_base_url = os.environ["AZURE_MAPS_ENDPOINT"] 

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "x-ms-client-id": self.azure_maps_client_id,
            "subscription-key": self.azure_maps_api_key
        }

    async def runQuery(self):
        try:
            logger.info(f"Starting query execution for conversation_id: {self.conversation_id}")
            await self.prepare()
            if (self.query_done):
                logger.info("Query done prematurely")
                return
            await self.get_ranked_answers()            
            logger.info(f"Query execution completed for conversation_id: {self.conversation_id}")
            return 
        except Exception as e:
            logger.exception(f"Error in runQuery: {e}")
            traceback.print_exc()
            raise
    
    async def prepare(self):
        # runs the tasks that need to be done before retrieval, ranking, etc.
        logger.info("Starting preparation phase")
        tasks = []
        
        # Adding all necessary preparation tasks
        tasks.append(asyncio.create_task(analyze_query.DetectItemType(self).do()))
        tasks.append(asyncio.create_task(self.decontextualizeQuery().do()))
        tasks.append(asyncio.create_task(relevance_detection.RelevanceDetection(self).do()))
        tasks.append(asyncio.create_task(memory.Memory(self).do()))
        tasks.append(asyncio.create_task(required_info.RequiredInfo(self).do()))
         
        try:
            logger.debug(f"Running {len(tasks)} preparation tasks concurrently")
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"Error during preparation tasks: {e}")
        finally:
            self.pre_checks_done_event.set()  # Signal completion regardless of errors
            self.state.set_pre_checks_done()
            
        logger.info("Preparation phase completed")
   
    async def rankItem(self, url, json_str, name, site):
        if not self.connection_alive_event.is_set():
            logger.warning("Connection lost, skipping item ranking")
            return
            
        try:
            logger.debug(f"Ranking item: {name} from {site}")
            prompt_str, ans_struc = find_prompt(site, self.item_type, self.RANKING_PROMPT_NAME)
            description = trim_json_hard(json_str)
            prompt = fill_prompt(prompt_str, self, {"item.description": description})
            logger.debug(f"Sending ranking request to LLM for item: {name}")
            ranking = await ask_llm(prompt, ans_struc, level="low", query_params=self.query_params)
            logger.debug(f"Received ranking score: {ranking.get('score', 'N/A')} for item: {name}")
            ansr = {
                'url': url,
                'site': site,
                'name': name,
                'ranking': ranking,
                'schema_object': json.loads(json_str),
                'sent': False,
            }
            
            if (ranking["score"] > self.GATHER_ITEMS_THRESHOLD):
                logger.info(f"High score item: {name} (score: {ranking['score']})")
                async with self._results_lock:  # Thread-safe append
                    self.final_ranked_answers.append(ansr)
                    
        except Exception as e:
            logger.error(f"Error in rankItem: {e}")
            logger.debug("Full error trace: ", exc_info=True)

    async def get_ranked_answers(self):
        logger.info("Starting retrieval and ranking process")
        try:
            # Wait for retrieval to be done if not already
            logger.info("Retrieving items for query")
            top_embeddings = await search(
                self.decontextualized_query, 
                self.site,
                query_params=self.query_params
            )
            self.items = top_embeddings  # Store all retrieved items
            logger.debug(f"Retrieved {len(top_embeddings)} items from database")
            # Rank each item
            tasks = []
            for url, json_str, name, site in top_embeddings:
                tasks.append(asyncio.create_task(self.rankItem(url, json_str, name, site)))
                        
            logger.debug(f"Running {len(tasks)} ranking tasks concurrently")
            await asyncio.gather(*tasks, return_exceptions=True)

            synthesizePrompt = self.SYNTHESIZE_PROMPT_NAME
            allowEmptyAnswers = False

            distanceRankingResponse = await PromptRunner(self).run_prompt(self.DISTANCE_RANKING_PROMPT_NAME) 

            if (distanceRankingResponse):
                
                score = int(distanceRankingResponse.get("score", 0)) 
                logger.debug(f"Distance ranking score: {score}")

                if score >= self.DISTANCE_RANKING_THRESHOLD:

                    location = distanceRankingResponse.get("location")      

                    if not location:
                        self.final_ranked_answers = []  # Clear ranked answers if we can't do distance ranking
                        synthesizePrompt = self.SYNTHESIZE_PROMPT_NAME_NO_LOCATION                     
                        allowEmptyAnswers = True  # Allow empty answers if we can't do distance ranking
                        return
                                                   
                    countryRegion = distanceRankingResponse.get("countryRegion")
    
                    if location and countryRegion:
                        await self.doDistanceRanking(location, countryRegion)

                           
            # Synthesize the answer from ranked items
            logger.info("Ranking completed, synthesizing answer")
            await self.synthesizeAnswer(allowEmptyAnswers, synthesizePrompt)
            
        except Exception as e:
            logger.exception(f"Error in get_ranked_answers: {e}")
            raise

    async def get_ranked_answers(self):

        logger.info("Starting retrieval and ranking process")

        try:

            # Wait for retrieval to be done if not already

            logger.info("Retrieving items for query")

            top_embeddings = await search(

                self.decontextualized_query,

                self.site,

                query_params=self.query_params

            )

            self.items = top_embeddings  # Store all retrieved items

            logger.debug(f"Retrieved {len(top_embeddings)} items from database")

            # Rank each item

            tasks = []

            for url, json_str, name, site in top_embeddings:
                tasks.append(asyncio.create_task(self.rankItem(url, json_str, name, site)))

            logger.debug(f"Running {len(tasks)} ranking tasks concurrently")

            await asyncio.gather(*tasks, return_exceptions=True)

            # Once first-pass ranking is done, check if we should do distance-based ranking

            allowEmptyAnswers = False
            promptName = self.SYNTHESIZE_PROMPT_NAME
            
            distanceRankingResponse = await PromptRunner(self).run_prompt(self.DISTANCE_RANKING_PROMPT_NAME)
 
            if (distanceRankingResponse):

                score = int(distanceRankingResponse.get("score", 0))

                logger.debug(f"Distance Ranking Prompt score: {score}")

                if score >= self.DISTANCE_RANKING_THRESHOLD:

                    location = distanceRankingResponse.get("location")

                    if not location:
                        self.final_ranked_answers = []  # Clear ranked answers if we can't do distance ranking    
                        promptName = self.SYNTHESIZE_PROMPT_NAME_NO_LOCATION  # Use no-location prompt for synthesis
                        allowEmptyAnswers = True  # Allow empty answers if we can't do distance ranking   
                        
                    else:                        
                        countryRegion = distanceRankingResponse.get("countryRegion")

                        if location and countryRegion:
                            await self.do_distance_ranking(location, countryRegion)
                        else:                        
                            logger.error("Distance Ranking Prompt did not return valid location and/or countryRegion")

            else:
                logger.error("No Distance Ranking response received")


            # Synthesize the answer from ranked items

            logger.info("Ranking completed, synthesizing answer")            
            await self.synthesizeAnswer(allowEmptyAnswers, promptName)  


        except Exception as e:

            logger.exception(f"Error in get_ranked_answers: {e}")
            raise

 
    async def do_distance_ranking(self, location: str, country_region: str):
        """Main entry point to rank results by travel time."""
        logger.debug(f"Starting distance ranking for: {location}, {country_region}")

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Geocode the source
                source_coords = await self._get_source_coordinates(session, location, country_region)
                if not source_coords:
                    return

                # 2. Extract and validate destinations
                destinations, valid_items = self._extract_destination_coordinates()
                if not destinations:
                    return

                # 3. Get Matrix Data
                matrix_results = await self._get_route_matrix(session, source_coords, destinations)
                
                # 4. Process and Sort
                if matrix_results:
                    self._rank_and_update_results(matrix_results, valid_items)

        except Exception as e:
            logger.exception(f"Critical error in do_distance_ranking: {e}")
            raise

    async def _get_source_coordinates(self, session: aiohttp.ClientSession, location: str, country_region: str) -> Optional[Tuple[float, float]]:
        # 1. Use 'query' instead of 'locality' to find both Cities and Districts
        # 2. Added 'entityType=PopulatedPlace' to filter out irrelevant POIs
        url = f"{self.azure_maps_base_url}/geocode?api-version=2025-01-01&query={location}, {country_region}&entityType=PopulatedPlace"
                
        async with session.get(url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status != 200:
                logger.error(f"Geocoding failed for {location}: Status {response.status}")
                return None
            
            data = await response.json()
            features = data.get("features", [])
            if not features:
                return None

            # Helper to calculate the area of the bounding box
            def get_bbox_area(feature):
                bbox = feature.get("bbox")
                if not bbox or len(bbox) < 4:
                    return float('inf')  # Treat features without bbox as least specific
                # bbox is [minLon, minLat, maxLon, maxLat]
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                return width * height

            # Find the feature with the SMALLEST bounding box.
            # This identifies the specific town/city rather than the broad administrative district.
            selected_feature = min(features, key=get_bbox_area)
            
            coords = selected_feature["geometry"]["coordinates"]
            # Azure Maps returns [longitude, latitude]
            return (coords[0], coords[1])

    def _extract_destination_coordinates(self) -> Tuple[List[List[float]], List[Dict]]:
        """Parses self.final_ranked_answers for valid geo strings."""
        dest_list = []
        valid_items = []

        for item in self.final_ranked_answers:
            schema = item.get("schema_object") or {}

            # Possible lat/long fields to check
            fields_to_check = ["geo", "location", "announcementLocation"]

            geo = None
            for field in fields_to_check:
                value = schema.get(field)
                # Check if the field exists and contains a comma
                if value and isinstance(value, str) and "," in value:
                    geo = value
                    break
        
            if not geo:
                continue

            try:
                lat, lon = [float(val.strip()) for val in geo.split(",")]
                # Azure Matrix API uses [longitude, latitude]
                dest_list.append([lon, lat])
                valid_items.append(item)
            except (ValueError, AttributeError):
                logger.warning(f"Malformed geo data for item: {item.get('name')}")
                continue

        return dest_list, valid_items

    async def _get_route_matrix(self, session: aiohttp.ClientSession, origin: Tuple[float, float], destinations: List[List[float]]) -> Optional[List[Dict]]:
        """Calls the Azure Maps Synchronous Route Matrix API."""
        matrix_url = f"{self.azure_maps_base_url}/route/matrix/sync/json?api-version=1.0&routeType=shortest"
        matrix_body = {
            "origins": {"type": "MultiPoint", "coordinates": [origin]},
            "destinations": {"type": "MultiPoint", "coordinates": destinations}
        }

        async with session.post(matrix_url, json=matrix_body, headers=self._headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("matrix", [[]])[0] # Return the first origin row
            
            logger.error(f"Matrix API failed: Status {response.status}")
            return None

    def _rank_and_update_results(self, matrix_results: List[Dict], valid_items: List[Dict]):
        """Combines matrix results with original data and sorts them."""
        ranked_results = []

        for i, route in enumerate(matrix_results):
            if route.get("statusCode") == 200:
                summary = route.get("response", {}).get("routeSummary", {})
                travel_time = summary.get("travelTimeInSeconds", float('inf'))
                ranked_results.append((valid_items[i], travel_time))

        # Sort by travel time (ascending)
        ranked_results.sort(key=lambda x: x[1])

        if ranked_results:
            self.final_ranked_answers = [
                {
                    "url": data["url"],
                    "site": data["site"],
                    "name": data["name"],
                    "score": "100", # Maintaining original static score
                    "description": f"Travel time in seconds: {time}",
                    "schema_object": data["schema_object"]
                }
                for data, time in ranked_results
            ]
            logger.debug(f"Successfully ranked {len(self.final_ranked_answers)} items.")

    async def getDescription(self, url, json_str, query, answer, name, site):
        try:
            logger.debug(f"Getting description for item: {name}")
            description = await PromptRunner(self).run_prompt(self.DESCRIPTION_PROMPT_NAME)
            logger.debug(f"Got description for item: {name}")
            return (url, name, site, description["description"], json_str)
        except Exception as e:
            logger.error(f"Error getting description for {name}: {str(e)}")
            logger.debug("Full error trace: ", exc_info=True)
            raise
    
    async def synthesizeAnswer(self, allowEmptyAnswers=False, promptName=SYNTHESIZE_PROMPT_NAME): 
        if not self.connection_alive_event.is_set():
            logger.warning("Connection lost, skipping answer synthesis")
            return
            
        try:
            logger.info("Starting answer synthesis")
            
            # Check if we have any ranked answers to work with
            if not self.final_ranked_answers and not allowEmptyAnswers:
                logger.warning("No ranked answers found, sending empty response")
                message = {
                    "message_type": "nlws",
                    "@type": "GeneratedAnswer",
                    "answer": "I couldn't find relevant information to answer your question.", 
                    "items": []
                }
                await self.send_message(message)
                return
                
            response = await PromptRunner(self).run_prompt(promptName, timeout=100, verbose=True)
            logger.debug(f"Synthesis response received")
            
            json_results = []
            description_tasks = []
                        
            answer = response.get("answer", "Something has gone wrong")
            
            # Create initial message with just the answer
            message = {"message_type": "nlws", "@type": "GeneratedAnswer", "answer": answer, "items": json_results}
            logger.info("Sending initial answer")
            await self.send_message(message)
                                       
        except Exception as e:
            logger.exception(f"Error in synthesizeAnswer: {e}")
            if self.connection_alive_event.is_set():
                try:
                    error_msg = {"message_type": "nlws", "@type": "GeneratedAnswer", "answer": "I encountered an error while generating your answer. Please try again.", "items": []}
                    await self.send_message(error_msg)
                except:
                    pass
            raise