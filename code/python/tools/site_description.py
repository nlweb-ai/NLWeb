#!/usr/bin/env python3
"""
Shopify Store Description Generator

This script processes JSONL files containing Shopify store information and generates
detailed 2000-word descriptions for each store by:
1. Fetching robots.txt and sitemap data
2. Analyzing URL patterns using LLM
3. Generating comprehensive descriptions
"""

import json
import sys
import asyncio
import time
import traceback
from typing import Dict, List, Optional, Any
from pathlib import Path
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from io import BytesIO
import gzip

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm import ask_llm
from core.config import CONFIG
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("site_description")

class ShopifyDescriptionGenerator:
    """Generate detailed descriptions for Shopify stores."""
    
    def __init__(self, input_file: str, output_file: str, llm_provider: Optional[str] = None):
        """Initialize the generator with input and output file paths."""
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.llm_provider = llm_provider  # Allow override of LLM provider
        
    def get_processed_urls(self):
        """Get set of URLs already processed from output file."""
        processed_urls = set()
        if self.output_file.exists():
            line_count = 0
            with open(self.output_file, 'r') as f:
                for line in f:
                    line_count += 1
                    try:
                        data = json.loads(line)
                        if 'url' in data:
                            processed_urls.add(data['url'])
                    except Exception as e:
                        print(f"Warning: Could not parse line {line_count}: {e}")
                        continue
            print(f"Resuming from previous run:")
            print(f"  - Found {line_count} lines in output file")
            print(f"  - Loaded {len(processed_urls)} unique URLs from output")
        return processed_urls
    
    def get_sitemaps_from_robots(self, domain: str) -> tuple[List[str], str]:
        """Extract sitemap URLs from robots.txt and detect store type.
        Returns: (sitemaps, store_type)
        """
        if not domain.startswith(('http://', 'https://')):
            domain = f'https://{domain}'
        
        parsed = urlparse(domain)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        try:
            response = requests.get(robots_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            
            robots_content = response.text.lower()
            
            # Detect CMS/platform type from robots.txt patterns
            store_type = "Website"  # Default
            
            # Check for Shopify patterns
            if 'shopify' in robots_content or '.myshopify.com' in domain:
                store_type = "Shopify"
            # Check for CraftCMS
            elif '/cpresources/' in robots_content:
                store_type = "CraftCMS"
            # Check for WordPress/WooCommerce
            elif 'wp-admin' in robots_content or 'wp-content' in robots_content:
                if 'woocommerce' in robots_content:
                    store_type = "WooCommerce"
                else:
                    store_type = "WordPress"
            # Check for Magento
            elif 'magento' in robots_content or '/downloader/' in robots_content:
                store_type = "Magento"
            # Check for BigCommerce
            elif 'bigcommerce' in robots_content:
                store_type = "BigCommerce"
            # Check for Squarespace
            elif 'squarespace' in robots_content:
                store_type = "Squarespace"
            # Check for Wix
            elif 'wix' in robots_content or '_wix_' in robots_content:
                store_type = "Wix"
            # Check for PrestaShop
            elif 'prestashop' in robots_content or '/modules/' in robots_content:
                store_type = "PrestaShop"
            # Check for OpenCart
            elif 'opencart' in robots_content or '/catalog/' in robots_content:
                store_type = "OpenCart"
            # Check for Drupal
            elif 'drupal' in robots_content or '/core/' in robots_content:
                store_type = "Drupal"
            # Check for Joomla
            elif 'joomla' in robots_content or '/administrator/' in robots_content:
                store_type = "Joomla"
            
            # Override for known Shopify stores (only if truly Shopify)
            known_shopify_domains = ['bragg.com']  # Removed bobsredmill.com since it's CraftCMS
            if any(domain.endswith(d) for d in known_shopify_domains):
                store_type = "Shopify"
            
            sitemaps = []
            for line in response.text.splitlines():
                line = line.strip()
                if line.lower().startswith('sitemap:'):
                    sitemap_url = line.split(':', 1)[1].strip()
                    if not sitemap_url.startswith(('http://', 'https://')):
                        sitemap_url = urljoin(domain, sitemap_url)
                    sitemaps.append(sitemap_url)
            
            return sitemaps, store_type
        except Exception as e:
            logger.warning(f"Could not read robots.txt from {robots_url}: {e}")
            return [], "Website"
    
    def extract_urls_from_sitemap(self, sitemap_url: str, limit: int = 50) -> List[str]:
        """Extract URLs from a sitemap (limited to avoid overwhelming the LLM)."""
        urls = []
        
        try:
            response = requests.get(sitemap_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            
            if response.status_code != 200:
                return urls
                
            if sitemap_url.endswith('.gz'):
                content = gzip.GzipFile(fileobj=BytesIO(response.content)).read()
            else:
                content = response.content
            
            root = ET.fromstring(content)
            
            # Handle namespace
            namespace = root.tag[1:].split("}")[0] if "}" in root.tag else ""
            ns = {"ns": namespace} if namespace else {}
            
            # Check if this is a sitemap index
            sitemaps = root.findall(".//ns:sitemap", ns) if ns else root.findall(".//sitemap")
            if sitemaps:
                # Process first sitemap from index
                for sitemap in sitemaps[:1]:  # Just get first one
                    loc = sitemap.find("ns:loc", ns) if ns else sitemap.find("loc")
                    if loc is not None and loc.text:
                        return self.extract_urls_from_sitemap(loc.text.strip(), limit)
            else:
                # Regular sitemap
                url_elements = root.findall(".//ns:url", ns) if ns else root.findall(".//url")
                for url_elem in url_elements[:limit]:
                    loc = url_elem.find("ns:loc", ns) if ns else url_elem.find("loc")
                    if loc is not None and loc.text:
                        urls.append(loc.text.strip())
            
        except Exception as e:
            logger.warning(f"Error processing sitemap {sitemap_url}: {e}")
        
        return urls
    
    def get_default_sitemaps(self, domain: str) -> List[str]:
        """Try default sitemap locations."""
        if not domain.startswith(('http://', 'https://')):
            domain = f'https://{domain}'
        
        parsed = urlparse(domain)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        return [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml",
            f"{base_url}/sitemap/sitemap.xml",
            f"{base_url}/sitemap_products_1.xml"  # Common Shopify pattern
        ]
    
    async def analyze_urls(self, store_name: str, urls: List[str]) -> str:
        """Use LLM to analyze URL patterns and predict content."""
        if not urls:
            return "No URLs available for analysis"
        
        # Prepare URL list for analysis
        url_sample = "\n".join(urls[:50])  # Limit to 50 URLs
        
        prompt = f"""Analyze these URLs from the Shopify store "{store_name}" and provide insights about:
1. Product categories and types
2. Site structure and organization
3. Special collections or features
4. Target audience based on URL patterns

URLs:
{url_sample}

Provide a detailed analysis that will help generate a comprehensive store description."""
        
        schema = {
            "type": "object",
            "properties": {
                "analysis": {
                    "type": "string",
                    "description": "Detailed analysis of the store based on URLs"
                }
            },
            "required": ["analysis"]
        }
        
        try:
            # Try different providers if the preferred one fails
            result = await ask_llm(
                prompt=prompt,
                schema=schema,
                provider=self.llm_provider,
                level="high",
                max_length=1024,
                timeout=30  # Increase timeout to 30 seconds
            )
            return result.get("analysis", "Analysis unavailable")
        except Exception as e:
            logger.error(f"Error analyzing URLs: {e}")
            return "URL analysis failed"
    
    async def generate_description(self, store_data: Dict, url_analysis: str) -> str:
        """Generate a detailed 2000-word description for the store."""
        
        # Truncate URL analysis if too long
        if len(url_analysis) > 2000:
            url_analysis = url_analysis[:2000] + "...[truncated for length]"
        
        prompt = f"""Create compact product inventory list for {store_data.get('name', 'Unknown')}.

Store URL: {store_data.get('url', '')}
Category: {store_data.get('category', 'General')}

Sitemap URLs analyzed:
{url_analysis}

Generate BULLET-POINT INVENTORY (no sentences, just lists):

## PRODUCTS BY CATEGORY
• Category1: item1, item2, item3, item4, item5
• Category2: item1, item2, item3, item4, item5
• Category3: item1, item2, item3, item4, item5
(Continue for all categories found)

## ALL PRODUCTS A-Z
• Product1 (size1, size2, size3)
• Product2 (flavor1, flavor2, flavor3)  
• Product3 (variant1, variant2)
• Product4 (pack sizes)
(List every product alphabetically)

## SPECIFICATIONS
• Sizes: list all sizes
• Flavors: list all flavors
• Colors: list all colors
• Materials: list all materials
• Package types: bottles, bags, boxes, etc.

## BRANDS
• Brand1
• Brand2
• Brand3

## NOT SOLD
• Category1, Category2, Category3
• Category4, Category5, Category6

RULES:
- Use bullets (•) not sentences
- NO marketing words (premium, quality, artisan, best, finest)
- NO descriptions, just product names
- Be specific: "habanero sauce" not "hot sauce"
- Include all sizes/variants in parentheses
- Keep extremely compact"""
        
        # Debug: Print prompt length
        print(f"  - Description prompt length: {len(prompt)} characters")
        if len(prompt) > 10000:
            print(f"    WARNING: Prompt is very long! First 500 chars:")
            print(f"    {prompt[:500]}...")
        
        schema = {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Compact bullet-point product inventory list"
                }
            },
            "required": ["description"]
        }
        
        # Retry logic for LLM calls
        max_retries = 5
        for attempt in range(max_retries):
            try:
                result = await ask_llm(
                    prompt=prompt,
                    schema=schema,
                    provider=self.llm_provider,
                    level="high",  # Use high-tier model for longer, quality descriptions
                    max_length=4096,
                    timeout=180  # Increase timeout to 180 seconds for longer descriptions
                )
                description = result.get("description", "")
                
                # Check for repetitive content (same phrase repeated many times)
                if description:
                    # Split into words and check for excessive repetition
                    words = description.split()
                    if len(words) > 100:
                        # Check if any 5-word phrase appears more than 10 times
                        phrase_counts = {}
                        for i in range(len(words) - 4):
                            phrase = ' '.join(words[i:i+5])
                            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
                        
                        max_repetitions = max(phrase_counts.values()) if phrase_counts else 0
                        if max_repetitions > 10:
                            print(f"    Warning: Detected repetitive content (phrase repeated {max_repetitions} times)")
                            description = ""  # Treat as failed
                
                if description and description != "Description generation failed":
                    return description
                else:
                    print(f"    Attempt {attempt + 1} failed: Empty or invalid response")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(5)  # Wait 5 seconds before retry
            except Exception as e:
                logger.error(f"Error generating description (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    print(f"    Retrying... ({attempt + 2}/{max_retries})")
                    await asyncio.sleep(5)  # Wait 5 seconds before retry
                else:
                    return "Description generation failed after 5 attempts"
        
        return "Description generation failed after all retries"
    
    async def process_store(self, store_data: Dict) -> Dict:
        """Process a single store entry."""
        url = store_data.get('url', '')
        name = store_data.get('name', 'Unknown Store')
        
        print(f"\nProcessing: {name} ({url})")
        
        # Step 1: Get sitemap URLs and detect store type
        print("  - Fetching robots.txt...")
        sitemaps, store_type = self.get_sitemaps_from_robots(url)
        print(f"  - Detected store type: {store_type}")
        
        if not sitemaps:
            print("  - Trying default sitemap locations...")
            for default_sitemap in self.get_default_sitemaps(url):
                try:
                    response = requests.head(default_sitemap, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                    if response.status_code == 200:
                        sitemaps = [default_sitemap]
                        break
                except:
                    continue
        
        # Step 2: Extract URLs from sitemap
        all_urls = []
        if sitemaps:
            print(f"  - Found {len(sitemaps)} sitemap(s)")
            for sitemap in sitemaps[:2]:  # Process max 2 sitemaps
                urls = self.extract_urls_from_sitemap(sitemap)
                all_urls.extend(urls)
                if all_urls:
                    break  # Got some URLs, that's enough
        else:
            print("  - No sitemaps found")
        
        # Step 3: Analyze URLs
        print(f"  - Analyzing {len(all_urls)} URLs...")
        url_analysis = await self.analyze_urls(name, all_urls)
        
        # Step 4: Generate detailed description
        print("  - Generating detailed description...")
        detailed_description = await self.generate_description(store_data, url_analysis)
        
        # Step 5: Prepare enhanced data
        enhanced_data = store_data.copy()
        enhanced_data['@type'] = store_type  # Use detected store type
        enhanced_data['detailed_description'] = detailed_description
        enhanced_data['sitemap_analysis'] = url_analysis
        enhanced_data['processing_metadata'] = {
            'processed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'sitemaps_found': len(sitemaps),
            'urls_analyzed': len(all_urls),
            'store_type': store_type
        }
        
        print(f"  - Complete! Description length: {len(detailed_description)} chars")
        
        # Add delay to avoid rate limits
        await asyncio.sleep(2)
        
        return enhanced_data
    
    async def run(self):
        """Process all stores from the input file."""
        # Get already processed URLs from output file
        processed_urls = self.get_processed_urls()
        
        # Load input data
        stores = []
        with open(self.input_file, 'r') as f:
            for line in f:
                try:
                    stores.append(json.loads(line))
                except:
                    continue
        
        print(f"Loaded {len(stores)} stores from {self.input_file}")
        
        # Count how many stores from THIS input file still need processing
        stores_to_process = []
        already_processed_count = 0
        
        for store in stores:
            url = store.get('url', '')
            if url not in processed_urls:
                stores_to_process.append(store)
            else:
                already_processed_count += 1
        
        print(f"  - {already_processed_count} stores from this input already processed")
        print(f"  - {len(stores_to_process)} stores remaining to process")
        
        # Check for duplicates in input
        all_input_urls = [store.get('url', '') for store in stores]
        unique_input_urls = set(all_input_urls)
        if len(all_input_urls) != len(unique_input_urls):
            print(f"\nWARNING: Input file has duplicate URLs!")
            print(f"  - Total entries: {len(all_input_urls)}")
            print(f"  - Unique URLs: {len(unique_input_urls)}")
            print(f"  - Duplicates: {len(all_input_urls) - len(unique_input_urls)}")
        
        # Process each store and write immediately
        for idx, store in enumerate(stores_to_process, 1):
            url = store.get('url', '')
            
            try:
                # Find the original position in the input file
                original_position = stores.index(store) + 1
                print(f"\n[{idx}/{len(stores_to_process)}] Processing new store (#{original_position} of {len(stores)} in input file)...")
                enhanced_store = await self.process_store(store)
                
                # Write to output file immediately (append mode)
                with open(self.output_file, 'a') as f:
                    f.write(json.dumps(enhanced_store) + '\n')
                    f.flush()  # Ensure data is written immediately
                
                print(f"  - Successfully saved to {self.output_file}")
                
            except Exception as e:
                print(f"Error processing {url}: {e}")
                logger.error(f"Error processing {url}: {traceback.format_exc()}")
                
                # Write original data with error note
                error_store = store.copy()
                error_store['processing_error'] = str(e)
                error_store['detailed_description'] = "Processing failed after all retries"
                
                with open(self.output_file, 'a') as f:
                    f.write(json.dumps(error_store) + '\n')
                    f.flush()
                
                print(f"  - Saved error record to {self.output_file}")
        
        # Count final results
        final_count = len(processed_urls) + len(stores_to_process)
        
        print(f"\nProcessing complete!")
        print(f"  - Processed {len(stores_to_process)} stores in this run")
        print(f"  - Total stores in output file: {final_count}")
        print(f"  - Output saved to: {self.output_file}")

def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python site_description.py <input.jsonl> <output.jsonl> [llm_provider]")
        print("Example: python site_description.py sample_stores.jsonl enhanced_stores.jsonl")
        print("Example with provider: python site_description.py sample_stores.jsonl enhanced_stores.jsonl openai")
        print("\nAvailable LLM providers from config:")
        from core.llm import get_available_providers
        providers = get_available_providers()
        if providers:
            for p in providers:
                print(f"  - {p}")
        else:
            print("  No providers configured (check environment variables)")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    llm_provider = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Check input file exists
    if not Path(input_file).exists():
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)
    
    # CONFIG is already initialized when imported
    # Initialize LLM providers
    from core.llm import init as llm_init, get_available_providers
    llm_init()
    
    # Check available providers
    available = get_available_providers()
    if not available:
        print("Error: No LLM providers are configured. Please set environment variables for API keys.")
        print("Required environment variables based on config_llm.yaml:")
        print("  - OPENAI_API_KEY for OpenAI")
        print("  - ANTHROPIC_API_KEY for Anthropic")
        print("  - GEMINI_API_KEY for Gemini")
        print("  - AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT for Azure OpenAI")
        sys.exit(1)
    
    if llm_provider and llm_provider not in available:
        print(f"Error: Provider '{llm_provider}' not available.")
        print(f"Available providers: {', '.join(available)}")
        sys.exit(1)
    
    if llm_provider:
        print(f"Using specified LLM provider: {llm_provider}")
    else:
        print(f"Using default LLM provider from config: {CONFIG.preferred_llm_endpoint}")
        if CONFIG.preferred_llm_endpoint not in available:
            llm_provider = available[0]
            print(f"Default provider not available, using: {llm_provider}")
    
    # Create and run generator
    generator = ShopifyDescriptionGenerator(input_file, output_file, llm_provider)
    asyncio.run(generator.run())

if __name__ == "__main__":
    main()