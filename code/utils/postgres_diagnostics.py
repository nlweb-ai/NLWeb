#!/usr/bin/env python3
# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Diagnostic script for PostgreSQL pgvector configuration
This script helps identify and fix configuration issues
"""

import os
import sys
import asyncio
import yaml
import pprint
import json

# More robust path handling for imports
script_path = os.path.abspath(__file__)
utils_dir = os.path.dirname(script_path)
code_dir = os.path.dirname(utils_dir)

# Add both directories to path
sys.path.insert(0, code_dir)  # Add code dir first
sys.path.insert(1, utils_dir)  # Then utils dir

# Import the required modules from the project
try:
    # Try direct import first
    try:
        from logging_config_helper import get_configured_logger
        print("Successfully imported logging_config_helper directly")
    except ImportError:
        # Fall back to package import
        from utils.logging_config_helper import get_configured_logger
        print("Successfully imported from utils.logging_config_helper")
    
    from config.config import CONFIG
    print("Successfully imported CONFIG")
    
    # Add import for PgVectorClient
    try:
        from retrieval.postgres import PgVectorClient
        print("Successfully imported PgVectorClient")
    except ImportError as e:
        print(f"Failed to import PgVectorClient: {e}")
    
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print(f"Make sure you're running this script from the code directory: {code_dir}")
    sys.exit(1)

logger = get_configured_logger("postgres_diagnostics")

async def diagnose_postgres_config():
    """Run diagnostics on PostgreSQL configuration"""
    print("\n=== PostgreSQL Configuration Diagnostics ===\n")
    
    # Check preferred endpoint
    preferred = CONFIG.preferred_retrieval_endpoint
    print(f"Preferred retrieval endpoint: {preferred}")
    
    # Load the raw YAML configuration
    config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(config_dir, "config", "config_retrieval.yaml")
    
    print(f"\nConfig file path: {config_path}")
    if not os.path.exists(config_path):
        print(f"ERROR: Configuration file does not exist at {config_path}")
        return
    
    print("Loading raw configuration from YAML...")
    try:
        with open(config_path, "r") as f:
            yaml_data = yaml.safe_load(f)
    except Exception as e:
        print(f"ERROR: Failed to load YAML configuration: {e}")
        return
    
    # Check if postgres is defined in the YAML
    print("\n=== YAML Configuration ===")
    if "endpoints" not in yaml_data:
        print("ERROR: No 'endpoints' section found in YAML configuration")
        return
    
    if "postgres" not in yaml_data["endpoints"]:
        print("ERROR: 'postgres' endpoint not found in YAML configuration")
        print("Available endpoints:", list(yaml_data["endpoints"].keys()))
        return
    
    # Get PostgreSQL configuration from YAML
    pg_config_yaml = yaml_data["endpoints"]["postgres"]
    print("\nPostgreSQL configuration from YAML:")
    
    # Validate YAML configuration
    required_keys = ["api_endpoint_env", "index_name", "db_type"]
    missing_keys = [k for k in required_keys if k not in pg_config_yaml]
    
    if missing_keys:
        print(f"\nWARNING: Missing required keys in YAML configuration: {missing_keys}")
    
    # Check CONFIG object
    print("\n=== CONFIG Object ===")
    if not hasattr(CONFIG, "retrieval_endpoints"):
        print("ERROR: CONFIG object does not have 'retrieval_endpoints' attribute")
        return
    
    if "postgres" not in CONFIG.retrieval_endpoints:
        print("ERROR: 'postgres' endpoint not found in CONFIG.retrieval_endpoints")
        print("Available endpoints:", list(CONFIG.retrieval_endpoints.keys()))
        return
    
    # Get PostgreSQL configuration from CONFIG
    pg_config_obj = CONFIG.retrieval_endpoints["postgres"]
    
    print("\nPostgreSQL configuration from CONFIG object:")
    print(f"  db_type: {pg_config_obj.db_type}")
    print(f"  api_endpoint: {pg_config_obj.api_endpoint}")
    print(f"  api_key_env: {pg_config_obj.api_key}")
    print(f"  index_name: {pg_config_obj.index_name}")
    print(f"  database_path: {pg_config_obj.database_path}")
    
    print("\n=== Environment Variables ===")
    postgres_env_vars = [k for k in os.environ.keys() if "PG" in k.upper() or "POSTGRES" in k.upper()]
    if postgres_env_vars:
        print("PostgreSQL-related environment variables found:")
        for var in postgres_env_vars:
            value = "********" if "password" in var.lower() or "pass" in var.lower() else os.environ[var]
            print(f"  {var}: {value}")
    else:
        print("No PostgreSQL-related environment variables found")
    
    # Generate fix suggestions
    print("\n=== Suggested Fixes ===")
    
    if not pg_config_yaml.get("api_endpoint_env"):
        print("1. Add 'api_endpoint_env' field to the postgres section in config_retrieval.yaml:")
        print("   api_endpoint_env: postgresql://<USERNAME>:<PASSWORD>@<HOST>:<PORT>/<DATABASE>?sslmode=require")
    
    if not pg_config_yaml.get("index_name"):
        print("2. Add 'index_name' field to the postgres section in config_retrieval.yaml:")
        print("   index_name: your_table_name")
    
    if not pg_config_yaml.get("db_type"):
        print("3. Add 'db_type' field to the postgres section in config_retrieval.yaml:")
        print("   db_type: postgres")
    
    print("\n=== Example Valid Configuration ===")
    print("""
  postgres:
    api_endpoint_env: POSTGRES_CONNECTION_STRING
    index_name: documents
    db_type: postgres
""")
    # Test connection with psycopg3 client
    print("\n=== Testing Connection with psycopg3 Client ===")
    try:
        client = PgVectorClient("postgres")
        
        print("Testing database connection...")
        connection_info = await client.test_connection()
        
        print("\nConnection test results:")
        print(f"  Success: {connection_info.get('success', False)}")
        
        if connection_info.get("error"):
            print(f"  Error: {connection_info['error']}")
            if "vector type not found in the database" in connection_info.get("error", ""):
                print("\nPossible pgvector extension issue:")
                print("  - Make sure the pgvector extension is installed in the database")
                print("  - Run 'CREATE EXTENSION IF NOT EXISTS vector;' in your PostgreSQL database")
                print("  - Refer to https://github.com/pgvector/pgvector for installation instructions")
        else:
            print(f"  PostgreSQL version: {connection_info.get('database_version')}")
            print(f"  pgvector installed: {connection_info.get('pgvector_installed')}")
            print(f"  Table exists: {connection_info.get('table_exists')}")
            print(f"  Document count: {connection_info.get('document_count')}")
        
        # Close connection pool
        await client.close()
        
    except Exception as e:
        print(f"ERROR testing connection: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(diagnose_postgres_config())
