#!/usr/bin/env python
"""
Remove duplicate sites from embeddings JSONL file.
Keeps the first occurrence of each site and removes subsequent duplicates.
"""

import json
import sys
from pathlib import Path
from typing import Set

def remove_duplicates(input_file: str, output_file: str = None) -> None:
    """
    Remove duplicate sites from embeddings file.
    
    Args:
        input_file: Path to input JSONL file with embeddings
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
    
    seen_sites: Set[str] = set()
    total_lines = 0
    kept_lines = 0
    duplicates_removed = 0
    
    # Track which sites had duplicates
    duplicate_sites = {}
    
    with open(input_path, 'r') as infile, open(output_file, 'w') as outfile:
        for line_num, line in enumerate(infile, 1):
            total_lines += 1
            
            try:
                data = json.loads(line.strip())
                site = data.get('site', '')
                
                if not site:
                    print(f"Warning: Line {line_num} has no 'site' field, keeping it")
                    outfile.write(line)
                    kept_lines += 1
                    continue
                
                if site not in seen_sites:
                    # First occurrence - keep it
                    seen_sites.add(site)
                    outfile.write(line)
                    kept_lines += 1
                else:
                    # Duplicate - skip it
                    duplicates_removed += 1
                    if site not in duplicate_sites:
                        duplicate_sites[site] = 1
                    else:
                        duplicate_sites[site] += 1
                    
                    # Log duplicate info
                    name = data.get('name', 'unnamed')
                    doc_id = data.get('id', 'no-id')
                    print(f"  Removing duplicate #{duplicate_sites[site]} of site '{site}' (name: {name}, id: {doc_id})")
                    
            except json.JSONDecodeError as e:
                print(f"Warning: Line {line_num} is not valid JSON: {e}")
                print(f"  Keeping the line as-is")
                outfile.write(line)
                kept_lines += 1
    
    print(f"\n=== Summary ===")
    print(f"Total lines processed: {total_lines}")
    print(f"Lines kept: {kept_lines}")
    print(f"Duplicates removed: {duplicates_removed}")
    print(f"Unique sites: {len(seen_sites)}")
    
    if duplicate_sites:
        print(f"\nSites that had duplicates removed:")
        for site, count in sorted(duplicate_sites.items()):
            print(f"  - {site}: {count} duplicate(s) removed")
    
    print(f"\nOutput written to: {output_file}")
    
    # Verify the output
    print("\nVerifying output...")
    output_sites = set()
    output_lines = 0
    
    with open(output_file, 'r') as f:
        for line in f:
            output_lines += 1
            try:
                data = json.loads(line.strip())
                site = data.get('site', '')
                if site in output_sites:
                    print(f"ERROR: Duplicate site '{site}' found in output!")
                output_sites.add(site)
            except:
                pass
    
    print(f"Output has {output_lines} lines with {len(output_sites)} unique sites")
    
    if len(output_sites) == kept_lines:
        print("✓ Verification passed: No duplicates in output")
    else:
        print("⚠ Warning: Output line count doesn't match unique site count")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Remove duplicate sites from embeddings JSONL file')
    parser.add_argument('input_file', help='Input JSONL file with embeddings')
    parser.add_argument('-o', '--output', help='Output file (default: input.dedup.txt)')
    
    args = parser.parse_args()
    
    remove_duplicates(args.input_file, args.output)


if __name__ == '__main__':
    main()