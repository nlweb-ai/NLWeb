# NLWeb Scraping Tools

This directory contains a collection of tools for crawling websites, extracting structured data, and loading it into the NLWeb search system.

## Overview

The scraping pipeline enables you to:
1. Extract URLs from website sitemaps
2. Crawl websites and download HTML content
3. Extract schema.org structured data from HTML pages
4. Load the extracted data into a vector database with embeddings

## Main Tool: crawlAndLoadSite.py

### Purpose
An end-to-end pipeline that automates the entire process of crawling a website and loading its structured data into the NLWeb search system.

### Basic Usage

```bash
# Crawl a website and load its data
python -m code.scraping.crawlAndLoadSite example.com

# Limit the number of pages to crawl
python -m code.scraping.crawlAndLoadSite example.com --max-pages 100

# Skip crawling if HTML files already exist
python -m code.scraping.crawlAndLoadSite example.com --skip-crawl

# Use verbose mode for detailed output
python -m code.scraping.crawlAndLoadSite example.com --verbose
```

### Command-Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `site` | The website domain or URL to crawl | Required |
| `--output-dir` | Custom output directory | `data/<site>` |
| `--sitemap` | Specific sitemap URL to use | Auto-discovered |
| `--max-pages` | Maximum number of pages to crawl | Unlimited |
| `--max-retries` | Maximum retries for failed requests | 3 |
| `--skip-crawl` | Skip crawling if HTML files exist | False |
| `--skip-extract` | Skip extraction if schema file exists | False |
| `--db-name` | Custom database name | Domain with underscores |
| `--verbose` | Enable verbose output | False |

### Pipeline Steps

#### Step 1: Extract URLs from Sitemap
- Discovers sitemap URL from robots.txt
- Parses sitemap XML to extract all page URLs
- Supports both regular and compressed sitemaps

#### Step 2: Crawl URLs
- Downloads HTML content from each URL
- Implements polite crawling with delays
- Uses exponential backoff for retry logic
- Rotates user agents to avoid blocking
- Validates content (rejects responses < 1KB)

#### Step 3: Extract Schema Markup
- Parses HTML files to find JSON-LD structured data
- Extracts schema.org markup
- Consolidates all schemas into a single JSON file

#### Step 4: Load to Database
- Loads extracted schemas into the vector database
- Automatically generates embeddings
- Creates searchable index for the website content

### Directory Structure

The tool creates the following directory structure:

```
data/
└── example_com/
    ├── urls/
    │   └── sitemap_urls.txt    # List of URLs from sitemap
    ├── html/
    │   ├── page1.html          # Downloaded HTML files
    │   ├── page2.html
    │   └── ...
    └── schemas/
        └── extracted_schemas.json  # Extracted schema.org data
```

## Component Tools

### expBackOffCrawl.py (SimpleCrawler)

A robust web crawler with intelligent retry logic:

- **Exponential Backoff**: Automatically retries failed requests with increasing delays
- **User Agent Rotation**: Cycles through different user agents to avoid detection
- **Content Validation**: Rejects invalid or too-small responses
- **Polite Crawling**: Random delays between requests (2-5 seconds)
- **Detailed Statistics**: Tracks success rates and failure reasons

### urlsFromSitemap.py

Extracts URLs from website sitemaps:

- Supports standard sitemap.xml format
- Handles compressed sitemaps (sitemap.xml.gz)
- Auto-discovers sitemaps from robots.txt
- Can process sitemap index files

### extractMarkup.py

Extracts structured data from HTML:

- Finds JSON-LD schema.org markup
- Parses and validates JSON data
- Handles multiple schemas per page
- Provides error reporting for invalid markup

## Example Workflow

### 1. Crawl a Recipe Website

```bash
python -m code.scraping.crawlAndLoadSite recipes.com --max-pages 1000
```

This will:
- Find the sitemap at recipes.com/sitemap.xml
- Download up to 1000 recipe pages
- Extract Recipe schema markup
- Load recipes into the database with embeddings

### 2. Update an Existing Crawl

```bash
python -m code.scraping.crawlAndLoadSite recipes.com --skip-crawl
```

This will:
- Skip downloading HTML (use existing files)
- Re-extract schemas from HTML files
- Load updated data into the database

### 3. Crawl with Custom Settings

```bash
python -m code.scraping.crawlAndLoadSite shop.com \
    --output-dir /custom/path \
    --max-pages 500 \
    --max-retries 5 \
    --db-name shopping_products \
    --verbose
```

## Best Practices

1. **Respect Robots.txt**: The crawler checks robots.txt for sitemap location
2. **Use --max-pages**: Start with a small number to test, then increase
3. **Monitor Progress**: Use --verbose to see detailed crawling statistics
4. **Check Content**: Verify extracted schemas before loading to database
5. **Incremental Updates**: Use --skip-crawl to re-process existing HTML

## Troubleshooting

### Common Issues

1. **No Sitemap Found**
   - Manually specify with `--sitemap` argument
   - Check if the site has a sitemap at standard locations

2. **Failed Requests**
   - Increase `--max-retries` for unreliable sites
   - Check if the site is blocking automated requests

3. **No Schema Data Found**
   - Verify the site uses schema.org markup
   - Check HTML files manually for JSON-LD scripts

4. **Database Load Failures**
   - Ensure database configuration is correct
   - Check that required environment variables are set

## Requirements

- Python 3.7+
- Required packages: requests, beautifulsoup4, lxml
- Database configuration (see main NLWeb documentation)
- Sufficient disk space for HTML storage

## Notes

- The crawler implements polite crawling with delays between requests
- Large sites may take considerable time to fully crawl
- HTML files are preserved for re-processing or debugging
- The tool respects existing files and won't re-download unless forced