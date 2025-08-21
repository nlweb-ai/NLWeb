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
from typing import Dict, Any, Set, List
from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG
from core.utils.nlweb_client import sites_from_who_streaming, ask_nlweb_server

logger = get_configured_logger("multi_site_query")

class MultiSiteQueryHandler:
    """Handler for multi-site query aggregation."""
    
    def __init__(self, params, handler):
        self.handler = handler
        self.params = params
        self.query = handler.query
        self.top_k_sites = params.get('top_k_sites', 5)
        self.results_per_site = params.get('results_per_site', 5)
        self.final_top_k = params.get('final_top_k', 10)
        
        # Track sites and results
        self.sites_queried = 0
        self.sites_successful = 0
        self.sites_failed = 0
        self.total_results_sent = 0
        self.seen_urls: Set[str] = set()  # For deduplication
        self.active_tasks: List[asyncio.Task] = []
        self.site_results: Dict[str, int] = {}  # Track results per site for summary
        self.held_results: List[Dict[str, Any]] = []  # Store lower-scoring results
        self.score_threshold = 84  # Only send results above this score immediately
        
    
    async def do(self):
        """Main execution method called by the framework."""
        try:
            # Send initial status
            await self._send_status_message("Identifying relevant sites for your query...")
            
            # Get who_endpoint from config
            who_endpoint = getattr(CONFIG, 'who_endpoint', 'http://localhost:8000/who')
            base_url = who_endpoint.replace('/who', '')  # Extract base URL for ask queries
            
            # First, collect all sites from /who endpoint
            sites_to_query = []
            site_count = 0
            async for site in sites_from_who_streaming(base_url, self.query):
                # Check if we've reached the limit
                if site_count >= self.top_k_sites:
                    break
                    
                domain = site.get('domain', '')
                if domain:
                    site_count += 1
                    sites_to_query.append(site)
            
            # Send intermediate message with all sites that will be searched
            if sites_to_query:
                await self._send_sites_list(sites_to_query)
            
            # Now query all sites asynchronously
            for index, site in enumerate(sites_to_query, 1):
                domain = site.get('domain', '')
                
                # Send status about this site
                await self._send_site_status(site, index)
                
                # Launch async task to query this site
                task = asyncio.create_task(self._query_site_and_stream(domain, site, base_url))
                self.active_tasks.append(task)
            
            # Wait for all site queries to complete
            if self.active_tasks:
                await asyncio.gather(*self.active_tasks, return_exceptions=True)
            
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
                
            
            # Send final summary
            await self._send_final_summary()
            
            # Return empty list as results are streamed directly
            return []
            
        except Exception as e:
            logger.error(f"Error in multi-site query: {str(e)}", exc_info=True)
            await self._send_error_message(f"Error during multi-site query: {str(e)}")
            return []
    
    async def _query_site_and_stream(self, domain: str, site_info: Dict[str, Any], base_url: str):
        """Query a single site and stream results as they arrive."""
        start_time = time.time()
        self.sites_queried += 1
        
        try:
            
            # Query the site using ask_nlweb_server
            results = await ask_nlweb_server(
                f"{base_url}/ask",
                self.query,
                streaming=True,  # Use streaming mode
                site=domain,
                top_k=self.results_per_site
            )
            
            # Process results
            sent_count = 0
            for result in results:
                # Deduplicate by URL
                url = result.get('url', '')
                if url and url not in self.seen_urls:
                    self.seen_urls.add(url)
                    
                    # Add source site information
                    result['source_site'] = domain
                    result['site_name'] = site_info.get('name', domain)
                    result['site_score'] = site_info.get('score', 0)
                    
                    # Get the score
                    score = result.get('score', 0)
                    
                    # Only send high-scoring results immediately
                    if score > self.score_threshold:
                        # Don't exceed global limit
                        if self.total_results_sent < self.final_top_k:
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
                "message_type": "multi_site_status",
                "status": message,
                "timestamp": time.time()
            })
    
    async def _send_sites_list(self, sites: List[Dict[str, Any]]):
        """Send intermediate message with list of all sites that will be searched."""
        if hasattr(self.handler, 'send_message'):
            # Format site names for display
            site_names = []
            for site in sites:
                name = site.get('name', site.get('domain', 'Unknown'))
                site_names.append(name)
            
            # Create a comma-separated list of sites
            sites_str = ", ".join(site_names)
            
            await self.handler.send_message({
                "message_type": "asking_sites",
                "message": sites_str
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
            # Format result for output
            formatted_result = {
                "message_type": "result",
                "content": [{
                    "@type": "Item",
                    "url": result.get('url', ''),
                    "name": result.get('name', 'Untitled'),
                    "site": result.get('source_site', ''),
                    "siteUrl": result.get('source_site', ''),
                    "score": result.get('score', 0),
                    "description": result.get('description', ''),
                    "schema_object": result.get('schema_object', {}),
                    "source_site_name": result.get('site_name', ''),
                    "source_site_score": result.get('site_score', 0)
                }],
                "query_id": self.handler.query_id
            }
            await self.handler.send_message(formatted_result)
    
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
            await self.handler.send_message({
                "message_type": "multi_site_complete",
                "sites_queried": self.sites_queried,
                "sites_successful": self.sites_successful,
                "sites_failed": self.sites_failed,
                "total_results": self.total_results_sent,
                "query": self.query
            })
    
    async def _send_error_message(self, error: str):
        """Send an error message."""
        if hasattr(self.handler, 'send_message'):
            await self.handler.send_message({
                "message_type": "multi_site_error",
                "error": error,
                "timestamp": time.time()
            })