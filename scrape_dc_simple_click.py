#!/usr/bin/env python3
"""
Simple Data Commons scraper that clicks on visible elements
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import json
import sys
import time
import re

try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WEBDRIVER_MANAGER = True
except ImportError:
    USE_WEBDRIVER_MANAGER = False

def setup_driver():
    """Set up Chrome driver - always visible for debugging"""
    chrome_options = Options()
    chrome_options.add_argument('--window-size=1920,1080')
    
    if USE_WEBDRIVER_MANAGER:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)
    
    return driver

def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_dc_simple_click.py <url> [output.jsonl]")
        sys.exit(1)
    
    url = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    driver = setup_driver()
    
    try:
        print(f"Loading: {url}")
        driver.get(url)
        
        print("\nWaiting 10 seconds for page to load...")
        print("Please manually expand the tree nodes in the Statistical Variables pane if needed")
        time.sleep(10)
        
        # Extract all links that look like statistical variables
        variables = []
        seen = set()
        
        # Find all links
        links = driver.find_elements(By.TAG_NAME, "a")
        print(f"\nFound {len(links)} links total")
        
        # Also find all text elements
        all_elements = driver.find_elements(By.XPATH, "//*[text()]")
        print(f"Found {len(all_elements)} elements with text")
        
        # Extract from links
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                
                # Look for statistical variable patterns in href
                if "/browser/" in href:
                    match = re.search(r'/browser/([A-Z][a-zA-Z0-9_]+)', href)
                    if match:
                        dcid = match.group(1)
                        if dcid not in seen and any(p in dcid for p in ['Count_', 'Median_', 'Percent_', 'Mean_', 'Amount_']):
                            seen.add(dcid)
                            variables.append({
                                'site': 'datacommons',
                                'dcid': dcid,
                                'description': text if text else f"Variable: {dcid}"
                            })
            except:
                continue
        
        # Extract from visible text
        for elem in all_elements:
            try:
                text = elem.text.strip()
                if text:
                    # Look for DCID patterns
                    matches = re.findall(r'\b([A-Z][a-zA-Z0-9]*_[a-zA-Z0-9_]+)\b', text)
                    for match in matches:
                        if match not in seen and any(p in match for p in ['Count_', 'Median_', 'Percent_', 'Mean_', 'Amount_']):
                            seen.add(match)
                            variables.append({
                                'site': 'datacommons',
                                'dcid': match,
                                'description': f"Variable: {match}"
                            })
            except:
                continue
        
        print(f"\nExtracted {len(variables)} variables")
        
        # Save results
        if output_file:
            with open(output_file, 'w') as f:
                for var in variables:
                    f.write(json.dumps(var) + '\n')
            print(f"Saved to {output_file}")
        else:
            for var in variables:
                print(json.dumps(var))
        
        # Show samples
        if variables:
            print("\nFirst 10 variables:")
            for var in variables[:10]:
                print(f"  {var['dcid']}")
        
        print("\nBrowser will remain open for 30 seconds for inspection...")
        time.sleep(30)
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()