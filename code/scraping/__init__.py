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

from .urlsFromSitemap import extract_urls_from_sitemap, process_site_or_sitemap, get_sitemaps_from_robots
from .expBackOffCrawl import SimpleCrawler
from .extractMarkup import process_directory, extract_schema_markup, extract_canonical_url

__all__ = [
    'extract_urls_from_sitemap',
    'process_site_or_sitemap',
    'get_sitemaps_from_robots',
    'SimpleCrawler',
    'process_directory',
    'extract_schema_markup',
    'extract_canonical_url'
]