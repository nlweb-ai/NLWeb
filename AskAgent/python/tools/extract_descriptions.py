#!/usr/bin/env python3
"""Extract and display descriptions from JSONL file"""

import json
import sys

def extract_descriptions(jsonl_file):
    """Extract and display descriptions from JSONL file."""
    with open(jsonl_file, 'r') as f:
        for line in f:
            data = json.loads(line)
            
            print("=" * 80)
            print(f"Store: {data.get('name', 'Unknown')}")
            print(f"URL: {data.get('url', 'Unknown')}")
            print(f"Category: {data.get('category', 'Unknown')}")
            print("=" * 80)
            
            print("\n📊 URL ANALYSIS:")
            print("-" * 40)
            print(data.get('sitemap_analysis', 'No analysis available'))
            
            print("\n📝 DETAILED DESCRIPTION:")
            print("-" * 40)
            detailed = data.get('detailed_description', 'No description available')
            
            # Format the description with proper line breaks
            if detailed and detailed != "Description generation failed":
                # Split into paragraphs for better readability
                paragraphs = detailed.split('\n\n')
                for para in paragraphs:
                    print(para)
                    print()
            else:
                print(detailed)
            
            print("\n📈 METADATA:")
            print("-" * 40)
            metadata = data.get('processing_metadata', {})
            print(f"Processed at: {metadata.get('processed_at', 'Unknown')}")
            print(f"Sitemaps found: {metadata.get('sitemaps_found', 0)}")
            print(f"URLs analyzed: {metadata.get('urls_analyzed', 0)}")
            print(f"Description length: {len(detailed)} characters")
            print()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extract_descriptions.py <jsonl_file>")
        sys.exit(1)
    
    extract_descriptions(sys.argv[1])