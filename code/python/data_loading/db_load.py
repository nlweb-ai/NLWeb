# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Utilities for loading JSON data into vector databases, with or without precomputed embeddings.
Now with support for CSV files, URLs, and RSS feeds.
"""

import os
import sys
import json
import csv
import pandas as pd
import asyncio
import aiohttp
import tempfile
import traceback
from urllib.parse import urlparse

from typing import List, Dict, Any, Tuple, Union, Optional

from core.config import CONFIG
from core.embedding import batch_get_embeddings
from data_loading.db_load_utils import (
    read_file_lines,
    prepare_documents_from_json,
    documents_from_csv_line,
)

# Import vector database client directly
from core.retriever import get_vector_db_client, upload_documents, delete_documents_by_site

# Import RSS to Schema converter
import data_loading.rss2schema as rss2schema

# Define URL extractor function since json_url_extractor module is not available
def process_line(line):
    """
    Process a line from a file to extract URL and JSON data.
    
    Handles two formats:
    1. Two columns per row, separated by tabs: URL and JSON
    2. One column: JSON only (URL will be extracted from the JSON)
    
    Args:
        line: Line from the file
        
    Returns:
        Tuple of (url, json_data)
    """
    parts = line.strip().split('\t')
    
    if len(parts) >= 2:
        # Format: URL and JSON 
        url = parts[0]
        json_data = parts[1]
        return url, json_data
    elif len(parts) == 1:
        # Format: JSON only, extract URL from within the JSON
        json_data = parts[0]
        try:
            json_obj = json.loads(json_data)
            
            # Try to extract URL from common fields
            url = None
            for field in ["url", "@id", "identifier"]:
                if field in json_obj and json_obj[field]:
                    url = json_obj[field]
                    break
                    
            if not url:
                return None, None
                
            return url, json_data
        except Exception as e:
            print(f"Error extracting URL from JSON: {str(e)}")
            return None, None
    else:
        return None, None

def get_embeddings_file_path(file_path: str) -> str:
    """
    Generate the path for the equivalent file with embeddings.
    
    Args:
        file_path: Path to the original file
        
    Returns:
        Path to the file with embeddings
    """
    # Extract the filename from the path (keep the same name)
    file_name = os.path.basename(file_path)
    
    # Generate a path in the embeddings folder (using the same filename)
    embeddings_path = os.path.join(CONFIG.nlweb.json_with_embeddings_folder, file_name)
    
    return embeddings_path

async def delete_site_from_database(site: str, database: str = None):
    """
    Delete all entries for a specific site from the configured database.
    
    Args:
        site: Site identifier to delete
        database: Specific database to use (if None, uses preferred endpoint)
        
    Returns:
        Number of entries deleted
    """
    # Use specified database or fall back to preferred endpoint
    endpoint_name = database or CONFIG.write_endpoint
    
    # Ensure the endpoint exists in configuration
    if endpoint_name not in CONFIG.retrieval_endpoints:
        raise ValueError(f"Database endpoint '{endpoint_name}' not found in configuration")
    
    # Use query_params for development mode override
    query_params = {"db": database} if database else None
    
    print(f"Deleting entries for site '{site}' using endpoint '{endpoint_name}'...")
    
    # Use the wrapper function for deletion
    deleted_count = await delete_documents_by_site(site, query_params=query_params)
    
    print(f"Deleted {deleted_count} documents for site '{site}'")
    return deleted_count

async def is_url(path: str) -> bool:
    """
    Check if a path is a URL.
    
    Args:
        path: Path to check
        
    Returns:
        True if the path is a URL, False otherwise
    """
    if not path:
        return False
        
    try:
        result = urlparse(path)
        # A URL must have both a scheme (http, https) and a network location (domain)
        valid_scheme = result.scheme in ['http', 'https', 'ftp', 'ftps']
        has_netloc = bool(result.netloc)
        
        # Additional check: local file paths may be parsed as URLs on some systems
        # Make sure it's not a Windows drive letter (like C:\)
        not_windows_path = not (len(result.scheme) == 1 and result.scheme.isalpha() and path[1:3] == ':\\')
        
        # Make sure it's not a relative file path
        not_relative_path = not os.path.exists(path)
        
        return valid_scheme and has_netloc and not_windows_path and not_relative_path
    except Exception:
        return False

async def fetch_url(url: str) -> Tuple[str, Optional[str]]:
    """
    Fetch content from a URL.
    
    Args:
        url: URL to fetch
        
    Returns:
        Tuple of (content, file_extension)
    """
    print(f"Fetching content from URL: {url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to fetch URL {url}: HTTP {response.status}")
                
                # Get content type and extension
                content_type = response.headers.get('Content-Type', '').lower()
                
                # Determine file extension based on content type
                ext = None
                if 'application/json' in content_type:
                    ext = '.json'
                elif 'text/csv' in content_type or 'application/csv' in content_type:
                    ext = '.csv'
                elif 'application/rss+xml' in content_type or 'application/atom+xml' in content_type:
                    ext = '.xml'
                elif 'text/xml' in content_type:
                    ext = '.xml'
                    
                # If extension not determined from content-type, try from URL
                if ext is None:
                    path = urlparse(url).path
                    if '.' in path:
                        ext = os.path.splitext(path)[1].lower()
                    # For URLs ending with 'feed' or similar
                    elif any(kw in path.lower() for kw in ['/feed', '/rss', '/podcast']):
                        ext = '.xml'
                
                # Get content as text
                content = await response.text()
                return content, ext
    except Exception as e:
        print(f"Error fetching URL {url}: {str(e)}")
        raise

async def save_url_content(url: str) -> Tuple[str, str]:
    """
    Fetch content from a URL and save to a temporary file.
    
    Args:
        url: URL to fetch
        
    Returns:
        Tuple of (file_path, file_type)
    """
    content, ext = await fetch_url(url)
    
    # Create a temporary file with the appropriate extension
    if ext is None:
        # Check content for RSS/XML markers
        if '<?xml' in content[:100] or '<rss' in content[:1000] or '<feed' in content[:1000]:
            ext = '.xml'
        else:
            ext = '.txt'  # Default extension if we can't determine
    
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode='w', encoding='utf-8') as temp:
        temp.write(content)
        temp_path = temp.name
    
    # Determine file type
    file_type = 'unknown'
    if ext.lower() in ['.json', '.jsonl']:
        file_type = 'json'
    elif ext.lower() == '.csv':
        file_type = 'csv'
    elif ext.lower() in ['.xml', '.rss', '.atom']:
        # Try to check if it's an RSS feed by looking for RSS-specific elements
        if ('<rss' in content or 
            '<feed' in content or 
            '<channel>' in content or 
            '<item>' in content or 
            '<entry>' in content or
            'xmlns:itunes' in content):
            file_type = 'rss'
        else:
            file_type = 'xml'  # Regular XML, not RSS/Atom
    
    print(f"Saved URL content to temporary file: {temp_path} (type: {file_type})")
    return temp_path, file_type

async def detect_file_type(file_path: str) -> Tuple[str, bool]:
    """
    Detect the type of a file based on its extension and content.
    Also determine if it already contains embeddings.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Tuple of (file_type, has_embeddings)
        file_type: 'json', 'csv', 'rss', 'unknown'
        has_embeddings: True if file already contains embeddings
    """
    # Check if this is a URL
    if await is_url(file_path):
        temp_path, file_type = await save_url_content(file_path)
        # URLs fetched fresh don't have embeddings
        return file_type, False
    
    # Get file extension
    ext = os.path.splitext(file_path)[1].lower()
    has_embeddings = False
    
    if ext in ['.json', '.jsonl']:
        # We need to check if this JSON file contains embeddings
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                parts = first_line.split('\t')
                if len(parts) >= 3:
                    # Likely has URL, JSON, and embeddings format
                    embedding_part = parts[2].strip()
                    if (embedding_part.startswith('[') and embedding_part.endswith(']')) or \
                       (embedding_part.replace(',', '').replace('-', '').replace('.', '').replace('e', '').replace('E', '').replace('+', '').isdigit()):
                        has_embeddings = True
        except Exception:
            pass
        return 'json', has_embeddings
    elif ext == '.csv':
        return 'csv', has_embeddings
    elif ext == '.xlsx':
        return 'xlsx', has_embeddings
    elif ext in ['.xml', '.rss', '.atom']:
        # Check if file contains RSS-like elements
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(2000)  # Read first 2000 chars for detection
                
                # Look for RSS markers in the content
                if ('<rss' in content or 
                    '<feed' in content or 
                    '<channel>' in content or 
                    '<item>' in content or 
                    '<entry>' in content or
                    'xmlns:itunes' in content):
                    return 'rss', has_embeddings
                
            # If we get here, it's probably regular XML, not RSS
            return 'xml', has_embeddings
        except Exception as e:
            print(f"Error checking XML type: {e}")
            return 'xml', has_embeddings
    
    # Check if file contains embeddings by examining content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            
            # Check for embeddings - typically 3 tab-separated fields with the last one
            # being a numeric vector (beginning with '[' or just numbers)
            if '\t' in first_line:
                parts = first_line.split('\t')
                if len(parts) >= 3:
                    # Check if the third part looks like an embedding vector
                    # Either [0.123, 0.456, ...] format or just 0.123,0.456,... format
                    embedding_part = parts[2].strip()
                    if (embedding_part.startswith('[') and embedding_part.endswith(']')) or \
                       (embedding_part.replace(',', '').replace('-', '').replace('.', '').replace('e', '').replace('E', '').replace('+', '').isdigit()):
                        has_embeddings = True
                elif len(parts) == 2:
                    # Check if this is URL + JSON format (2 tab-separated parts)
                    try:
                        json.loads(parts[1])
                        return 'json', has_embeddings
                    except:
                        pass
            
            # If we're checking a file with embeddings, it's a special JSON format
            if has_embeddings:
                return 'json', has_embeddings
            
            # Check if it's JSON
            if first_line.startswith('{') or first_line.startswith('['):
                return 'json', has_embeddings
            
            # Check if it's CSV
            if ',' in first_line and not first_line.startswith('<'):
                return 'csv', has_embeddings
            
            # Check if it's XML/RSS
            if first_line.startswith('<?xml') or '<' in first_line[:10]:
                # Check if file contains RSS-like elements
                f.seek(0)
                content = f.read(2000)  # Read first 2000 chars for detection
                
                if ('<rss' in content or 
                    '<feed' in content or 
                    '<channel>' in content or 
                    '<item>' in content or 
                    '<entry>' in content or
                    'xmlns:itunes' in content):
                    return 'rss', has_embeddings
                
                return 'xml', has_embeddings
    except Exception as e:
        print(f"Warning: Error while detecting file type: {e}")
    
    return 'unknown', has_embeddings

async def process_xlsx_file(file_path: str, site: str) -> list:
    """
    处理 Excel 文件（.xlsx），转为文档对象列表
    Args:
        file_path: Excel 文件路径
        site: 站点标识
    Returns:
        文档对象列表
    """
    print(f"Processing XLSX file: {file_path}")
    documents = []
    error_count = 0
    success_count = 0

    try:
        df = pd.read_excel(file_path, dtype=str)  # 读为字符串，避免类型问题
        if df.empty:
            print(f"Warning: XLSX file {file_path} is empty.")
            return documents

        for index, row in df.iterrows():
            try:
                row_data = row.to_dict()
                # 尝试提取 url/id 字段
                url = None
                for col in ['url', 'URL', 'link', 'Link', 'id', 'ID', 'identifier']:
                    if col in row_data and row_data[col]:
                        url = str(row_data[col])
                        break
                if not url:
                    url = f"xlsx:{os.path.basename(file_path)}:{index}"

                # 转为 JSON
                json_data = json.dumps(row_data, ensure_ascii=False)

                # 尝试提取 name/title 字段
                name = None
                for col in ['name', 'Name', 'title', 'Title', 'heading', 'Heading']:
                    if col in row_data and row_data[col]:
                        name = str(row_data[col])
                        break
                if not name:
                    name = f"Row {index} from {os.path.basename(file_path)}"

                # 组装文档对象
                document = {
                    "id": str(hash(url) % (2**63)),
                    "schema_json": json_data,
                    "url": url,
                    "name": name,
                    "site": site
                }
                documents.append(document)
                success_count += 1

                if (index + 1) % 1000 == 0:
                    print(f"Processed {index + 1} rows ({success_count} successful, {error_count} errors)")

            except Exception as row_error:
                error_count += 1
                print(f"Error processing row {index}: {str(row_error)}")
                continue

        print(f"XLSX processing complete: {success_count} rows processed successfully, {error_count} rows had errors")
        return documents

    except Exception as e:
        print(f"Fatal error processing XLSX file: {str(e)}")
        return documents 
              
async def process_csv_file(file_path: str, site: str) -> List[Dict[str, Any]]:
    """
    Process a standard CSV file into document objects without using pandas.
    
    Args:
        file_path: Path to the CSV file
        site: Site identifier
        
    Returns:
        List of document objects
    """
    print(f"Processing CSV file: {file_path}")
    
    documents = []
    error_count = 0
    success_count = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as csv_file:
            # First try to determine the dialect
            try:
                dialect = csv.Sniffer().sniff(csv_file.read(4096))
                csv_file.seek(0)
            except csv.Error:
                # If sniffer fails, use default dialect
                dialect = csv.excel
                csv_file.seek(0)
            
            # Try to create a reader - handle potential BOM or encoding issues
            try:
                csv_reader = csv.DictReader(csv_file, dialect=dialect)
                
                # Check if we have enough columns for meaningful data
                if len(csv_reader.fieldnames or []) < 2:
                    print(f"Warning: CSV file has fewer than 2 columns. This may not contain enough data.")
            except Exception as e:
                # If we have trouble with DictReader, try a more primitive approach
                print(f"Error with DictReader: {e}. Trying with simple CSV reader...")
                csv_file.seek(0)
                csv_reader = csv.reader(csv_file, dialect=dialect)
                # Read the header line
                header = next(csv_reader, [])
                if len(header) < 2:
                    print(f"Warning: CSV file has fewer than 2 columns. This may not contain enough data.")
                
                # Convert to a format compatible with our processing
                reader_with_header = []
                for row in csv_reader:
                    # If row is shorter than header, pad it
                    if len(row) < len(header):
                        row.extend([''] * (len(header) - len(row)))
                    # If row is longer than header, truncate it
                    elif len(row) > len(header):
                        row = row[:len(header)]
                    
                    row_dict = dict(zip(header, row))
                    reader_with_header.append(row_dict)
                
                csv_reader = reader_with_header
            
            # Process each row in the CSV
            for index, row in enumerate(csv_reader):
                try:
                    # Handle both DictReader objects and our manual dict list
                    if isinstance(csv_reader, list):
                        row_data = row
                    else:
                        row_data = row
                    
                    # Try to find a good identifier column (url, id, etc.)
                    url = None
                    
                    # Look for common URL/ID columns
                    for col in ['url', 'URL', 'link', 'Link', 'id', 'ID', 'identifier']:
                        if col in row_data and row_data[col]:
                            url = str(row_data[col])
                            break
                    
                    # If no URL found, use a generated one with the row index
                    if not url:
                        url = f"csv:{os.path.basename(file_path)}:{index}"
                    
                    # Convert row to JSON
                    json_data = json.dumps(row_data)
                    
                    # Find a good name field
                    name = None
                    for col in ['name', 'Name', 'title', 'Title', 'heading', 'Heading']:
                        if col in row_data and row_data[col]:
                            name = str(row_data[col])
                            break
                    
                    # If no name found, use a generated one
                    if not name:
                        name = f"Row {index} from {os.path.basename(file_path)}"
                    
                    # Create document
                    document = {
                        "id": str(hash(url) % (2**63)),  # Create a stable ID from the URL
                        "schema_json": json_data,
                        "url": url,
                        "name": name,
                        "site": site
                    }
                    
                    documents.append(document)
                    success_count += 1
                    
                    # Print progress periodically
                    if (index + 1) % 1000 == 0:
                        print(f"Processed {index + 1} rows ({success_count} successful, {error_count} errors)")
                
                except Exception as row_error:
                    # Log the error but continue processing other rows
                    error_count += 1
                    print(f"Error processing row {index}: {str(row_error)}")
                    if error_count <= 5:  # Only print detailed traceback for the first few errors
                        traceback.print_exc()
                    elif error_count == 6:
                        print("Suppressing further detailed error messages...")
                    
                    # Continue with the next row
                    continue
        
        print(f"CSV processing complete: {success_count} rows processed successfully, {error_count} rows had errors")
        return documents
    
    except Exception as e:
        print(f"Fatal error processing CSV file: {str(e)}")
        traceback.print_exc()
        # Return any documents we've managed to process so far
        print(f"Returning {len(documents)} documents that were processed before the error")
        return documents
    


async def process_rss_feed(file_path: str, site: str) -> List[Dict[str, Any]]:
    """
    Process an RSS/Atom feed into document objects.
    
    Args:
        file_path: Path to the RSS file or URL
        site: Site identifier
        
    Returns:
        List of document objects
    """
    print(f"Processing RSS/Atom feed: {file_path}")
    
    try:
        # Convert feed to schema.org format
        podcast_episodes = rss2schema.feed_to_schema(file_path)
        
        documents = []
        
        # Process each episode in the feed
        for episode in podcast_episodes:
            # Extract URL
            url = episode.get("url")
            
            # Generate a synthetic URL if needed
            if not url and "name" in episode:
                url = f"synthetic:{site}:{episode['name']}"
                episode["url"] = url
                print(f"Generated synthetic URL for episode: {episode['name']}")
            elif not url:
                # Skip items without any identifiable information
                continue
            
            # Convert to JSON - ensure no newlines in the JSON
            json_data = json.dumps(episode, ensure_ascii=False).replace("\n", " ")
            
            # Extract name
            name = episode.get("name", "Untitled Episode")
            
            # Create document
            document = {
                "id": str(hash(url) % (2**63)),  # Create a stable ID from the URL
                "schema_json": json_data,
                "url": url,
                "name": name,
                "site": site
            }
            
            documents.append(document)
        
        print(f"Processed {len(documents)} episodes from RSS/Atom feed")
        return documents
    except Exception as e:
        print(f"Error processing RSS/Atom feed: {str(e)}")
        traceback.print_exc()
        return []

async def loadJsonWithEmbeddingsToDB(file_path: str, site: str, batch_size: int = 100, delete_existing: bool = False, database: str = None):
    """
    Load data from a file with precomputed embeddings into the database.
    
    The file should have 3 columns per row, separated by tabs:
    1. URL for the item
    2. JSON for the item
    3. Embedding for the item
    
    Args:
        file_path: Path to the input file (URL, JSON, embedding)
        site: Site identifier
        batch_size: Number of documents to process and upload in each batch
        delete_existing: Whether to delete existing entries for this site before loading
        database: Specific database endpoint to use (if None, uses preferred endpoint)
    """
    # Check if this is a URL
    is_url_path = await is_url(file_path)
    temp_path = None
    
    if is_url_path:
        temp_path, _ = await save_url_content(file_path)
        file_path = temp_path
    print(f"file_path: {file_path}")
    try:
        resolved_path = None
        
        # First, check if the file exists at the given path
        if os.path.exists(file_path):
            # Check if this file actually contains embeddings
            file_type, has_embeddings = await detect_file_type(file_path)
            if has_embeddings:
                # If the file exists and has embeddings, use it directly
                print(f"File exists and contains embeddings, using directly: {file_path}")
                resolved_path = file_path
            else:
                print(f"File exists but doesn't contain embeddings: {file_path}")
        
        # If we haven't resolved a path yet, try standard resolution methods
        if resolved_path is None:
            embeddings_folder = CONFIG.nlweb.json_with_embeddings_folder
            
            # If the path already starts with the embeddings folder, use it directly
            if file_path.startswith(embeddings_folder):
                resolved_path = file_path
            else:
                # Otherwise, it might be just a filename or relative path, so resolve it
                embeddings_path = get_embeddings_file_path(file_path)
                
                # Check if the resolved embeddings path exists
                if os.path.exists(embeddings_path):
                    resolved_path = embeddings_path
                else:
                    # Last resort: Check if the file exists in the base folder
                    if os.path.exists(file_path):
                        resolved_path = file_path
                    else:
                        # If still not found, use the standard embeddings path (which might not exist)
                        resolved_path = embeddings_path
        
        # Use specified database or fall back to preferred endpoint
        endpoint_name = database or CONFIG.write_endpoint
        
        print(f"Loading data with embeddings from {resolved_path} for site {site} using database endpoint '{endpoint_name}'")
        
        # Check if resolved path exists
        if not os.path.exists(resolved_path):
            raise FileNotFoundError(f"File not found: {resolved_path}")
        
        # Delete existing entries for this site if requested
        if delete_existing:
            await delete_site_from_database(site, endpoint_name)
        
        # Read all lines from the file
        lines = await read_file_lines(resolved_path)
        total_lines = len(lines)
        
        print(f"Found {total_lines} lines in the file")
        
        # Use query_params for development mode override
        query_params = {"db": database} if database else None
        
        # Process lines in batches
        batch_documents = []
        total_documents = 0
        
        for i, line in enumerate(lines):
            try:
                # Use documents_from_csv_line utility to process the line
                documents = documents_from_csv_line(line, site)
                batch_documents.extend(documents)
                
                # When batch is full or we've reached the end, upload to database
                if len(batch_documents) >= batch_size or i == total_lines - 1:
                    if batch_documents:
                        batch_idx = i // batch_size
                        total_batches = (total_lines + batch_size - 1) // batch_size
                        
                        # Upload directly using the wrapper function
                        print(f"Uploading batch {batch_idx+1} of {total_batches} ({len(batch_documents)} documents)")
                        await upload_documents(batch_documents, query_params=query_params)
                        print(f"Successfully uploaded batch {batch_idx+1}")
                        
                        total_documents += len(batch_documents)
                        batch_documents = []
            except Exception as e:
                print(f"Error processing line {i+1}: {str(e)}")
            
            # Print progress
            if (i+1) % 1000 == 0 or i == total_lines - 1:
                print(f"Processed {i+1}/{total_lines} lines")
        
        print(f"Loading completed. Added {total_documents} documents to the database.")
        return total_documents
    finally:
        # Clean up temporary file if needed
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                print(f"Cleaned up temporary file: {temp_path}")
            except Exception:
                pass

async def loadJsonToDB(file_path: str, site: str, batch_size: int = 100, delete_existing: bool = False, force_recompute: bool = False, database: str = None):
    """
    Load data from a file, compute embeddings, and store in the database.
    
    The file can have one of multiple formats:
    1. Two columns per row, separated by tabs: URL and JSON
    2. One column: JSON only (URL will be extracted from the JSON)
    3. CSV file with headers
    4. RSS/Atom feed
    5. URL pointing to any of the above types
    
    Args:
        file_path: Path to the input file or URL
        site: Site identifier
        batch_size: Number of documents to process and upload in each batch
        delete_existing: Whether to delete existing entries for this site before loading
        force_recompute: Whether to force recomputation of embeddings
        database: Specific database endpoint to use (if None, uses preferred endpoint)
    """
    # Check if this is a URL
    is_url_path = await is_url(file_path)
    temp_path = None
    
    if is_url_path:
        temp_path, _ = await save_url_content(file_path)
        original_path = file_path  # Keep original URL for reference
        file_path = temp_path
    else:
        original_path = file_path  # Use original path for non-URLs
    
    try:
        # First, check if the file exists at the given path
        if os.path.exists(file_path):
            resolved_path = file_path  # Use directly if it exists
        else:
            # If not, try to resolve it from the JSON data folder
            resolved_path = os.path.join(CONFIG.nlweb.json_data_folder, file_path)
            if not os.path.exists(resolved_path):
                # If still not found, check if it's an absolute path
                if os.path.isabs(file_path):
                    resolved_path = file_path
                else:
                    # Last attempt: just use the provided path (might not exist)
                    resolved_path = file_path
        
        # Use specified database or fall back to preferred endpoint
        endpoint_name = database or CONFIG.write_endpoint
        
        print(f"Loading data from {original_path} (resolved to {resolved_path}) for site {site} using database endpoint '{endpoint_name}'")
        
        # Detect file type
        file_type, has_embeddings = await detect_file_type(resolved_path)
        print(f"Detected file type: {file_type}")
        
        # If embeddings are detected, switch to loadJsonWithEmbeddingsToDB
        if has_embeddings and not force_recompute:
            print(f"File already contains embeddings, switching to direct loading mode...")
            return await loadJsonWithEmbeddingsToDB(resolved_path, site, batch_size, delete_existing, endpoint_name)
        
        # Check for existing embeddings file if not forcing recomputation
        embeddings_path = get_embeddings_file_path(os.path.basename(original_path))
        
        if os.path.exists(embeddings_path) and not force_recompute:
            # In interactive mode, ask the user what to do
            if sys.stdin.isatty():
                response = input(f"A file with embeddings already exists at {embeddings_path}. Use it? (y/n): ")
                use_existing = response.lower() in ('y', 'yes')
            else:
                # In non-interactive mode, default to using the existing file
                use_existing = True
                print(f"Using existing file with embeddings at {embeddings_path}")
            
            if use_existing:
                # Use the existing file with embeddings
                return await loadJsonWithEmbeddingsToDB(embeddings_path, site, batch_size, delete_existing, endpoint_name)
            else:
                print(f"Proceeding to compute new embeddings for {original_path}")
        
        # If we get here, we need to process the file based on its type and compute embeddings
        
        # Delete existing entries for this site if requested
        if delete_existing:
            await delete_site_from_database(site, endpoint_name)
        
        # Use query_params for development mode override
        query_params = {"db": database} if database else None
        
        # Get embedding provider from config
        provider = CONFIG.preferred_embedding_provider
        provider_config = CONFIG.get_embedding_provider(provider)
        model = provider_config.model if provider_config else None
        
        print(f"Using embedding provider: {provider}, model: {model}")
        
        # Initialize documents list
        all_documents = []
        
        # IMPORTANT FIX:
        # For XML files with RSS-like content, force it to be processed as RSS
        # even if it wasn't explicitly detected as RSS
        if file_type == 'xml' and is_url_path and (
            '/feed' in original_path.lower() or 
            '/rss' in original_path.lower() or 
            '/podcast' in original_path.lower() or
            original_path.lower().endswith(('feed', 'rss', 'podcast', 'xml'))
           ):
            print("XML file from URL looks like it might be an RSS feed. Processing as RSS...")
            file_type = 'rss'
        
        # Process based on file type
        if file_type == 'csv':
            # Process standard CSV file
            all_documents = await process_csv_file(resolved_path, site)
        elif file_type == 'xlsx':
            # Process standard CSV file
            all_documents = await process_xlsx_file(resolved_path, site)
        elif file_type == 'rss' or (file_type == 'xml' and ('/feed' in original_path.lower() or '/rss' in original_path.lower())):
            # Process RSS/Atom feed
            print("Processing as RSS feed...")
            all_documents = await process_rss_feed(resolved_path, site)
        else:
            # Default to JSON processing
            # Read all lines from the file
            lines = await read_file_lines(resolved_path)
            total_lines = len(lines)
            
            print(f"Found {total_lines} lines in the file")
            
            # Check the first few lines to detect if this is a JSON-only file
            sample_lines = lines[:min(5, len(lines))]
            json_only_format = True
            
            for line in sample_lines:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    json_only_format = False
                    break
            
            if json_only_format:
                print("Detected JSON-only format. URLs will be extracted from within the JSON data.")
            
            # Process each line to extract documents
            for line in lines:
                try:
                    # Process the line, handling JSON-only format if needed
                    url, json_data = process_line(line)
                    
                    if url is None or json_data is None:
                        continue
                    
                    # Prepare documents
                    documents, _ = prepare_documents_from_json(url, json_data, site)
                    all_documents.extend(documents)
                except Exception as e:
                    print(f"Error processing line: {str(e)}")
                    continue
        
        # If we have documents to process
        if all_documents:
            # Ensure the directory exists for the embeddings file
            os.makedirs(os.path.dirname(embeddings_path), exist_ok=True)
            
            # Open file to write documents with embeddings
            with open(embeddings_path, 'w', encoding='utf-8') as embed_file:
                # Extract texts for embedding
                texts = [doc["schema_json"] for doc in all_documents]
                
                # Process in batches
                total_documents = 0
                
                for i in range(0, len(all_documents), batch_size):
                    batch_docs = all_documents[i:i+batch_size]
                    batch_texts = texts[i:i+batch_size]
                    
                    if batch_docs and batch_texts:
                        try:
                            print(f"Computing embeddings for batch of {len(batch_texts)} texts")
                            
                            # Compute embeddings for the batch
                            embeddings = await batch_get_embeddings(batch_texts, provider, model)
                            
                            # Add embeddings to documents
                            docs_with_embeddings = []
                            
                            for j, embedding in enumerate(embeddings):
                                if j < len(batch_docs):
                                    doc = batch_docs[j].copy()  # Create a copy of the document
                                    
                                    # Add embedding to document
                                    doc["embedding"] = embedding
                                    
                                    # Format embedding as string - ensure no newlines
                                    embedding_str = str(embedding).replace(' ', '').replace('\n', '')
                                    
                                    # Ensure JSON has no newlines
                                    doc_json = doc['schema_json'].replace('\n', ' ')
                                    
                                    # Write to embeddings file
                                    embed_file.write(f"{doc['url']}\t{doc_json}\t{embedding_str}\n")
                                    
                                    docs_with_embeddings.append(doc)
                            
                            # Upload batch using the client directly
                            batch_idx = i // batch_size
                            total_batches = (len(all_documents) + batch_size - 1) // batch_size
                            
                            print(f"Uploading batch {batch_idx+1} of {total_batches} ({len(docs_with_embeddings)} documents)")
                            await upload_documents(docs_with_embeddings, query_params=query_params)
                            print(f"Successfully uploaded batch {batch_idx+1}")
                            
                            total_documents += len(docs_with_embeddings)
                        except Exception as e:
                            print(f"Error processing batch: {str(e)}")
                            traceback.print_exc()
                    
                    # Print progress
                    print(f"Processed {min(i+batch_size, len(all_documents))}/{len(all_documents)} documents")
            
            print(f"Loading completed. Added {total_documents} documents to the database.")
            print(f"Saved file with embeddings to {embeddings_path}")
            
            return total_documents
        else:
            print("No documents were extracted from the file.")
            return 0
    finally:
        # Clean up temporary file if needed
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                print(f"Cleaned up temporary file: {temp_path}")
            except Exception:
                pass

async def loadUrlListToDB(file_path: str, site: str, batch_size: int = 100, delete_existing: bool = False, force_recompute: bool = False, database: str = None):
    """
    Process a file containing a list of URLs, fetch each URL, and load the content into the database.
    Each line in the file should be a single URL pointing to RSS/XML or JSON content.
    The file itself can be a local file or a URL.
    
    Args:
        file_path: Path to the file containing URLs, one per line, or a URL to such a file
        site: Site identifier
        batch_size: Number of documents to process and upload in each batch
        delete_existing: Whether to delete existing entries for this site before loading
        force_recompute: Whether to force recomputation of embeddings
        database: Specific database endpoint to use (if None, uses preferred endpoint)
        
    Returns:
        Total number of documents loaded
    """
    # Use specified database or fall back to preferred endpoint
    endpoint_name = database or CONFIG.write_endpoint
    
    # Check if the file_path is a URL
    is_url_list_remote = await is_url(file_path)
    temp_path = None
    
    try:
        # If the file is a URL, fetch it first
        if is_url_list_remote:
            print(f"URL list file is a remote URL. Fetching: {file_path}")
            content, _ = await fetch_url(file_path)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w', encoding='utf-8') as temp:
                temp.write(content)
                temp_path = temp.name
                
            print(f"Saved URL list to temporary file: {temp_path}")
            # Use the temp path for further processing
            file_path = temp_path
    
        # Read all lines from the file, each line should be a URL
        lines = await read_file_lines(file_path)
        total_urls = len(lines)
        
        # Filter out empty lines and comments
        urls = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
        total_valid_urls = len(urls)
        
        print(f"Found {total_valid_urls} valid URLs out of {total_urls} lines in the file")
        
        # Delete existing entries for this site if requested (do this only once)
        if delete_existing:
            await delete_site_from_database(site, endpoint_name)
        
        # Get client directly from the factory function, using query_params for development mode override
        query_params = {"db": database} if database else None
        client = get_vector_db_client(query_params=query_params)
        
        # Process each URL
        total_documents = 0
        for i, url in enumerate(urls):
            print(f"\nProcessing URL {i+1}/{total_valid_urls}: {url}")
            
            # Check if this is a valid URL
            if not await is_url(url):
                print(f"Warning: Invalid URL format, skipping: {url}")
                continue
            
            try:
                # Fetch content from URL
                temp_url_path, _ = await save_url_content(url)
                
                try:
                    # Detect type of the content
                    file_type, has_embeddings = await detect_file_type(temp_url_path)
                    print(f"Detected file type: {file_type}")
                    
                    # Process based on file type
                    doc_count = 0
                    if file_type == 'rss' or file_type == 'xml':
                        # Process as RSS/XML
                        # The URL becomes the 'site' for grouping purposes if requested
                        actual_site = site
                        docs = await process_rss_feed(temp_url_path, actual_site)
                        
                        if docs:
                            # Get embedding provider from config
                            provider = CONFIG.preferred_embedding_provider
                            provider_config = CONFIG.get_embedding_provider(provider)
                            model = provider_config.model if provider_config else None
                            
                            # Process in batches
                            for j in range(0, len(docs), batch_size):
                                batch_docs = docs[j:j+batch_size]
                                batch_texts = [doc["schema_json"] for doc in batch_docs]
                                
                                # Compute embeddings
                                embeddings = await batch_get_embeddings(batch_texts, provider, model)
                                
                                # Add embeddings to documents
                                docs_with_embeddings = []
                                for k, embedding in enumerate(embeddings):
                                    if k < len(batch_docs):
                                        doc = batch_docs[k].copy()
                                        doc["embedding"] = embedding
                                        docs_with_embeddings.append(doc)
                                
                                # Upload batch directly with client
                                batch_idx = j // batch_size
                                total_batches = (len(docs) + batch_size - 1) // batch_size
                                
                                print(f"Uploading batch {batch_idx+1} of {total_batches} ({len(docs_with_embeddings)} documents)")
                                await upload_documents(docs_with_embeddings, query_params=query_params)
                                print(f"Successfully uploaded batch {batch_idx+1}")
                                
                                doc_count += len(docs_with_embeddings)
                    elif file_type == 'json':
                        # Process as JSON
                        # For each JSON file, we'll process it and add to the database
                        doc_count = await loadJsonToDB(temp_url_path, site, batch_size, False, force_recompute, endpoint_name)
                    else:
                        print(f"Warning: Unsupported file type for URL {url}: {file_type}")
                    
                    total_documents += doc_count
                    print(f"Added {doc_count} documents from URL: {url}")
                    
                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_url_path):
                        os.unlink(temp_url_path)
                        print(f"Cleaned up temporary file: {temp_url_path}")
            
            except Exception as e:
                print(f"Error processing URL {url}: {str(e)}")
                traceback.print_exc()
                print("Continuing with next URL...")
        
        print(f"\nProcessing completed. Added a total of {total_documents} documents from {total_valid_urls} URLs.")
        return total_documents
    
    except Exception as e:
        print(f"Error reading URL list file: {str(e)}")
        traceback.print_exc()
        return 0
    finally:
        # Clean up the temporary file if we created one
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                print(f"Cleaned up temporary URL list file: {temp_path}")
            except Exception:
                pass

async def delete_site(site: str, database: str = None):
    """
    Delete all entries for a specific site from the database.
    
    Args:
        site: Site identifier to delete
        database: Specific database endpoint to use (if None, uses preferred endpoint)
    """
    count = await delete_site_from_database(site, database)
    print(f"Deleted {count} entries for site '{site}'")

async def main():
    """
    Main function for command-line use.
    
    Example usage:
        python db_loader.py file.txt site_name
        python db_loader.py https://example.com/feed.rss site_name
        python db_loader.py data.csv site_name
        python db_loader.py --delete-site site_name
        python db_loader.py file.txt site_name --database qdrant_local
        python db_loader.py --force-recompute file.txt site_name
        python db_loader.py --url-list urls.txt site_name
        python db_loader.py --url-list https://example.com/feed_list.txt site_name
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Load data into vector database")
    parser.add_argument("--delete-site", action="store_true",
                        help="Delete existing entries for the site before loading")
    parser.add_argument("--only-delete", action="store_true",
                        help="Only delete entries for the site, don't load data")
    parser.add_argument("--force-recompute", action="store_true",
                        help="Force recomputation of embeddings even if a file with embeddings exists")
    parser.add_argument("--url-list", action="store_true",
                        help="Treat the input file as a list of URLs to process (one URL per line). The list file itself can be local or a URL.")
    parser.add_argument("file_path", nargs="?", help="Path to the input file or URL")
    parser.add_argument("site", help="Site identifier")
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Batch size for processing and uploading")
    parser.add_argument("--database", type=str, default=None,
                        help="Specific database endpoint to use (from config_retrieval.yaml)")
    
    args = parser.parse_args()
    
    # Validate database if specified
    if args.database and args.database not in CONFIG.retrieval_endpoints:
        parser.error(f"Database endpoint '{args.database}' not found in configuration. Available options: {', '.join(CONFIG.retrieval_endpoints.keys())}")
    
    # Handle delete-only mode
    if args.only_delete:
        await delete_site(args.site, args.database)
        return
    
    # Validate file path if we're not just deleting
    if args.file_path is None and not args.only_delete:
        parser.error("file_path is required unless --only-delete is specified")
    
    # Handle URL list mode
    if args.url_list:
        is_url_path = await is_url(args.file_path)
        if is_url_path:
            print(f"Processing remote URL list from: {args.file_path}")
        else:
            print(f"Processing local URL list file: {args.file_path}")
            
        await loadUrlListToDB(args.file_path, args.site, args.batch_size, args.delete_site, args.force_recompute, args.database)
        return
    
    # Normal processing mode
    # Check if file exists at the specified path
    if not await is_url(args.file_path) and not os.path.exists(args.file_path):
        print(f"Warning: File not found at '{args.file_path}'. Will try to resolve or download it.")
    
    # Determine if the file is a URL
    is_url_path = await is_url(args.file_path)
    temp_path = None
    file_path = args.file_path
    
    # If it's a URL, fetch the content
    if is_url_path:
        print(f"Fetching content from URL: {args.file_path}")
        temp_path, _ = await save_url_content(args.file_path)
        file_path = temp_path
    
    try:
        # Detect file type and if it contains embeddings
        if os.path.exists(file_path):
            file_type, has_embeddings = await detect_file_type(file_path)
            print(f"Detected file type: {file_type}, contains embeddings: {'Yes' if has_embeddings else 'No'}")
            
            # Process based on whether the file has embeddings
            if has_embeddings and not args.force_recompute:
                print("File already contains embeddings, loading directly...")
                await loadJsonWithEmbeddingsToDB(file_path, args.site, args.batch_size, args.delete_site, args.database)
            else:
                print("Computing embeddings for file...")
                await loadJsonToDB(file_path, args.site, args.batch_size, args.delete_site, args.force_recompute, args.database)
        else:
            print(f"Error: File not found at '{file_path}'")
            sys.exit(1)
    finally:
        # Clean up temporary file if needed
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                print(f"Cleaned up temporary file: {temp_path}")
            except Exception:
                pass

if __name__ == "__main__":
    asyncio.run(main())