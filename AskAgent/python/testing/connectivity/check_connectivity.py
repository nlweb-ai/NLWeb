"""
Check connectivity for all services required by the application.
Run this script to validate environment variables and API access.
"""

# Error handling for imports
import os
import sys
import asyncio
import time
import argparse

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
try:
    from core.config import CONFIG
    from core.llm import ask_llm
    from core.embedding import get_embedding
    from core.retriever import search, get_vector_db_client
    from testing.connectivity.azure_connectivity import check_azure_search_api, check_azure_openai_api, check_openai_api, check_azure_embedding_api
    from testing.connectivity.snowflake_connectivity import check_embedding, check_complete, check_search
    from testing.connectivity.inception_connectivity import check_inception_api

except ImportError as e:
    print(f"Error importing required libraries: {e}")
    print("Please ensure you are in the /code/python directory and run: pip install -r requirements.txt")
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

    # Check if this is a provider that needs special handling
    if llm_name in ["azure_openai", "openai"]:
        if llm_name == "azure_openai":
            return await check_azure_openai_api()
        elif llm_name == "openai":
            return await check_openai_api()
    elif llm_name == "inception":
        return await check_inception_api()
    elif llm_name == "snowflake_complete":
        return await check_complete()

    # Default LLM check using ask_llm
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

    # Check if this is a provider that needs special handling
    if embedding_name == "azure_embedding":
        return await check_azure_embedding_api()
    elif embedding_name == "snowflake_embedding":
        return await check_embedding()

    # Default embedding check using get_embedding
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

    # Check if this is a provider that needs special handling
    if retrieval_name in ["nlweb_west", "nlweb_east"] and CONFIG.retrieval_endpoints[retrieval_name].db_type == "azure_search":
        return await check_azure_search_api()
    elif retrieval_name == "snowflake_retrieval":
        return await check_search()

    # Default retriever check using get_vector_db_client
    try:
        # We need to use this specific vector db client to test its connectivity.  The general search will try all and hide errors.  
        client = get_vector_db_client(retrieval_name)
        resp = await client.search("e", site="all", num_results=1)
        #print(f"Output from {retrieval_name}: {str(resp)}")
        
        # Check if the response is a valid list (even if empty)
        if isinstance(resp, list):
            if len(resp) > 0:
                # Check if the response format is correct
                if len(resp[0]) >= 4:
                    print(f"✅ Retriever API connectivity check successful for {retrieval_name}. Found {len(resp)} results.")
                    return True
                else:
                    print(f"❌ Retriever API connectivity check failed for {retrieval_name}: Output format is incorrect. Expected at least 4 fields per result.")
                    return False
            else:
                # Empty results are OK - the retriever is working, just no data
                print(f"✅ Retriever API connectivity check successful for {retrieval_name}. Connection established (no data in collection yet).")
                return True
        else:
            print(f"❌ Retriever API connectivity check failed for {retrieval_name}: Expected list response, got {type(resp).__name__}")
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
        
        retrieval_config = CONFIG.write_endpoint
        # NOTE: I can't use a retrieval client.enabled_endpoints here, because it does validation and will just remove any invalid endpoints. 
        # The purpose of this method is to surface these invalid endpoints to the user.   
        for retrieval_endpoint in CONFIG.retrieval_endpoints:
            if CONFIG.retrieval_endpoints[retrieval_endpoint].enabled:  
                print(f"Using configuration from enabled retrieval endpoint: {retrieval_endpoint}")  
                tasks.append(check_retriever(retrieval_endpoint))
    
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
