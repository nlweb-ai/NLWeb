#!/usr/bin/env python
"""
Remove duplicate URLs from JSONL file.
Keeps the first occurrence of each URL and removes subsequent duplicates.
"""

import json
import sys
from pathlib import Path
from typing import Set

def remove_duplicates(input_file: str, output_file: str = None) -> None:
    """
    Remove duplicate URLs from JSONL file.
    
    Args:
        input_file: Path to input JSONL file
        output_file: Path to output file (if None, creates .dedup version)
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"Error: Input file {input_file} does not exist")
        sys.exit(1)
    
    if output_file is None:
        output_file = input_path.with_suffix('.dedup.txt')
    else:
        output_file = Path(output_file)
    
    print(f"Reading from: {input_path}")
    print(f"Writing to: {output_file}")
    
    seen_urls: Set[str] = set()
    total_lines = 0
    kept_lines = 0
    duplicates_removed = 0
    
    # Track which URLs had duplicates
    duplicate_urls = {}
    
    with open(input_path, 'r') as infile, open(output_file, 'w') as outfile:
        for line_num, line in enumerate(infile, 1):
            total_lines += 1
            
            try:
                data = json.loads(line.strip())
                url = data.get('url', '')
                
                if not url:
                    print(f"Warning: Line {line_num} has no 'url' field, keeping it")
                    outfile.write(line)
                    kept_lines += 1
                    continue
                
                if url not in seen_urls:
                    # First occurrence - keep it
                    seen_urls.add(url)
                    outfile.write(line)
                    kept_lines += 1
                else:
                    # Duplicate - skip it
                    duplicates_removed += 1
                    if url not in duplicate_urls:
                        duplicate_urls[url] = 1
                    else:
                        duplicate_urls[url] += 1
                    
                    # Log duplicate info
                    name = data.get('name', 'unnamed')
                    doc_id = data.get('id', 'no-id')
                    print(f"  Removing duplicate #{duplicate_urls[url]} of URL '{url}' (name: {name}, id: {doc_id})")
                    
            except json.JSONDecodeError as e:
                print(f"Warning: Line {line_num} is not valid JSON: {e}")
                print(f"  Keeping the line as-is")
                outfile.write(line)
                kept_lines += 1
    
    print(f"\n=== Summary ===")
    print(f"Total lines processed: {total_lines}")
    print(f"Lines kept: {kept_lines}")
    print(f"Duplicates removed: {duplicates_removed}")
    print(f"Unique URLs: {len(seen_urls)}")
    
    if duplicate_urls:
        print(f"\nURLs that had duplicates removed:")
        for url, count in sorted(duplicate_urls.items())[:30]:  # Limit output to first 30
            print(f"  - {url}: {count} duplicate(s) removed")
        if len(duplicate_urls) > 30:
            print(f"  ... and {len(duplicate_urls) - 30} more")
    
    print(f"\nOutput written to: {output_file}")
    
    # Verify the output
    print("\nVerifying output...")
    output_urls = set()
    output_lines = 0
    
    with open(output_file, 'r') as f:
        for line in f:
            output_lines += 1
            try:
                data = json.loads(line.strip())
                url = data.get('url', '')
                if url and url in output_urls:
                    print(f"ERROR: Duplicate URL '{url}' found in output!")
                if url:
                    output_urls.add(url)
            except:
                pass
    
    print(f"Output has {output_lines} lines with {len(output_urls)} unique URLs")
    
    if duplicates_removed > 0:
        print(f"✓ Successfully removed {duplicates_removed} duplicates")
    else:
        print("✓ No duplicates found")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Remove duplicate URLs from JSONL file')
    parser.add_argument('input_file', help='Input JSONL file')
    parser.add_argument('-o', '--output', help='Output file (default: input.dedup.txt)')
    
    args = parser.parse_args()
    
    remove_duplicates(args.input_file, args.output)


if __name__ == '__main__':
    main()