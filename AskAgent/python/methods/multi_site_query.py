# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Multi-Site Query Handler for aggregating results from multiple sites.

This handler:
1. Uses /who endpoint to identify relevant sites for a query (streaming)
2. Queries sites asynchronously as they arrive using ask_nlweb_server
3. Streams results back to browser as they become available
4. Sends progress updates

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import time
from typing import Dict, Any, List
from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG
from core.utils.nlweb_client import sites_from_who_streaming, ask_nlweb_streaming

logger = get_configured_logger("multi_site_query")

class MultiSiteQueryHandler:
    """Handler for multi-site query aggregation."""
    
    def __init__(self, params, handler):
        print(f"\n[MULTI-SITE-HANDLER] Initializing with query: {handler.query}")
        print(f"[MULTI-SITE-HANDLER] Params: {params}")
        self.handler = handler
        self.params = params
        self.query = handler.query
        self.top_k_sites = params.get('top_k_sites', 10)
        self.results_per_site = params.get('results_per_site', 5)
        self.final_top_k = params.get('final_top_k', 100)
        
        # Track sites and results
        self.sites_queried = 0
        self.sites_successful = 0
        self.sites_failed = 0
        self.total_results_sent = 0
        self.active_tasks: List[asyncio.Task] = []
        self.site_results: Dict[str, int] = {}  # Track results per site for summary
        self.held_results: List[Dict[str, Any]] = []  # Store lower-scoring results
        self.score_threshold = 79  # Only send results above this score immediately
        
    
    async def do(self):
        """Main execution method called by the framework."""
        try:
            await self._send_status_message("Identifying relevant sites ...")
            
            who_endpoint = getattr(CONFIG.nlweb, 'who_endpoint', 'http://localhost:8000/who') if hasattr(CONFIG, 'nlweb') else 'http://localhost:8000/who'
            # Ask queries should go to localhost where this server is running
            ask_base_url = 'http://localhost:8000'
            print(f"[Using who_endpoint: {who_endpoint}")
            
            sites_to_query = []
            site_count = 0
            print(f"Calling sites_from_who_streaming with endpoint={who_endpoint}, query={self.query}")
            
            # Start querying sites immediately as they arrive from the streaming endpoint
            async for site in sites_from_who_streaming(who_endpoint, self.query):
                # Check if we've reached the limit
                if site_count >= self.top_k_sites:
                    break
                    
                domain = site.get('domain', '')
                if domain:
                    site_count += 1
                    sites_to_query.append(site)
                    
                    # Send status about this site immediately
                    await self._send_site_status(site, site_count)
                    
                    task = asyncio.create_task(self._query_site_and_stream(domain, site, ask_base_url))
                    self.active_tasks.append(task)

            # Send the complete list of sites that are being searched
            if sites_to_query:
                await self._send_sites_list(sites_to_query)
            else:
                print(f"[MULTI-SITE] WARNING: No sites returned from who endpoint!")
            
            # Wait for all site queries to complete
            if self.active_tasks:
                results = await asyncio.gather(*self.active_tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        print(f"[MULTI-SITE] Task {i+1} failed with error: {result}")
            # If we haven't sent enough results, send the best of the held results
            if self.total_results_sent < self.final_top_k and self.held_results:
                # Sort held results by score (descending)
                self.held_results.sort(key=lambda x: x.get('score', 0), reverse=True)
                
                # Send the top remaining results
                remaining_slots = self.final_top_k - self.total_results_sent
                for result in self.held_results[:remaining_slots]:
                    await self._send_result(result)
                    self.total_results_sent += 1
                    
                    # Update the count for the source site
                    source_site = result.get('source_site', '')
                    if source_site in self.site_results:
                        self.site_results[source_site] += 1
           
            await self._send_final_summary()
            
            # Return empty list as results are streamed directly
            return []
            
        except Exception as e:
            print(f"[MULTI-SITE] ERROR: {str(e)}")
            import traceback
            print(f"[MULTI-SITE] Traceback: {traceback.format_exc()}")
            logger.error(f"Error in multi-site query: {str(e)}", exc_info=True)
            await self._send_error_message(f"Error during multi-site query: {str(e)}")
            return []
    
    async def _query_site_and_stream(self, domain: str, site_info: Dict[str, Any], base_url: str):
        """Query a single site and stream results as they arrive."""
        start_time = time.time()
        self.sites_queried += 1
        
        # Use site-specific query if provided by who service, otherwise use original query
        site_query = site_info.get('query', self.query)
        
        try:
            
            # Check if this is a Shopify site based on @type and add retrieval endpoint if so
            additional_params = {}
            site_type = site_info.get('@type', '')
            if 'shopify' in site_type.lower():
                # Use shopify_mcp retrieval endpoint for Shopify sites
                additional_params['retrieval'] = 'shopify'
            # Add tool=search to skip tool selection and use search directly
            additional_params['tool'] = 'search'
           
            # Process results as they arrive via streaming
            sent_count = 0
            async for result in ask_nlweb_streaming(
                f"{base_url}/ask",
                site_query,  # Use the site-specific query
                site=domain,
                top_k=self.results_per_site,
                **additional_params
            ):
                # Add source site information
                result['source_site'] = domain
                result['site_name'] = site_info.get('name', domain)
                result['site_score'] = site_info.get('score', 0)
                
                # Get the score
                score = result.get('score', 0)
                
                # Send all high-scoring results immediately (no limit)
                if score > self.score_threshold:
                    await self._send_result(result)
                    sent_count += 1
                    self.total_results_sent += 1
                else:
                    # Store lower-scoring results for later
                    self.held_results.append(result)
            
            response_time = time.time() - start_time
            self.sites_successful += 1
            
            # Store results count for summary
            self.site_results[domain] = sent_count
            
            # Send site completion status
            await self._send_site_complete(domain, sent_count, response_time)
            
        except Exception as e:
            self.sites_failed += 1
            response_time = time.time() - start_time
            
            # Store failed site with 0 results
            self.site_results[domain] = 0
            
            logger.error(f"Error querying site {domain}: {str(e)}")
            await self._send_site_error(domain, str(e), response_time)
    
    async def _send_status_message(self, message: str):
        """Send a status update message."""
        if hasattr(self.handler, 'send_message'):
            await self.handler.send_message({
                "message_type": "intermediate_message",
                "status": message,
                "timestamp": time.time()
            })
    
    async def _send_sites_list(self, sites: List[Dict[str, Any]]):
        """Send intermediate message with list of all sites that will be searched."""
        if hasattr(self.handler, 'send_message'):
            # Format sites with both name and domain for the UI to make clickable
            sites_data = []
            for site in sites:
                site_data = {
                    'name': site.get('name', site.get('domain', 'Unknown')),
                    'domain': site.get('domain', '')
                }
                # Include the site-specific query if different from original
                if 'query' in site and site['query'] != self.query:
                    site_data['query'] = site['query']
                sites_data.append(site_data)
            
            await self.handler.send_message({
                "message_type": "asking_sites",
                "sites": sites_data,
                "query": self.query  # Include the query for the UI to use in links
            })
    
    async def _send_site_status(self, site: Dict[str, Any], index: int):
        """Send status about a site being queried."""
        if hasattr(self.handler, 'send_message'):
            await self.handler.send_message({
                "message_type": "site_querying",
                "site": site.get('domain', ''),
                "site_name": site.get('name', ''),
                "site_score": site.get('score', 0),
                "index": index,
                "total": self.top_k_sites
            })
    
    async def _send_result(self, result: Dict[str, Any]):
        """Send a single result to the browser."""
        if hasattr(self.handler, 'send_message'):
            # Preserve the @type if it exists (e.g., CricketStatistics)
            result_type = result.get('@type', 'Item')
            
            # Format result for output
            formatted_result = {
                "message_type": "result",
                "content": [{
                    "@type": result_type,
                    "url": result.get('url', ''),
                    "name": result.get('name', 'Untitled'),
                    "site": result.get('source_site', ''),
                    "score": result.get('score', 0),
                    "description": result.get('description', ''),
                    "schema_object": result.get('schema_object', {}),
                    "source_site_name": result.get('site_name', ''),
                    "source_site_score": result.get('site_score', 0)
                }],
                "conversation_id": self.handler.conversation_id
            }
            # Fire and forget - don't await
            asyncio.create_task(self.handler.send_message(formatted_result))
    
    async def _send_site_complete(self, domain: str, result_count: int, response_time: float):
        """Send notification that a site query completed."""
        if hasattr(self.handler, 'send_message'):
            await self.handler.send_message({
                "message_type": "site_complete",
                "site": domain,
                "results_count": result_count,
                "response_time": f"{response_time:.2f}s"
            })
    
    async def _send_site_error(self, domain: str, error: str, response_time: float):
        """Send notification that a site query failed."""
        if hasattr(self.handler, 'send_message'):
            await self.handler.send_message({
                "message_type": "site_error",
                "site": domain,
                "error": error,
                "response_time": f"{response_time:.2f}s"
            })
    
    async def _send_final_summary(self):
        """Send final summary of the multi-site query."""
        # Print simple console summary table
        if self.site_results:
            print("\n" + "=" * 50)
            print(f"Multi-site query results for: '{self.query}'")
            print("-" * 50)
            print(f"{'Site':<35} {'Results':>10}")
            print("-" * 50)
            for site, count in sorted(self.site_results.items(), key=lambda x: x[1], reverse=True):
                print(f"{site:<35} {count:>10}")
            print("-" * 50)
            print(f"{'TOTAL':<35} {self.total_results_sent:>10}")
            print("=" * 50 + "\n")
        
        if hasattr(self.handler, 'send_message'):
            message = {
                "message_type": "multi_site_complete",
                "sites_queried": self.sites_queried,
                "sites_successful": self.sites_successful,
                "sites_failed": self.sites_failed,
                "total_results": self.total_results_sent,
                "query": self.query
            }
            
            await self.handler.send_message(message)
    
    async def _send_error_message(self, error: str):
        """Send an error message."""
        if hasattr(self.handler, 'send_message'):
            await self.handler.send_message({
                "message_type": "multi_site_error",
                "error": error,
                "timestamp": time.time()
            })