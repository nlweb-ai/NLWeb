"""
Check Azure connectivity for all services required by the application.
Run this script to validate environment variables and API access.
"""

import os
import sys
import asyncio
import time

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

async def check_search_api():
    """Check Azure AI Search connectivity"""
    print("\nChecking Azure AI Search connectivity...")
    
    # Get search configuration from CONFIG
    preferred_endpoint = CONFIG.preferred_retrieval_endpoint
    if preferred_endpoint not in CONFIG.retrieval_endpoints:
        print(f"❌ Preferred retrieval endpoint '{preferred_endpoint}' not configured")
        return False
    
    retrieval_config = CONFIG.retrieval_endpoints[preferred_endpoint]
    
    api_key = retrieval_config.api_key
    if not api_key:
        print("❌ API key for Azure AI Search not configured")
        return False
    
    endpoint = retrieval_config.api_endpoint
    if not endpoint:
        print("❌ Endpoint for Azure AI Search not configured")
        return False
    
    index_name = retrieval_config.index_name or "embeddings1536"
    
    try:
        credential = AzureKeyCredential(api_key)
        search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential
        )
        
        # Simple query to check connectivity
        result = search_client.get_document_count()
        print(f"✅ Successfully connected to Azure AI Search. Document count: {result}")
        return True
    except Exception as e:
        print(f"❌ Error connecting to Azure AI Search: {e}")
        return False

async def check_inception_api():
    """Check Inception API connectivity"""
    print("\nChecking Inception API connectivity...")
    
    # Check if Inception is configured
    if "inception" not in CONFIG.llm_providers:
        print("❌ Inception provider not configured")
        return False
    
    inception_config = CONFIG.llm_providers["inception"]
    api_key = inception_config.api_key
    
    if not api_key:
        print("❌ API key for Inception not configured")
        return False
    
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.inceptionlabs.ai/v1")
        models = client.models.list()
        print(f"✅ Successfully connected to Inception API")
        return True
    except Exception as e:
        print(f"❌ Error connecting to Inception API: {e}")
        return False

async def check_openai_api():
    """Check OpenAI API connectivity"""
    print("\nChecking OpenAI API connectivity...")
    
    # Check if OpenAI is configured
    if "openai" not in CONFIG.llm_providers:
        print("❌ OpenAI provider not configured")
        return False
    
    openai_config = CONFIG.llm_providers["openai"]
    api_key = openai_config.api_key
    
    if not api_key:
        print("❌ API key for OpenAI not configured")
        return False
    
    try:
        client = OpenAI(api_key=api_key)
        models = client.models.list()
        print(f"✅ Successfully connected to OpenAI API")
        return True
    except Exception as e:
        print(f"❌ Error connecting to OpenAI API: {e}")
        return False

async def check_azure_openai_api():
    """Check Azure OpenAI API connectivity"""
    print("\nChecking Azure OpenAI API connectivity...")
    
    # Check if Azure OpenAI is configured
    if "azure_openai" not in CONFIG.llm_providers:
        print("❌ Azure OpenAI provider not configured")
        return False
    
    azure_config = CONFIG.llm_providers["azure_openai"]
    api_key = azure_config.api_key
    endpoint = azure_config.endpoint
    api_version = azure_config.api_version or "2024-12-01-preview"
    
    if not api_key:
        print("❌ API key for Azure OpenAI not configured")
        return False
    
    if not endpoint:
        print("❌ Endpoint for Azure OpenAI not configured")
        return False

    try:
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        
        # Try to list deployments
        deployments = client.models.list()
        print(f"✅ Successfully connected to Azure OpenAI API")
        return True
    except Exception as e:
        print(f"❌ Error connecting to Azure OpenAI API: {e}")
        return False

async def check_embedding_api():
    """Check Azure Embedding API connectivity"""
    print("\nChecking Azure Embedding API connectivity...")
    
    # Check if Azure OpenAI embedding is configured
    if "azure_openai" not in CONFIG.embedding_providers:
        print("❌ Azure OpenAI embedding provider not configured")
        return False
    
    azure_embedding_config = CONFIG.embedding_providers["azure_openai"]
    api_key = azure_embedding_config.api_key
    endpoint = azure_embedding_config.endpoint
    api_version = azure_embedding_config.api_version or "2024-10-21"
    embedding_model = azure_embedding_config.model
    
    if not api_key:
        print("❌ API key for Azure Embedding not configured")
        return False
    
    if not endpoint:
        print("❌ Endpoint for Azure Embedding not configured")
        return False
    
    if not embedding_model:
        print("❌ Embedding model not configured, using default")
        embedding_model = "text-embedding-3-small"
    
    try:
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        
        # Try to create an embedding
        response = client.embeddings.create(
            input="Hello world",
            model=embedding_model
        )
        
        if len(response.data[0].embedding) > 0:
            print(f"✅ Successfully connected to Azure Embedding API")
            return True
        else:
            print("❌ Got empty embedding response")
            return False
    except Exception as e:
        print(f"❌ Error connecting to Azure Embedding API: {e}")
        return False

async def main():
    """Run all connectivity checks"""
    print("Running Azure connectivity checks...")
    print(f"Using configuration from preferred LLM provider: {CONFIG.preferred_llm_provider}")
    print(f"Using configuration from preferred embedding provider: {CONFIG.preferred_embedding_provider}")
    print(f"Using configuration from preferred retrieval endpoint: {CONFIG.preferred_retrieval_endpoint}")
    
    start_time = time.time()
    
    # Create and run all checks simultaneously
    tasks = [
        check_search_api(),
        check_inception_api(),
        check_openai_api(),
        check_azure_openai_api(),
        check_embedding_api()
    ]
    
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