import requests
import xml.etree.ElementTree as ET
import gzip
from io import BytesIO
import sys
from urllib.parse import urljoin, urlparse

def extract_urls_from_sitemap(sitemap_url, output_file, verbose=False):
    try:
        if verbose:
            print(f"Processing sitemap: {sitemap_url}")
            
        # Fetch sitemap content
        response = requests.get(sitemap_url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'DNT': '1', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1'})
        
        if response.status_code != 200:
            print(f"Warning: HTTP {response.status_code} for {sitemap_url}")
            return
            
        if sitemap_url.endswith('.gz'):
            content = gzip.GzipFile(fileobj=BytesIO(response.content)).read()
        else:
            content = response.content

        # Parse XML
        root = ET.fromstring(content)

        # Handle both sitemap index files and regular sitemaps
        # Remove namespace for easier parsing
        namespace = root.tag[1:].split("}")[0] if "}" in root.tag else ""
        ns = {"ns": namespace} if namespace else {}

        # Open output file in append mode
        with open(output_file, 'a') as f:
            # Check if this is a sitemap index
            sitemaps = root.findall(".//ns:sitemap", ns) if ns else root.findall(".//sitemap")
            if sitemaps:
                # This is a sitemap index
                if verbose:
                    print(f"  Found sitemap index with {len(sitemaps)} sitemaps")
                for sitemap in sitemaps:
                    loc = sitemap.find("ns:loc", ns) if ns else sitemap.find("loc")
                    if loc is not None and loc.text:
                        # Recursively process each sitemap
                        extract_urls_from_sitemap(loc.text.strip(), output_file, verbose)
            else:
                # This is a regular sitemap
                urls = root.findall(".//ns:url", ns) if ns else root.findall(".//url")
                if verbose:
                    print(f"  Found {len(urls)} URLs in sitemap")
                url_count = 0
                for url in urls:
                    loc = url.find("ns:loc", ns) if ns else url.find("loc")
                    if loc is not None and loc.text:
                        f.write(loc.text.strip() + '\n')
                        url_count += 1
                if verbose:
                    print(f"  Wrote {url_count} URLs to file")

    except Exception as e:
        print(f"Error processing sitemap {sitemap_url}: {str(e)}")

def get_sitemaps_from_robots(domain):
    """Extract sitemap URLs from robots.txt"""
    # Ensure domain has protocol
    if not domain.startswith(('http://', 'https://')):
        domain = f'https://{domain}'
    
    parsed = urlparse(domain)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    try:
        response = requests.get(robots_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        
        sitemaps = []
        for line in response.text.splitlines():
            line = line.strip()
            if line.lower().startswith('sitemap:'):
                sitemap_url = line.split(':', 1)[1].strip()
                # Handle relative URLs
                if not sitemap_url.startswith(('http://', 'https://')):
                    sitemap_url = urljoin(domain, sitemap_url)
                sitemaps.append(sitemap_url)
        
        return sitemaps
    except Exception as e:
        print(f"Could not read robots.txt from {robots_url}: {e}")
        return []


def process_site_or_sitemap(input_arg, output_file, verbose=True):
    """
    Process either a sitemap URL or a domain.
    If given a domain, checks robots.txt for sitemaps.
    """
    # Clear/create the output file
    open(output_file, 'w').close()
    
    # Check if input looks like a sitemap URL
    if input_arg.endswith(('.xml', '.xml.gz')) or '/sitemap' in input_arg:
        # Direct sitemap URL provided
        print(f"Processing sitemap: {input_arg}")
        extract_urls_from_sitemap(input_arg, output_file, verbose)
    else:
        # Assume it's a domain, check robots.txt
        print(f"Checking robots.txt for domain: {input_arg}")
        sitemaps = get_sitemaps_from_robots(input_arg)
        
        if sitemaps:
            print(f"Found {len(sitemaps)} sitemap(s) in robots.txt")
            for sitemap in sitemaps:
                print(f"Processing sitemap: {sitemap}")
                extract_urls_from_sitemap(sitemap, output_file, verbose)
        else:
            # Try default sitemap locations
            domain = input_arg
            if not domain.startswith(('http://', 'https://')):
                domain = f'https://{domain}'
            
            parsed = urlparse(domain)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            default_sitemaps = [
                f"{base_url}/sitemap.xml",
                f"{base_url}/sitemap_index.xml",
                f"{base_url}/sitemap/sitemap.xml"
            ]
            
            print("No sitemaps found in robots.txt, trying default locations...")
            for sitemap in default_sitemaps:
                try:
                    print(f"Trying: {sitemap}")
                    response = requests.head(sitemap, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                    if response.status_code == 200:
                        print(f"Found sitemap at: {sitemap}")
                        extract_urls_from_sitemap(sitemap, output_file, verbose)
                        break
                except:
                    continue
            else:
                print("No sitemaps found at default locations")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python urlsFromSitemap.py <sitemap_url_or_domain> <output_file> [--verbose]")
        print("Examples:")
        print("  python urlsFromSitemap.py https://example.com/sitemap.xml urls.txt")
        print("  python urlsFromSitemap.py example.com urls.txt")
        print("  python urlsFromSitemap.py example.com urls.txt --verbose")
        sys.exit(1)

    input_arg = sys.argv[1]
    output_file = sys.argv[2]
    verbose = len(sys.argv) > 3 and sys.argv[3] == '--verbose'
    
    process_site_or_sitemap(input_arg, output_file, verbose)
