"""
Check connectivity for all services required by the application.
Run this script to validate environment variables and API access.
"""

from config.config import CONFIG
from azure_connectivity import check_azure_search_api, check_azure_openai_api, check_openai_api, check_azure_embedding_api
from snowflake_connectivity import check_embedding, check_complete, check_search
   
import os
import sys
import asyncio
import time

'''
# Add error handling for imports
try:
    from openai import OpenAI, AzureOpenAI
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from config.config import CONFIG
except ImportError as e:
    print(f"Error importing required libraries: {e}")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)
'''

async def main():
    """Run all connectivity checks"""
    print("Checking NLWeb configuration and connectivity...")
    
    # Retrieve preferred provider from config
    model_config = CONFIG.preferred_llm_provider
    print(f"Using configuration from preferred LLM provider: {model_config}")
    
    embedding_config = CONFIG.preferred_embedding_provider
    print(f"Using configuration from preferred embedding provider: {embedding_config}")
    
    retrieval_config = CONFIG.preferred_retrieval_endpoint
    print(f"Using configuration from preferred retrieval endpoint: {retrieval_config}")

    start_time = time.time()
    
    # Create and run all checks simultaneously
    tasks = []

    # TODO: this might require Python 3.10+ for match-case syntax
    match model_config:
        case "azure_openai":
            tasks.append(check_azure_openai_api())
        case "openai":
            tasks.append(check_openai_api())
        case "snowflake":
            tasks.append(check_complete())
        case _:
            print(f"Unknown provider configuration: {model_config}  Please check your settings.")

    match embedding_config:
        case "azure_openai":
            tasks.append(check_azure_embedding_api())
        case "openai":
            tasks.append(check_openai_api())
        case "snowflake":
            tasks.append(check_embedding())
        case _:
            print(f"Unknown provider configuration: {embedding_config}  Please check your settings.")

    match retrieval_config:
        case "azure_ai_search_1":
            tasks.append(check_azure_search_api())
        case "azure_ai_search_2":
            tasks.append(check_azure_search_api())
        case "azure_ai_search_test":
            tasks.append(check_azure_search_api())
        case "snowflake":
            tasks.append(check_search())
        case _:
            print(f"Unknown provider configuration: {retrieval_config}  Please check your settings.")
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Count successful connections
    successful = sum(1 for r in results if r is True)
    total = len(tasks)
    
    print(f"\n====== SUMMARY ======")
    print(f"✅ {successful}/{total} connections successful")
    
    if successful < total:
        print("❌ Some connections failed. Please check error messages above.")
    else:
        print("✅ All connections successful! Your environment is configured correctly.")
    
    elapsed_time = time.time() - start_time
    print(f"Time taken: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())

