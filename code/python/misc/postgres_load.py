#!/usr/bin/env python3
# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Script to verify and create PostgreSQL schema for pgvector if it doesn't exist
"""

import os
import sys
import asyncio
import argparse

# More robust path handling for imports
script_path = os.path.abspath(__file__)
misc_dir = os.path.dirname(script_path)
python_dir = os.path.dirname(misc_dir)

# Add both directories to path
sys.path.insert(0, python_dir)  # Add code dir first
sys.path.insert(1, misc_dir)  # Then utils dir

#pip install dependencies
def init():
    """Initialize the script by installing required packages"""
    import subprocess
    import sys

    # Install required packages for PostgreSQL
    for package in _db_type_packages.get("postgres", []):
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
_db_type_packages = {
    "postgres": ["psycopg", "psycopg[binary]>=3.1.12", "psycopg[pool]>=3.2.0", "pgvector>=0.4.0"],
}
init()

# Import the required modules from the project
try:
    from retrieval_providers.postgres_client import PgVectorClient
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print(f"Make sure you're running this script from the python directory: {python_dir}")
    sys.exit(1)

# SQL for creating the table and indexes
CREATE_TABLE_SQL = """
-- Create the pgvector extension if it doesn't exist
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the documents table for vector embeddings
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,              -- Document ID (URL or other unique identifier)
    url TEXT NOT NULL,               -- URL of the document
    name TEXT NOT NULL,              -- Name of the document (title or similar)
    schema_json JSONB NOT NULL,      -- JSON schema of the document
    site TEXT NOT NULL,              -- Site or domain of the document
    embedding vector(1536) NOT NULL  -- Vector embedding (adjust dimension to match your model)
);

-- Create a vector index for faster similarity searches
CREATE INDEX IF NOT EXISTS embedding_cosine_idx 
ON documents USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 200);
"""

async def setup_postgres_schema(args):
    """Set up the PostgreSQL schema for vector search"""
    print("\n=== PostgreSQL Schema Setup ===\n")
    
    client = PgVectorClient(args.endpoint)
    
    # First test the connection
    print("Testing PostgreSQL connection...")
    try:
        connection_info = await client.test_connection()
        
        if not connection_info.get("success"):
            print(f"ERROR: Could not connect to PostgreSQL: {connection_info.get('error')}")
            return False
    except Exception as e:
        print(f"ERROR: Could not connect to PostgreSQL: {e}")
        return False
    
    print(f"Successfully connected to PostgreSQL {connection_info.get('database_version')}")
    
    # Check if pgvector is installed
    if not connection_info.get("pgvector_installed"):
        print("WARNING: pgvector extension is not installed in the database")
        print("Please install the pgvector extension before continuing")
        return False
    
    # Check if table exists and has correct schema
    print(f"\nChecking schema for table '{client.table_name}'...")
    schema_info = await client.check_table_schema()
    
    if schema_info.get("error"):
        print(f"ERROR checking table schema: {schema_info.get('error')}")
        return False
    
    if not schema_info.get("table_exists"):
        print(f"Table '{client.table_name}' does not exist. Creating it...")
        
        # Create the table and indexes
        async def _create_schema(conn):
            async with conn.cursor() as cur:
                await cur.execute(CREATE_TABLE_SQL)
                await conn.commit()
                return True
        
        try:
            await client._execute_with_retry(_create_schema)
            print(f"Successfully created table '{client.table_name}' and indexes")
        except Exception as e:
            print(f"ERROR creating schema: {e}")
            await client.close()  # Make sure to close the connection on error
            return False
    else:
        print(f"Table '{client.table_name}' already exists")
        
        # Check for any schema issues
        if schema_info.get("needs_corrections"):
            print("\nThe following schema issues were detected:")
            for issue in schema_info.get("needs_corrections"):
                print(f"  - {issue}")
            
            if args.fix:
                print("\nAttempting to fix schema issues...")
                # Implement schema fixes here if --fix is provided
                print("Schema fixes not implemented yet - please fix manually")
            else:
                print("\nRun this script with --fix to attempt to fix these issues")
    
    # Show schema information
    print("\nCurrent schema:")
    print(f"  Table: {client.table_name}")
    print(f"  Primary key: {schema_info.get('primary_key')}")
    print(f"  Vector column: {schema_info.get('vector_column', 'None')} {schema_info.get('vector_dimension', '')}")
    print(f"  Vector indexes: {len(schema_info.get('vector_indexes', []))}")
    
    # Close the connection pool when done
    print("\nClosing connection pool...")
    await client.close()
    
    print("\nSetup complete!")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PostgreSQL pgvector Schema Setup")
    parser.add_argument("--endpoint", default="postgres", help="Name of the PostgreSQL endpoint to use")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix schema issues if any are found")
    args = parser.parse_args()
    
    async def main():
        try:
            return await setup_postgres_schema(args)
        except Exception as e:
            print(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    asyncio.run(main())
