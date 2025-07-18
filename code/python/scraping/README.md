# Incremental Website Crawler

## Overview

The incremental crawler (`incrementalCrawlAndLoad.py`) is designed to crawl websites one page at a time, extract schema.org markup, generate embeddings, and load the data into a vector database. Unlike a batch crawler, this tool processes URLs individually and maintains state, allowing you to stop and resume crawling at any time.

## Key Features

- **Incremental Processing**: Processes one URL at a time instead of batch processing
- **Resume Capability**: Automatically resumes from where it left off if interrupted
- **HTML Archiving**: Saves all crawled HTML pages for future reference
- **Status Tracking**: Maintains detailed crawl status in JSON format
- **Real-time Progress**: Shows live progress with schema type statistics
- **Database Flexibility**: Supports multiple vector database backends

## Usage

### Basic Usage
Run this command from the "code" directory:

```bash
# Crawl a website using default settings
python -m scraping.incrementalCrawlAndLoad example.com

# Specify a maximum number of pages to crawl
python -m scraping.incrementalCrawlAndLoad example.com --max-pages 100

# Use a specific database backend
python -m scraping.incrementalCrawlAndLoad example.com --database qdrant_local
```

### Command Line Options

- `site`: Website domain or URL to crawl (required)
- `--output-dir`: Custom output directory (default: `NLWeb/data/<domain>`)
- `--sitemap`: Specific sitemap URL to use instead of auto-discovery
- `--max-pages`: Maximum number of pages to crawl
- `--max-retries`: Maximum retries for failed requests (default: 3)
- `--no-resume`: Start fresh instead of resuming previous crawl
- `--reprocess`: Reprocess existing HTML files (skip download, recompute embeddings)
- `--db-name`: Database name/collection for loading (default: domain name)
- `--database`: Specific database endpoint (e.g., azure_ai_search, qdrant_local)
- `--verbose`: Enable verbose output

### Examples

```bash
# Resume a previous crawl
python -m scraping.incrementalCrawlAndLoad example.com

# Start fresh (ignore previous progress)
python -m scraping.incrementalCrawlAndLoad example.com --no-resume

# Use custom output directory
python -m scraping.incrementalCrawlAndLoad example.com --output-dir ./my-crawl-data

# Crawl with specific database and limit
python -m scraping.incrementalCrawlAndLoad example.com --database azure_ai_search --max-pages 500

# Reprocess existing HTML files with new embeddings
python -m scraping.incrementalCrawlAndLoad example.com --reprocess

# Reprocess and send to a different database
python -m scraping.incrementalCrawlAndLoad example.com --reprocess --database qdrant_local
```

## Output Structure

The crawler creates the following directory structure:

```
NLWeb/data/<domain>/
├── urls/
│   └── <domain>_urls.txt          # List of all URLs from sitemap
├── html/
│   ├── <hash>_<path>.html        # Saved HTML pages
│   └── ...
└── crawl_status.json             # Detailed status for each URL
```

## Status Tracking

The `crawl_status.json` file tracks detailed information for each URL:

```json
{
  "url_hash": {
    "url": "https://example.com/page",
    "started_at": "2024-01-15T10:30:00",
    "fetched_at": "2024-01-15T10:30:01",
    "page_size": 45678,
    "html_file": "hash_page.html",
    "json_size": 2345,
    "schema_count": 3,
    "uploaded_at": "2024-01-15T10:30:02",
    "documents_uploaded": 3,
    "completed": true,
    "uploaded": true
  }
}
```

## Progress Display

During crawling, you'll see real-time progress updates:

```
Progress: 156/3507 (4.4%) | Success: 150 | Failed: 2 | Already crawled: 4 | JSON: 125.3KB | Schemas: 287 | Docs uploaded: 150 | Types: Product:89, WebPage:45, Organization:12
```

The progress shows:
- **Progress**: Current page / Total pages (percentage)
- **Success**: Successfully processed pages
- **Failed**: Pages that failed to process
- **Already crawled**: Pages skipped because they were previously processed
- **JSON**: Total size of extracted schema.org data
- **Schemas**: Total number of schemas found
- **Docs uploaded**: Documents successfully uploaded to database
- **Types**: Top 3 most common schema.org types found

## Final Summary

At completion, you'll see a detailed summary:

```
INFO:incremental_crawl_and_load:Crawl completed: 150 successful, 2 failed, 4 already crawled
INFO:incremental_crawl_and_load:Total JSON extracted: 125.3KB from 287 schemas
INFO:incremental_crawl_and_load:Total documents uploaded to database: 150
INFO:incremental_crawl_and_load:Schema types found:
INFO:incremental_crawl_and_load:  Product: 89
INFO:incremental_crawl_and_load:  WebPage: 45
INFO:incremental_crawl_and_load:  Organization: 12
INFO:incremental_crawl_and_load:  BreadcrumbList: 8
INFO:incremental_crawl_and_load:  SearchAction: 3
INFO:incremental_crawl_and_load:Data uploaded to: qdrant_local
```

## How It Works

1. **URL Discovery**: Extracts URLs from the website's sitemap(s)
2. **Incremental Processing**: For each URL:
   - Checks if HTML already exists (skip download if yes)
   - Downloads and saves HTML if needed
   - Extracts schema.org markup using BeautifulSoup
   - Counts schema types recursively
   - Generates embeddings for the content
   - Uploads to the specified database
   - Updates status file
3. **Resume Logic**: 
   - Always refreshes URL list to catch new pages
   - Checks saved HTML files to avoid re-downloading
   - Uses status file to track which pages are fully processed

## Resume Behavior

The crawler is designed to be stopped and resumed:

- **Stopping**: Press Ctrl+C to stop the crawler gracefully
- **Resuming**: Run the same command again - it will:
  - Skip pages that have already been downloaded AND processed
  - Re-process pages that were downloaded but not uploaded
  - Continue with new pages

## Reprocess Mode

The `--reprocess` flag allows you to recompute embeddings and re-upload existing HTML files:

- **Purpose**: Useful when you want to:
  - Change the embedding model
  - Upload to a different database
  - Fix issues with previous uploads
  - Update embeddings after configuration changes
- **Behavior**:
  - Skips downloading (won't fetch new pages)
  - Only processes URLs that have existing HTML files
  - Recomputes embeddings for all content
  - Re-uploads to the specified database
- **Note**: This will overwrite existing entries in the database

## Database Configuration

The crawler uses the database configuration from `config_retrieval.yaml`. You can:

1. Use the default database (configured as `write_endpoint`)
2. Specify a database with `--database` flag
3. Available options depend on your configuration (e.g., azure_ai_search, qdrant_local, milvus, opensearch)

## Error Handling

- Failed pages are marked in the status file with error messages
- The crawler continues with the next URL after failures
- HTTP errors are retried with exponential backoff
- All errors are logged for debugging

## Performance Notes

- Each page is processed individually (no batching)
- Embeddings are generated per page
- Database uploads happen immediately after processing
- HTML files are kept permanently for reference
- The status file is updated after each page

## Comparison with Batch Crawler

| Feature | Incremental Crawler | Batch Crawler |
|---------|-------------------|---------------|
| Processing | One page at a time | All pages in phases |
| Resumability | Full resume support | Limited |
| HTML Storage | Always saved | Temporary |
| Status Tracking | Detailed per-URL | Basic statistics |
| Memory Usage | Low (one page) | High (all pages) |
| Speed | Slower | Faster |
| Interruption Recovery | Excellent | Poor |

## Troubleshooting

1. **"Already crawled" count is high**: This is normal when resuming - it means those pages were successfully processed before

2. **Progress seems slow**: The incremental approach trades speed for reliability and resumability

3. **Database upload fails**: Check your database configuration and credentials in the config files

4. **No schemas found**: Some pages may not have schema.org markup - this is normal

5. **httpx logs appearing**: These should be suppressed, but if they appear, they indicate embedding API calls

## Environment Variables

- `NLWEB_OUTPUT_DIR`: Override the default data directory location

## Tips

1. For large sites, use `--max-pages` to test with a subset first
2. Monitor the schema types to understand what content is being found
3. Check `crawl_status.json` for detailed information about any failures
4. Use `--verbose` for more detailed logging
5. The HTML archive can be used for debugging or reprocessing