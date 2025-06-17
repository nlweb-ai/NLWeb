#!/usr/bin/env python3
"""
Example usage of the web scraping module.
Shows how to use the scraping functions programmatically.
"""

import os
import json
from scraping import (
    extract_urls_from_sitemap,
    SimpleCrawler,
    extract_schema_markup,
    extract_canonical_url,
    process_directory
)


def example_basic_scraping():
    """Basic example: scrape a few pages and extract schemas"""
    
    print("=== Basic Scraping Example ===\n")
    
    # 1. Extract URLs from a sitemap
    sitemap_url = "https://example.com/sitemap.xml"
    urls_file = "example_urls.txt"
    
    print(f"1. Extracting URLs from {sitemap_url}")
    try:
        extract_urls_from_sitemap(sitemap_url, urls_file)
        
        # Read and limit URLs
        with open(urls_file, 'r') as f:
            urls = f.readlines()[:5]  # Just first 5 URLs
        
        print(f"   Found {len(urls)} URLs to process\n")
    except Exception as e:
        print(f"   Could not extract from sitemap: {e}")
        # Use some example URLs instead
        urls = [
            "https://example.com/\n",
            "https://example.com/about\n",
            "https://example.com/products\n"
        ]
    
    # 2. Crawl the URLs
    print("2. Crawling URLs...")
    html_dir = "example_html"
    os.makedirs(html_dir, exist_ok=True)
    
    crawler = SimpleCrawler(target_dir=html_dir, max_retries=2)
    crawler.crawl_urls(urls)
    
    print(f"   Crawled {crawler.stats.success} pages successfully\n")
    
    # 3. Extract schema markup from all HTML files
    print("3. Extracting schema markup...")
    schema_file = process_directory(html_dir)
    
    if os.path.exists(schema_file):
        with open(schema_file, 'r') as f:
            schema_count = sum(1 for line in f if line.strip())
        print(f"   Extracted schemas from {schema_count} pages")
        print(f"   Results saved to: {schema_file}\n")
    
    # Clean up
    if os.path.exists(urls_file):
        os.remove(urls_file)


def example_single_page_extraction():
    """Example: extract schema from a single HTML file"""
    
    print("=== Single Page Extraction Example ===\n")
    
    # For this example, let's create a sample HTML file
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sample Product Page</title>
        <link rel="canonical" href="https://example.com/products/sample" />
        <script type="application/ld+json">
        {
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": "Sample Product",
            "description": "This is a sample product",
            "brand": {
                "@type": "Brand",
                "name": "Example Brand"
            },
            "offers": {
                "@type": "Offer",
                "url": "https://example.com/products/sample",
                "priceCurrency": "USD",
                "price": "29.99"
            }
        }
        </script>
    </head>
    <body>
        <h1>Sample Product</h1>
    </body>
    </html>
    """
    
    # Save to temporary file
    temp_file = "sample_page.html"
    with open(temp_file, 'w') as f:
        f.write(sample_html)
    
    # Extract canonical URL
    canonical = extract_canonical_url(temp_file)
    print(f"Canonical URL: {canonical}")
    
    # Extract schema markup
    schemas_str = extract_schema_markup(temp_file)
    schemas = json.loads(schemas_str)
    
    print(f"\nFound {len(schemas)} schema(s):")
    for i, schema in enumerate(schemas):
        print(f"\nSchema {i+1}:")
        print(json.dumps(schema, indent=2))
    
    # Clean up
    os.remove(temp_file)


def example_custom_processing():
    """Example: custom processing of extracted data"""
    
    print("\n=== Custom Processing Example ===\n")
    
    # Let's say we have a schema file from previous extraction
    schema_data = [
        {
            "url": "https://example.com/product1",
            "schemas": [{
                "@type": "Product",
                "name": "Product 1",
                "price": "19.99"
            }]
        },
        {
            "url": "https://example.com/product2", 
            "schemas": [{
                "@type": "Product",
                "name": "Product 2",
                "price": "29.99"
            }]
        }
    ]
    
    # Process the data - extract all products with prices
    products = []
    for item in schema_data:
        for schema in item['schemas']:
            if schema.get('@type') == 'Product':
                products.append({
                    'url': item['url'],
                    'name': schema.get('name', 'Unknown'),
                    'price': schema.get('price', 'N/A')
                })
    
    print("Extracted Products:")
    for product in products:
        print(f"- {product['name']}: ${product['price']} ({product['url']})")


def example_batch_processing():
    """Example: process multiple sites in batch"""
    
    print("\n=== Batch Processing Example ===\n")
    
    sites = [
        "example.com",
        "example.org",
        "example.net"
    ]
    
    results = {}
    
    for site in sites:
        print(f"Processing {site}...")
        
        # Create site-specific directory
        site_dir = f"data_{site.replace('.', '_')}"
        os.makedirs(site_dir, exist_ok=True)
        
        # You would implement the full pipeline here
        # For this example, we'll just show the structure
        results[site] = {
            'output_dir': site_dir,
            'status': 'completed',
            'urls_found': 10,  # Example numbers
            'pages_crawled': 8,
            'schemas_extracted': 5
        }
    
    # Summary
    print("\nBatch Processing Summary:")
    for site, result in results.items():
        print(f"\n{site}:")
        print(f"  URLs found: {result['urls_found']}")
        print(f"  Pages crawled: {result['pages_crawled']}")
        print(f"  Schemas extracted: {result['schemas_extracted']}")
        print(f"  Output: {result['output_dir']}/")


if __name__ == "__main__":
    import sys
    
    examples = {
        '1': ('Basic scraping', example_basic_scraping),
        '2': ('Single page extraction', example_single_page_extraction),
        '3': ('Custom processing', example_custom_processing),
        '4': ('Batch processing', example_batch_processing)
    }
    
    if len(sys.argv) > 1 and sys.argv[1] in examples:
        _, func = examples[sys.argv[1]]
        func()
    else:
        print("Web Scraping Examples")
        print("=" * 40)
        print("\nAvailable examples:")
        for key, (name, _) in examples.items():
            print(f"{key}. {name}")
        
        print(f"\nRun with: python {sys.argv[0]} <example_number>")
        print(f"Example: python {sys.argv[0]} 1")