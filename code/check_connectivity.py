"""
Check connectivity for all services required by the application.
Run this script to validate environment variables and API access.
"""

# Error handling for imports
try:
    import os
    import sys
    import asyncio
    import time

    from config.config import CONFIG
    from azure_connectivity import check_azure_search_api, check_azure_openai_api, check_openai_api, check_azure_embedding_api
    from snowflake_connectivity import check_embedding, check_complete, check_search
    from inception_connectivity import check_inception_api

except ImportError as e:
    print(f"Error importing required libraries: {e}")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)


async def log_unknown_provider(config_type, config_name):
    """Log an unknown provider configuration"""
    print(f"❌ Unknown {config_type} provider configuration: {config_name}. Please check your settings.")
    return False

'''
async def get_llm_check(llm_name):
    """Get the LLM check function based on the provider name"""
    match llm_name:
        case "azure_openai":
            return check_azure_openai_api
        case "openai":
            return check_openai_api
        case "snowflake":
            return check_complete
        case "inception":
            return check_inception_api
        # TODO: add the rest of the providers as they are implemented
        case _:
            print(f"❌ Unknown LLM provider: {llm_name}. Please check your settings.")
            return None

async def get_all_providers():
    """Get a list of all configured providers"""
    providers = []
    for provider_name, provider_config in CONFIG.llm_endpoints.items():
        if provider_config and hasattr(provider_config, 'api_key') and provider_config.api_key:
            providers.append(provider_name)
    return providers
'''

async def main():
    """Run all connectivity checks"""
    print("Checking NLWeb configuration and connectivity...")
    
    # Retrieve preferred provider from config
    model_config = CONFIG.preferred_llm_endpoint
    print(f"Using configuration from preferred LLM provider: {model_config}")
    
    embedding_config = CONFIG.preferred_embedding_provider
    print(f"Using configuration from preferred embedding provider: {embedding_config}")
    
    retrieval_config = CONFIG.preferred_retrieval_endpoint
    retrieval_dbtype_config = CONFIG.retrieval_endpoints[CONFIG.preferred_retrieval_endpoint].db_type
    print(f"Using configuration from preferred retrieval endpoint: {retrieval_config} with db_type {retrieval_dbtype_config}")  

    start_time = time.time()
    
    # Create and run all checks simultaneously
    tasks = []

    '''
    # TODO: implement support for "check all providers" option; this will be useful for testing
    model_check = get_llm_check(model_config)
    if model_check:
        tasks.append(model_check)
    else:
        tasks.append(log_unknown_provider("LLM", model_config))

    '''
    match model_config:
        case "azure_openai":
            tasks.append(check_azure_openai_api())
        case "openai":
            tasks.append(check_openai_api())
        case "snowflake":
            tasks.append(check_complete())
        case "inception":
            tasks.append(check_inception_api())
        # TODO: we need to add support for HuggingFace and other providers below
        case "anthropic":
            print("Anthropic provider is not yet implemented in connectivity checks.")
            # tasks.append(check_anthropic_api())  # Uncomment when implemented
        case "gemini":
            print("Gemini provider is not yet implemented in connectivity checks.")
            # tasks.append(check_gemini_api())  # Uncomment when implemented
        case "huggingface":
            print("HuggingFace provider is not yet implemented in connectivity checks.")
            # tasks.append(check_huggingface_api())  # Uncomment when implemented
        case "deepseek_azure":
            print("DeepSeek Azure provider is not yet implemented in connectivity checks.")
            # tasks.append(check_deepseek_azure_api())  # Uncomment when implemented
        case "llama_azure":
            print("Llama Azure provider is not yet implemented in connectivity checks.")
            # tasks.append(check_llama_azure_api())  # Uncomment when implemented
        case _:
            tasks.append(log_unknown_provider("LLM", model_config))
            #print(f"Unknown provider configuration: {model_config}  Please check your settings.")

    match embedding_config:
        case "azure_openai":
            tasks.append(check_azure_embedding_api())
        case "openai":
            tasks.append(check_openai_api())
        case "snowflake":
            tasks.append(check_embedding())
        case "gemini":
            # TODO: implement Gemini embedding provider check
            print("Gemini embedding provider is not yet implemented in connectivity checks.")
            # tasks.append(check_gemini_embedding_api())  # Uncomment when implemented
        case _:
            tasks.append(log_unknown_provider("embedding", embedding_config))
            #print(f"Unknown provider configuration: {embedding_config}  Please check your settings.")

    match retrieval_dbtype_config:
        case "azure_ai_search":
            tasks.append(check_azure_search_api())
        case "snowflake_cortex_search":
            tasks.append(check_search())
        # TODO: implement support for other retrieval providers: milvus, qdrant, opensearch
        case _:
            tasks.append(log_unknown_provider("retrieval", retrieval_config))
            #print(f"Unknown provider configuration: {retrieval_config}  Please check your settings.")
    
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
