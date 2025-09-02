#!/usr/bin/env python3
"""Create HNSW metadata file in the correct format"""

import json
from pathlib import Path

def create_metadata():
    """Create metadata.json file mapping integer IDs to document metadata"""
    
    embeddings_file = Path.home() / "mahi/data/sites/embeddings/large/allsites.txt"
    output_file = Path("code/python/data/hnswlib/nlweb_hnswlib_metadata.json")
    
    print(f"Reading embeddings from {embeddings_file}")
    
    metadata = {}
    
    with open(embeddings_file, 'r') as f:
        for i, line in enumerate(f):
            data = json.loads(line)
            # Store metadata for each document ID
            metadata[str(i)] = {
                'id': data.get('id', ''),
                'name': data.get('name', ''),
                'site': data.get('site', ''),
                'url': data.get('url', ''),
                'domain': data.get('domain', data.get('site', '')),
                'schema_json': data.get('schema_json', {})
            }
    
    print(f"Created metadata for {len(metadata)} documents")
    
    # Save metadata
    print(f"Saving metadata to {output_file}")
    with open(output_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("Successfully created metadata file")

if __name__ == "__main__":
    create_metadata()