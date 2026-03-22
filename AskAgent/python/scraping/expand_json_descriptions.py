#!/usr/bin/env python3
"""
JSONL Site Description Enhancer

This script processes JSONL files containing site descriptions and enhances them
using LLM analysis, optionally crawling site content for better understanding.
"""

import json
import asyncio
import aiohttp
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
import time
import re
from bs4 import BeautifulSoup
import openai
from anthropic import Anthropic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhancement.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class SiteInfo:
    url: str
    name: str
    category: str
    description: str
    type_field: str
    crawled_content: Optional[List[str]] = None
    sitemap_urls: Optional[List[str]] = None

class WebCrawler:
    """Handles website crawling and content extraction."""
    
    def __init__(self, max_pages: int = 5, timeout: int = 30):
        self.max_pages = max_pages
        self.timeout = timeout
        self.session = None
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; SiteAnalyzer/1.0; +https://example.com/bot)'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_sitemap_urls(self, base_url: str) -> List[str]:
        """Extract URLs from sitemap."""
        sitemap_urls = [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml",
            f"{base_url}/robots.txt"
        ]
        
        all_urls = []
        
        for sitemap_url in sitemap_urls:
            try:
                async with self.session.get(sitemap_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        if sitemap_url.endswith('robots.txt'):
                            # Extract sitemap URLs from robots.txt
                            sitemap_matches = re.findall(r'Sitemap:\s*(.+)', content, re.IGNORECASE)
                            for match in sitemap_matches:
                                try:
                                    async with self.session.get(match.strip()) as sitemap_response:
                                        if sitemap_response.status == 200:
                                            sitemap_content = await sitemap_response.text()
                                            urls = self.parse_sitemap(sitemap_content)
                                            all_urls.extend(urls[:self.max_pages])
                                except Exception as e:
                                    logger.warning(f"Error fetching sitemap from robots.txt {match}: {e}")
                        else:
                            urls = self.parse_sitemap(content)
                            all_urls.extend(urls[:self.max_pages])
                        
                        if all_urls:
                            break  # Found a working sitemap
                            
            except Exception as e:
                logger.warning(f"Error fetching sitemap {sitemap_url}: {e}")
                continue
        
        # If no sitemap found, use common page paths
        if not all_urls:
            common_paths = [
                '', '/about', '/products', '/services', '/menu', '/recipes',
                '/categories', '/shop', '/catalog', '/food', '/cooking'
            ]
            all_urls = [f"{base_url}{path}" for path in common_paths]
        
        return list(set(all_urls))[:self.max_pages]
    
    def parse_sitemap(self, content: str) -> List[str]:
        """Parse XML sitemap to extract URLs."""
        urls = []
        try:
            root = ET.fromstring(content)
            
            # Handle sitemap index
            for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None and loc.text:
                    # Recursively fetch individual sitemaps
                    # For simplicity, we'll just add the sitemap URL itself
                    pass
            
            # Handle URL entries
            for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                loc = url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None and loc.text:
                    urls.append(loc.text)
                    
        except ET.ParseError as e:
            logger.warning(f"Error parsing sitemap XML: {e}")
            
        return urls
    
    async def crawl_page(self, url: str) -> Optional[str]:
        """Crawl a single page and extract meaningful content."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    return self.extract_content(content)
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            logger.warning(f"Error crawling {url}: {e}")
            return None
    
    def extract_content(self, html: str) -> str:
        """Extract meaningful content from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script, style, and other non-content elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        
        # Extract text from main content areas
        content_selectors = [
            'main', 'article', '[role="main"]', '.content', '#content',
            '.main', '.recipe', '.product', '.menu-item', '.category'
        ]
        
        content_text = []
        
        for selector in content_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True, separator=' ')
                if text and len(text) > 50:  # Only meaningful content
                    content_text.append(text)
        
        # If no specific content areas found, use body
        if not content_text:
            body = soup.find('body')
            if body:
                content_text.append(body.get_text(strip=True, separator=' '))
        
        # Clean and limit content
        full_content = ' '.join(content_text)
        # Remove excessive whitespace
        full_content = re.sub(r'\s+', ' ', full_content).strip()
        
        # Limit to reasonable length (for LLM processing)
        if len(full_content) > 10000:
            full_content = full_content[:10000] + "..."
        
        return full_content
    
    async def crawl_site(self, base_url: str) -> Tuple[List[str], List[str]]:
        """Crawl a site and return sitemap URLs and content."""
        # Normalize base URL
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"https://{base_url}"
        
        # Get URLs from sitemap
        urls = await self.get_sitemap_urls(base_url)
        logger.info(f"Found {len(urls)} URLs for {base_url}")
        
        # Crawl pages
        content_list = []
        for url in urls[:self.max_pages]:
            content = await self.crawl_page(url)
            if content:
                content_list.append(content)
            # Rate limiting
            await asyncio.sleep(1)
        
        logger.info(f"Crawled {len(content_list)} pages for {base_url}")
        return urls, content_list

class LLMClient:
    """Handles LLM API calls for description enhancement."""
    
    def __init__(self, provider: str, api_key: str, model: str = None):
        self.provider = provider.lower()
        self.api_key = api_key
        
        if self.provider == 'openai':
            openai.api_key = api_key
            self.model = model or 'gpt-4o'
        elif self.provider == 'anthropic':
            self.client = Anthropic(api_key=api_key)
            self.model = model or 'claude-3-5-sonnet-20241022'
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def create_enhancement_prompt(self, site_info: SiteInfo) -> str:
        """Create prompt for LLM to enhance site description."""
        base_prompt = f"""
You need to enhance a site description for "{site_info.name}" (category: {site_info.category}).

Current description: "{site_info.description}"

CRITICAL REQUIREMENTS:
1. Focus on WHAT CONTENT/PRODUCTS/SERVICES are available on the site
2. Include SPECIFIC examples (recipe names, product types, service categories)
3. Describe what kinds of QUERIES could be answered by this site's content
4. DO NOT include company history, founder stories, or business details
5. Make it 200-400 words focused on practical content for determining query relevance

"""
        
        if site_info.crawled_content:
            content_sample = '\n\n'.join(site_info.crawled_content)[:5000]
            base_prompt += f"""
WEBSITE CONTENT ANALYSIS:
Based on crawled content from the website, here's what I found:

{content_sample}

Use this content to identify specific offerings, products, recipes, services, or topics available on the site.
"""
        
        base_prompt += """
OUTPUT FORMAT:
Return ONLY the enhanced description as a single paragraph of 200-400 words. Focus on:
- Specific products/recipes/content available
- Categories and types of information
- What questions this site could answer
- Functional capabilities

Do not include introduction phrases like "This site offers" - start directly with the site name and what it contains.
"""
        
        return base_prompt
    
    async def enhance_description(self, site_info: SiteInfo) -> str:
        """Use LLM to enhance the site description."""
        prompt = self.create_enhancement_prompt(site_info)
        
        try:
            if self.provider == 'openai':
                response = await asyncio.to_thread(
                    openai.chat.completions.create,
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert at analyzing websites and creating concise, practical descriptions focused on content and offerings rather than business history."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=800,
                    temperature=0.7
                )
                return response.choices[0].message.content.strip()
                
            elif self.provider == 'anthropic':
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=800,
                    temperature=0.7,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.content[0].text.strip()
                
        except Exception as e:
            logger.error(f"LLM API error for {site_info.name}: {e}")
            return site_info.description  # Return original on error

class JSONLEnhancer:
    """Main class for enhancing JSONL site descriptions."""
    
    def __init__(self, llm_client: LLMClient, crawler: WebCrawler = None):
        self.llm_client = llm_client
        self.crawler = crawler
    
    def load_jsonl(self, file_path: Path) -> List[SiteInfo]:
        """Load JSONL file and convert to SiteInfo objects."""
        sites = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line.strip())
                    site = SiteInfo(
                        url=data.get('url', ''),
                        name=data.get('name', ''),
                        category=data.get('category', ''),
                        description=data.get('description', ''),
                        type_field=data.get('@type', '')
                    )
                    sites.append(site)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error on line {line_num}: {e}")
                except Exception as e:
                    logger.error(f"Error processing line {line_num}: {e}")
        
        logger.info(f"Loaded {len(sites)} sites from {file_path}")
        return sites
    
    async def enhance_site(self, site_info: SiteInfo, crawl: bool = True) -> SiteInfo:
        """Enhance a single site's description."""
        logger.info(f"Processing {site_info.name} ({site_info.url})")
        
        # Optional crawling
        if crawl and self.crawler and site_info.url:
            try:
                urls, content = await self.crawler.crawl_site(site_info.url)
                site_info.sitemap_urls = urls
                site_info.crawled_content = content
            except Exception as e:
                logger.warning(f"Crawling failed for {site_info.url}: {e}")
        
        # Enhance description with LLM
        enhanced_description = await self.llm_client.enhance_description(site_info)
        site_info.description = enhanced_description
        
        return site_info
    
    def save_jsonl(self, sites: List[SiteInfo], output_path: Path):
        """Save enhanced sites to JSONL file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            for site in sites:
                data = {
                    'url': site.url,
                    '@type': site.type_field,
                    'name': site.name,
                    'category': site.category,
                    'description': site.description
                }
                f.write(json.dumps(data) + '\n')
        
        logger.info(f"Saved {len(sites)} enhanced descriptions to {output_path}")
    
    async def process_all(self, input_path: Path, output_path: Path, crawl: bool = True, 
                         batch_size: int = 5, delay: float = 2.0):
        """Process all sites in the JSONL file."""
        sites = self.load_jsonl(input_path)
        enhanced_sites = []
        
        # Process in batches to avoid overwhelming APIs/servers
        for i in range(0, len(sites), batch_size):
            batch = sites[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(sites)-1)//batch_size + 1}")
            
            # Process batch concurrently
            tasks = [self.enhance_site(site, crawl) for site in batch]
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Batch processing error: {result}")
                    else:
                        enhanced_sites.append(result)
                        
            except Exception as e:
                logger.error(f"Batch {i//batch_size + 1} failed: {e}")
            
            # Rate limiting between batches
            if i + batch_size < len(sites):
                logger.info(f"Waiting {delay} seconds before next batch...")
                await asyncio.sleep(delay)
            
            # Save progress periodically
            if len(enhanced_sites) % (batch_size * 2) == 0:
                temp_path = output_path.with_suffix(f'.temp_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jsonl')
                self.save_jsonl(enhanced_sites, temp_path)
                logger.info(f"Progress saved to {temp_path}")
        
        # Save final results
        self.save_jsonl(enhanced_sites, output_path)
        return enhanced_sites

async def main():
    parser = argparse.ArgumentParser(description="Enhance JSONL site descriptions using LLM")
    parser.add_argument('input_file', help='Input JSONL file path')
    parser.add_argument('output_file', help='Output JSONL file path')
    parser.add_argument('--provider', choices=['openai', 'anthropic'], required=True,
                       help='LLM provider')
    parser.add_argument('--api_key', required=True, help='API key for LLM provider')
    parser.add_argument('--model', help='Model name (optional)')
    parser.add_argument('--crawl', action='store_true', help='Enable web crawling')
    parser.add_argument('--max_pages', type=int, default=5, 
                       help='Maximum pages to crawl per site')
    parser.add_argument('--batch_size', type=int, default=3,
                       help='Number of sites to process concurrently')
    parser.add_argument('--delay', type=float, default=2.0,
                       help='Delay between batches (seconds)')
    parser.add_argument('--timeout', type=int, default=30,
                       help='HTTP timeout (seconds)')
    
    args = parser.parse_args()
    
    # Initialize components
    llm_client = LLMClient(args.provider, args.api_key, args.model)
    
    crawler = None
    if args.crawl:
        crawler = WebCrawler(max_pages=args.max_pages, timeout=args.timeout)
    
    enhancer = JSONLEnhancer(llm_client, crawler)
    
    # Process files
    input_path = Path(args.input_file)
    output_path = Path(args.output_file)
    
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return
    
    logger.info(f"Starting enhancement process...")
    logger.info(f"Input: {input_path}")
    logger.info(f"Output: {output_path}")
    logger.info(f"Provider: {args.provider}")
    logger.info(f"Crawling: {args.crawl}")
    
    start_time = time.time()
    
    if crawler:
        async with crawler:
            await enhancer.process_all(
                input_path, output_path, args.crawl, 
                args.batch_size, args.delay
            )
    else:
        await enhancer.process_all(
            input_path, output_path, args.crawl, 
            args.batch_size, args.delay
        )
    
    end_time = time.time()
    logger.info(f"Enhancement completed in {end_time - start_time:.2f} seconds")

if __name__ == '__main__':
    asyncio.run(main())
