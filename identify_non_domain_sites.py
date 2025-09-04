#!/usr/bin/env python3
"""
Identify entries in allsites.txt where the URL is not a proper domain.
Separate these into a different file.
"""

import json
import re
from pathlib import Path

def is_proper_domain(url):
    """
    Check if a URL looks like a proper domain.
    A proper domain should have at least one dot and look like a domain/URL.
    """
    # Remove protocol if present
    url = url.replace('http://', '').replace('https://', '').strip('/')
    
    # Check if it has at least one dot (like example.com)
    # or if it's localhost
    if '.' in url or url == 'localhost':
        return True
    
    # Check if it's just a single word without dots (like 'seriouseats')
    if re.match(r'^[a-zA-Z0-9\-_]+$', url):
        return False
    
    return False

def main():
    # Set up paths
    data_dir = Path.home() / "mahi/data/sites/jsonl"
    input_file = data_dir / "allsites.txt"
    output_file = data_dir / "non_domain_sites.txt"
    proper_domains_file = data_dir / "proper_domain_sites.txt"
    
    if not input_file.exists():
        print(f"Error: {input_file} does not exist")
        return
    
    print(f"Reading from: {input_file}")
    
    non_domain_sites = []
    proper_domain_sites = []
    non_domain_urls = []
    
    # Read and process each line
    with open(input_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                url = data.get('url', '')
                
                if not is_proper_domain(url):
                    non_domain_sites.append(line)
                    non_domain_urls.append(url)
                    print(f"Non-domain site found: {url}")
                else:
                    proper_domain_sites.append(line)
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}")
                continue
    
    # Write non-domain sites to separate file
    with open(output_file, 'w') as f:
        for line in non_domain_sites:
            f.write(line + '\n')
    
    # Write proper domain sites to separate file (optional)
    with open(proper_domains_file, 'w') as f:
        for line in proper_domain_sites:
            f.write(line + '\n')
    
    print(f"\n=== Summary ===")
    print(f"Total sites processed: {len(non_domain_sites) + len(proper_domain_sites)}")
    print(f"Non-domain sites found: {len(non_domain_sites)}")
    print(f"Proper domain sites: {len(proper_domain_sites)}")
    print(f"\nNon-domain sites written to: {output_file}")
    print(f"Proper domain sites written to: {proper_domains_file}")
    
    if non_domain_urls:
        print(f"\n=== List of Non-Domain URLs ===")
        for url in sorted(set(non_domain_urls)):
            print(f"  - {url}")

if __name__ == "__main__":
    main()