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
    import argparse

    from config.config import CONFIG
    from llm.llm import ask_llm
    from embedding.embedding import get_embedding
    from retrieval.retriever import get_vector_db_client
    from azure_connectivity import check_azure_search_api, check_azure_openai_api, check_openai_api, check_azure_embedding_api
    from snowflake_connectivity import check_embedding, check_complete, check_search
    from inception_connectivity import check_inception_api

except ImportError as e:
    print(f"Error importing required libraries: {e}")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)


# Generic function to log unknown provider configurations
async def log_unknown_provider(config_type, config_name):
    """Log an unknown provider configuration"""
    print(f"❌ Unknown {config_type} provider configuration: {config_name}. Please check your settings.")
    return False


# Function to check LLM API connectivity
async def check_llm_api(llm_name) -> bool:
    print(f"Checking LLM API connectivity for {llm_name}...")
    if llm_name not in CONFIG.llm_endpoints:
        await log_unknown_provider("LLM", llm_name)
        return False

    try:
        schema = {"capital": "string"}
        test_prompt = "What is the capital of France?"
        # Using a larger timeout than the default because we don't want to fail on slow responses
        output = await ask_llm(test_prompt, schema=schema, provider=llm_name, timeout=20)
        #print(f"Output from {llm_name}: {output}")
        if not output:
            print(f"❌ LLM API connectivity check failed for {llm_name}: No valid output received.")
            return False
        elif str(output).__contains__("Paris") or str(output).__contains__("paris"):
            print(f"✅ LLM API connectivity check successful for {llm_name}. Output contains expected answer.")
            return True
        else:
            print(f"❌ LLM API connectivity check failed for {llm_name}: Output does not contain expected answer 'Paris'.  Please verify manually: {str(output)}")
            return False
    except Exception as e:
        print(f"❌ LLM API connectivity check failed for {llm_name}: {type(e).__name__}: {str(e)}")
        return False
    

# Function to check embedding API connectivity
async def check_embedding_api(embedding_name) -> bool:
    print(f"Checking embedding API connectivity for {embedding_name}...")
    if embedding_name not in CONFIG.embedding_providers:
        await log_unknown_provider("embedding", embedding_name)
        return False

    try:
        test_prompt = "What is the capital of France?"
        output = await get_embedding(test_prompt, provider=embedding_name, model=CONFIG.embedding_providers[embedding_name].model, timeout=30)
        #print(f"Output from {embedding_name}: {output}")
        #print(str(output))
        if not output:
            print(f"❌ Embedding API connectivity check failed for {embedding_name}: No valid output received.")
            return False
        # Verify output is a list of floats
        elif isinstance(output, list) and len(output) > 2 and all(isinstance(i, float) for i in output):
            print(f"✅ Embedding API connectivity check successful for {embedding_name}. Output is list of floats.")
            return True
        else:
            print(f"❌ Embedding API connectivity check failed for {embedding_name}: Output is not a list of floats.  Please verify manually: {str(output)}")
            return False
    except Exception as e:
        print(f"❌ Embedding API connectivity check failed for {embedding_name}: {type(e).__name__}: {str(e)}")
        return False
    

# Function to check retriever connectivity
async def check_retriever(retrieval_name) -> bool:
    print(f"Checking retriever connectivity for {retrieval_name}...")
    if retrieval_name not in CONFIG.retrieval_endpoints:
        await log_unknown_provider("retriever", retrieval_name)
        return False

    try:
        client = get_vector_db_client(retrieval_name)
        resp = await client.search("e", site="all", num_results=1)
        good_output = len(resp) > 0 #and len(resp[0]) == 4
        #print(f"Output from {retrieval_name}: {str(resp)}")
        #print(f"Good Output from {retrieval_name}: {str(good_output)}")
        if not resp:
            print(f"❌ Retriever API connectivity check failed for {retrieval_name}: No valid output received.")
            return False
        elif good_output:
            print(f"✅ Retriever API connectivity check successful for {retrieval_name}. Output is in expected format.")
            return True
        elif not good_output:
            print(f"❌ Retriever API connectivity check failed for {retrieval_name}: Output is not in expected format.  Please verify manually: {str(resp)}")
            return False
        else:
            print(f"❌ Retriever API connectivity check failed for {retrieval_name}: What is happening here?  Please verify manually: {str(resp)}")
            return False
    except Exception as e:
        print(f"❌ Retriever API connectivity check failed for {retrieval_name}: {type(e).__name__}: {str(e)}")
        return False


async def main():
    # Create and run all checks simultaneously
    tasks = []

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Check connectivity for all services required by NLWeb")
    parser.add_argument("--all", action='store_true', default=False,
                        help="Run all connectivity checks for every known provider",)
    args = parser.parse_args()
    
    start_time = time.time()

    if args.all:
        """Run all connectivity checks"""
        print("Running NLWeb connectivity checks for all known providers...")
        print("This may take a while, please be patient...")
        for llm_provider in CONFIG.llm_endpoints:
            tasks.append(check_llm_api(llm_provider))

        for embedding_provider in CONFIG.embedding_providers:
            tasks.append(check_embedding_api(embedding_provider))

        for retrieval_provider in CONFIG.retrieval_endpoints:
            tasks.append(check_retriever(retrieval_provider))

    else:
        """Run connectivity checks for preferred providers only"""
        print("Checking NLWeb configuration and connectivity...")
    
        # Retrieve preferred provider from config
        model_config = CONFIG.preferred_llm_endpoint
        print(f"Using configuration from preferred LLM provider: {model_config}")
        tasks.append(check_llm_api(model_config))
        
        embedding_config = CONFIG.preferred_embedding_provider
        print(f"Using configuration from preferred embedding provider: {embedding_config}")
        tasks.append(check_embedding_api(embedding_config))
        
        retrieval_config = CONFIG.preferred_retrieval_endpoint
        retrieval_dbtype_config = CONFIG.retrieval_endpoints[CONFIG.preferred_retrieval_endpoint].db_type
        print(f"Using configuration from preferred retrieval endpoint: {retrieval_config} with db_type {retrieval_dbtype_config}")  
        tasks.append(check_retriever(retrieval_config))
    
    # Run all tasks concurrently
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
