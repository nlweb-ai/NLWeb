#!/usr/bin/env python3
"""
Test script for the web scraping pipeline.
This script provides a simple test function to scrape and extract markup from a given site.
"""

import os
import sys
import tempfile
import shutil
from urllib.parse import urlparse

# Import scraping modules
from .urlsFromSitemap import extract_urls_from_sitemap, process_site_or_sitemap
from .expBackOffCrawl import SimpleCrawler
from .extractMarkup import process_directory, extract_schema_markup, extract_canonical_url

# Import common utilities
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("test_scraping")


def test_scrape_and_extract(site_url, max_urls=10, output_dir=None):
    """
    Test function to scrape a website and extract schema markup.
    
    Args:
        site_url: The website URL (e.g., "https://example.com" or just "example.com")
        max_urls: Maximum number of URLs to process (default: 10)
        output_dir: Output directory (default: temporary directory)
    
    Returns:
        dict: Results containing paths to generated files and statistics
    """
    # Parse the site URL
    if not site_url.startswith(('http://', 'https://')):
        site_url = f'https://{site_url}'
    
    parsed = urlparse(site_url)
    domain = parsed.netloc
    
    # Set up output directory
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix=f"nlweb_test_{domain.replace('.', '_')}_")
        logger.info(f"Using temporary directory: {output_dir}")
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    # Create subdirectories
    urls_dir = os.path.join(output_dir, "urls")
    html_dir = os.path.join(output_dir, "html")
    schema_dir = os.path.join(output_dir, "schemas")
    
    for directory in [urls_dir, html_dir, schema_dir]:
        os.makedirs(directory, exist_ok=True)
    
    results = {
        'domain': domain,
        'output_dir': output_dir,
        'urls_extracted': 0,
        'pages_crawled': 0,
        'schemas_found': 0,
        'errors': []
    }
    
    try:
        # Step 1: Extract URLs from sitemap (will check robots.txt automatically)
        urls_file = os.path.join(urls_dir, f"{domain}_urls.txt")
        logger.info(f"Step 1: Extracting URLs for {domain}")
        
        try:
            # Use the new function that handles both domains and sitemap URLs
            process_site_or_sitemap(domain, urls_file)
            
            # Count and limit URLs
            with open(urls_file, 'r') as f:
                all_urls = f.readlines()
            
            results['urls_extracted'] = len(all_urls)
            logger.info(f"Found {len(all_urls)} URLs in sitemap")
            
            # Limit to max_urls
            if len(all_urls) > max_urls:
                logger.info(f"Limiting to first {max_urls} URLs")
                urls_to_process = all_urls[:max_urls]
                with open(urls_file, 'w') as f:
                    f.writelines(urls_to_process)
            else:
                urls_to_process = all_urls
                
        except Exception as e:
            logger.error(f"Failed to extract URLs from sitemap: {e}")
            results['errors'].append(f"Sitemap extraction failed: {e}")
            # Create a minimal URL list with just the homepage
            urls_to_process = [site_url + '\n']
            with open(urls_file, 'w') as f:
                f.writelines(urls_to_process)
        
        # Step 3: Crawl the URLs
        logger.info(f"Step 3: Crawling {len(urls_to_process)} URLs")
        crawler = SimpleCrawler(target_dir=html_dir, max_retries=2)
        crawler.crawl_urls(urls_to_process)
        
        results['pages_crawled'] = crawler.stats.success
        logger.info(f"Crawled {crawler.stats.success} pages successfully")
        
        if crawler.stats.failures > 0:
            results['errors'].append(f"Failed to crawl {crawler.stats.failures} pages")
        
        # Step 4: Extract schema markup
        logger.info("Step 4: Extracting schema markup")
        schema_file = os.path.join(schema_dir, f"{domain}_schemas.txt")
        
        # Process the HTML directory
        output_file = process_directory(html_dir)
        
        # Move the output file to schema directory if it was created elsewhere
        if os.path.exists(output_file) and output_file != schema_file:
            shutil.move(output_file, schema_file)
        
        # Count schemas found
        if os.path.exists(schema_file):
            with open(schema_file, 'r') as f:
                schema_count = sum(1 for line in f if line.strip())
            results['schemas_found'] = schema_count
            logger.info(f"Extracted schemas from {schema_count} pages")
        
        # Add file paths to results
        results['files'] = {
            'urls': urls_file,
            'html_dir': html_dir,
            'schemas': schema_file if os.path.exists(schema_file) else None
        }
        
        # Print summary
        print("\n" + "="*60)
        print(f"Test Scraping Results for {domain}")
        print("="*60)
        print(f"URLs found in sitemap: {results['urls_extracted']}")
        print(f"Pages crawled successfully: {results['pages_crawled']}")
        print(f"Pages with schema markup: {results['schemas_found']}")
        print(f"Output directory: {results['output_dir']}")
        
        if results['errors']:
            print("\nErrors encountered:")
            for error in results['errors']:
                print(f"  - {error}")
        
        # Show sample of extracted schemas
        if results['schemas_found'] > 0 and os.path.exists(schema_file):
            print("\nSample of extracted schemas (first 3):")
            with open(schema_file, 'r') as f:
                for i, line in enumerate(f):
                    if i >= 3:
                        break
                    if line.strip():
                        url, schema = line.strip().split('\t', 1)
                        print(f"\n{i+1}. URL: {url}")
                        # Pretty print first 200 chars of schema
                        import json
                        try:
                            schema_obj = json.loads(schema)
                            pretty_schema = json.dumps(schema_obj, indent=2)
                            if len(pretty_schema) > 200:
                                print(f"   Schema: {pretty_schema[:200]}...")
                            else:
                                print(f"   Schema: {pretty_schema}")
                        except:
                            print(f"   Schema: {schema[:200]}...")
        
        print("="*60 + "\n")
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        results['errors'].append(f"Test failed: {e}")
        raise
    
    return results


def test_single_page(url):
    """
    Test extracting schema markup from a single page.
    
    Args:
        url: The page URL to test
    
    Returns:
        dict: Extracted schema data and canonical URL
    """
    import requests
    import tempfile
    
    logger.info(f"Testing single page: {url}")
    
    # Create a temporary file for the HTML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        temp_file = f.name
        
        # Download the page
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            f.write(response.text)
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return {'error': str(e)}
    
    try:
        # Extract schema and canonical URL
        schemas = extract_schema_markup(temp_file)
        canonical = extract_canonical_url(temp_file)
        
        result = {
            'url': url,
            'canonical_url': canonical,
            'schemas': schemas
        }
        
        # Pretty print the result
        print(f"\nPage: {url}")
        print(f"Canonical URL: {canonical or 'Not found'}")
        
        if schemas and schemas != '[]':
            import json
            try:
                schema_obj = json.loads(schemas)
                print(f"Schemas found: {len(schema_obj)}")
                for i, schema in enumerate(schema_obj):
                    print(f"\n  Schema {i+1}:")
                    print(f"    Type: {schema.get('@type', 'Unknown')}")
                    if 'name' in schema:
                        print(f"    Name: {schema['name']}")
                    if 'url' in schema:
                        print(f"    URL: {schema['url']}")
            except:
                print(f"Raw schemas: {schemas[:200]}...")
        else:
            print("No schemas found")
        
        return result
        
    finally:
        # Clean up
        os.unlink(temp_file)


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 2:
        print("Usage: python test_scraping.py <site_url> [max_urls]")
        print("Examples:")
        print("  python test_scraping.py example.com")
        print("  python test_scraping.py https://example.com 5")
        print("  python test_scraping.py --single https://example.com/page.html")
        sys.exit(1)
    
    if sys.argv[1] == "--single" and len(sys.argv) > 2:
        # Test a single page
        test_single_page(sys.argv[2])
    else:
        # Test full scraping pipeline
        site = sys.argv[1]
        max_urls = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        
        results = test_scrape_and_extract(site, max_urls=max_urls)
        
        print(f"\nTest completed. Results saved in: {results['output_dir']}")