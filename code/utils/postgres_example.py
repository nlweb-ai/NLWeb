#!/usr/bin/env python3
# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Example script to test the PostgreSQL vector database integration
This script demonstrates how to initialize and use the PgVectorClient
"""

import json
import os
import asyncio
import sys
from pprint import pprint

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the required modules from the project
from config.config import CONFIG
from retrieval.postgres import PgVectorClient
from utils.logging_config_helper import get_configured_logger

# Set up logging
logger = get_configured_logger("postgres_example")

async def main():
    """Main function to test the PostgreSQL vector database integration"""
    print("\n=== PostgreSQL Vector Database Example ===\n")
    
    # Print configuration information
    print("Current configuration:")
    print(f"  Preferred endpoint: {CONFIG.preferred_retrieval_endpoint}")
    
    # Initialize the PostgreSQL client
    try:
        print("\nInitializing PgVector client...")
        client = PgVectorClient("postgres")
        
        # Test the connection
        print("Testing connection...")
        connection_info = await client.test_connection()
        
        print("\nConnection test results:")
        print(f"  Success: {connection_info.get('success', False)}")
        
        if connection_info.get("error"):
            print(f"  Error: {connection_info['error']}")
            return
            
        print(f"  PostgreSQL version: {connection_info.get('database_version')}")
        print(f"  pgvector installed: {connection_info.get('pgvector_installed')}")
        print(f"  Table exists: {connection_info.get('table_exists')}")
        print(f"  Document count: {connection_info.get('document_count')}")
        
        # Only continue if the connection was successful and the table exists
        if connection_info.get("success") and connection_info.get("table_exists"):
            
            # Example: Search for documents
            print("\nPerforming a test search query...")
            query = "How does Azure Postgres Flexible Server work?"
            results = await client.search(query, site=None, num_results=1)
            
            print(f"\nQuery: {query}")
            print(f"Found {len(results)} results")
            
            for i, result in enumerate(results):
                print(f"\nResult {i+1}:")
                print(f"  Text: {result[0][:100]}...")
                print(f"  URL: {result[1]}")
                print(f"  Context: {result[2][:50]}..." if result[2] else "  No context")
                
            # Example: Search by URL
            if results and results[0][1]:
                url = json.loads(results[0][1])["url"] # Get URL from the first result
                print(f"\nSearching for document with URL: {url}")
                doc = await client.search_by_url(url)
                
                if doc:
                    print("Document found!")
                    print(f"  Text: {doc[0][:100]}...")
                else:
                    print("Document not found")
                    
            # Close the connection pool when done
            print("\nClosing connection pool...")
            await client.close()
    
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
