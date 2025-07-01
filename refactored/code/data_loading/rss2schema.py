# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
RSS to Schema.org converter
Transforms RSS/Atom feeds into Schema.org JSON format.
From the oldest to the newer to the latest.
"""

import xml.etree.ElementTree as ET
import re
import traceback
from typing import List, Dict, Any, Optional, Tuple, Union
from urllib.parse import urlparse
import json
import os

# XML namespace mappings for common RSS/podcast namespaces
NAMESPACES = {
    'atom': 'http://www.w3.org/2005/Atom',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
    'googleplay': 'http://www.google.com/schemas/play-podcasts/1.0',
    'media': 'http://search.yahoo.com/mrss/',
    'podcast': 'https://podcastindex.org/namespace/1.0'
}

def safe_get_text(element: Optional[ET.Element]) -> str:
    """
    Safely extract text from an XML element.
    
    Args:
        element: XML element or None
        
    Returns:
        Text content or empty string
    """
    if element is None:
        return ""
    
    return element.text or ""

def fix_url(url: str) -> str:
    """
    Ensure URL is properly formatted.
    
    Args:
        url: Input URL
        
    Returns:
        Fixed URL
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # Add missing scheme if needed
    if url and not (url.startswith('http://') or url.startswith('https://')):
        if url.startswith('//'):
            url = 'https:' + url
        else:
            url = 'https://' + url
    
    return url

def extract_duration(duration_str: str) -> Optional[str]:
    """
    Extract and normalize duration from various formats.
    
    Args:
        duration_str: Duration string from feed
        
    Returns:
        Normalized duration string or None
    """
    if not duration_str:
        return None
    
    duration_str = duration_str.strip()
    
    # If already in ISO format like PT1H30M15S
    if duration_str.startswith('PT'):
        return duration_str
    
    # Handle common formats
    
    # Format: HH:MM:SS
    if re.match(r'^\d+:\d+:\d+$', duration_str):
        hours, minutes, seconds = map(int, duration_str.split(':'))
        return f"PT{hours}H{minutes}M{seconds}S"
    
    # Format: MM:SS
    if re.match(r'^\d+:\d+$', duration_str):
        minutes, seconds = map(int, duration_str.split(':'))
        return f"PT{minutes}M{seconds}S"
    
    # Format: seconds (as number)
    if re.match(r'^\d+$', duration_str):
        seconds = int(duration_str)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        result = "PT"
        if hours > 0:
            result += f"{hours}H"
        if minutes > 0:
            result += f"{minutes}M"
        if seconds > 0 or (hours == 0 and minutes == 0):
            result += f"{seconds}S"
        
        return result
    
    # Return as-is if we can't parse it
    return duration_str

def extract_guid(item: ET.Element) -> Optional[str]:
    """
    Extract GUID from an RSS item element.
    
    Args:
        item: RSS item element
        
    Returns:
        GUID string or None
    """
    guid_elem = item.find('guid')
    
    if guid_elem is not None:
        # Check if it's a permalink
        is_permalink = guid_elem.get('isPermaLink')
        
        if is_permalink == 'true' and guid_elem.text:
            return fix_url(guid_elem.text)
        
        return guid_elem.text
    
    return None

def extract_url_candidates(item: ET.Element) -> List[str]:
    """
    Extract all possible URL candidates from an RSS item.
    
    Args:
        item: RSS item element
        
    Returns:
        List of URL candidates
    """
    candidates = []
    
    # Link is the primary URL in RSS
    link = item.find('link')
    if link is not None and link.text:
        candidates.append(fix_url(link.text))
    
    # GUID can be a permalink
    guid = item.find('guid')
    if guid is not None and guid.text and guid.get('isPermaLink') != 'false':
        candidates.append(fix_url(guid.text))
    
    # Look in namespaced elements
    for ns_prefix, ns_uri in NAMESPACES.items():
        # Atom link
        if ns_prefix == 'atom':
            for atom_link in item.findall(f".//{{{ns_uri}}}link"):
                href = atom_link.get('href')
                rel = atom_link.get('rel', 'alternate')
                
                # Prefer alternate links
                if href and rel == 'alternate':
                    candidates.insert(0, fix_url(href))
                elif href:
                    candidates.append(fix_url(href))
    
    # Enclosures can have URLs
    for enclosure in item.findall('enclosure'):
        url = enclosure.get('url')
        if url:
            candidates.append(fix_url(url))
    
    # Media content can have URLs
    for ns_prefix, ns_uri in NAMESPACES.items():
        if ns_prefix == 'media':
            for media in item.findall(f".//{{{ns_uri}}}content"):
                url = media.get('url')
                if url:
                    candidates.append(fix_url(url))
    
    # Return unique non-empty URLs
    return [url for url in candidates if url and url != 'https://']

def extract_best_url(item: ET.Element, feed_url: Optional[str] = None) -> Optional[str]:
    """
    Extract the best URL for an RSS item.
    
    Args:
        item: RSS item element
        feed_url: URL of the feed itself (for fallback)
        
    Returns:
        Best URL or None
    """
    candidates = extract_url_candidates(item)
    
    if not candidates:
        # No URL found, try to generate a synthetic one using the title and feed URL
        title = item.find('title')
        if title is not None and title.text and feed_url:
            # Create a slug from the title
            slug = re.sub(r'[^\w\s-]', '', title.text.lower())
            slug = re.sub(r'[\s-]+', '-', slug)
            
            # Parse the feed URL to get the domain
            parsed_url = urlparse(feed_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Generate a synthetic URL
            return f"{base_url}/episode/{slug}"
        
        return None
    
    # Return the first (best) candidate
    return candidates[0]

def parse_rss_2_0(root: ET.Element, feed_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parse an RSS 2.0 feed into Schema.org format.
    
    Args:
        root: XML root element
        feed_url: URL of the feed
        
    Returns:
        List of Schema.org formatted items
    """
    result = []
    
    # Get channel element
    channel = root.find('channel')
    if channel is None:
        print("Warning: No channel element found in RSS feed")
        return result
    
    # Extract podcast (feed) information
    podcast_title = safe_get_text(channel.find('title'))
    podcast_description = safe_get_text(channel.find('description'))
    podcast_link = safe_get_text(channel.find('link'))
    podcast_language = safe_get_text(channel.find('language'))
    
    # Extract image
    podcast_image = None
    image_elem = channel.find('image')
    if image_elem is not None:
        image_url = safe_get_text(image_elem.find('url'))
        if image_url:
            podcast_image = {"@type": "ImageObject", "url": fix_url(image_url)}
    
    # iTunes image (higher quality)
    for ns_prefix, ns_uri in NAMESPACES.items():
        if ns_prefix == 'itunes':
            itunes_image = channel.find(f".//{{{ns_uri}}}image")
            if itunes_image is not None and 'href' in itunes_image.attrib:
                podcast_image = {"@type": "ImageObject", "url": fix_url(itunes_image.get('href'))}
    
    # Create basic podcast series schema
    podcast_series = {
        "@type": "PodcastSeries",
        "name": podcast_title,
        "description": podcast_description,
        "url": fix_url(podcast_link) or feed_url or ""
    }
    
    if podcast_image:
        podcast_series["image"] = podcast_image
    
    if podcast_language:
        podcast_series["inLanguage"] = podcast_language
    
    # Process each item (episode)
    for item in channel.findall('item'):
        try:
            # Basic fields
            title = safe_get_text(item.find('title'))
            description = safe_get_text(item.find('description'))
            pub_date = safe_get_text(item.find('pubDate'))
            
            # URL (critical field)
            url = extract_best_url(item, feed_url)
            
            if not url and not title:
                # Skip items without any identifiable information
                continue
            
            # Create episode schema
            episode = {
                "@type": "PodcastEpisode",
                "name": title,
                "description": description,
                "datePublished": pub_date
            }
            
            if url:
                episode["url"] = url
            
            # Add GUID if available
            guid = extract_guid(item)
            if guid and guid != url:
                episode["identifier"] = guid
            
            # Add enclosure (audio file)
            enclosure = item.find('enclosure')
            if enclosure is not None:
                enclosure_url = enclosure.get('url')
                enclosure_type = enclosure.get('type')
                enclosure_length = enclosure.get('length')
                
                if enclosure_url:
                    audio_object = {
                        "@type": "AudioObject",
                        "contentUrl": fix_url(enclosure_url)
                    }
                    
                    if enclosure_type:
                        audio_object["encodingFormat"] = enclosure_type
                    
                    if enclosure_length:
                        try:
                            audio_object["contentSize"] = int(enclosure_length)
                        except ValueError:
                            pass
                    
                    episode["associatedMedia"] = audio_object
            
            # Add iTunes specific fields
            for ns_prefix, ns_uri in NAMESPACES.items():
                if ns_prefix == 'itunes':
                    # Duration
                    duration_elem = item.find(f".//{{{ns_uri}}}duration")
                    if duration_elem is not None and duration_elem.text:
                        duration = extract_duration(duration_elem.text)
                        if duration:
                            episode["duration"] = duration
                    
                    # Episode number
                    episode_number = item.find(f".//{{{ns_uri}}}episode")
                    if episode_number is not None and episode_number.text:
                        try:
                            episode["episodeNumber"] = int(episode_number.text)
                        except ValueError:
                            pass
                    
                    # Season number
                    season_number = item.find(f".//{{{ns_uri}}}season")
                    if season_number is not None and season_number.text:
                        try:
                            episode["partOfSeason"] = {
                                "@type": "PodcastSeason",
                                "seasonNumber": int(season_number.text)
                            }
                        except ValueError:
                            pass
            
            # Add image if available
            for ns_prefix, ns_uri in NAMESPACES.items():
                if ns_prefix == 'itunes':
                    itunes_image = item.find(f".//{{{ns_uri}}}image")
                    if itunes_image is not None and 'href' in itunes_image.attrib:
                        episode["image"] = {
                            "@type": "ImageObject",
                            "url": fix_url(itunes_image.get('href'))
                        }
            
            # Add podcast series reference
            episode["partOf"] = podcast_series
            
            # Add to result
            result.append(episode)
        except Exception as e:
            print(f"Error processing RSS item: {str(e)}")
            traceback.print_exc()
    
    return result

def parse_atom(root: ET.Element, feed_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parse an Atom feed into Schema.org format.
    
    Args:
        root: XML root element
        feed_url: URL of the feed
        
    Returns:
        List of Schema.org formatted items
    """
    result = []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    
    # Extract feed information
    feed_title = safe_get_text(root.find('atom:title', ns))
    feed_subtitle = safe_get_text(root.find('atom:subtitle', ns))
    
    # Extract feed link
    feed_link = feed_url
    for link in root.findall('atom:link', ns):
        rel = link.get('rel', 'alternate')
        if rel == 'self' and not feed_link:
            feed_link = link.get('href')
        elif rel == 'alternate':
            feed_link = link.get('href')
            break
    
    feed_link = fix_url(feed_link or "")
    
    # Create podcast series schema
    podcast_series = {
        "@type": "PodcastSeries",
        "name": feed_title,
        "description": feed_subtitle,
        "url": feed_link
    }
    
    # Process each entry
    for entry in root.findall('atom:entry', ns):
        try:
            # Basic fields
            title = safe_get_text(entry.find('atom:title', ns))
            summary = safe_get_text(entry.find('atom:summary', ns))
            published = safe_get_text(entry.find('atom:published', ns))
            updated = safe_get_text(entry.find('atom:updated', ns))
            
            # Extract link (URL)
            entry_url = None
            for link in entry.findall('atom:link', ns):
                rel = link.get('rel', 'alternate')
                if rel == 'alternate':
                    entry_url = link.get('href')
                    break
            
            if not entry_url:
                # Try any link
                for link in entry.findall('atom:link', ns):
                    if 'href' in link.attrib:
                        entry_url = link.get('href')
                        break
            
            entry_url = fix_url(entry_url or "")
            
            if not entry_url and not title:
                # Skip entries without any identifiable information
                continue
            
            # Create episode schema
            episode = {
                "@type": "PodcastEpisode",
                "name": title,
                "description": summary,
                "datePublished": published or updated
            }
            
            if entry_url:
                episode["url"] = entry_url
            
            # Add ID if available
            entry_id = safe_get_text(entry.find('atom:id', ns))
            if entry_id and entry_id != entry_url:
                episode["identifier"] = entry_id
            
            # Extract media enclosures
            for link in entry.findall('atom:link', ns):
                rel = link.get('rel', '')
                if rel == 'enclosure' or link.get('type', '').startswith('audio/'):
                    href = link.get('href')
                    if href:
                        audio_object = {
                            "@type": "AudioObject",
                            "contentUrl": fix_url(href)
                        }
                        
                        mime_type = link.get('type')
                        if mime_type:
                            audio_object["encodingFormat"] = mime_type
                        
                        length = link.get('length')
                        if length:
                            try:
                                audio_object["contentSize"] = int(length)
                            except ValueError:
                                pass
                        
                        episode["associatedMedia"] = audio_object
                        break
            
            # Add podcast series reference
            episode["partOf"] = podcast_series
            
            # Add to result
            result.append(episode)
        except Exception as e:
            print(f"Error processing Atom entry: {str(e)}")
            traceback.print_exc()
    
    return result

def feed_to_schema(feed_path: str) -> List[Dict[str, Any]]:
    """
    Convert an RSS/Atom feed to Schema.org format.
    
    Args:
        feed_path: Path to the feed file
        
    Returns:
        List of Schema.org formatted items
    """
    try:
        # Determine feed URL (for generating proper URLs if needed)
        feed_url = None
        if feed_path.startswith(('http://', 'https://')):
            feed_url = feed_path
        
        # Parse the XML
        tree = ET.parse(feed_path)
        root = tree.getroot()
        
        # Determine feed type
        if root.tag == 'rss':
            # RSS 2.0
            return parse_rss_2_0(root, feed_url)
        elif root.tag.endswith('feed'):
            # Atom
            return parse_atom(root, feed_url)
        elif root.tag == 'RDF':
            # RSS 1.0 (RDF) - not fully supported, use the channel as a fallback
            channel = root.find('channel')
            if channel is not None:
                return parse_rss_2_0(root, feed_url)
        
        # Unknown format, try to look for channel element anyway
        channel = root.find('channel')
        if channel is not None:
            return parse_rss_2_0(root, feed_url)
        
        print(f"Unsupported feed format: {root.tag}")
        return []
    
    except Exception as e:
        print(f"Error converting feed to schema: {str(e)}")
        traceback.print_exc()
        return []

def main():
    """Command-line interface for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert RSS/Atom feeds to Schema.org JSON")
    parser.add_argument("feed_path", help="Path to feed file or URL")
    parser.add_argument("-o", "--output", help="Output file (default: print to stdout)")
    
    args = parser.parse_args()
    
    try:
        items = feed_to_schema(args.feed_path)
        
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                for item in items:
                    # Format: url <tab> json
                    if "url" in item:
                        # Ensure JSON is on a single line with no newlines
                        json_str = json.dumps(item, ensure_ascii=False).replace("\n", " ")
                        f.write(f"{item['url']}\t{json_str}\n")
            
            print(f"Converted {len(items)} items to {args.output}")
        else:
            # Print to stdout
            print(json.dumps(items, indent=2, ensure_ascii=False))
    
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()