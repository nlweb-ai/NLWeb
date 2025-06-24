#!/usr/bin/env python3

import urllib.request
import urllib.parse
import re
import csv
import json
import time
from html.parser import HTMLParser

class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_tag = None
        self.current_attrs = {}
        self.current_text = ""
        
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        self.current_attrs = dict(attrs)
        if tag == 'a' and 'href' in self.current_attrs:
            self.links.append({
                'href': self.current_attrs['href'],
                'text': '',
                'attrs': self.current_attrs
            })
            
    def handle_data(self, data):
        if self.current_tag == 'a' and self.links:
            self.links[-1]['text'] += data.strip()
            
    def handle_endtag(self, tag):
        self.current_tag = None

class NPRPodcastScraperComplete:
    def __init__(self):
        self.base_url = "https://www.npr.org"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.podcasts_data = []
        self.visited_orgs = set()
        self.visited_podcasts = set()
        
    def get_page(self, url):
        """Fetch webpage content"""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            # Add 10 second timeout
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
            
    def extract_links(self, html):
        """Extract all links from HTML"""
        parser = LinkExtractor()
        parser.feed(html)
        return parser.links
        
    def extract_rss_feed(self, html):
        """Extract RSS feed URL from various possible locations"""
        # Method 1: Look for actual RSS/XML feeds
        rss_patterns = [
            r'href="([^"]+feeds\.npr\.org[^"]+podcast\.xml)"',
            r'href="([^"]+\.xml)"',
            r'href="([^"]+/rss[^"]*)"',
            r'href="([^"]+feeds\.[^"]+)"',
            r'"rssUrl":"([^"]+)"',
            r'"feedUrl":"([^"]+)"',
        ]
        
        for pattern in rss_patterns:
            match = re.search(pattern, html)
            if match:
                rss_url = match.group(1)
                # Clean up URLs that have query parameters appended
                if 'addrssfeed=' in rss_url:
                    # Extract the actual RSS URL from YouTube Music links
                    rss_match = re.search(r'addrssfeed=([^&]+)', rss_url)
                    if rss_match:
                        return urllib.parse.unquote(rss_match.group(1))
                return rss_url
                
        # Method 2: Look for RSS links in the extracted links
        links = self.extract_links(html)
        for link in links:
            href = link['href']
            if href and ('feeds.npr.org' in href or '.xml' in href or '/rss' in href):
                if 'addrssfeed=' in href:
                    rss_match = re.search(r'addrssfeed=([^&]+)', href)
                    if rss_match:
                        return urllib.parse.unquote(rss_match.group(1))
                return href
                
        return ''
        
    def get_categories(self):
        """Get all podcast categories from the main page"""
        url = "https://www.npr.org/podcasts-and-shows/"
        html = self.get_page(url)
        if not html:
            return []
            
        categories = []
        links = self.extract_links(html)
        
        for link in links:
            href = link['href']
            if '/podcasts/20' in href:
                category_url = urllib.parse.urljoin(self.base_url, href)
                category_name = link['text']
                if category_url not in [c[1] for c in categories] and category_name:
                    categories.append((category_name, category_url))
                    
        return categories
        
    def get_podcasts_from_category(self, category_url):
        """Get all podcasts from a category page"""
        html = self.get_page(category_url)
        if not html:
            return []
            
        podcasts = []
        links = self.extract_links(html)
        
        for link in links:
            href = link['href']
            if '/podcasts/' in href and '/podcasts/20' not in href and href.count('/') >= 3:
                podcast_url = urllib.parse.urljoin(self.base_url, href)
                if podcast_url not in podcasts and '/organizations/' not in podcast_url:
                    podcasts.append(podcast_url)
                    
        return podcasts
        
    def get_podcast_details(self, podcast_url):
        """Extract podcast details including RSS feed and organization"""
        if podcast_url in self.visited_podcasts:
            return None
            
        self.visited_podcasts.add(podcast_url)
        html = self.get_page(podcast_url)
        if not html:
            return None
            
        details = {
            'podcast_url': podcast_url,
            'podcast_name': '',
            'rss_feed': '',
            'org_url': '',
            'org_name': ''
        }
        
        # Extract podcast name from title or h1
        title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if title_match:
            details['podcast_name'] = title_match.group(1).strip()
        else:
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                details['podcast_name'] = title_match.group(1).split('|')[0].strip()
                
        # Extract RSS feed
        details['rss_feed'] = self.extract_rss_feed(html)
                
        # Extract organization link
        links = self.extract_links(html)
        for link in links:
            href = link['href']
            if '/podcasts/organizations/' in href:
                details['org_url'] = urllib.parse.urljoin(self.base_url, href)
                details['org_name'] = link['text']
                break
                
        return details
        
    def get_podcasts_from_organization(self, org_url):
        """Get all podcasts from an organization page"""
        if org_url in self.visited_orgs:
            return []
            
        self.visited_orgs.add(org_url)
        html = self.get_page(org_url)
        if not html:
            return []
            
        podcasts = []
        links = self.extract_links(html)
        
        for link in links:
            href = link['href']
            if '/podcasts/' in href and '/organizations/' not in href and href.count('/') >= 3:
                podcast_url = urllib.parse.urljoin(self.base_url, href)
                if podcast_url not in podcasts:
                    podcasts.append(podcast_url)
                    
        return podcasts
        
    def scrape_all_podcasts(self, limit_categories=None, limit_podcasts_per_category=None):
        """Main scraping function"""
        print("Getting categories...")
        categories = self.get_categories()
        print(f"Found {len(categories)} categories")
        
        if not categories:
            # Fallback: hardcode some known categories
            categories = [
                ('Arts', 'https://www.npr.org/podcasts/2000/arts'),
                ('Business', 'https://www.npr.org/podcasts/2007/business'),
                ('Comedy', 'https://www.npr.org/podcasts/2013/comedy'),
                ('Health & Fitness', 'https://www.npr.org/podcasts/2031/health-fitness'),
                ('Music', 'https://www.npr.org/podcasts/2037/music'),
                ('News', 'https://www.npr.org/podcasts/2038/news'),
                ('Politics', 'https://www.npr.org/podcasts/2039/politics'),
                ('Science', 'https://www.npr.org/podcasts/2047/science'),
                ('Technology', 'https://www.npr.org/podcasts/2061/technology'),
            ]
            print("Using fallback categories")
        
        if limit_categories:
            categories = categories[:limit_categories]
            
        for category_name, category_url in categories:
            print(f"\nProcessing category: {category_name}")
            podcasts = self.get_podcasts_from_category(category_url)
            print(f"Found {len(podcasts)} podcasts in {category_name}")
            
            if limit_podcasts_per_category:
                podcasts = podcasts[:limit_podcasts_per_category]
                
            for podcast_url in podcasts:
                print(f"  Processing: {podcast_url}")
                
                details = self.get_podcast_details(podcast_url)
                if details and details['podcast_name']:
                    self.podcasts_data.append(details)
                    
                    # Also get podcasts from the organization
                    if details['org_url']:
                        org_podcasts = self.get_podcasts_from_organization(details['org_url'])
                        print(f"    Found {len(org_podcasts)} podcasts from organization: {details['org_name']}")
                        
                        for org_podcast_url in org_podcasts:
                            org_details = self.get_podcast_details(org_podcast_url)
                            if org_details and org_details['podcast_name']:
                                self.podcasts_data.append(org_details)
                                
                time.sleep(3)  # Be respectful with requests
                
    def save_to_tsv(self, filename='npr_podcasts_complete.tsv'):
        """Save the collected data to a TSV file"""
        # Remove duplicates based on podcast URL
        unique_podcasts = {}
        for podcast in self.podcasts_data:
            url = podcast['podcast_url']
            if url not in unique_podcasts:
                unique_podcasts[url] = podcast
                
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(['Podcast URL', 'RSS Feed', 'Organization URL', 'Podcast Name', 'Organization Name'])
            
            for podcast in unique_podcasts.values():
                writer.writerow([
                    podcast['podcast_url'],
                    podcast['rss_feed'],
                    podcast['org_url'],
                    podcast['podcast_name'],
                    podcast['org_name']
                ])
                
        print(f"\nSaved {len(unique_podcasts)} unique podcasts to {filename}")

def main():
    scraper = NPRPodcastScraperComplete()
    
    # Full scraping - all categories and all podcasts
    scraper.scrape_all_podcasts()
    
    scraper.save_to_tsv()

if __name__ == "__main__":
    main()