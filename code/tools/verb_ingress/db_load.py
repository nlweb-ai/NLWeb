#!/usr/bin/env python3
# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Main entry point for the NLWeb ingress system.

This provides the same interface as the original db_load.py but uses the new
modular Strategy + Factory Pattern-based ingress system for supported data types
(OpenAPI JSON, Java Interface) while falling back to the original system for
other types (JSON, CSV, RSS, etc.).
"""

from tools.verb_ingress.factory import auto_select_strategy, get_available_strategies
from retrieval.retriever import get_vector_db_client
from embedding.embedding import batch_get_embeddings
from config.config import CONFIG
import asyncio
import argparse
import sys
import os
from typing import Optional

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))


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
    endpoint_name = database or CONFIG.preferred_retrieval_endpoint

    # Ensure the endpoint exists in configuration
    if endpoint_name not in CONFIG.retrieval_endpoints:
        raise ValueError(
            f"Database endpoint '{endpoint_name}' not found in configuration")

    # Get a client for the specified endpoint
    client = get_vector_db_client(endpoint_name)

    print(
        f"Deleting entries for site '{site}' from {client.db_type} using endpoint '{endpoint_name}'...")

    # Use the client's delete_documents_by_site method
    deleted_count = await client.delete_documents_by_site(site)

    print(f"Deleted {deleted_count} documents for site '{site}'")
    return deleted_count


async def process_with_ingress_system(file_path: str, site: str, batch_size: int = 100,
                                      delete_existing: bool = False, database: str = None) -> int:
    """
    Process a file using the new ingress system (Strategy + Factory Pattern).

    Args:
        file_path: Path to the file to process
        site: Site identifier
        batch_size: Number of documents to process per batch
        delete_existing: Whether to delete existing site data first
        database: Database endpoint to use

    Returns:
        Number of documents processed, or -1 if file type not supported by ingress system
    """
    # Try to auto-select strategy from the ingress system
    strategy = auto_select_strategy(file_path=file_path)

    if not strategy:
        # File type not supported by ingress system, return -1 to indicate fallback needed
        return -1

    print(f"Using ingress strategy: {strategy.get_strategy_name()}")

    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return 0

    # Load file data
    try:
        # Special handling for different file types
        if file_path.lower().endswith('.java'):
            from tools.verb_ingress.java_strategy import JavaStrategy
            data = JavaStrategy.load_from_file(file_path)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {str(e)}")
        return 0

    # Process data
    print(f"Processing {file_path} for site '{site}'...")
    documents, texts = strategy.process_data(data, file_path, site)

    if not documents:
        print("No documents generated from the input data")
        return 0

    print(f"Generated {len(documents)} documents")

    # Setup database connection
    endpoint_name = database or CONFIG.preferred_retrieval_endpoint

    if endpoint_name not in CONFIG.retrieval_endpoints:
        print(
            f"Error: Database endpoint '{endpoint_name}' not found in configuration")
        return 0

    client = get_vector_db_client(endpoint_name)

    # Delete existing data if requested
    if delete_existing:
        print(f"Deleting existing data for site '{site}'...")
        deleted_count = await client.delete_documents_by_site(site)
        print(f"Deleted {deleted_count} existing documents")

    # Get embedding provider configuration
    provider = CONFIG.preferred_embedding_provider
    provider_config = CONFIG.get_embedding_provider(provider)
    model = provider_config.model if provider_config else None

    print(f"Using embedding provider: {provider}, model: {model}")

    # Process in batches
    total_processed = 0

    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i+batch_size]
        batch_texts = texts[i:i+batch_size]

        if not batch_docs:
            continue

        try:
            batch_idx = i // batch_size + 1
            total_batches = (len(documents) + batch_size - 1) // batch_size

            print(
                f"Processing batch {batch_idx}/{total_batches} ({len(batch_docs)} documents)...")

            # Generate embeddings
            embeddings = await batch_get_embeddings(batch_texts, provider, model)

            # Add embeddings to documents
            docs_with_embeddings = []
            for doc, embedding in zip(batch_docs, embeddings):
                doc_copy = doc.copy()
                doc_copy["embedding"] = embedding
                docs_with_embeddings.append(doc_copy)

            # Upload to database
            print(f"Uploading batch {batch_idx}/{total_batches}...")
            uploaded_count = await client.upload_documents(docs_with_embeddings)

            print(
                f"Successfully uploaded batch {batch_idx} ({uploaded_count} documents)")
            total_processed += uploaded_count

        except Exception as e:
            print(f"Error processing batch {batch_idx}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Continue with next batch

    print(f"Completed processing. Total documents uploaded: {total_processed}")
    return total_processed


async def process_url_with_ingress_system(url: str, site: str, batch_size: int = 100,
                                          delete_existing: bool = False, database: str = None) -> int:
    """
    Process data from a URL using the ingress system (currently supports OpenAPI URLs).

    Args:
        url: URL to fetch data from
        site: Site identifier
        batch_size: Number of documents to process per batch
        delete_existing: Whether to delete existing site data first
        database: Database endpoint to use

    Returns:
        Number of documents processed, or -1 if URL type not supported by ingress system
    """
    # For now, only OpenAPI strategy supports URL fetching
    try:
        from tools.verb_ingress.openapi_strategy import OpenAPIStrategy

        strategy = OpenAPIStrategy()

        # Fetch data from URL
        print(f"Fetching data from {url}...")
        data = await OpenAPIStrategy.fetch_from_url(url)

        # Validate that the strategy can handle this data
        if not strategy.validate_input(data):
            print(f"URL data not supported by ingress system: {url}")
            return -1

        # Process the rest like a file
        print(f"Processing OpenAPI data for site '{site}'...")
        documents, texts = strategy.process_data(data, url, site)

        if not documents:
            print("No documents generated from the URL data")
            return 0

        print(f"Generated {len(documents)} documents")

        # Setup database connection
        endpoint_name = database or CONFIG.preferred_retrieval_endpoint

        if endpoint_name not in CONFIG.retrieval_endpoints:
            print(
                f"Error: Database endpoint '{endpoint_name}' not found in configuration")
            return 0

        client = get_vector_db_client(endpoint_name)

        # Delete existing data if requested
        if delete_existing:
            print(f"Deleting existing data for site '{site}'...")
            deleted_count = await client.delete_documents_by_site(site)
            print(f"Deleted {deleted_count} existing documents")

        # Get embedding provider configuration
        provider = CONFIG.preferred_embedding_provider
        provider_config = CONFIG.get_embedding_provider(provider)
        model = provider_config.model if provider_config else None

        print(f"Using embedding provider: {provider}, model: {model}")

        # Process in batches (similar to file processing)
        total_processed = 0

        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i+batch_size]
            batch_texts = texts[i:i+batch_size]

            if not batch_docs:
                continue

            try:
                batch_idx = i // batch_size + 1
                total_batches = (len(documents) + batch_size - 1) // batch_size

                print(
                    f"Processing batch {batch_idx}/{total_batches} ({len(batch_docs)} documents)...")

                # Generate embeddings
                embeddings = await batch_get_embeddings(batch_texts, provider, model)

                # Add embeddings to documents
                docs_with_embeddings = []
                for doc, embedding in zip(batch_docs, embeddings):
                    doc_copy = doc.copy()
                    doc_copy["embedding"] = embedding
                    docs_with_embeddings.append(doc_copy)

                # Upload to database
                print(f"Uploading batch {batch_idx}/{total_batches}...")
                uploaded_count = await client.upload_documents(docs_with_embeddings)

                print(
                    f"Successfully uploaded batch {batch_idx} ({uploaded_count} documents)")
                total_processed += uploaded_count

            except Exception as e:
                print(f"Error processing batch {batch_idx}: {str(e)}")
                import traceback
                traceback.print_exc()
                # Continue with next batch

        print(
            f"Completed processing. Total documents uploaded: {total_processed}")
        return total_processed

    except Exception as e:
        print(f"Error processing URL {url} with ingress system: {str(e)}")
        return -1


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
        from urllib.parse import urlparse
        result = urlparse(path)
        # A URL must have both a scheme (http, https) and a network location (domain)
        valid_scheme = result.scheme in ['http', 'https', 'ftp', 'ftps']
        has_netloc = bool(result.netloc)

        # Additional check: local file paths may be parsed as URLs on some systems
        # Make sure it's not a Windows drive letter (like C:\)
        not_windows_path = not (
            len(result.scheme) == 1 and result.scheme.isalpha() and path[1:3] == ':\\')

        # Make sure it's not a relative file path
        not_relative_path = not os.path.exists(path)

        return valid_scheme and has_netloc and not_windows_path and not_relative_path
    except Exception:
        return False


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
    Main function for command-line use with the same interface as original db_load.py.

    Example usage:
        python db_load.py file.txt site_name
        python db_load.py https://api.github.com/openapi.json github-api
        python db_load.py MyInterface.java java-api
        python db_load.py --delete-site site_name
        python db_load.py file.txt site_name --database qdrant_local
        python db_load.py --force-recompute file.txt site_name
    """
    parser = argparse.ArgumentParser(
        description="Load data into vector database using new ingress system for supported types, falling back to original system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process OpenAPI JSON (ingress system)
  python db_load.py https://api.github.com/openapi.json github-api
  
  # Process Java interface (ingress system)  
  python db_load.py MyInterface.java java-api
  
  # Process other types (falls back to original system)
  python db_load.py data.csv my-site
  python db_load.py feed.rss my-site
  
  # Delete site data
  python db_load.py --delete-site my-site
  
  # Force recompute embeddings
  python db_load.py --force-recompute file.json my-site
        """
    )

    parser.add_argument("--delete-site", action="store_true",
                        help="Delete existing entries for the site before loading")
    parser.add_argument("--only-delete", action="store_true",
                        help="Only delete entries for the site, don't load data")
    parser.add_argument("--force-recompute", action="store_true",
                        help="Force recomputation of embeddings (falls back to original system)")
    parser.add_argument("--url-list", action="store_true",
                        help="Treat input as URL list (falls back to original system)")
    parser.add_argument("file_path", nargs="?",
                        help="Path to the input file or URL")
    parser.add_argument("site", help="Site identifier")
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Batch size for processing and uploading")
    parser.add_argument("--database", type=str, default=None,
                        help="Specific database endpoint to use (from config_retrieval.yaml)")

    args = parser.parse_args()

    # Validate database if specified
    if args.database and args.database not in CONFIG.retrieval_endpoints:
        parser.error(
            f"Database endpoint '{args.database}' not found in configuration. Available options: {', '.join(CONFIG.retrieval_endpoints.keys())}")

    # Handle delete-only mode
    if args.only_delete:
        await delete_site(args.site, args.database)
        return

    # Validate file path if we're not just deleting
    if args.file_path is None and not args.only_delete:
        parser.error("file_path is required unless --only-delete is specified")

    # Handle special modes that require fallback to original system
    if args.url_list or args.force_recompute:
        print("URL list or force recompute mode - falling back to original db_load.py system...")
        # Import and delegate to original system
        try:
            from tools import db_load
            # Reconstruct sys.argv for the original system
            sys.argv = ['db_load.py']
            if args.delete_site:
                sys.argv.append('--delete-site')
            if args.only_delete:
                sys.argv.append('--only-delete')
            if args.force_recompute:
                sys.argv.append('--force-recompute')
            if args.url_list:
                sys.argv.append('--url-list')
            if args.file_path:
                sys.argv.append(args.file_path)
            sys.argv.append(args.site)
            if args.batch_size != 100:
                sys.argv.extend(['--batch-size', str(args.batch_size)])
            if args.database:
                sys.argv.extend(['--database', args.database])

            await db_load.main()
            return
        except ImportError:
            print("Error: Original db_load.py system not available")
            return

    # Check if it's a URL
    is_url_input = await is_url(args.file_path)

    if is_url_input:
        # Try URL processing with ingress system first
        print(f"Processing URL: {args.file_path}")
        result = await process_url_with_ingress_system(
            args.file_path, args.site, args.batch_size, args.delete_site, args.database
        )

        if result == -1:
            # URL not supported by ingress system, fall back to original system
            print(
                "URL type not supported by ingress system - falling back to original db_load.py system...")
            try:
                from tools import db_load
                # Reconstruct sys.argv for the original system
                sys.argv = ['db_load.py']
                if args.delete_site:
                    sys.argv.append('--delete-site')
                sys.argv.append(args.file_path)
                sys.argv.append(args.site)
                if args.batch_size != 100:
                    sys.argv.extend(['--batch-size', str(args.batch_size)])
                if args.database:
                    sys.argv.extend(['--database', args.database])

                await db_load.main()
            except ImportError:
                print("Error: Original db_load.py system not available")
    else:
        # File processing
        if not os.path.exists(args.file_path):
            print(f"Error: File not found: {args.file_path}")
            return

        # Try processing with ingress system first
        print(f"Processing file: {args.file_path}")
        result = await process_with_ingress_system(
            args.file_path, args.site, args.batch_size, args.delete_site, args.database
        )

        if result == -1:
            # File type not supported by ingress system, fall back to original system
            print(
                "File type not supported by ingress system - falling back to original db_load.py system...")
            try:
                from tools import db_load
                # Reconstruct sys.argv for the original system
                sys.argv = ['db_load.py']
                if args.delete_site:
                    sys.argv.append('--delete-site')
                sys.argv.append(args.file_path)
                sys.argv.append(args.site)
                if args.batch_size != 100:
                    sys.argv.extend(['--batch-size', str(args.batch_size)])
                if args.database:
                    sys.argv.extend(['--database', args.database])

                await db_load.main()
            except ImportError:
                print("Error: Original db_load.py system not available")


if __name__ == "__main__":
    asyncio.run(main())
