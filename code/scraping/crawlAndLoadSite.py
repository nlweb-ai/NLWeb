#!/usr/bin/env python3
"""
Crawl a website, extract schema markup, and load it into the database.
This script combines URL extraction, crawling, markup extraction, and database loading.

Usage:
    python -m code.scraping.crawlAndLoadSite example.com
    python -m code.scraping.crawlAndLoadSite example.com --max-pages 100
    python -m code.scraping.crawlAndLoadSite example.com --skip-crawl
"""

import os
import sys
import argparse
from urllib.parse import urlparse

# Import local scraping modules
from .urlsFromSitemap import process_site_or_sitemap
from .expBackOffCrawl import SimpleCrawler
from .extractMarkup import process_directory

# Import database loading tool
from tools.db_load import main as db_load_main

# Import common utilities
from utils.logger import get_logger
from config.config import CONFIG

logger = get_logger("crawl_and_load")


def main():
    parser = argparse.ArgumentParser(
        description="Crawl website, extract schema markup, and load into database",
        epilog="""
Examples:
  %(prog)s example.com
      Crawl example.com and load schemas into database
  
  %(prog)s example.com --max-pages 100
      Limit crawling to 100 pages
  
  %(prog)s example.com --skip-crawl
      Skip crawling (use existing HTML files) and just extract/load
  
  %(prog)s example.com --output-dir ./my-data
      Use custom output directory
  
  %(prog)s example.com --db-name my_site
      Use custom database name (default: uses domain name)
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
    parser.add_argument("--skip-crawl", action="store_true",
                       help="Skip crawling step (use existing HTML files)")
    parser.add_argument("--skip-extract", action="store_true",
                       help="Skip extraction step (use existing schema file)")
    parser.add_argument("--db-name", default=None,
                       help="Database name for loading (default: domain name)")
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
        # Use NLWEB_OUTPUT_DIR if available, otherwise use data directory
        output_base = os.getenv('NLWEB_OUTPUT_DIR', 'data')
        base_dir = os.path.join(output_base, domain.replace('.', '_'))
    
    # Create subdirectories
    urls_dir = os.path.join(base_dir, "urls")
    html_dir = os.path.join(base_dir, "html")
    schema_dir = os.path.join(base_dir, "schemas")
    
    for directory in [urls_dir, html_dir, schema_dir]:
        os.makedirs(directory, exist_ok=True)
    
    logger.info(f"Starting crawl and load pipeline for {domain}")
    logger.info(f"Output directory: {base_dir}")
    
    # Step 1: Get URLs from sitemap
    urls_file = os.path.join(urls_dir, f"{domain}_urls.txt")
    
    if not os.path.exists(urls_file) and not args.skip_crawl:
        logger.info("Step 1: Extracting URLs from sitemap...")
        
        if args.sitemap:
            # Direct sitemap URL provided
            logger.info(f"Using provided sitemap: {args.sitemap}")
            process_site_or_sitemap(args.sitemap, urls_file, verbose=args.verbose)
        else:
            # Let process_site_or_sitemap handle robots.txt checking
            logger.info(f"Checking robots.txt and default locations for {domain}")
            process_site_or_sitemap(domain, urls_file, verbose=args.verbose)
        
        # Count URLs and limit if needed
        with open(urls_file, 'r') as f:
            all_urls = f.readlines()
        
        url_count = len(all_urls)
        logger.info(f"Found {url_count} URLs")
        
        # Limit URLs if max_pages is set
        if args.max_pages and url_count > args.max_pages:
            logger.info(f"Limiting to {args.max_pages} pages")
            with open(urls_file, 'w') as f:
                f.writelines(all_urls[:args.max_pages])
            url_count = args.max_pages
    else:
        if os.path.exists(urls_file):
            with open(urls_file, 'r') as f:
                url_count = sum(1 for _ in f)
            logger.info(f"Using existing URLs file with {url_count} URLs")
        else:
            logger.info("Skipping URL extraction")
            url_count = 0
    
    # Step 2: Crawl URLs
    if not args.skip_crawl and url_count > 0:
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
    
    if not args.skip_extract:
        logger.info("Step 3: Extracting schema markup...")
        
        # Process the HTML directory
        output_file = process_directory(html_dir)
        
        # Move the output file to schema directory if it was created elsewhere
        if os.path.exists(output_file) and output_file != schema_file:
            import shutil
            shutil.move(output_file, schema_file)
            logger.info(f"Schema extraction complete: {schema_file}")
        
        # Count schemas
        if os.path.exists(schema_file):
            with open(schema_file, 'r') as f:
                schema_count = sum(1 for line in f if line.strip())
            logger.info(f"Extracted schemas from {schema_count} pages")
        else:
            logger.error("No schema file was created")
            return
    else:
        logger.info("Skipping extraction step")
        if not os.path.exists(schema_file):
            logger.error(f"Schema file not found: {schema_file}")
            return
    
    # Step 4: Load into database
    logger.info("Step 4: Loading schemas into database...")
    
    # Determine database name/site identifier
    db_name = args.db_name or domain.replace('.', '_')
    
    # Import and use db_load functionality directly
    try:
        from tools.db_load import load_file_to_database
        
        logger.info(f"Loading into database with site identifier '{db_name}'...")
        
        # The schema file format matches what db_load expects: URL\tJSON per line
        # db_load will handle the embeddings generation automatically
        asyncio.run(load_file_to_database(
            file_path=schema_file,
            database=db_name,  # This becomes the 'site' identifier
            namespace=f'https://{domain}',
            type_name='Thing',  # Default, will be overridden by schema @type
            id_prefix=None,
            max_size=None,
            generate_embeddings=True  # Let db_load generate embeddings
        ))
        
        logger.info("Database loading complete!")
        
    except ImportError:
        # Fallback to calling db_load via command line if direct import fails
        logger.warning("Could not import db_load directly, falling back to command line")
        
        # Prepare arguments for db_load
        db_load_args = [
            'db_load.py',
            '--input', schema_file,
            '--site', db_name,  # Use --site instead of --db
            '--namespace', f'https://{domain}',
            '--type', 'Thing'
        ]
        
        # Call db_load via subprocess
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'code.tools.db_load'] + db_load_args[1:],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"db_load failed: {result.stderr}")
            raise Exception(f"Database loading failed: {result.stderr}")
        
        logger.info("Database loading complete!")
        
    except Exception as e:
        logger.error(f"Error loading into database: {e}")
        raise
    
    # Print summary
    print("\n" + "="*60)
    print(f"Crawl and Load Complete for {domain}")
    print("="*60)
    print(f"URLs processed: {url_count}")
    print(f"Output directory: {base_dir}")
    print(f"Schema file: {schema_file}")
    print(f"Database name: {db_name}")
    print("="*60)


if __name__ == "__main__":
    main()