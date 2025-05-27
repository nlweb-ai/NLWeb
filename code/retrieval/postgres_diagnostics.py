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

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the required modules from the project
try:
    from config.config import CONFIG
    from utils.logging_config_helper import get_configured_logger
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print("Make sure you're running this script from the NLWeb/code directory")
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
    
    # Check if postgres_vector is defined in the YAML
    print("\n=== YAML Configuration ===")
    if "endpoints" not in yaml_data:
        print("ERROR: No 'endpoints' section found in YAML configuration")
        return
    
    if "postgres_vector" not in yaml_data["endpoints"]:
        print("ERROR: 'postgres_vector' endpoint not found in YAML configuration")
        print("Available endpoints:", list(yaml_data["endpoints"].keys()))
        return
    
    # Get PostgreSQL configuration from YAML
    pg_config_yaml = yaml_data["endpoints"]["postgres_vector"]
    print("\nPostgreSQL configuration from YAML:")
    
    # Create a safe copy without password
    safe_config = pg_config_yaml.copy()
    if "password" in safe_config:
        safe_config["password"] = "********"
    
    pprint.pprint(safe_config)
    
    # Validate YAML configuration
    required_keys = ["host", "database_name", "db_type"]
    missing_keys = [k for k in required_keys if k not in pg_config_yaml]
    
    if missing_keys:
        print(f"\nWARNING: Missing required keys in YAML configuration: {missing_keys}")
    
    # Check if either username or username_env is provided
    if "username" not in pg_config_yaml and "username_env" not in pg_config_yaml:
        print("\nWARNING: Neither 'username' nor 'username_env' is provided in the configuration")
    
    # Check if either password or password_env is provided
    if "password" not in pg_config_yaml and "password_env" not in pg_config_yaml:
        print("\nWARNING: Neither 'password' nor 'password_env' is provided in the configuration")
    
    # Check if environment variables are defined when env keys are used
    if "username_env" in pg_config_yaml:
        env_var = pg_config_yaml["username_env"]
        if env_var not in os.environ:
            print(f"\nWARNING: Environment variable '{env_var}' for username is not set")
    
    if "password_env" in pg_config_yaml:
        env_var = pg_config_yaml["password_env"]
        if env_var not in os.environ:
            print(f"\nWARNING: Environment variable '{env_var}' for password is not set")
    
    # Check CONFIG object
    print("\n=== CONFIG Object ===")
    if not hasattr(CONFIG, "retrieval_endpoints"):
        print("ERROR: CONFIG object does not have 'retrieval_endpoints' attribute")
        return
    
    if "postgres_vector" not in CONFIG.retrieval_endpoints:
        print("ERROR: 'postgres_vector' endpoint not found in CONFIG.retrieval_endpoints")
        print("Available endpoints:", list(CONFIG.retrieval_endpoints.keys()))
        return
    
    # Get PostgreSQL configuration from CONFIG
    pg_config_obj = CONFIG.retrieval_endpoints["postgres_vector"]
    
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
    
    if not pg_config_yaml.get("host"):
        print("1. Add 'host' field to the postgres_vector section in config_retrieval.yaml:")
        print("   host: your-postgres-hostname.database.azure.com")
    
    if not pg_config_yaml.get("database_name"):
        print("2. Add 'database_name' field to the postgres_vector section in config_retrieval.yaml:")
        print("   database_name: your_database_name")
    
    if "username" not in pg_config_yaml and "username_env" not in pg_config_yaml:
        print("3. Add either direct username or environment variable reference:")
        print("   username: your_username")
        print("   # OR")
        print("   username_env: POSTGRES_USERNAME")
    
    if "password" not in pg_config_yaml and "password_env" not in pg_config_yaml:
        print("4. Add either direct password (not recommended for production) or environment variable reference:")
        print("   password: your_password")
        print("   # OR")
        print("   password_env: POSTGRES_PASSWORD")
    
    print("\n=== Example Valid Configuration ===")
    print("""
postgres_vector:
  host: your-postgres-server.database.azure.com
  port: 5432
  database_name: your_database
  username: your_username
  password: your_password  # Or use username_env/password_env 
  table_name: documents
  db_type: postgres
""")

if __name__ == "__main__":
    asyncio.run(diagnose_postgres_config())
