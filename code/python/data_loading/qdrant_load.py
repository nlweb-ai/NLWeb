import os
import sys
import asyncio
from typing import List, Dict, Any
from db_create_utils import documentsFromCSVLine

# Add parent directory to path to import from code modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.config import CONFIG
from core.retriever import upload_documents as upload_documents_wrapper, get_vector_db_client

# Default collection name and embedding size
COLLECTION_NAME = "nlweb_collection"
EMBEDDING_SIZE = 1536

# Default embeddings path (can be overridden by command line argument)
DEFAULT_EMBEDDINGS_PATH = "./data/sites/embeddings/small"


async def recreate_collection(client, collection_name: str, vector_size: int):
    """Recreate a collection in the write endpoint database"""
    # Note: This is specific to Qdrant and may not work with other backends
    # For a more generic approach, consider adding a recreate_collection method to the retriever interface
    print(f"WARNING: Collection recreation is not supported through the generic interface.")
    print(f"Please use database-specific tools to recreate collections.")
    print(f"Write endpoint is configured as: {CONFIG.write_endpoint}")


def get_documents_from_csv(csv_file_path, site):
    """Reads and parses documents from a CSV-style text file"""
    documents = []
    with open(csv_file_path, "r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                try:
                    docs = documentsFromCSVLine(line, site)
                    documents.extend(docs)
                except ValueError as e:
                    print(f"Skipping row due to error: {str(e)}")
    return documents


async def upload_documents_to_database(documents: List[Dict[str, Any]], database: str = None):
    """Upload documents to the configured write endpoint or specified database"""
    # Filter out documents without embeddings
    valid_documents = [doc for doc in documents if "embedding" in doc and doc["embedding"]]
    
    if not valid_documents:
        print("No documents with embeddings to upload")
        return 0
    
    # Upload documents using the wrapper function
    if database:
        # If a specific database is provided, use it
        print(f"Using specified database: {database}")
        uploaded_count = await upload_documents_wrapper(valid_documents, endpoint_name=database)
    else:
        # Otherwise use the configured write endpoint
        if not CONFIG.write_endpoint:
            raise ValueError("No write endpoint configured and no database specified")
        print(f"Using configured write endpoint: {CONFIG.write_endpoint}")
        uploaded_count = await upload_documents_wrapper(valid_documents)
    
    print(f"Uploaded {uploaded_count} documents")
    return uploaded_count


async def upload_data_from_csv(csv_file_path: str, site: str, database: str = None):
    """Load data from CSV and upload to the database"""
    documents = get_documents_from_csv(csv_file_path, site)
    print(f"Found {len(documents)} documents for site '{site}'")
    
    if documents:
        await upload_documents_to_database(documents, database)
    
    return len(documents)


async def main():
    """Main function to load data from CSV files to the configured database"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Load data from CSV files to vector database")
    parser.add_argument("--path", default=DEFAULT_EMBEDDINGS_PATH, 
                       help="Path to directory containing embedding files")
    parser.add_argument("--database", help="Specific database endpoint to use (overrides write_endpoint)")
    parser.add_argument("--recreate", action="store_true", 
                       help="Recreate collection (WARNING: Not supported through generic interface)")
    parser.add_argument("--site", help="Specific site to load (default: use filename as site)")
    
    args = parser.parse_args()
    
    # Check if write endpoint is configured
    if not args.database and not CONFIG.write_endpoint:
        print("ERROR: No write endpoint configured and no --database specified")
        print("Please configure 'write_endpoint' in config_retrieval.yaml or specify --database")
        return
    
    # Display configuration
    print(f"Loading data from: {args.path}")
    if args.database:
        print(f"Target database: {args.database} (override)")
    else:
        print(f"Target database: {CONFIG.write_endpoint} (from config)")
    
    if args.recreate:
        client = get_vector_db_client(endpoint_name=args.database)
        await recreate_collection(client, COLLECTION_NAME, EMBEDDING_SIZE)
    
    # Process files
    embedding_path = args.path
    if not os.path.exists(embedding_path):
        print(f"ERROR: Path does not exist: {embedding_path}")
        return
    
    total_documents = 0
    csv_files = [f for f in os.listdir(embedding_path) if f.endswith(".txt")]
    
    if not csv_files:
        print(f"No .txt files found in {embedding_path}")
        return
    
    print(f"Found {len(csv_files)} files to process")
    
    for csv_file in csv_files:
        # Use filename as site name if not specified
        site = args.site or csv_file.replace(".txt", "")
        
        print(f"\nProcessing file: {csv_file} for site: {site}")
        csv_file_path = os.path.join(embedding_path, csv_file)
        
        try:
            documents_added = await upload_data_from_csv(csv_file_path, site, args.database)
            total_documents += documents_added
        except Exception as e:
            print(f"Error processing file {csv_file}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\nData processing completed. Total documents added: {total_documents}")


if __name__ == "__main__":
    asyncio.run(main())
