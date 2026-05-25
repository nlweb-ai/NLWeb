"""
Web scraping utilities for NLWeb.

This module provides functionality for:
- Extracting URLs from sitemaps
- Crawling websites with exponential backoff
- Extracting schema markup from HTML
- Loading extracted data into vector database

Main scripts:
- markupFromSite.py: Extract markup and optionally generate embeddings
  Usage: python -m code.scraping.markupFromSite <domain>

- crawlAndLoadSite.py: Complete pipeline from crawl to database
  Usage: python -m code.scraping.crawlAndLoadSite <domain>
"""

from .expBackOffCrawl import SimpleCrawler
from .extractMarkup import extract_canonical_url, extract_schema_markup, process_directory
from .urlsFromSitemap import extract_urls_from_sitemap, get_sitemaps_from_robots, process_site_or_sitemap

__all__ = [
    'SimpleCrawler',
    'extract_canonical_url',
    'extract_schema_markup',
    'extract_urls_from_sitemap',
    'get_sitemaps_from_robots',
    'process_directory',
    'process_site_or_sitemap'
]
