#!/usr/bin/env python3
"""
Compute embeddings for store descriptions using text-embedding-3-large model.
Reads JSONL file with store descriptions and adds embeddings to each record.
"""

import json
import sys
import os
import argparse
import logging
import asyncio
from typing import List, Dict, Any
from pathlib import Path

# Add parent directory to path to import from core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.embedding import get_embedding

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class EmbeddingProcessor:
    def __init__(self, embedding_size: str = "small"):
        """Initialize the embedding processor.
        
        Args:
            embedding_size: Size of embedding model to use ("small" or "large")
        """
        self.embedding_size = embedding_size.lower()
        if self.embedding_size not in ["small", "large"]:
            raise ValueError("embedding_size must be 'small' or 'large'")
        
        # Set model based on size
        self.model = f"text-embedding-3-{self.embedding_size}"
        logger.info(f"Using embedding model: {self.model}")
    
    async def get_embedding_async(self, text: str) -> List[float]:
        """
        Get embedding for a text using the embedding API.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            # Use the get_embedding function from core/embedding.py
            # Using azure_openai provider with selected model size
            embedding = await get_embedding(
                text=text,
                provider="azure_openai",  # Use Azure OpenAI
                model=self.model,
                timeout=60  # Increase timeout for Azure
            )
            
            if embedding and isinstance(embedding, list):
                return embedding
            else:
                logger.error(f"Invalid embedding response: {embedding}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return []
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Synchronous wrapper for get_embedding_async.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        return asyncio.run(self.get_embedding_async(text))
    
    def create_embedding_text(self, store_data: Dict[str, Any]) -> str:
        """
        Create text to embed from store data.
        Combines relevant fields for comprehensive embedding.
        
        Args:
            store_data: Dictionary containing store information
            
        Returns:
            Combined text for embedding
        """
        parts = []
        
        # Add store name
        if "name" in store_data:
            parts.append(f"Store: {store_data['name']}")
        
        # Add URL/domain
        if "url" in store_data:
            parts.append(f"Domain: {store_data['url']}")
        
        # Add category
        if "category" in store_data:
            parts.append(f"Category: {store_data['category']}")
        
        # Add description
        if "description" in store_data:
            parts.append(f"Description: {store_data['description']}")
        
        # Add detailed description if available
        if "detailed_description" in store_data and store_data["detailed_description"] != "Description generation failed after all retries":
            parts.append(f"Products: {store_data['detailed_description']}")
        
        # Add sitemap analysis if available
        if "sitemap_analysis" in store_data and store_data["sitemap_analysis"] != "Analysis unavailable":
            parts.append(f"Analysis: {store_data['sitemap_analysis']}")
        
        # Add store type
        if "@type" in store_data:
            parts.append(f"Platform: {store_data['@type']}")
        
        return "\n".join(parts)
    
    def process_file(self, input_file: str, output_file: str, skip_existing: bool = True):
        """
        Process JSONL file and add embeddings to each record.
        Creates output in db_load.py compatible format.
        
        Args:
            input_file: Path to input JSONL file
            output_file: Path to output JSONL file with embeddings
            skip_existing: Skip records that already have embeddings
        """
        input_path = Path(input_file)
        output_path = Path(output_file)
        
        if not input_path.exists():
            logger.error(f"Input file not found: {input_file}")
            return
        
        # Read existing output if resuming
        processed_urls = set()
        existing_records = []
        
        if output_path.exists() and skip_existing:
            logger.info(f"Reading existing output file: {output_file}")
            with open(output_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            if "url" in record:
                                processed_urls.add(record["url"])
                                existing_records.append(record)
                        except json.JSONDecodeError:
                            continue
            logger.info(f"Found {len(processed_urls)} already processed records")
        
        # Process input file
        stores_to_process = []
        total_stores = 0
        
        with open(input_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        store_data = json.loads(line)
                        total_stores += 1
                        
                        # Skip if already processed
                        if skip_existing and store_data.get("url") in processed_urls:
                            continue
                        
                        stores_to_process.append(store_data)
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse line: {line[:100]}...")
                        continue
        
        logger.info(f"Loaded {total_stores} stores from {input_file}")
        logger.info(f"Processing {len(stores_to_process)} new stores")
        
        # Open output file in append mode if resuming, write mode otherwise
        mode = 'a' if (output_path.exists() and skip_existing) else 'w'
        
        # If writing fresh, first write existing records
        if mode == 'w' and existing_records:
            with open(output_path, 'w') as f:
                for record in existing_records:
                    f.write(json.dumps(record) + '\n')
            mode = 'a'
        
        # Process each store
        with open(output_path, mode) as out_f:
            for i, store_data in enumerate(stores_to_process, 1):
                store_name = store_data.get("name", "Unknown")
                store_url = store_data.get("url", "Unknown")
                
                logger.info(f"\n[{i}/{len(stores_to_process)}] Processing: {store_name} ({store_url})")
                
                # Check if embedding already exists
                if "embedding" in store_data and store_data["embedding"]:
                    logger.info("  - Embedding already exists, skipping")
                    # Write in db_load.py format
                    document = self.create_document(store_data)
                    out_f.write(json.dumps(document) + '\n')
                    out_f.flush()
                    continue
                
                # Create text for embedding (use the full store data as JSON)
                embedding_text = json.dumps(store_data, separators=(',', ':'))
                logger.info(f"  - Created embedding text ({len(embedding_text)} chars)")
                
                # Get embedding
                logger.info("  - Computing embedding...")
                embedding = self.get_embedding(embedding_text)
                
                if embedding:
                    # Add model info to store_data for document creation
                    store_data["embedding_model"] = self.model
                    store_data["embedding_provider"] = "azure_openai"
                    
                    # Create document in db_load.py compatible format
                    document = self.create_document(store_data, embedding)
                    
                    logger.info(f"  - Embedding computed: {len(embedding)} dimensions")
                    
                    # Write immediately only if embedding was successful
                    out_f.write(json.dumps(document) + '\n')
                    out_f.flush()
                    logger.info(f"  - Saved to {output_file}")
                else:
                    logger.warning("  - Failed to compute embedding, skipping this record")
        
        logger.info(f"\nProcessing complete! Results saved to {output_file}")
    
    def create_document(self, store_data: Dict[str, Any], embedding: List[float] = None) -> Dict[str, Any]:
        """
        Create a document in db_load.py compatible format.
        
        Args:
            store_data: Original store data
            embedding: Computed embedding vector (optional)
            
        Returns:
            Document dictionary with id, schema_json, url, name, site, and embedding
        """
        # Extract URL and name
        url = store_data.get("url", "")
        name = store_data.get("name", "")
        
        # Extract site from URL (domain without subdomain)
        site = url
        if url:
            # Remove protocol if present
            if "://" in url:
                site = url.split("://")[1]
            # Get just the domain
            site = site.split("/")[0]
            # Remove www. if present
            if site.startswith("www."):
                site = site[4:]
        
        # Create document matching db_load.py format
        document = {
            "id": str(hash(url) % (2**63)),  # Create a stable ID from the URL
            "schema_json": json.dumps(store_data, separators=(',', ':')),  # Store full data as JSON string
            "url": url,
            "name": name,
            "site": site
        }
        
        # Add embedding if provided
        if embedding:
            document["embedding"] = embedding
        elif "embedding" in store_data:
            # Use existing embedding if present
            document["embedding"] = store_data["embedding"]
        
        return document

def main():
    parser = argparse.ArgumentParser(description='Compute embeddings for store descriptions')
    parser.add_argument('input_file', help='Input JSONL file with store descriptions')
    parser.add_argument('output_file', help='Output JSONL file with embeddings added')
    parser.add_argument('--size', choices=['small', 'large'], default='small',
                       help='Embedding model size (small or large, default: small)')
    parser.add_argument('--reprocess', action='store_true', 
                       help='Reprocess all records, even if they already have embeddings')
    
    args = parser.parse_args()
    
    processor = EmbeddingProcessor(embedding_size=args.size)
    processor.process_file(
        args.input_file, 
        args.output_file,
        skip_existing=not args.reprocess
    )

if __name__ == "__main__":
    main()