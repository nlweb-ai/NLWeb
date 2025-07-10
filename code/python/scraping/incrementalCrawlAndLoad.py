#!/usr/bin/env python3
"""
Incremental website crawler with schema markup extraction and database loading.
This script crawls URLs one by one, maintaining state to allow resumption.

Usage - run this from the 'python' directory:
    python -m scraping.incrementalCrawlAndLoad example.com
    python -m scraping.incrementalCrawlAndLoad example.com --max-pages 100
    python -m scraping.incrementalCrawlAndLoad example.com --resume
"""

import os
import sys
import json
import time
import argparse
import asyncio
import aiohttp
from datetime import datetime
from urllib.parse import urlparse
import hashlib
from typing import Dict, List, Optional, Tuple
import logging

# Import local scraping modules
from .urlsFromSitemap import process_site_or_sitemap
from .extractMarkup import extract_schema_markup, extract_canonical_url

# Import database and embedding modules
from data_loading.db_load_utils import prepare_documents_from_json
from core.embedding import batch_get_embeddings
from core.retriever import upload_documents

# Import common utilities
from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG

logger = get_configured_logger("incremental_crawl_and_load")

# Suppress httpx INFO logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Suppress Azure SDK logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)


class IncrementalCrawler:
    """Incremental crawler that maintains state and processes URLs one by one."""
    
    def __init__(self, domain: str, output_dir: str, db_name: str, max_retries: int = 3, database: str = None, reprocess_mode: bool = False):
        self.domain = domain
        self.output_dir = output_dir
        self.db_name = db_name
        self.max_retries = max_retries
        self.database = database  # Specific retrieval backend to use
        self.reprocess_mode = reprocess_mode  # Whether to reprocess existing files
        
        # Set up directories
        self.urls_dir = os.path.join(output_dir, "urls")
        self.html_dir = os.path.join(output_dir, "html")
        self.status_file = os.path.join(output_dir, "crawl_status.json")
        
        # Create directories
        os.makedirs(self.urls_dir, exist_ok=True)
        os.makedirs(self.html_dir, exist_ok=True)
        
        # Load or initialize status
        self.status = self._load_status()
        
        # Statistics
        self.stats = {
            "total_urls": 0,
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "already_crawled": 0,
            "reprocessed": 0,
            "total_json_size": 0,
            "total_schemas": 0,
            "total_documents_uploaded": 0,
            "schema_types": {}  # Count of each @type found
        }
        
    def _load_status(self) -> Dict[str, Dict]:
        """Load crawl status from file or create new one."""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading status file: {e}. Starting fresh.")
                return {}
        return {}
    
    def _save_status(self):
        """Save current status to file."""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(self.status, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving status file: {e}")
    
    def _get_url_hash(self, url: str) -> str:
        """Generate a unique hash for a URL."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_html_filename(self, url: str) -> str:
        """Generate filename for saving HTML content."""
        url_hash = self._get_url_hash(url)
        # Also include a sanitized version of the URL for readability
        parsed = urlparse(url)
        path = parsed.path.strip('/').replace('/', '_') or 'index'
        # Limit filename length and sanitize
        if len(path) > 50:
            path = path[:50]
        # Remove problematic characters
        path = "".join(c for c in path if c.isalnum() or c in ('_', '-', '.'))
        return f"{url_hash}_{path}.html"
    
    def _extract_schema_types(self, schema_obj):
        """Recursively extract @type values from schema objects."""
        types = []
        
        if isinstance(schema_obj, dict):
            # Check for @type at current level
            if '@type' in schema_obj:
                schema_type = schema_obj['@type']
                if isinstance(schema_type, list):
                    types.extend(schema_type)
                else:
                    types.append(schema_type)
            
            # Recursively check all values
            for key, value in schema_obj.items():
                if isinstance(value, (dict, list)):
                    types.extend(self._extract_schema_types(value))
                    
        elif isinstance(schema_obj, list):
            # Process each item in the list
            for item in schema_obj:
                types.extend(self._extract_schema_types(item))
                
        return types
    
    def _print_status(self):
        """Print current crawl status on a single line."""
        processed = self.stats["processed"]
        total = self.stats["total_urls"]
        successful = self.stats["successful"]
        failed = self.stats["failed"]
        skipped = self.stats["skipped"]
        already_crawled = self.stats["already_crawled"]
        total_json_kb = self.stats["total_json_size"] / 1024
        total_schemas = self.stats["total_schemas"]
        total_docs = self.stats["total_documents_uploaded"]
        
        if total > 0:
            progress_pct = (processed / total) * 100
        else:
            progress_pct = 0
            
        if self.reprocess_mode:
            status_line = (
                f"\rProgress: {processed}/{total} ({progress_pct:.1f}%) | "
                f"Reprocessed: {self.stats['reprocessed']} | Success: {successful} | "
                f"Failed: {failed} | Skipped: {skipped} | "
                f"JSON: {total_json_kb:.1f}KB | Schemas: {total_schemas} | "
                f"Docs uploaded: {total_docs}"
            )
        else:
            status_line = (
                f"\rProgress: {processed}/{total} ({progress_pct:.1f}%) | "
                f"Success: {successful} | Failed: {failed} | "
                f"Already crawled: {already_crawled} | "
                f"JSON: {total_json_kb:.1f}KB | Schemas: {total_schemas} | "
                f"Docs uploaded: {total_docs}"
            )
        
        # Add top schema types to status line
        if self.stats["schema_types"]:
            # Get top 3 types by count
            sorted_types = sorted(self.stats["schema_types"].items(), key=lambda x: -x[1])[:3]
            types_str = ", ".join([f"{t}:{c}" for t, c in sorted_types])
            status_line += f" | Types: {types_str}"
        
        # Print without newline and flush
        print(status_line, end='', flush=True)
    
    async def _fetch_page(self, url: str) -> Optional[Tuple[str, int]]:
        """Fetch a single page and return HTML content and size."""
        async with aiohttp.ClientSession() as session:
            for attempt in range(self.max_retries):
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            html = await response.text()
                            return html, len(html.encode('utf-8'))
                        else:
                            logger.debug(f"HTTP {response.status} for {url}")
                            if attempt == self.max_retries - 1:
                                return None
                except Exception as e:
                    logger.debug(f"Error fetching {url} (attempt {attempt + 1}): {e}")
                    if attempt == self.max_retries - 1:
                        return None
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        return None
    
    def _html_file_exists(self, url: str) -> Tuple[bool, Optional[str]]:
        """Check if HTML file for URL already exists."""
        filename = self._get_html_filename(url)
        filepath = os.path.join(self.html_dir, filename)
        if os.path.exists(filepath):
            return True, filepath
        return False, None
    
    async def _process_single_url(self, url: str) -> bool:
        """Process a single URL: fetch, extract, embed, and upload."""
        url_hash = self._get_url_hash(url)
        
        # Check if HTML file already exists (page already crawled)
        file_exists, html_filepath = self._html_file_exists(url)
        
        if file_exists:
            # Check if it's been fully processed
            if url_hash in self.status and self.status[url_hash].get("uploaded", False) and not self.reprocess_mode:
                self.stats["already_crawled"] += 1
                return True
            else:
                # HTML exists but not fully processed, or we're in reprocess mode
                if self.reprocess_mode:
                    logger.debug(f"Reprocessing existing HTML for {url}")
                    self.stats["reprocessed"] += 1
                else:
                    logger.debug(f"HTML exists for {url}, continuing with processing")
        
        # Initialize or update status entry
        if url_hash not in self.status:
            self.status[url_hash] = {
                "url": url,
                "started_at": datetime.now().isoformat(),
                "completed": False,
                "uploaded": False
            }
        
        try:
            # Step 1: Fetch the page if not already downloaded
            if not file_exists:
                if self.reprocess_mode:
                    # In reprocess mode, skip URLs without existing HTML
                    logger.debug(f"No HTML file for {url} in reprocess mode, skipping")
                    self.stats["skipped"] += 1
                    return True
                    
                result = await self._fetch_page(url)
                if result is None:
                    self.status[url_hash]["error"] = "Failed to fetch page"
                    self.status[url_hash]["completed_at"] = datetime.now().isoformat()
                    self._save_status()
                    self.stats["failed"] += 1
                    return False
                
                html_content, page_size = result
                self.status[url_hash]["page_size"] = page_size
                self.status[url_hash]["fetched_at"] = datetime.now().isoformat()
                
                # Save HTML to file
                filename = self._get_html_filename(url)
                html_filepath = os.path.join(self.html_dir, filename)
                with open(html_filepath, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                self.status[url_hash]["html_file"] = filename
                self._save_status()
            else:
                # Read existing file size
                self.status[url_hash]["page_size"] = os.path.getsize(html_filepath)
                self.status[url_hash]["html_file"] = os.path.basename(html_filepath)
            
            # Step 2: Extract schema markup from saved file
            canonical_url = extract_canonical_url(html_filepath)
            schemas_str = extract_schema_markup(html_filepath)
            
            # Use canonical URL if found, otherwise use original URL
            final_url = canonical_url or url
            
            # Parse schemas
            schemas = []
            if schemas_str:
                try:
                    schemas = json.loads(schemas_str)
                    logger.debug(f"Extracted {len(schemas)} schemas from {url}")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse schemas for {url}")
            
            if not schemas:
                logger.debug(f"No schemas found for {url}, skipping upload")
                self.status[url_hash]["json_size"] = 0
                self.status[url_hash]["schema_count"] = 0
                self.status[url_hash]["completed"] = True
                self.status[url_hash]["uploaded"] = True
                self.status[url_hash]["completed_at"] = datetime.now().isoformat()
                self._save_status()
                self.stats["successful"] += 1
                return True
            

            logger.debug(f"Processing {len(schemas)} schemas from {url}")
            
            # Process schemas and prepare for upload
            total_json_size = len(schemas_str.encode('utf-8'))
            self.status[url_hash]["json_size"] = total_json_size
            self.status[url_hash]["schema_count"] = len(schemas)
            
            # Update global statistics
            self.stats["total_json_size"] += total_json_size
            self.stats["total_schemas"] += len(schemas)
            
            # Extract and count @type values
            for schema in schemas:
                types_found = self._extract_schema_types(schema)
                for schema_type in types_found:
                    if schema_type in self.stats["schema_types"]:
                        self.stats["schema_types"][schema_type] += 1
                    else:
                        self.stats["schema_types"][schema_type] = 1
            
            # Step 3: Prepare documents for database
            documents_to_upload = []
                
            # Log successful upload
            logger.debug(f"Preparing {len(schemas)} schemas for upload from {url}")
            docs, _ = prepare_documents_from_json(final_url, schemas_str, self.db_name)
            documents_to_upload.extend(docs)
            # Log successful upload
            logger.debug(f"Prepared {len(documents_to_upload)} documents from {url}")
            
            # Step 4: Generate embeddings and upload
            if documents_to_upload:
                # Get embedding provider
                provider = CONFIG.preferred_embedding_provider
                provider_config = CONFIG.get_embedding_provider(provider)
                model = provider_config.model if provider_config else None
                
                # Extract texts for embedding
                texts = [doc["schema_json"] for doc in documents_to_upload]
                
                # Generate embeddings
                embeddings = await batch_get_embeddings(texts, provider, model)
                
                # Add embeddings to documents
                for i, doc in enumerate(documents_to_upload):
                    if i < len(embeddings):
                        doc["embedding"] = embeddings[i]
                
                # Upload to database
                # Use specified database or default
                query_params = {"db": [self.database]} if self.database else None
                await upload_documents(documents_to_upload, query_params=query_params)
                
                # Log successful upload
                logger.debug(f"Uploaded {len(documents_to_upload)} documents from {url}")
                
                self.status[url_hash]["uploaded_at"] = datetime.now().isoformat()
                self.status[url_hash]["documents_uploaded"] = len(documents_to_upload)
                
                # Update global statistics
                self.stats["total_documents_uploaded"] += len(documents_to_upload)
            
            # Mark as completed
            self.status[url_hash]["completed"] = True
            self.status[url_hash]["uploaded"] = True
            self.status[url_hash]["completed_at"] = datetime.now().isoformat()
            self._save_status()
            self.stats["successful"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            self.status[url_hash]["error"] = str(e)
            self.status[url_hash]["completed_at"] = datetime.now().isoformat()
            self._save_status()
            self.stats["failed"] += 1
            return False
    
    async def crawl(self, urls: List[str], resume: bool = True):
        """Crawl a list of URLs incrementally."""
        self.stats["total_urls"] = len(urls)
        
        logger.info(f"Starting incremental crawl of {len(urls)} URLs")
        if resume and self.status:
            already_processed = sum(1 for s in self.status.values() if s.get("uploaded", False))
            logger.info(f"Resuming from previous state: {already_processed} URLs already fully processed")
        
        # Process URLs one by one
        for i, url in enumerate(urls):
            self.stats["processed"] = i + 1
            await self._process_single_url(url)
            self._print_status()
        
        # Print final newline
        print()
        
        # Print summary
        if self.reprocess_mode:
            logger.info(f"Reprocessing completed: {self.stats['reprocessed']} files reprocessed, "
                       f"{self.stats['successful']} successful, {self.stats['failed']} failed, "
                       f"{self.stats['skipped']} skipped (no HTML file)")
        else:
            logger.info(f"Crawl completed: {self.stats['successful']} successful, "
                       f"{self.stats['failed']} failed, {self.stats['already_crawled']} already crawled")
        logger.info(f"Total JSON extracted: {self.stats['total_json_size'] / 1024:.1f}KB from {self.stats['total_schemas']} schemas")
        logger.info(f"Total documents uploaded to database: {self.stats['total_documents_uploaded']}")
        
        # Show schema types found
        if self.stats["schema_types"]:
            logger.info("Schema types found:")
            # Sort by count (descending) and then by name
            sorted_types = sorted(self.stats["schema_types"].items(), key=lambda x: (-x[1], x[0]))
            for schema_type, count in sorted_types:
                logger.info(f"  {schema_type}: {count}")
        
        # Show which database was used
        if self.database:
            logger.info(f"Data uploaded to: {self.database}")
        else:
            logger.info(f"Data uploaded to: {CONFIG.write_endpoint} (default)")


async def main():
    parser = argparse.ArgumentParser(
        description="Incrementally crawl website, extract schema markup, and load into database",
        epilog="""
Examples:
  %(prog)s example.com
      Incrementally crawl example.com and load schemas into database
  
  %(prog)s example.com --max-pages 100
      Limit crawling to 100 pages
  
  %(prog)s example.com --resume
      Resume a previous crawl (default behavior)
  
  %(prog)s example.com --no-resume
      Start fresh, ignoring previous progress
  
  %(prog)s example.com --output-dir ./my-data
      Use custom output directory
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("site", 
                       help="Website domain or URL (e.g., example.com, https://example.com)")
    parser.add_argument("--output-dir", default=None, 
                       help="Output directory (default: data/<site> or $NLWEB_OUTPUT_DIR/<site>)")
    parser.add_argument("--sitemap", default=None,
                       help="Specific sitemap URL to use instead of auto-discovery")
    parser.add_argument("--max-pages", type=int, default=None,
                       help="Maximum number of pages to crawl (default: all)")
    parser.add_argument("--max-retries", type=int, default=3,
                       help="Maximum retries for failed requests (default: 3)")
    parser.add_argument("--no-resume", action="store_true",
                       help="Start fresh instead of resuming previous crawl")
    parser.add_argument("--reprocess", action="store_true",
                       help="Reprocess existing HTML files (skip download, recompute embeddings and upload)")
    parser.add_argument("--db-name", default=None,
                       help="Database name for loading (default: domain name)")
    parser.add_argument("--database", default=None,
                       help="Specific database endpoint to use (e.g., azure_ai_search, qdrant_local)")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Parse domain
    domain = args.site
    if domain.startswith("http://") or domain.startswith("https://"):
        parsed = urlparse(domain)
        domain = parsed.netloc
    
    # Set up output directory
    if args.output_dir:
        base_dir = args.output_dir
    else:
        # Use NLWEB_OUTPUT_DIR if available, otherwise use ../data directory
        if os.getenv('NLWEB_OUTPUT_DIR'):
            output_base = os.getenv('NLWEB_OUTPUT_DIR')
        else:
            # Get the parent directory (NLWeb) and use its data folder
            current_dir = os.path.dirname(os.path.abspath(__file__))  # scraping dir
            code_dir = os.path.dirname(current_dir)  # code dir
            nlweb_dir = os.path.dirname(code_dir)  # NLWeb dir
            output_base = os.path.join(nlweb_dir, 'data')
        base_dir = os.path.join(output_base, domain.replace('.', '_'))
    
    # Database name
    db_name = args.db_name or domain.replace('.', '_')
    
    logger.info(f"Starting incremental crawl for {domain}")
    logger.info(f"Output directory: {base_dir}")
    if args.reprocess:
        logger.info("REPROCESS MODE: Will skip downloading and reprocess existing HTML files")
    if args.database:
        logger.info(f"Using database endpoint: {args.database}")
    else:
        logger.info("Using default database endpoint from configuration")
    
    # Initialize crawler
    crawler = IncrementalCrawler(domain, base_dir, db_name, args.max_retries, args.database, args.reprocess)
    
    # Step 1: Get URLs from sitemap
    urls_file = os.path.join(crawler.urls_dir, f"{domain}_urls.txt")
    
    # Always refresh the URL list to check for new pages
    logger.info("Extracting URLs from sitemap...")
    
    if args.sitemap:
        logger.info(f"Using provided sitemap: {args.sitemap}")
        process_site_or_sitemap(args.sitemap, urls_file, verbose=args.verbose)
    else:
        logger.info(f"Checking robots.txt and default locations for {domain}")
        process_site_or_sitemap(domain, urls_file, verbose=args.verbose)
    
    # Read URLs
    with open(urls_file, 'r') as f:
        all_urls = [line.strip() for line in f if line.strip()]
    
    url_count = len(all_urls)
    logger.info(f"Found {url_count} URLs")
    
    # Limit URLs if max_pages is set
    if args.max_pages and url_count > args.max_pages:
        logger.info(f"Limiting to {args.max_pages} pages")
        all_urls = all_urls[:args.max_pages]
    
    # Clear status if not resuming
    if args.no_resume and os.path.exists(crawler.status_file):
        logger.info("Clearing previous crawl status")
        os.remove(crawler.status_file)
        crawler.status = {}
    
    # Start crawling
    await crawler.crawl(all_urls, resume=not args.no_resume)


if __name__ == "__main__":
    asyncio.run(main())