#!/usr/bin/env python3
# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Test script for PostgreSQL connection with the PgVectorClient
This script helps debug connection and configuration issues
"""

import os
import sys
import asyncio
import yaml
from pprint import pprint

# More robust path handling for imports
script_path = os.path.abspath(__file__)
utils_dir = os.path.dirname(script_path)
code_dir = os.path.dirname(utils_dir)

# Add both directories to path
sys.path.insert(0, code_dir)  # Add code dir first
sys.path.insert(1, utils_dir)  # Then utils dir

# Import the required modules from the project
try:
    from retrieval.postgres import PgVectorClient
    from config.config import CONFIG
    
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print(f"Make sure you're running this script from the code directory: {code_dir}")
    sys.exit(1)

async def test_postgres_connection():
    """Test the PostgreSQL connection using PgVectorClient"""
    print("\n=== PostgreSQL Connection Test ===\n")
    
    # Print configuration information
    print("Retrieval configuration:")
    print(f"  Preferred endpoint: {CONFIG.preferred_retrieval_endpoint}")
    
    # Check if the postgres endpoint exists in the configuration
    postgres_endpoint = "postgres" 
    if postgres_endpoint not in CONFIG.retrieval_endpoints:
        print(f"\nError: '{postgres_endpoint}' endpoint not found in CONFIG.retrieval_endpoints")
        print("Available endpoints:", list(CONFIG.retrieval_endpoints.keys()))
        return
    
    # Get the raw configuration from the YAML file for debugging
    try:
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        config_file = os.path.join(config_dir, "config_retrieval.yaml")
        
        print(f"\nReading raw configuration from: {config_file}")
        with open(config_file, "r") as f:
            raw_config = yaml.safe_load(f)
            
        if "endpoints" in raw_config and postgres_endpoint in raw_config["endpoints"]:
            postgres_config = raw_config["endpoints"][postgres_endpoint]
            print("\nPostgreSQL raw configuration:")
            # Copy the dict and mask the password if present
            safe_config = postgres_config.copy()
            if "password" in safe_config:
                safe_config["password"] = "*****"
            pprint(safe_config)
        else:
            print(f"Error: '{postgres_endpoint}' not found in the YAML configuration")
            return
    except Exception as e:
        print(f"Error reading raw configuration: {e}")
    
    # Try to initialize the client and test the connection
    try:
        print("\nInitializing PgVectorClient...")
        client = PgVectorClient(postgres_endpoint)
        
        print("Testing database connection...")
        connection_info = await client.test_connection()
        
        print("\nConnection test results:")
        print(f"  Success: {connection_info['success']}")
        
        if connection_info.get("error"):
            print(f"  Error: {connection_info['error']}")
        
        if connection_info["success"]:
            print(f"  PostgreSQL version: {connection_info['database_version']}")
            print(f"  pgvector installed: {connection_info['pgvector_installed']}")
            print(f"  Table exists: {connection_info['table_exists']}")
            print(f"  Document count: {connection_info['document_count']}")
            
            print("\nConnection configuration:")
            pprint(connection_info["configuration"])
            
            # Close the connection pool when done
            print("\nClosing connection pool...")
            await client.close()
    
    except Exception as e:
        print(f"\nError testing PostgreSQL connection: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_postgres_connection())
