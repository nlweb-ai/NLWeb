"""
Utilities for working with vector databases and document processing.
Includes functions for document creation, transformation, and database operations.
"""

import os
import json
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from config.config import CONFIG
from tools.trim_schema_json import trim_schema_json

# Item type categorization
SKIP_TYPES = ["ItemList", "ListItem", "AboutPage", "WebPage", "WebSite", "Person"]

INCLUDE_TYPES = [
    "Recipe", "NeurIPSPoster", "InvitedTalk", "Oral", "Movie", "LocalBusiness", "Review",
    "TVShow", "TVEpisode", "Product", "Offer", "PodcastEpisode", "Book",
    "Podcast", "TVSeries", "ProductGroup", "Event", "FoodEstablishment",
    "Apartment", "House", "Home", "RealEstateListing", "SingleFamilyResidence", "Offer",
    "AggregateOffer", "Event", "BusinessEvent", "Festival", "MusicEvent", "EducationEvent",
    "SocialEvent", "SportsEvent"
]

# Path constants (can be overridden by config)
EMBEDDINGS_PATH_SMALL = "./data/embeddings/small/"
EMBEDDINGS_PATH_LARGE = "./data/embeddings/large/"
EMBEDDING_SIZE = "small"

# ---------- File and JSON Processing Functions ----------

async def read_file_lines(file_path: str) -> List[str]:
    """
    Read lines from a file, handling different encodings.
    
    Args:
        file_path: Path to the file
        
    Returns:
        List of lines from the file
    """
    encodings = ['utf-8', 'latin-1', 'utf-16']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                return [line.strip() for line in file if line.strip()]
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
            raise
    
    raise ValueError(f"Could not read file {file_path} with any of the attempted encodings")

def int64_hash(string):
    """
    Compute a hash value for a string, ensuring it fits within int64 range.
    
    Args:
        string: The string to hash
        
    Returns:
        int64 hash value
    """
    hash_value = hash(string)
    return np.int64(hash_value)

def should_include_item(js):
    """
    Check if an item should be included based on its type.
    
    Args:
        js: JSON object to check
        
    Returns:
        True if the item should be included, False otherwise
    """
    if "@type" in js:
        item_type = js["@type"]
        if isinstance(item_type, list):
            if any(t in INCLUDE_TYPES for t in item_type):
                return True
        if item_type in INCLUDE_TYPES:
            return True
    elif "@graph" in js:
        for item in js["@graph"]:
            if should_include_item(item):
                return True
    return False

def normalize_item_list(js):
    """
    Normalize a JSON item list into a consistent format.
    
    Args:
        js: JSON object or list to normalize
        
    Returns:
        Normalized list of items
    """
    retval = []
    if isinstance(js, list):
        for item in js:
            if isinstance(item, list) and len(item) == 1:
                item = item[0]
            if "@graph" in item:
                for subitem in item["@graph"]:
                    retval.append(subitem)
            else:
                retval.append(item)
        return retval
    elif "@graph" in js:
        return js["@graph"]
    else:
        return [js]

def get_item_name(item: Dict[str, Any]) -> str:
    """
    Extract name from a JSON item using various fields.
    
    Args:
        item: JSON item to extract name from
        
    Returns:
        Name string or empty string if no name found
    """
    if isinstance(item, list):
        for subitem in item:
            name = get_item_name(subitem)
            if name:
                return name
    
    name_fields = ["name", "headline", "title", "keywords"]
    
    for field in name_fields:
        if field in item and item[field]:
            return item[field]
    
    # Try to extract from URL if name fields aren't present
    url = None
    if "url" in item:
        url = item["url"]
    elif "@id" in item:
        url = item["@id"]
    
    if not url:
        return ""
        
    # Extract name from URL
    parts = url.replace('https://', '').replace('http://', '').split('/', 1)
    if len(parts) > 1:
        path = parts[1]
        path_parts = path.split('/')
        longest_part = max(path_parts, key=len) if path_parts else ""
        name = ' '.join(word.capitalize() for word in longest_part.replace('-', ' ').split())
        return name
        
    return ""

# ---------- Document Preparation Functions ----------

def prepare_documents_from_json(url: str, json_data: str, site: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Prepare documents from URL and JSON data.
    
    Args:
        url: URL for the item
        json_data: JSON data for the item
        site: Site identifier
        
    Returns:
        Tuple of (documents, texts_for_embedding)
    """
    try:
        # Parse and trim the JSON
        json_obj = json.loads(json_data)
        trimmed_json = trim_schema_json(json_obj, site)
        
        if not trimmed_json:
            return [], []
        
        # Convert to list if not already
        if not isinstance(trimmed_json, list):
            trimmed_json = [trimmed_json]
        
        documents = []
        texts = []
        
        # Process each item in the JSON
        for i, item in enumerate(trimmed_json):
            if item is None:
                continue
                
            item_url = url if i == 0 else f"{url}#{i}"
            item_json = json.dumps(item)
            
            # Add document to batch
            doc = {
                "id": str(int64_hash(item_url)),
                "schema_json": item_json,
                "url": item_url,
                "name": get_item_name(item),
                "site": site
            }
            
            documents.append(doc)
            texts.append(item_json)
        
        return documents, texts
    except Exception as e:
        print(f"Error preparing documents from JSON: {str(e)}")
        return [], []

def documents_from_csv_line(line, site):
    """
    Parse a line with URL, JSON, and embedding into document objects.
    
    Args:
        line: Tab-separated line with URL, JSON, and embedding
        site: Site identifier
        
    Returns:
        List of document objects
    """
    try:
        url, json_data, embedding_str = line.strip().split('\t')
        embedding_str = embedding_str.replace("[", "").replace("]", "") 
        embedding = [float(x) for x in embedding_str.split(',')]
        js = json.loads(json_data)
        js = trim_schema_json(js, site)
    except Exception as e:
        print(f"Error processing line: {str(e)}")
        return []
    
    documents = []
    if not isinstance(js, list):
        js = [js]
    
    for i, item in enumerate(js):
        # No longer filtering by should_include_item - trimming already handles this
        item_url = url if i == 0 else f"{url}#{i}"
        name = get_item_name(item)
        
        documents.append({
            "id": str(int64_hash(item_url)),
            "embedding": embedding,
            "schema_json": json.dumps(item),
            "url": item_url,
            "name": name,
            "site": site
        })
    
    return documents

# ---------- Database Client Functions ----------

# Note: This function is maintained for backward compatibility
# In new code, import get_vector_db_client directly from retriever.py
async def get_vector_client(endpoint_name=None):
    """
    Get a client for the specified retrieval endpoint from config.
    This is a backward compatibility wrapper.
    For new code, import get_vector_db_client directly from retriever.py.
    
    Args:
        endpoint_name: Name of the endpoint to use (if None, uses preferred endpoint)
        
    Returns:
        Tuple of (client, db_type) for backward compatibility
    """
    # Dynamically import to avoid circular imports
    from retriever import get_vector_db_client
    
    # Get the client
    client = get_vector_db_client(endpoint_name)
    
    # Return both the client and the db_type for backward compatibility
    return client, client.db_type

# Note: This function is maintained for backward compatibility
async def upload_batch_to_db(client, db_type, documents, batch_idx, total_batches, endpoint_name=None):
    """
    Upload a batch of documents to the database using the client.
    This is a backward compatibility wrapper.
    For new code, use client.upload_documents() directly.
    
    Args:
        client: VectorDBClient instance
        db_type: Type of database (no longer used, kept for backward compatibility)
        documents: List of documents to upload
        batch_idx: Current batch index
        total_batches: Total number of batches
        endpoint_name: Name of the database endpoint to use (if None, uses preferred endpoint)
    """
    if not documents:
        return
    
    try:
        print(f"Uploading batch {batch_idx+1} of {total_batches} ({len(documents)} documents)")
        
        # Use the client's upload_documents method (db_type is ignored)
        uploaded_count = await client.upload_documents(documents)
            
        print(f"Successfully uploaded batch {batch_idx+1} ({uploaded_count} documents)")
    
    except Exception as e:
        print(f"Error uploading batch {batch_idx+1}: {str(e)}")
        import traceback
        traceback.print_exc()
        # Don't re-raise the exception to allow processing to continue with other batches
        print(f"Continuing with next batch...")

def resolve_file_path(file_path: str, with_embeddings: bool = False) -> str:
    """
    Resolve a file path, using config defaults for relative paths.
    
    Args:
        file_path: Original file path
        with_embeddings: Whether the file contains embeddings
        
    Returns:
        Resolved file path
    """
    # If path is absolute, return it as is
    if os.path.isabs(file_path):
        return file_path
    
    # If the file exists at the provided path, use it as is
    if os.path.exists(file_path):
        return os.path.abspath(file_path)
    
    # For relative paths, use the config
    if hasattr(CONFIG, 'nlweb'):
        if with_embeddings:
            base_folder = CONFIG.nlweb.json_with_embeddings_folder
        else:
            base_folder = CONFIG.nlweb.json_data_folder
            
        # Create the directory if it doesn't exist
        os.makedirs(base_folder, exist_ok=True)
        
        # Join the base folder with the provided file path
        # Make sure we're using the basename to avoid path duplication
        return os.path.join(base_folder, os.path.basename(file_path))
    
    # If config doesn't have nlweb settings, return the original path
    return file_path