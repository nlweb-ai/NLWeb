#!/usr/bin/env python3
"""
Extract schema markup from websites.
This script integrates URL extraction from sitemaps, content crawling,
schema markup extraction, and embedding generation.

Usage:
    python -m code.scraping.markupFromSite example.com
    python -m code.scraping.markupFromSite example.com --max-retries 5
    python -m code.scraping.markupFromSite example.com --skip-embeddings
"""

import os
import sys
import argparse
import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

# Import local scraping modules
from .urlsFromSitemap import extract_urls_from_sitemap, process_site_or_sitemap
from .expBackOffCrawl import SimpleCrawler
from .extractMarkup import process_directory
from .embedding import process_files as generate_embeddings

# Import common utilities from the repository
from misc.logger.logging_config_helper import get_configured_logger
from config.config import CONFIG

logger = get_configured_logger("scraping_main")


def main():
    parser = argparse.ArgumentParser(
        description="Extract schema markup from websites",
        epilog="""
Examples:
  %(prog)s example.com
      Extract markup from example.com (checks robots.txt for sitemaps)
  
  %(prog)s https://example.com
      Same as above, with explicit protocol
  
  %(prog)s example.com --output-dir ./my-data
      Save results to custom directory
  
  %(prog)s example.com --sitemap https://example.com/products-sitemap.xml
      Use specific sitemap instead of auto-discovery
  
  %(prog)s example.com --skip-embeddings
      Skip embedding generation step
  
  %(prog)s example.com --max-retries 5
      Increase retry attempts for failed requests
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("site", 
                       help="Website domain or URL (e.g., example.com, https://example.com)")
    parser.add_argument("--output-dir", default=None, 
                       help="Output directory (default: data/<site> or $NLWEB_OUTPUT_DIR/<site>)")
    parser.add_argument("--sitemap", default=None,
                       help="Specific sitemap URL to use instead of auto-discovery via robots.txt")
    parser.add_argument("--max-retries", type=int, default=3,
                       help="Maximum retries for failed requests (default: 3)")
    parser.add_argument("--embedding-model", choices=["small", "large"], default="small",
                       help="Embedding model size (default: small)")
    parser.add_argument("--skip-crawl", action="store_true",
                       help="Skip crawling step (useful if HTML files already exist)")
    parser.add_argument("--skip-extract", action="store_true",
                       help="Skip extraction step (useful if schemas already extracted)")
    parser.add_argument("--skip-embeddings", action="store_true",
                       help="Skip embedding generation step")
    
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
        # Use NLWEB_OUTPUT_DIR if available, otherwise use data directory
        output_base = os.getenv('NLWEB_OUTPUT_DIR', 'data')
        base_dir = os.path.join(output_base, domain.replace('.', '_'))
    
    # Create subdirectories
    urls_dir = os.path.join(base_dir, "urls")
    html_dir = os.path.join(base_dir, "html")
    schema_dir = os.path.join(base_dir, "schemas")
    embeddings_dir = os.path.join(base_dir, "embeddings")
    
    for directory in [urls_dir, html_dir, schema_dir, embeddings_dir]:
        os.makedirs(directory, exist_ok=True)
    
    logger.info(f"Starting scraping pipeline for {domain}")
    logger.info(f"Output directory: {base_dir}")
    
    # Step 1: Get URLs from sitemap
    urls_file = os.path.join(urls_dir, f"{domain}_urls.txt")
    
    if not os.path.exists(urls_file):
        logger.info("Step 1: Extracting URLs from sitemap...")
        
        if args.sitemap:
            # Direct sitemap URL provided
            logger.info(f"Using provided sitemap: {args.sitemap}")
            process_site_or_sitemap(args.sitemap, urls_file)
        else:
            # Let process_site_or_sitemap handle robots.txt checking
            logger.info(f"Checking robots.txt and default locations for {domain}")
            process_site_or_sitemap(domain, urls_file)
        
        # Count URLs
        with open(urls_file, 'r') as f:
            url_count = sum(1 for _ in f)
        logger.info(f"Extracted {url_count} URLs")
    else:
        logger.info(f"URLs file already exists: {urls_file}")
    
    # Step 2: Crawl URLs
    if not args.skip_crawl:
        logger.info("Step 2: Crawling URLs...")
        
        with open(urls_file, 'r') as f:
            urls = f.readlines()
        
        crawler = SimpleCrawler(
            target_dir=html_dir,
            max_retries=args.max_retries
        )
        
        crawler.crawl_urls(urls)
        logger.info(f"Crawling complete. Success: {crawler.stats.success}, Failed: {crawler.stats.failures}")
    else:
        logger.info("Skipping crawl step")
    
    # Step 3: Extract schema markup
    schema_file = os.path.join(schema_dir, f"{domain}_schemas.txt")
    
    if not args.skip_extract and not os.path.exists(schema_file):
        logger.info("Step 3: Extracting schema markup...")
        
        # Process the HTML directory
        output_file = process_directory(html_dir)
        
        # Move the output file to schema directory
        if os.path.exists(output_file):
            os.rename(output_file, schema_file)
            logger.info(f"Schema extraction complete: {schema_file}")
        else:
            logger.error("Schema extraction failed")
    else:
        logger.info("Skipping extraction step")
    
    # Step 4: Generate embeddings
    if not args.skip_embeddings and os.path.exists(schema_file):
        logger.info("Step 4: Generating embeddings...")
        
        # Run the async embedding generation
        asyncio.run(generate_embeddings(
            schema_file,
            embeddings_dir,
            size=args.embedding_model
        ))
        
        logger.info("Embedding generation complete")
    else:
        logger.info("Skipping embedding generation")
    
    logger.info("Pipeline complete!")
    logger.info(f"Results saved in: {base_dir}")
    
    # Print summary
    print("\nSummary:")
    print(f"- URLs file: {urls_file}")
    print(f"- HTML files: {html_dir}")
    print(f"- Schema file: {schema_file}")
    print(f"- Embeddings: {embeddings_dir}")


if __name__ == "__main__":
    main()