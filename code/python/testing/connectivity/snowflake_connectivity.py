"""
Check connectivity to Snowflake services.
Run this script to validate environment variables and API access.
"""

import os
import sys
import asyncio
import time
import traceback

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from core.llm import ask_llm
    from core.embedding import get_embedding
    from core.retriever import search, search_all_sites, get_sites as get_sites_wrapper
except ImportError as e:
    print(f"Error importing required libraries: {e}")
    print("Please ensure you are in the /code/python directory and run: pip install -r requirements.txt")
    sys.exit(1)

async def check_and_print(f) -> bool:
    try:
        result = await f()
        if result:
            print(f"✅ {f.__name__}")
        else:
            print(f"❌ {f.__name__}")
        return result
    except Exception as e:
        print(f"❌ {f.__name__}: {e}")
        print(traceback.format_exc())
        return False

async def check_embedding() -> bool:
    response = await get_embedding("Testing connectivity", provider="snowflake")
    return len(response) > 0

async def check_complete() -> bool:
    resp = await ask_llm(
        prompt="The answer to the ultimate question of life, the universe, and everything is",
        schema={"answer": "string"},
        provider="snowflake")
    return resp.get("answer", None) is not None

async def check_search() -> bool:
    resp = await search_all_sites("funny movies", top_n=1, endpoint_name="snowflake_cortex_search_1")
    return len(resp) > 0 and len(resp[0]) == 4

async def list_sites() -> bool:
    sites = await get_sites_wrapper(endpoint_name="snowflake_cortex_search_1")
    if not sites:
        raise Exception("No sites found in Snowflake Cortex Search Service")
    print(f"Found {len(sites)} unique sites: {', '.join(sites)}")
    return True

async def main():
    """Run all connectivity checks"""

    start_time = time.time()
    tasks = [
        check_and_print(check_embedding),
        check_and_print(check_complete),
        check_and_print(check_search),
        check_and_print(list_sites),
    ]
    print("Running Snowflake connectivity checks...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    successful = sum(1 for r in results if r is True)
    total = len(tasks)
    
    print(f"\n====== SUMMARY ======")
    print(f"{successful}/{total} connections successful")
    if successful < total:
        print("❌ Some connections failed. Please check error messages above.")
    else:
        print("✅ All connections successful! Your environment is configured correctly.")
    elapsed_time = time.time() - start_time
    print(f"Time taken: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())

