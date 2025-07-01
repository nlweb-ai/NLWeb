#!/usr/bin/env python3

import csv
import os
import sys
import time
import json
import urllib.request
import urllib.error
from data_loading.rss2schema import feed_to_schema as feed_to_schema_compact

def fetch_rss_to_file(rss_url, temp_file):
    """Fetch RSS feed and save to temporary file"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = urllib.request.Request(rss_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read()
            with open(temp_file, 'wb') as f:
                f.write(content)
        return True
    except Exception as e:
        print(f"Error fetching RSS {rss_url}: {e}")
        return False

def clean_org_name(org_name):
    """Clean organization name for use as filename"""
    # Remove 'From ' prefix
    if org_name.startswith('From '):
        org_name = org_name[5:]
    
    # Replace problematic characters
    org_name = org_name.replace('/', '_')
    org_name = org_name.replace('\\', '_')
    org_name = org_name.replace(':', '_')
    org_name = org_name.replace('*', '_')
    org_name = org_name.replace('?', '_')
    org_name = org_name.replace('"', '_')
    org_name = org_name.replace('<', '_')
    org_name = org_name.replace('>', '_')
    org_name = org_name.replace('|', '_')
    org_name = org_name.strip()
    
    return org_name

def clean_json_string(obj):
    """Remove newlines from JSON string"""
    json_str = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    # Remove any newlines that might be in the content
    json_str = json_str.replace('\n', ' ').replace('\r', ' ')
    # Clean up multiple spaces
    json_str = ' '.join(json_str.split())
    return json_str

def transform_episode(item, podcast_info):
    """Transform a single episode to match the expected format"""
    # Start with basic structure
    transformed = {
        "@context": "https://schema.org",
        "@type": "PodcastEpisode"
    }
    
    # Copy basic fields
    if "name" in item:
        transformed["name"] = item["name"]
    if "description" in item:
        # Limit description length to reduce file size
        desc = item["description"]
        if len(desc) > 500:
            # Truncate at sentence boundary if possible
            desc = desc[:500]
            last_period = desc.rfind('.')
            if last_period > 300:
                desc = desc[:last_period + 1]
            else:
                desc = desc.strip() + "..."
        transformed["description"] = desc
    if "datePublished" in item:
        transformed["datePublished"] = item["datePublished"]
    
    # Use the episode URL from the item
    if "url" in item:
        transformed["url"] = item["url"]
    else:
        # Fallback to podcast URL if no episode URL
        transformed["url"] = podcast_info["podcast_url"]
    
    # Add partOfSeries with full description like in reference
    transformed["partOfSeries"] = {
        "@type": "PodcastSeries",
        "name": podcast_info["podcast_name"]
    }
    
    # Add series description if available
    if "partOf" in item and isinstance(item["partOf"], dict) and "description" in item["partOf"]:
        transformed["partOfSeries"]["description"] = item["partOf"]["description"]
    
    # Extract image URL and put it at top level
    image_url = None
    if "partOf" in item and isinstance(item["partOf"], dict):
        if "image" in item["partOf"]:
            if isinstance(item["partOf"]["image"], dict) and "url" in item["partOf"]["image"]:
                image_url = item["partOf"]["image"]["url"]
            elif isinstance(item["partOf"]["image"], str):
                image_url = item["partOf"]["image"]
    
    if image_url:
        transformed["image"] = image_url
    
    return transformed

def process_npr_podcasts_by_org(tsv_file, output_dir, limit=None):
    """Process NPR podcasts TSV file and write episodes to files by organization"""
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Track statistics
    stats = {
        'total_podcasts': 0,
        'successful': 0,
        'failed_rss': 0,
        'failed_conversion': 0,
        'no_rss': 0,
        'total_episodes': 0,
        'orgs_processed': {}  # Track episodes per org
    }
    
    # Track open file handles
    org_files = {}
    
    # Temporary file for RSS downloads
    temp_rss_file = os.path.join(output_dir, '.temp_rss.xml')
    
    try:
        with open(tsv_file, 'r', encoding='utf-8') as f_in:
            reader = csv.reader(f_in, delimiter='\t')
            
            # Skip header
            header = next(reader)
            print(f"Processing podcasts from {tsv_file}")
            print(f"Output directory: {output_dir}")
            print(f"Columns: {header}")
            
            for row_num, row in enumerate(reader, start=2):
                if limit and stats['total_podcasts'] >= limit:
                    print(f"\nReached limit of {limit} podcasts")
                    break
                    
                if len(row) < 5:
                    print(f"Row {row_num}: Skipping - insufficient columns")
                    continue
                
                podcast_url = row[0]
                rss_feed = row[1]
                org_url = row[2]
                podcast_name = row[3]
                org_name = row[4]
                
                stats['total_podcasts'] += 1
                
                # Skip if no RSS feed
                if not rss_feed or rss_feed == '':
                    print(f"Row {row_num}: No RSS feed for {podcast_name}")
                    stats['no_rss'] += 1
                    continue
                
                # Clean organization name
                clean_org = clean_org_name(org_name)
                if not clean_org:
                    clean_org = 'Unknown_Organization'
                
                print(f"\nRow {row_num}: Processing {podcast_name}")
                print(f"  RSS: {rss_feed}")
                print(f"  Organization: {org_name} -> {clean_org}")
                
                # Fetch RSS feed
                if not fetch_rss_to_file(rss_feed, temp_rss_file):
                    stats['failed_rss'] += 1
                    continue
                
                # Convert to schema.org
                try:
                    schema_items = feed_to_schema_compact(temp_rss_file)
                    
                    if not schema_items:
                        print(f"  No items converted from RSS feed")
                        stats['failed_conversion'] += 1
                        continue
                    
                    print(f"  Converted {len(schema_items)} items to schema.org")
                    
                    # Get or create file handle for this organization
                    org_file_path = os.path.join(output_dir, f"{clean_org}.txt")
                    
                    if clean_org not in org_files:
                        # Open new file
                        org_files[clean_org] = open(org_file_path, 'w', encoding='utf-8')
                        stats['orgs_processed'][clean_org] = 0
                        print(f"  Created new file: {org_file_path}")
                    else:
                        print(f"  Appending to existing file: {org_file_path}")
                    
                    # Transform and write each episode as a separate line
                    podcast_info = {
                        "podcast_url": podcast_url,
                        "podcast_name": podcast_name,
                        "org_name": clean_org,
                        "org_url": org_url
                    }
                    
                    episodes_written = 0
                    for item in schema_items:
                        transformed = transform_episode(item, podcast_info)
                        
                        # Write as single line: Episode URL<tab>[JSON object in array]
                        episode_url = transformed.get("url", podcast_url)
                        episode_array = [transformed]
                        line = f"{episode_url}\t{clean_json_string(episode_array)}\n"
                        org_files[clean_org].write(line)
                        episodes_written += 1
                        stats['total_episodes'] += 1
                    
                    stats['orgs_processed'][clean_org] += episodes_written
                    print(f"  Wrote {episodes_written} episodes to {clean_org}.txt")
                    stats['successful'] += 1
                    
                except Exception as e:
                    print(f"  Error converting RSS to schema: {e}")
                    stats['failed_conversion'] += 1
                
                # Be respectful with requests
                time.sleep(2)
                
                # Clean up temp file
                if os.path.exists(temp_rss_file):
                    os.remove(temp_rss_file)
    
    except Exception as e:
        print(f"Error processing TSV file: {e}")
    
    finally:
        # Close all open files
        for org, file_handle in org_files.items():
            file_handle.close()
            print(f"Closed file for {org}")
            
        # Clean up temp file
        if os.path.exists(temp_rss_file):
            os.remove(temp_rss_file)
    
    # Print summary
    print("\n" + "="*50)
    print("Processing Summary:")
    print(f"Total podcasts: {stats['total_podcasts']}")
    print(f"Successfully processed: {stats['successful']}")
    print(f"Total episodes written: {stats['total_episodes']}")
    print(f"No RSS feed: {stats['no_rss']}")
    print(f"Failed to fetch RSS: {stats['failed_rss']}")
    print(f"Failed to convert: {stats['failed_conversion']}")
    print(f"\nEpisodes per organization:")
    for org, count in sorted(stats['orgs_processed'].items()):
        print(f"  {org}: {count} episodes")
    print("="*50)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Process NPR podcasts by organization")
    parser.add_argument("--tsv", default="/Users/rvguha/v2/NLWeb/data/npr_podcasts_complete.tsv",
                       help="Path to TSV file")
    parser.add_argument("--output", default="/Users/rvguha/v2/NLWeb/data/podcasts",
                       help="Output directory")
    parser.add_argument("--limit", type=int, help="Limit number of podcasts to process")
    
    args = parser.parse_args()
    
    process_npr_podcasts_by_org(args.tsv, args.output, args.limit)

if __name__ == "__main__":
    main()