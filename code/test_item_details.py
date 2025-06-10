#!/usr/bin/env python3

"""
Test script for item details functionality.
"""

import asyncio
import sys
import os
import subprocess

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from set_keys.sh
def load_environment():
    """Load environment variables from set_keys.sh"""
    try:
        # Read and execute set_keys.sh
        with open('set_keys.sh', 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if line.startswith('export ') and '=' in line:
                # Parse export statements
                line = line.replace('export ', '')
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                os.environ[key] = value
                print(f"Loaded: {key}")
        
        print("Environment variables loaded successfully")
    except Exception as e:
        print(f"Error loading environment: {e}")

from core.baseHandler import NLWebHandler

async def test_item_details():
    """Test the item details functionality directly."""
    
    print("=== TESTING ITEM DETAILS FUNCTIONALITY ===")
    
    # Load environment variables
    load_environment()
    print("-" * 50)
    
    # Simulate query parameters for the item details query (as URL-parsed arrays)
    query_params = {
        'query': ['give me the ingredients for the olive oil plum cake recipe from nytimes'],
        'site': ['all'],
        'mode': ['list'],
        'streaming': ['false'],
        'prev': []
    }
    
    print(f"Query: {query_params['query']}")
    print(f"Site: {query_params['site']}")
    print("-" * 50)
    
    try:
        # Create and run the handler
        handler = NLWebHandler(query_params, None)
        result = await handler.runQuery()
        
        print("\n=== FINAL RESULT ===")
        print(f"Result type: {type(result)}")
        print(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        
        if isinstance(result, dict):
            for key, value in result.items():
                if key == 'results' and isinstance(value, list):
                    print(f"{key}: {len(value)} results")
                    for i, item in enumerate(value[:3]):  # Show first 3
                        print(f"  Result {i+1}: {str(item)[:100]}...")
                else:
                    print(f"{key}: {str(value)[:100]}...")
                    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_item_details())