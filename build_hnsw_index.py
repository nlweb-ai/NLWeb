#!/usr/bin/env python3
"""Build HNSW index from computed embeddings"""

import json
import numpy as np
import hnswlib
from pathlib import Path

def build_hnsw_index():
    """Build HNSW index from embeddings file"""
    
    # Paths
    embeddings_file = Path.home() / "mahi/data/sites/embeddings/large/allsites.txt"
    index_file = Path.home() / "mahi/data/sites/embeddings/large/allsites_hnsw.index"
    
    print(f"Reading embeddings from {embeddings_file}")
    
    # Load embeddings
    embeddings = []
    ids = []
    domains = []
    
    with open(embeddings_file, 'r') as f:
        for i, line in enumerate(f):
            data = json.loads(line)
            embeddings.append(data['embedding'])
            ids.append(i)
            domains.append(data.get('domain', f'site_{i}'))
    
    print(f"Loaded {len(embeddings)} embeddings")
    
    # Convert to numpy array
    embeddings_array = np.array(embeddings, dtype='float32')
    dim = embeddings_array.shape[1]
    print(f"Embedding dimension: {dim}")
    
    # Create HNSW index
    print("Building HNSW index...")
    index = hnswlib.Index(space='cosine', dim=dim)
    
    # Initialize index with parameters
    # M = 16, ef_construction = 200 are reasonable defaults
    index.init_index(max_elements=len(embeddings), ef_construction=200, M=16)
    
    # Add items to index
    print("Adding embeddings to index...")
    index.add_items(embeddings_array, ids)
    
    # Set ef for querying (higher = more accurate but slower)
    index.set_ef(50)
    
    # Save index
    print(f"Saving index to {index_file}")
    index.save_index(str(index_file))
    
    # Save metadata (domains) separately
    metadata_file = index_file.with_suffix('.metadata.json')
    print(f"Saving metadata to {metadata_file}")
    with open(metadata_file, 'w') as f:
        json.dump({'domains': domains, 'dim': dim, 'count': len(embeddings)}, f, indent=2)
    
    print(f"Successfully built HNSW index with {len(embeddings)} vectors")
    
    # Test the index
    print("\nTesting index with a random query...")
    test_query = embeddings_array[0:1]  # Use first embedding as test
    labels, distances = index.knn_query(test_query, k=5)
    print(f"Found {len(labels[0])} nearest neighbors")
    print(f"Nearest neighbor indices: {labels[0]}")
    print(f"Distances: {distances[0]}")

if __name__ == "__main__":
    build_hnsw_index()