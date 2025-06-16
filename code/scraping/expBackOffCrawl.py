import sys
import os
import requests
from urllib.parse import urlparse
import time
from typing import List, Optional
from dataclasses import dataclass, field
from collections import Counter
import logging
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# List of common user agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]

@dataclass
class ResponseInfo:
    """Store information about problematic responses for analysis"""
    url: str
    status: Optional[int] = None
    content_length: Optional[int] = None
    content_sample: Optional[str] = None
    error_type: Optional[str] = None
    
    def __str__(self):
        parts = [f"URL: {self.url}"]
        if self.status:
            parts.append(f"Status: {self.status}")
        if self.content_length is not None:
            parts.append(f"Size: {self.content_length} bytes")
        if self.error_type:
            parts.append(f"Error: {self.error_type}")
        if self.content_sample:
            # Truncate and clean sample for display
            sample = self.content_sample.strip()
            if len(sample) > 100:
                sample = sample[:97] + "..."
            # Replace newlines with spaces for compact display
            sample = sample.replace("\n", " ").replace("\r", "")
            parts.append(f"Content: '{sample}'")
        return " | ".join(parts)

@dataclass
class CrawlStats:
    total: int = 0
    success: int = 0
    failures: int = 0
    retries: int = 0
    failure_reasons: Counter = field(default_factory=Counter)
    retry_reasons: Counter = field(default_factory=Counter)
    small_responses: List[ResponseInfo] = field(default_factory=list)
    
    def add_small_response(self, response_info: ResponseInfo):
        """Add a small response to the tracking list, maintaining a reasonable size"""
        self.small_responses.append(response_info)
        # Keep the list at a reasonable size to avoid memory issues
        if len(self.small_responses) > 100:  # Keep the most recent 100
            self.small_responses = self.small_responses[-100:]
    
    def print_status(self):
        """Print the current status"""
        print(f"\rProgress: {self.success} successful | {self.failures} failed | " 
              f"Retries: {self.retries} | Total: {self.total}", end="", flush=True)
    
    def print_failure_summary(self):
        """Print a summary of failures at the end of the crawl"""
        print("\n\nFailure Analysis:")
        print("-" * 60)
        
        # Print permanent failures
        if self.failure_reasons:
            print("Permanent Failures:")
            for reason, count in self.failure_reasons.most_common():
                percentage = (count / self.failures * 100) if self.failures > 0 else 0
                print(f"  {reason}: {count} ({percentage:.1f}%)")
        else:
            print("No permanent failures recorded")
            
        # Print retry statistics
        if self.retry_reasons:
            print("\nRetried Errors:")
            total_retries = sum(self.retry_reasons.values())
            for reason, count in self.retry_reasons.most_common():
                percentage = (count / total_retries * 100)
                print(f"  {reason}: {count} ({percentage:.1f}%)")
        else:
            print("\nNo retries recorded")
            
        # Display small responses
        if self.small_responses:
            print("\nSamples of Small Responses:")
            print("-" * 60)
            # Show up to 10 samples
            for i, response in enumerate(self.small_responses[-10:]):
                print(f"{i+1}. {response}")
                
        print("-" * 60)

class SimpleCrawler:
    def __init__(self, target_dir: str, max_retries: int = 3):
        self.target_dir = target_dir
        self.max_retries = max_retries
        self.stats = CrawlStats()
        
        # Create target directory if it doesn't exist
        os.makedirs(target_dir, exist_ok=True)

    def categorize_error(self, error, status: int = None, content_length: int = None) -> str:
        """Categorize the type of error encountered"""
        error_str = str(error).lower()
        
        if content_length is not None and content_length < 1024:
            return "Content too small (<1KB)"
        elif status is not None:
            if status == 403:
                return "Access forbidden (403)"
            elif status == 404:
                return "Page not found (404)"
            elif status == 429:
                return "Rate limited (429)"
            elif status == 500:
                return "Server error (500)"
            elif status >= 400:
                return f"HTTP error {status}"
        
        if "timeout" in error_str:
            return "Request timeout"
        elif "connection" in error_str:
            return "Connection error"
        elif "dns" in error_str:
            return "DNS resolution failed"
        elif "ssl" in error_str:
            return "SSL/TLS error"
        elif "invalid" in error_str and "url" in error_str:
            return "Invalid URL"
        return f"Other error: {error_str[:100]}"

    def get_retry_delay(self, attempt: int, error_type: str = None) -> float:
        """
        Calculate delay using exponential backoff algorithm.
        Base delay is 2 seconds, doubled for each attempt with some jitter.
        """
        # Longer base delay for rate limiting errors
        base_delay = 5.0 if error_type and "429" in error_type else 2.0
        
        # Calculate exponential backoff with jitter
        # 2^attempt gives us: 2, 4, 8, 16, 32, etc.
        delay = base_delay * (2 ** attempt)
        
        # Add jitter (±25%)
        jitter = delay * 0.25
        delay = delay + random.uniform(-jitter, jitter)
        
        # Cap maximum delay at 5 minutes
        return min(delay, 300)

    def should_retry(self, error_type: str, attempt: int) -> bool:
        """Determine whether to retry based on error type and attempt number"""
        # Don't retry if we've hit the maximum attempts
        if attempt >= self.max_retries:
            return False
            
        # Never retry for these error types
        if error_type and any(x in error_type for x in ["404", "403", "Invalid URL", "<1KB"]):
            return False
            
        # Always retry for these error types
        if error_type and any(x in error_type for x in [
            "429", "500", "timeout", "connection", "dns", "ssl"
        ]):
            return True
            
        # For other errors, retry if we haven't hit the max retries
        return attempt < self.max_retries


    def crawl_url(self, url: str, attempt: int = 0):
        """Crawl a single URL with retry logic"""
        # Skip empty URLs
        if not url.strip():
            return
            
        # Parse URL to create filename
        parsed_url = urlparse(url)
        filename = parsed_url.netloc + parsed_url.path
        if filename.endswith('/'):
            filename = filename[:-1]
        filename = filename.replace('/', '_') + '.html'
        output_path = os.path.join(self.target_dir, filename)

        # Note: We now check for existing files in crawl_urls() before calling this method
        # so we don't need to check again here

        try:
            content = None
            status = None
            
            logger.info(f"Fetching {url} directly")
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=30)
            status = response.status_code
            content = response.text
            
            content_length = len(content.encode('utf-8')) if content else 0
            
            # Check content length (1KB = 1024 bytes)
            if content_length < 1024:
                # Print the small content directly
                print(f"\n\n{'=' * 80}")
                print(f"SMALL CONTENT DETECTED ({content_length} bytes) from {url}")
                print(f"{'=' * 80}")
                print(content[:1000] if len(content) > 1000 else content)  # Limit to first 1000 chars
                print(f"{'=' * 80}\n")
                
                # Create a response info object for small responses
                response_info = ResponseInfo(
                    url=url,
                    status=status,
                    content_length=content_length,
                    content_sample=content[:200] if content else None,
                    error_type="Content too small (<1KB)"
                )
                self.stats.add_small_response(response_info)
                
                raise Exception("Response too small")
            
            if status != 200:
                raise Exception(f"HTTP {status}")
            
            # Write response to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.stats.success += 1
            
        except Exception as e:
            error_str = str(e)
            content_sample = locals().get('content', '')[:200] if locals().get('content') else None
            if content_sample is None:
                content_sample = ""
            error_type = self.categorize_error(e, status, len(content_sample))
            
            # Create response info for tracking errors with content
            if content_sample and "too small" not in error_str.lower():
                response_info = ResponseInfo(
                    url=url,
                    status=status,
                    content_length=content_length,
                    content_sample=content_sample,
                    error_type=error_type
                )
                self.stats.add_small_response(response_info)
            
            # Check if we should retry
            if self.should_retry(error_type, attempt):
                # Calculate delay with exponential backoff
                delay = self.get_retry_delay(attempt, error_type)
                
                # Update stats
                self.stats.retries += 1
                self.stats.retry_reasons[error_type] += 1
                
                # Log the retry attempt
                logger.info(f"Retry {attempt+1}/{self.max_retries} for {url} after {delay:.2f}s due to {error_type}")
                
                # Wait for the backoff delay
                time.sleep(delay)
                
                # Retry the request
                self.crawl_url(url, attempt + 1)
            else:
                # This is a final failure
                self.stats.failures += 1
                self.stats.failure_reasons[error_type] += 1
                logger.error(f"Failed to fetch {url}: {error_type}")

    def crawl_urls(self, urls: List[str]):
        """Crawl multiple URLs one at a time"""
        # Filter out empty URLs and count total
        valid_urls = [url.strip() for url in urls if url.strip()]
        self.stats.total = len(valid_urls)
        
        # Process each URL sequentially
        for i, url in enumerate(valid_urls):
            # Update status before each request
            print(f"\r[{i+1}/{self.stats.total}] ", end="")
            self.stats.print_status()
            
            # Check if file already exists before processing
            parsed_url = urlparse(url)
            filename = parsed_url.netloc + parsed_url.path
            if filename.endswith('/'):
                filename = filename[:-1]
            filename = filename.replace('/', '_') + '.html'
            output_path = os.path.join(self.target_dir, filename)
            
            # Skip without delay if file exists
            if os.path.exists(output_path):
                logger.info(f"File already exists for {url}, skipping")
                continue
            
            # Process the URL
            self.crawl_url(url)
            
            # Random delay between requests (2 to 5 seconds)
            # Only delay if we're not at the last URL
            if i < len(valid_urls) - 1:
                delay = random.uniform(2, 5)
                logger.info(f"Pausing for {delay:.2f} seconds before next request")
                time.sleep(delay)
        
        # Print final status and summary
        self.stats.print_status()
        print("\n")  # Add some space
        self.stats.print_failure_summary()

def main():
    if len(sys.argv) < 3:
        print("Usage: python crawlUrls.py <input_file> <target_directory> [max_retries]")
        sys.exit(1)

    input_file = sys.argv[1]
    target_dir = sys.argv[2]
    
    # Parse additional arguments
    max_retries = 3  # Default
    
    # Check for max_retries
    if len(sys.argv) > 3:
        max_retries = int(sys.argv[3])

    # Read URLs
    with open(input_file, 'r') as f:
        urls = f.readlines()

    # Create and run crawler
    crawler = SimpleCrawler(
        target_dir=target_dir, 
        max_retries=max_retries
    )
    
    print(f"Starting crawler with sequential processing")
    print(f"Max retries: {max_retries}")
    
    crawler.crawl_urls(urls)

if __name__ == "__main__":
    main()