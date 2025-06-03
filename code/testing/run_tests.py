# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
System test runner for NLWeb.

This module provides functionality to run system tests by calling NLWebHandler
in non-streaming mode and returning the number of results.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import traceback
import json
import ast
import argparse
import sys
from typing import List, Dict, Any, Optional
from core.baseHandler import NLWebHandler
from utils.logging_config_helper import get_configured_logger
from config.config import CONFIG
from llm.llm import get_available_providers

logger = get_configured_logger("nlweb_testing")


def get_config_defaults() -> Dict[str, Any]:
    """Get default values from config files."""
    defaults = {
        'site': 'all',
        'model': 'gpt-4o-mini',
        'generate_mode': 'list', 
        'retrieval_backend': CONFIG.preferred_retrieval_endpoint,
        'prev': []
    }
    
    # Try to get preferred model from LLM config
    if hasattr(CONFIG, 'preferred_llm_provider') and CONFIG.preferred_llm_provider:
        llm_provider = CONFIG.get_llm_provider()
        if llm_provider and llm_provider.models:
            # Use the 'low' model as default for testing
            defaults['model'] = llm_provider.models.low or defaults['model']
    
    return defaults


async def run_system_test(query: str, prev: List[str], site: str, model: str, 
                         generate_mode: str, retrieval_backend: str, **kwargs) -> int:
    """
    Run a system test by calling NLWebHandler in non-streaming mode.
    
    Args:
        query (str): The user query to test (required)
        prev (List[str]): Previous queries for context (required)
        site (str): The site to search (required)
        model (str): The model to use (required)
        generate_mode (str): The generation mode (required)
        retrieval_backend (str): The retrieval backend endpoint to use (required)
        **kwargs: Additional query parameters
        
    Returns:
        int: Number of results in the answer, or -1 if error occurred
        
    Raises:
        ValueError: If any required argument is None or empty
        Exception: Re-raises any exceptions that occur during testing
    """
    
    # Validate all required arguments
    if not query:
        raise ValueError("query argument is required and cannot be empty")
    if prev is None:
        raise ValueError("prev argument is required (use empty list [] if no previous queries)")
    if not site:
        raise ValueError("site argument is required and cannot be empty")
    if not model:
        raise ValueError("model argument is required and cannot be empty")
    if not generate_mode:
        raise ValueError("generate_mode argument is required and cannot be empty")
    if not retrieval_backend:
        raise ValueError("retrieval_backend argument is required and cannot be empty")
        
    # Prepare query parameters for NLWebHandler - format as expected by get_param function
    # get_param expects values to be lists with single elements for HTTP request format
    query_params = {
        "query": [query],
        "prev": prev,  # prev is already a list
        "site": [site],
        "model": [model],
        "generate_mode": [generate_mode],
        "streaming": ["False"],  # Non-streaming mode for testing
        "query_id": [f"test_{hash(query)}_{hash(str(prev))}"],
        "db": [retrieval_backend],  # Override retrieval backend
        **kwargs
    }
    
    # Add LLM-related parameters if provided (for development mode override)
    if kwargs.get('llm_provider'):
        query_params["llm_provider"] = [kwargs['llm_provider']]
    if kwargs.get('llm_level'):
        query_params["llm_level"] = [kwargs['llm_level']]
    
    handler = None
    result_count = -1
    
    try:
        logger.info(f"Starting system test for query: '{query}'")
        logger.debug(f"Test parameters: site={site}, model={model}, generate_mode={generate_mode}, retrieval_backend={retrieval_backend}")
        logger.debug(f"Previous queries: {prev}")
        
        # Initialize NLWebHandler with null http_handler since we're not streaming
        handler = NLWebHandler(query_params, http_handler=None)
        
        # Run the query
        result = await handler.runQuery()
        
        # Extract results count
        if result and "results" in result:
            result_count = len(result["results"])
            logger.info(f"System test completed successfully. Found {result_count} results")
        else:
            result_count = 0
            logger.info("System test completed successfully. No results found")
            
        return result_count
        
    except Exception as e:
        logger.error(f"Error during system test: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Site: {site}")
        logger.error(f"Model: {model}")
        logger.error(f"Generate mode: {generate_mode}")
        logger.error(f"Retrieval backend: {retrieval_backend}")
        logger.error(f"Previous queries: {prev}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Re-raise the exception for caller to handle if needed
        raise
        
    finally:
        # Clean up any resources if needed
        if handler:
            try:
                # Set connection as not alive to prevent any further operations
                handler.is_connection_alive = False
                logger.debug("Handler cleanup completed")
            except Exception as cleanup_error:
                logger.warning(f"Error during handler cleanup: {cleanup_error}")


def run_system_test_sync(query: str, prev: List[str], site: str, model: str,
                        generate_mode: str, retrieval_backend: str, **kwargs) -> tuple[int, str]:
    """
    Synchronous wrapper for run_system_test.
    
    Args:
        query (str): The user query to test (required)
        prev (List[str]): Previous queries for context (required)
        site (str): The site to search (required)
        model (str): The model to use (required)
        generate_mode (str): The generation mode (required)
        retrieval_backend (str): The retrieval backend endpoint to use (required)
        **kwargs: Additional query parameters
        
    Returns:
        tuple[int, str]: (Number of results in the answer, error message if any)
                        Returns (-1, error_message) if error occurred
    """
    try:
        result_count = asyncio.run(run_system_test(query, prev, site, model, generate_mode, retrieval_backend, **kwargs))
        return result_count, None
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in synchronous system test: {error_msg}")
        return -1, error_msg


def generate_test_combinations(args):
    """
    Generate all test combinations based on args.llm_provider and args.generate_mode.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        List of test configurations, each containing the specific parameters to test
    """
    # Determine LLM providers to test
    if args.llm_provider == 'all':
        llm_providers = get_available_providers()
        if not llm_providers:
            print("No LLM providers are available!")
            sys.exit(1)
    elif args.llm_provider:
        llm_providers = [args.llm_provider]
    else:
        llm_providers = [None]  # Use default provider
    
    # Determine generation modes to test
    if args.generate_mode == 'all':
        generation_modes = ['list', 'summarize', 'generate']
    else:
        generation_modes = [args.generate_mode]
    
    # Generate all combinations
    combinations = []
    for provider in llm_providers:
        for gen_mode in generation_modes:
            test_config = {
                'llm_provider': provider,
                'generate_mode': gen_mode,
                'llm_level': args.llm_level,
                'description': f"Provider: {provider or 'default'}, Mode: {gen_mode}"
            }
            combinations.append(test_config)
    
    return combinations


def run_single_test_combination(args, test_config, combination_num, total_combinations):
    """
    Run a single test with the specified configuration.
    
    Args:
        args: Parsed command line arguments
        test_config: Dictionary with test configuration (llm_provider, generate_mode, etc.)
        combination_num: Current combination number (for display)
        total_combinations: Total number of combinations (for display)
        
    Returns:
        Dictionary with test results
    """
    print(f"\n--- Test {combination_num}/{total_combinations}: {test_config['description']} ---")
    
    # Prepare kwargs for this test
    test_kwargs = {}
    if test_config['llm_provider']:
        test_kwargs['llm_provider'] = test_config['llm_provider']
    if test_config['llm_level']:
        test_kwargs['llm_level'] = test_config['llm_level']
    
    try:
        if args.show_results:
            detailed_result = asyncio.run(run_system_test_with_details(
                query=args.query,
                prev=args.prev,
                site=args.site,
                model=args.model,
                generate_mode=test_config['generate_mode'],
                retrieval_backend=args.retrieval_backend,
                **test_kwargs
            ))
            
            if detailed_result['success']:
                print(f"✓ Success: {detailed_result['result_count']} results")
                if detailed_result['results'] and len(detailed_result['results']) > 0:
                    print(f"  Top result: {detailed_result['results'][0].get('name', 'N/A')}")
            else:
                print(f"✗ Failed: {detailed_result['error']}")
            
            return {
                'config': test_config,
                'success': detailed_result['success'],
                'result_count': detailed_result['result_count'],
                'error': detailed_result.get('error')
            }
        else:
            count, error_message = run_system_test_sync(
                query=args.query,
                prev=args.prev,
                site=args.site,
                model=args.model,
                generate_mode=test_config['generate_mode'],
                retrieval_backend=args.retrieval_backend,
                **test_kwargs
            )
            
            if count >= 0:
                print(f"✓ Success: {count} results")
            else:
                print(f"✗ Failed: {error_message if error_message else 'Unknown error'}")
            
            return {
                'config': test_config,
                'success': count >= 0,
                'result_count': count,
                'error': error_message if count < 0 else None
            }
            
    except Exception as e:
        print(f"✗ Failed: {e}")
        return {
            'config': test_config,
            'success': False,
            'result_count': -1,
            'error': str(e)
        }


async def run_system_test_with_details(query: str, prev: List[str], site: str, model: str, 
                                      generate_mode: str, retrieval_backend: str, **kwargs) -> Dict[str, Any]:
    """
    Run a system test and return detailed results including the full response.
    
    Args:
        query (str): The user query to test (required)
        prev (List[str]): Previous queries for context (required)
        site (str): The site to search (required)
        model (str): The model to use (required)
        generate_mode (str): The generation mode (required)
        retrieval_backend (str): The retrieval backend endpoint to use (required)
        **kwargs: Additional query parameters
        
    Returns:
        Dict[str, Any]: Dictionary containing result_count, results, and other response data
        
    Raises:
        ValueError: If any required argument is None or empty
        Exception: Re-raises any exceptions that occur during testing
    """
    
    # Validate all required arguments (same as run_system_test)
    if not query:
        raise ValueError("query argument is required and cannot be empty")
    if prev is None:
        raise ValueError("prev argument is required (use empty list [] if no previous queries)")
    if not site:
        raise ValueError("site argument is required and cannot be empty")
    if not model:
        raise ValueError("model argument is required and cannot be empty")
    if not generate_mode:
        raise ValueError("generate_mode argument is required and cannot be empty")
    if not retrieval_backend:
        raise ValueError("retrieval_backend argument is required and cannot be empty")
        
    # Prepare query parameters for NLWebHandler - format as expected by get_param function
    # get_param expects values to be lists with single elements for HTTP request format
    query_params = {
        "query": [query],
        "prev": prev,  # prev is already a list
        "site": [site],
        "model": [model],
        "generate_mode": [generate_mode],
        "streaming": ["False"],  # Non-streaming mode for testing
        "query_id": [f"test_{hash(query)}_{hash(str(prev))}"],
        "db": [retrieval_backend],  # Override retrieval backend
        **kwargs
    }
    
    # Add LLM-related parameters if provided (for development mode override)
    if kwargs.get('llm_provider'):
        query_params["llm_provider"] = [kwargs['llm_provider']]
    if kwargs.get('llm_level'):
        query_params["llm_level"] = [kwargs['llm_level']]
    
    handler = None
    
    try:
        logger.info(f"Starting detailed system test for query: '{query}'")
        logger.debug(f"Test parameters: site={site}, model={model}, generate_mode={generate_mode}, retrieval_backend={retrieval_backend}")
        logger.debug(f"Previous queries: {prev}")
        
        # Initialize NLWebHandler with null http_handler since we're not streaming
        handler = NLWebHandler(query_params, http_handler=None)
        
        # Run the query
        result = await handler.runQuery()
        
        # Extract results and count
        result_count = 0
        results = []
        if result and "results" in result:
            results = result["results"]
            result_count = len(results)
            logger.info(f"Detailed system test completed successfully. Found {result_count} results")
        else:
            logger.info("Detailed system test completed successfully. No results found")
            
        return {
            'result_count': result_count,
            'results': results,
            'full_response': result,
            'success': True,
            'error': None
        }
        
    except Exception as e:
        logger.error(f"Error during detailed system test: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Site: {site}")
        logger.error(f"Model: {model}")
        logger.error(f"Generate mode: {generate_mode}")
        logger.error(f"Retrieval backend: {retrieval_backend}")
        logger.error(f"Previous queries: {prev}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return {
            'result_count': -1,
            'results': [],
            'full_response': None,
            'success': False,
            'error': str(e)
        }
        
    finally:
        # Clean up any resources if needed
        if handler:
            try:
                # Set connection as not alive to prevent any further operations
                handler.is_connection_alive = False
                logger.debug("Handler cleanup completed")
            except Exception as cleanup_error:
                logger.warning(f"Error during handler cleanup: {cleanup_error}")


def print_detailed_results(results: List[Any]) -> None:
    """
    Print detailed results in a formatted way.
    
    Args:
        results: List of result items from NLWebHandler
    """
    if not results:
        print("No results found.")
        return
    
    print(f"\nDetailed Results ({len(results)} items):")
    print("=" * 80)
    
    for i, result in enumerate(results, 1):
        print(f"\nResult {i}:")
        print("-" * 40)
        
        # Extract common fields, handling different possible formats
        if isinstance(result, dict):
            name = result.get('name', result.get('title', 'N/A'))
            description = result.get('description', result.get('summary', result.get('content', 'N/A')))
            url = result.get('url', result.get('link', 'N/A'))
            score = result.get('score', result.get('relevance_score', 'N/A'))
        elif isinstance(result, list) and len(result) >= 4:
            # Handle list format: [name, description, url, score, ...]
            name = result[0] if len(result) > 0 else 'N/A'
            description = result[1] if len(result) > 1 else 'N/A'
            url = result[2] if len(result) > 2 else 'N/A'
            score = result[3] if len(result) > 3 else 'N/A'
        else:
            # Fallback for unexpected formats
            name = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
            description = 'N/A'
            url = 'N/A'
            score = 'N/A'
        
        print(f"Name: {name}")
        print(f"Description: {description[:200]}{'...' if len(str(description)) > 200 else ''}")
        print(f"URL: {url}")
        print(f"Score: {score}")


def run_json_tests(json_file_path: str) -> Dict[str, Any]:
    """
    Read test cases from a JSON file and run system tests for each case.
    
    Expected JSON format: Array of objects with these fields:
    - query: The user query to test
    - prev: Previous queries (as string, e.g., "query1, query2" or empty string)
    - site: The site to search
    - generate_mode: The generation mode
    - streaming: Streaming mode (ignored for tests, always False)
    - db: The retrieval backend to use
    - llm_provider: LLM provider to use (optional, can be "all")
    
    Args:
        json_file_path (str): Path to the JSON file containing test cases
        
    Returns:
        Dict[str, Any]: Summary of test results including total, passed, failed counts
        
    Raises:
        FileNotFoundError: If JSON file doesn't exist
        ValueError: If JSON format is invalid or required fields are missing
    """
    print(f"Reading test cases from: {json_file_path}")
    
    # Test results tracking
    test_results = []
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as jsonfile:
            test_cases = json.load(jsonfile)
            
            if not isinstance(test_cases, list):
                raise ValueError("JSON file must contain an array of test cases")
            
            # Validate required fields
            required_fields = ['query', 'prev', 'site', 'generate_mode', 'db']
            
            print(f"Found {len(test_cases)} test cases")
            print("=" * 80)
            
            # Expand test cases that have llm_provider: "all"
            expanded_test_cases = []
            for case_num, case in enumerate(test_cases, start=1):
                # Validate required fields
                missing_fields = [field for field in required_fields if field not in case]
                if missing_fields:
                    raise ValueError(f"Missing required fields in test case {case_num}: {missing_fields}")
                
                llm_provider = case.get('llm_provider', '').strip() if case.get('llm_provider') else None
                
                if llm_provider == 'all':
                    # Expand to test all available providers
                    available_providers = get_available_providers()
                    if not available_providers:
                        print(f"Warning: No LLM providers available for test case {case_num}")
                        available_providers = [None]  # Use default
                    
                    for provider in available_providers:
                        expanded_case = {
                            'original_case_num': case_num,
                            'query': case['query'].strip(),
                            'site': case['site'].strip(),
                            'generate_mode': case['generate_mode'].strip(),
                            'db': case['db'].strip(),
                            'llm_provider': provider,
                            'prev_str': case['prev'].strip()
                        }
                        expanded_test_cases.append(expanded_case)
                else:
                    # Single test case
                    expanded_case = {
                        'original_case_num': case_num,
                        'query': case['query'].strip(),
                        'site': case['site'].strip(),
                        'generate_mode': case['generate_mode'].strip(),
                        'db': case['db'].strip(),
                        'llm_provider': llm_provider,
                        'prev_str': case['prev'].strip()
                    }
                    expanded_test_cases.append(expanded_case)
            
            print(f"Expanded to {len(expanded_test_cases)} total test runs")
            print("=" * 80)
            
            for test_num, case in enumerate(expanded_test_cases, start=1):
                total_tests += 1
                
                test_case = {
                    'row': test_num,
                    'original_case': case['original_case_num'],
                    'query': case['query'],
                    'site': case['site'],
                    'generate_mode': case['generate_mode'],
                    'db': case['db'],
                    'llm_provider': case['llm_provider'],
                    'result_count': -1,
                    'success': False,
                    'error': None
                }
                
                # Parse prev queries from string representation
                try:
                    prev_str = case['prev_str']
                    if prev_str == '' or prev_str.lower() == 'none':
                        test_case['prev'] = []
                    else:
                        # Split comma-separated previous queries
                        if ',' in prev_str:
                            test_case['prev'] = [q.strip() for q in prev_str.split(',')]
                        else:
                            test_case['prev'] = [prev_str]
                except (ValueError, SyntaxError) as e:
                    test_case['error'] = f"Invalid prev format: {e}"
                    test_case['prev'] = []
                
                print(f"Test {test_num}: {test_case['query'][:50]}{'...' if len(test_case['query']) > 50 else ''}")
                print(f"  Site: {test_case['site']}, Mode: {test_case['generate_mode']}, DB: {test_case['db']}, LLM: {test_case['llm_provider'] or 'default'}")
                print(f"  Previous queries: {test_case['prev']}")
                
                # Skip test if there was an error parsing
                if test_case['error']:
                    print(f"  SKIPPED: {test_case['error']}")
                    failed_tests += 1
                    test_results.append(test_case)
                    print("-" * 40)
                    continue
                
                # Run the test
                try:
                    # Prepare kwargs for llm_provider if specified
                    test_kwargs = {}
                    if test_case['llm_provider']:
                        test_kwargs['llm_provider'] = test_case['llm_provider']
                    
                    # Get default model from config
                    defaults = get_config_defaults()
                    
                    result_count, error_message = run_system_test_sync(
                        query=test_case['query'],
                        prev=test_case['prev'],
                        site=test_case['site'],
                        model=defaults['model'],
                        generate_mode=test_case['generate_mode'],
                        retrieval_backend=test_case['db'],
                        **test_kwargs
                    )
                    
                    test_case['result_count'] = result_count
                    if error_message:
                        test_case['error'] = error_message
                    # In testing mode, 0 results should be considered failure if errors occurred
                    # Check if we're in testing mode and got 0 results
                    if CONFIG.is_testing_mode() and result_count == 0:
                        test_case['success'] = False
                        test_case['error'] = test_case.get('error') or "No results returned in testing mode"
                    else:
                        test_case['success'] = result_count >= 0
                    
                    if test_case['success']:
                        print(f"  PASSED: {result_count} results")
                        passed_tests += 1
                    else:
                        error_details = test_case.get('error', 'Unknown error')
                        print(f"  FAILED: Error occurred (result_count = {result_count})")
                        if CONFIG.is_testing_mode() and error_details and error_details != 'Unknown error':
                            print(f"  Error details: {error_details}")
                        failed_tests += 1
                        
                except Exception as e:
                    test_case['error'] = str(e)
                    if CONFIG.is_testing_mode():
                        print(f"  FAILED: {e}")
                        # In testing mode, print detailed error information
                        import traceback
                        print(f"  Error details: {traceback.format_exc()}")
                    else:
                        print(f"  FAILED: {e}")
                    failed_tests += 1
                
                test_results.append(test_case)
                print("-" * 40)
                
    except FileNotFoundError:
        raise FileNotFoundError(f"JSON file not found: {json_file_path}")
    except Exception as e:
        raise ValueError(f"Error reading CSV file: {e}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
    
    # Print failed tests details
    if failed_tests > 0:
        print("\nFAILED TESTS:")
        print("-" * 40)
        for test in test_results:
            if not test['success']:
                print(f"Row {test['row']}: {test['query'][:50]}{'...' if len(test['query']) > 50 else ''}")
                if test['error']:
                    print(f"  Error: {test['error']}")
                else:
                    print(f"  Result count: {test['result_count']}")
    
    # Print successful tests with result counts
    if passed_tests > 0:
        print("\nSUCCESSFUL TESTS:")
        print("-" * 40)
        for test in test_results:
            if test['success']:
                print(f"Row {test['row']}: {test['query'][:50]}{'...' if len(test['query']) > 50 else ''} - {test['result_count']} results")
    
    return {
        'total_tests': total_tests,
        'passed_tests': passed_tests,
        'failed_tests': failed_tests,
        'success_rate': (passed_tests/total_tests*100) if total_tests > 0 else 0,
        'test_results': test_results
    }


def create_argument_parser():
    """Create and configure the argument parser with help messages."""
    defaults = get_config_defaults()
    
    parser = argparse.ArgumentParser(
        description="NLWeb System Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
CSV File Format:
===============
The CSV file must contain the following columns (with header row):

Required Columns:
  query          - The user query to test (string)
  prev           - Previous queries for context (string representation of list)
                   Examples: "[]" or "['first query', 'second query']"
  site           - The site to search (string, e.g., "all", "seriouseats")
  model          - The model to use (string, e.g., "gpt-4o-mini", "claude-3-sonnet")
  generate_mode  - The generation mode (string, e.g., "list", "none", "summarize", "generate")
  db             - The retrieval backend to use (string, e.g., "default", "qdrant", "milvus")

Optional Columns:
  streaming      - Streaming mode (ignored for tests, always set to False)

Example CSV content:
===================
query,prev,site,model,generate_mode,streaming,db
"What are some pasta recipes?","[]",seriouseats,gpt-4o-mini,none,False,default
"How to make carbonara?","['What are some pasta recipes?']",seriouseats,gpt-4o-mini,summarize,False,qdrant
"Best pizza places in NYC","[]",all,claude-3-sonnet,generate,False,milvus

Default Values (from config):
=============================
site: {defaults['site']}
model: {defaults['model']}
generate_mode: {defaults['generate_mode']}
retrieval_backend: {defaults['retrieval_backend']}
prev: {defaults['prev']}

Usage Examples:
===============
# Run CSV tests
python run_tests.py --file test_cases.csv

# Run single test with required query only (uses config defaults)
python run_tests.py --query "What are some pasta recipes?"

# Run single test with custom parameters
python run_tests.py --query "How to make pizza?" --site seriouseats --model gpt-4o --generate_mode summarize

# Run single test with previous queries
python run_tests.py --query "Tell me more about carbonara" --prev "What are some pasta recipes?" "How to make carbonara?"

# Run single test and show detailed results (name, description, url, score)
python run_tests.py --query "What are pasta recipes?" --show_results

# Run single test with LLM provider override (development mode only)
python run_tests.py --query "What are pasta recipes?" --llm_provider anthropic --llm_level high

# Run single test with all available LLM providers (development mode only)
python run_tests.py --query "What are pasta recipes?" --llm_provider all

# Run single test with all generation modes
python run_tests.py --query "What are pasta recipes?" --generate_mode all

# Run test with all LLM providers and all generation modes
python run_tests.py --query "What are pasta recipes?" --llm_provider all --generate_mode all

# Run example test
python run_tests.py --example

# Show this help
python run_tests.py --help
        """)
    
    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=False)
    
    mode_group.add_argument(
        '--file', '-f',
        type=str,
        help='Path to CSV file containing test cases'
    )
    
    mode_group.add_argument(
        '--query', '-q',
        type=str,
        help='Single query to test (other parameters use config defaults unless specified)'
    )
    
    mode_group.add_argument(
        '--example',
        action='store_true',
        help='Run a single example test'
    )
    
    # Single test parameters (only used with --query)
    parser.add_argument(
        '--site', '-s',
        type=str,
        default=defaults['site'],
        help=f'Site to search (default: {defaults["site"]})'
    )
    
    parser.add_argument(
        '--model', '-m',
        type=str,
        default=defaults['model'],
        help=f'Model to use (default: {defaults["model"]})'
    )
    
    parser.add_argument(
        '--generate_mode', '-g',
        type=str,
        choices=['list', 'none', 'summarize', 'generate', 'all'],
        default=defaults['generate_mode'],
        help=f'Generation mode (default: {defaults["generate_mode"]}) - use "all" to test all modes'
    )
    
    parser.add_argument(
        '--retrieval_backend', '--db', '-d',
        type=str,
        default=defaults['retrieval_backend'],
        help=f'Retrieval backend to use (default: {defaults["retrieval_backend"]})'
    )
    
    parser.add_argument(
        '--prev', '-p',
        nargs='*',
        default=defaults['prev'],
        help='Previous queries for context (space-separated strings)'
    )
    
    parser.add_argument(
        '--llm_provider',
        type=str,
        default=None,
        help='LLM provider to use (only in development mode, e.g., "openai", "anthropic", "gemini", or "all" to test all available providers)'
    )
    
    parser.add_argument(
        '--llm_level',
        type=str,
        choices=['low', 'high'],
        default=None,
        help='LLM model level to use (only in development mode)'
    )
    
    parser.add_argument(
        '--show_results',
        action='store_true',
        help='Show detailed results (name, description, url, score) when using --query mode'
    )
    
    return parser


if __name__ == "__main__":
    parser = create_argument_parser()
    
    # Add mode argument to override config
    parser.add_argument(
        '--mode',
        choices=['development', 'production', 'testing'],
        default=None,
        help='Override the application mode from config (defaults to config value)'
    )
    
    args = parser.parse_args()
    
    # Override mode if specified, otherwise set to testing by default
    if args.mode:
        CONFIG.set_mode(args.mode)
        print(f"Mode overridden to: {args.mode}")
    else:
        # Default to testing mode for test runs
        CONFIG.set_mode('testing')
        print("Mode set to: testing (default for tests)")
    
    if args.example:
        # Run single example test
        defaults = get_config_defaults()
        try:
            print("Running single test example...")
            print(f"Using config defaults: site={defaults['site']}, model={defaults['model']}, generate_mode={defaults['generate_mode']}, retrieval_backend={defaults['retrieval_backend']}")
            count, error_message = run_system_test_sync(
                query="What are some popular pasta recipes?",
                prev=defaults['prev'],
                site=defaults['site'], 
                model=defaults['model'],
                generate_mode=defaults['generate_mode'],
                retrieval_backend=defaults['retrieval_backend']
            )
            if count >= 0:
                print(f"Test completed with {count} results")
            else:
                print(f"Test failed: {error_message if error_message else 'Unknown error'}")
        except Exception as e:
            print(f"Test failed: {e}")
            
    elif args.file:
        # Run CSV tests
        try:
            summary = run_json_tests(args.file)
            print(f"\nOverall summary: {summary['passed_tests']}/{summary['total_tests']} tests passed ({summary['success_rate']:.1f}%)")
        except Exception as e:
            print(f"Error running CSV tests: {e}")
            
    elif args.query:
        # Run single test with specified query
        try:
            print(f"Running tests for query: '{args.query}'")
            print(f"Base parameters: site={args.site}, model={args.model}, retrieval_backend={args.retrieval_backend}")
            if args.llm_level:
                print(f"LLM level override: {args.llm_level}")
            print(f"Previous queries: {args.prev}")
            
            # Generate all test combinations
            combinations = generate_test_combinations(args)
            
            if len(combinations) > 1:
                print(f"\nRunning {len(combinations)} test combinations...")
                if args.llm_provider == 'all' and args.generate_mode == 'all':
                    print("Testing all LLM providers with all generation modes")
                elif args.llm_provider == 'all':
                    print(f"Testing all LLM providers with mode: {args.generate_mode}")
                elif args.generate_mode == 'all':
                    print(f"Testing all generation modes with provider: {args.llm_provider or 'default'}")
            
            # Run all test combinations
            all_results = []
            for i, test_config in enumerate(combinations, 1):
                result = run_single_test_combination(args, test_config, i, len(combinations))
                all_results.append(result)
            
            # Print summary if multiple combinations were tested
            if len(combinations) > 1:
                print(f"\n=== Summary of {len(combinations)} test combinations ===")
                print(f"{'Provider':<15} {'Mode':<10} {'Status':<10} {'Results':<8} {'Error'}")
                print("-" * 75)
                
                for result in all_results:
                    config = result['config']
                    provider = config['llm_provider'] or 'default'
                    mode = config['generate_mode']
                    status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
                    result_count = str(result['result_count']) if result['success'] else "N/A"
                    error_msg = result['error'][:20] + "..." if result['error'] and len(result['error']) > 20 else (result['error'] or "")
                    
                    print(f"{provider:<15} {mode:<10} {status:<10} {result_count:<8} {error_msg}")
                
                successful = [r for r in all_results if r['success']]
                failed = [r for r in all_results if not r['success']]
                print(f"\nTotal: {len(all_results)} | Successful: {len(successful)} | Failed: {len(failed)}")
            else:
                # Single test case - show detailed results if requested
                result = all_results[0]
                if args.show_results and result['success']:
                    # Re-run with detailed results for single test
                    test_config = result['config']
                    test_kwargs = {}
                    if test_config['llm_provider']:
                        test_kwargs['llm_provider'] = test_config['llm_provider']
                    if test_config['llm_level']:
                        test_kwargs['llm_level'] = test_config['llm_level']
                    
                    detailed_result = asyncio.run(run_system_test_with_details(
                        query=args.query,
                        prev=args.prev,
                        site=args.site,
                        model=args.model,
                        generate_mode=test_config['generate_mode'],
                        retrieval_backend=args.retrieval_backend,
                        **test_kwargs
                    ))
                    
                    if detailed_result['results']:
                        print_detailed_results(detailed_result['results'])
                    else:
                        print("No detailed results to display.")
                
        except Exception as e:
            print(f"Test failed: {e}")
            
    else:
        # No arguments provided - show help
        parser.print_help()