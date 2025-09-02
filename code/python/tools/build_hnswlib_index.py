#!/usr/bin/env python3
"""
Build HNSW index from JSONL embeddings file.

Usage:
    python -m tools.build_hnswlib_index <input_jsonl> <output_dir>

Example:
    python -m tools.build_hnswlib_index \
        /Users/rvguha/mahi/data/sites/embeddings/small/allsites.txt \
        ../data/hnswlib
"""

import json
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

try:
    import hnswlib
except ImportError:
    print("Error: hnswlib not installed. Please run: pip install hnswlib")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class HnswIndexBuilder:
    def __init__(self, max_elements: int = 1000000, M: int = 16, ef_construction: int = 200):
        """
        Initialize the HNSW index builder.
        
        Args:
            max_elements: Maximum number of elements in the index
            M: Number of bi-directional links created for each element
            ef_construction: Size of the dynamic list used during construction
        """
        self.max_elements = max_elements
        self.M = M
        self.ef_construction = ef_construction
        self.index = None
        self.metadata = {}
        self.sites = {}
        self.dimension = None
        
    def build_index(self, input_file: str, output_dir: str, index_name: str = "nlweb_hnswlib"):
        """
        Build HNSW index from JSONL file containing embeddings.
        
        Args:
            input_file: Path to JSONL file with documents and embeddings
            output_dir: Directory to save index and metadata files
            index_name: Prefix for output files
        """
        input_path = Path(input_file)
        output_path = Path(output_dir)
        
        if not input_path.exists():
            logger.error(f"Input file not found: {input_file}")
            return False
            
        # Create output directory if it doesn't exist
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Building HNSW index from: {input_file}")
        logger.info(f"Output directory: {output_dir}")
        
        # Load documents and determine embedding dimension
        documents = self._load_documents(input_path)
        if not documents:
            logger.error("No valid documents found with embeddings")
            return False
            
        logger.info(f"Loaded {len(documents)} documents with embeddings")
        logger.info(f"Embedding dimension: {self.dimension}")
        
        # Initialize HNSW index
        self.index = hnswlib.Index(space='cosine', dim=self.dimension)
        self.index.init_index(max_elements=self.max_elements, ef_construction=self.ef_construction, M=self.M)
        
        # Add embeddings to index
        logger.info("Building HNSW index...")
        self._add_to_index(documents)
        
        # Set ef parameter for searching (can be adjusted at runtime)
        self.index.set_ef(50)
        
        # Save index and metadata
        self._save_index(output_path, index_name)
        
        logger.info(f"Index building complete!")
        logger.info(f"Files created:")
        logger.info(f"  - {output_path / f'{index_name}_{self.dimension}.bin'}")
        logger.info(f"  - {output_path / f'{index_name}_metadata.json'}")
        logger.info(f"  - {output_path / f'{index_name}_sites.json'}")
        
        return True
    
    def _load_documents(self, input_path: Path) -> List[Dict[str, Any]]:
        """
        Load documents from JSONL file and extract embeddings.
        
        Args:
            input_path: Path to input JSONL file
            
        Returns:
            List of documents with embeddings
        """
        documents = []
        line_count = 0
        no_embedding_count = 0
        
        with open(input_path, 'r') as f:
            for line in f:
                line_count += 1
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    doc = json.loads(line)
                    
                    # Check if document has embedding
                    if "embedding" not in doc or not doc["embedding"]:
                        no_embedding_count += 1
                        continue
                    
                    # Determine dimension from first valid embedding
                    if self.dimension is None:
                        self.dimension = len(doc["embedding"])
                        logger.info(f"Detected embedding dimension: {self.dimension}")
                    
                    # Verify consistent dimensions
                    if len(doc["embedding"]) != self.dimension:
                        logger.warning(f"Line {line_count}: Embedding dimension mismatch "
                                     f"(expected {self.dimension}, got {len(doc['embedding'])})")
                        continue
                    
                    documents.append(doc)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_count}: Invalid JSON - {e}")
                    continue
        
        if no_embedding_count > 0:
            logger.warning(f"Skipped {no_embedding_count} documents without embeddings")
        
        return documents
    
    def _add_to_index(self, documents: List[Dict[str, Any]]):
        """
        Add documents to HNSW index and build metadata mappings.
        
        Args:
            documents: List of documents with embeddings
        """
        # Process documents in batches for efficiency
        batch_size = 1000
        total_added = 0
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]
            embeddings = []
            ids = []
            
            for doc_idx, doc in enumerate(batch):
                global_idx = i + doc_idx
                
                # Use global index as ID
                doc_id = global_idx
                ids.append(doc_id)
                embeddings.append(doc["embedding"])
                
                # Store metadata
                self.metadata[doc_id] = {
                    "url": doc.get("url", ""),
                    "name": doc.get("name", ""),
                    "site": doc.get("site", ""),
                    "schema_json": doc.get("schema_json", "")
                }
                
                # Build site index
                site = doc.get("site", "")
                if site:
                    if site not in self.sites:
                        self.sites[site] = []
                    self.sites[site].append(doc_id)
            
            # Add batch to index
            self.index.add_items(embeddings, ids)
            total_added += len(batch)
            
            if total_added % 10000 == 0:
                logger.info(f"Added {total_added}/{len(documents)} documents to index")
        
        logger.info(f"Added all {len(documents)} documents to index")
        logger.info(f"Index contains {len(self.sites)} unique sites")
    
    def _save_index(self, output_path: Path, index_name: str):
        """
        Save HNSW index and metadata to disk.
        
        Args:
            output_path: Directory to save files
            index_name: Prefix for file names
        """
        # Save HNSW index
        index_file = output_path / f"{index_name}_{self.dimension}.bin"
        self.index.save_index(str(index_file))
        logger.info(f"Saved HNSW index to {index_file}")
        
        # Save metadata
        metadata_file = output_path / f"{index_name}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f)
        logger.info(f"Saved metadata for {len(self.metadata)} documents")
        
        # Save site index
        sites_file = output_path / f"{index_name}_sites.json"
        with open(sites_file, 'w') as f:
            json.dump(self.sites, f)
        logger.info(f"Saved site index for {len(self.sites)} sites")


def main():
    parser = argparse.ArgumentParser(description='Build HNSW index from JSONL embeddings file')
    parser.add_argument('input_file', help='Input JSONL file with embeddings')
    parser.add_argument('output_dir', help='Output directory for index and metadata')
    parser.add_argument('--index-name', default='nlweb_hnswlib', 
                       help='Prefix for output files (default: nlweb_hnswlib)')
    parser.add_argument('--max-elements', type=int, default=1000000,
                       help='Maximum number of elements in index (default: 1000000)')
    parser.add_argument('--M', type=int, default=16,
                       help='Number of bi-directional links per element (default: 16)')
    parser.add_argument('--ef-construction', type=int, default=200,
                       help='Size of dynamic list for construction (default: 200)')
    
    args = parser.parse_args()
    
    builder = HnswIndexBuilder(
        max_elements=args.max_elements,
        M=args.M,
        ef_construction=args.ef_construction
    )
    
    success = builder.build_index(
        args.input_file,
        args.output_dir,
        args.index_name
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()