# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
End-to-end test runner for NLWeb.

This module runs full query-to-results tests by calling NLWebHandler
in non-streaming mode and validating the complete pipeline.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from testing.base_test_runner import BaseTestRunner, TestType, TestCase, TestResult
from core.baseHandler import NLWebHandler
from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG

logger = get_configured_logger("nlweb_end_to_end_test")


@dataclass
class EndToEndTestCase(TestCase):
    """Test case for end-to-end tests."""
    query: str
    prev: List[str]
    site: str
    model: str
    generate_mode: str
    retrieval_backend: str
    llm_provider: Optional[str] = None
    llm_level: Optional[str] = None
    expected_min_results: Optional[int] = None
    expected_max_results: Optional[int] = None


@dataclass
class EndToEndTestResult(TestResult):
    """Test result for end-to-end tests."""
    result_count: int = -1
    results: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.results is None:
            self.results = []


class EndToEndTestRunner(BaseTestRunner):
    """Test runner for end-to-end query tests."""
    
    def __init__(self):
        """Initialize end-to-end test runner."""
        super().__init__(TestType.END_TO_END)
        
    def get_config_defaults(self) -> Dict[str, Any]:
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
    
    def validate_test_case(self, test_case: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate end-to-end test case has required fields."""
        required_fields = ['query']
        missing_fields = [field for field in required_fields if field not in test_case or not test_case[field]]
        
        if missing_fields:
            return False, f"Missing required fields: {missing_fields}"
            
        # Validate prev field format
        if 'prev' in test_case and test_case['prev'] and not isinstance(test_case['prev'], list):
            # Try to parse string representation
            prev_str = test_case['prev']
            if isinstance(prev_str, str):
                if prev_str == '' or prev_str.lower() == 'none':
                    test_case['prev'] = []
                elif ',' in prev_str:
                    test_case['prev'] = [q.strip() for q in prev_str.split(',')]
                else:
                    test_case['prev'] = [prev_str]
            else:
                return False, f"Invalid 'prev' format: expected list or string, got {type(prev_str)}"
                
        return True, None
    
    async def run_single_test(self, test_case: Dict[str, Any]) -> EndToEndTestResult:
        """Run a single end-to-end test."""
        start_time = time.time()
        
        # Get defaults and merge with test case
        defaults = self.get_config_defaults()
        
        # Create test case object
        e2e_case = EndToEndTestCase(
            test_type=self.test_type,
            test_id=test_case.get('test_id', 0),
            original_case_num=test_case.get('original_case_num', 0),
            query=test_case['query'],
            prev=test_case.get('prev', defaults['prev']),
            site=test_case.get('site', defaults['site']),
            model=test_case.get('model', defaults['model']),
            generate_mode=test_case.get('generate_mode', defaults['generate_mode']),
            retrieval_backend=test_case.get('db', test_case.get('retrieval_backend', defaults['retrieval_backend'])),
            llm_provider=test_case.get('llm_provider'),
            llm_level=test_case.get('llm_level'),
            expected_min_results=test_case.get('expected_min_results'),
            expected_max_results=test_case.get('expected_max_results'),
            description=test_case.get('description', f"Query: {test_case['query'][:50]}...")
        )
        
        handler = None
        
        try:
            logger.info(f"Starting end-to-end test for query: '{e2e_case.query}'")
            logger.debug(f"Test parameters: site={e2e_case.site}, model={e2e_case.model}, "
                        f"generate_mode={e2e_case.generate_mode}, retrieval_backend={e2e_case.retrieval_backend}")
            
            # Prepare query parameters for NLWebHandler
            query_params = {
                "query": [e2e_case.query],
                "prev": e2e_case.prev,  # prev is already a list
                "site": [e2e_case.site],
                "model": [e2e_case.model],
                "generate_mode": [e2e_case.generate_mode],
                "streaming": ["False"],  # Non-streaming mode for testing
                "query_id": [f"test_{hash(e2e_case.query)}_{hash(str(e2e_case.prev))}"],
                "db": [e2e_case.retrieval_backend],
            }
            
            # Add LLM-related parameters if provided
            if e2e_case.llm_provider:
                query_params["llm_provider"] = [e2e_case.llm_provider]
            if e2e_case.llm_level:
                query_params["llm_level"] = [e2e_case.llm_level]
            
            # Initialize NLWebHandler with null http_handler since we're not streaming
            handler = NLWebHandler(query_params, http_handler=None)
            
            # Run the query
            result = await handler.runQuery()
            
            # Extract results
            result_count = 0
            results = []
            if result and "results" in result:
                results = result["results"]
                result_count = len(results)
                
            # Validate result count if expectations are set
            error = None
            success = True
            
            if e2e_case.expected_min_results is not None and result_count < e2e_case.expected_min_results:
                error = f"Expected at least {e2e_case.expected_min_results} results, got {result_count}"
                success = False
            elif e2e_case.expected_max_results is not None and result_count > e2e_case.expected_max_results:
                error = f"Expected at most {e2e_case.expected_max_results} results, got {result_count}"
                success = False
            elif CONFIG.is_testing_mode() and result_count == 0:
                error = "No results returned in testing mode"
                success = False
                
            logger.info(f"End-to-end test completed. Found {result_count} results")
            
            return EndToEndTestResult(
                test_case=e2e_case,
                success=success,
                error=error,
                result_count=result_count,
                results=results,
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.exception(f"Error during end-to-end test: {e}")
            return EndToEndTestResult(
                test_case=e2e_case,
                success=False,
                error=str(e),
                result_count=-1,
                execution_time=time.time() - start_time
            )
            
        finally:
            # Clean up handler
            if handler:
                try:
                    handler.is_connection_alive = False
                    logger.debug("Handler cleanup completed")
                except Exception as cleanup_error:
                    logger.warning(f"Error during handler cleanup: {cleanup_error}")
    
    def print_detailed_results(self, results: List[Dict[str, Any]]) -> None:
        """Print detailed results for a single test."""
        if not results:
            print("No results found.")
            return
        
        print(f"\nDetailed Results ({len(results)} items):")
        print("=" * 80)
        
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print("-" * 40)
            
            # Extract common fields
            if isinstance(result, dict):
                name = result.get('name', result.get('title', 'N/A'))
                description = result.get('description', result.get('summary', result.get('content', 'N/A')))
                url = result.get('url', result.get('link', 'N/A'))
                score = result.get('score', result.get('relevance_score', 'N/A'))
            else:
                name = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                description = 'N/A'
                url = 'N/A'
                score = 'N/A'
            
            print(f"Name: {name}")
            print(f"Description: {description[:200]}{'...' if len(str(description)) > 200 else ''}")
            print(f"URL: {url}")
            print(f"Score: {score}")


async def main():
    """Main function for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="End-to-end test runner for NLWeb")
    parser.add_argument('--file', '-f', type=str, help='JSON file with test cases')
    parser.add_argument('--query', '-q', type=str, help='Single query to test')
    parser.add_argument('--site', '-s', type=str, default='all', help='Site to search')
    parser.add_argument('--model', '-m', type=str, help='Model to use')
    parser.add_argument('--generate_mode', '-g', type=str, 
                       choices=['list', 'none', 'summarize', 'generate'], 
                       default='list', help='Generation mode')
    parser.add_argument('--db', '-d', type=str, help='Retrieval backend')
    parser.add_argument('--prev', '-p', nargs='*', default=[], help='Previous queries')
    parser.add_argument('--show_results', action='store_true', help='Show detailed results')
    
    args = parser.parse_args()
    
    # Set testing mode
    CONFIG.set_mode('testing')
    
    runner = EndToEndTestRunner()
    
    if args.file:
        # Run tests from file
        test_cases = runner.load_test_file(args.file)
        expanded_cases = runner.expand_test_cases_for_providers(test_cases)
        summary = await runner.run_tests(expanded_cases)
        runner.print_summary(summary)
    elif args.query:
        # Run single test
        test_case = {
            'query': args.query,
            'site': args.site,
            'generate_mode': args.generate_mode,
            'prev': args.prev
        }
        if args.model:
            test_case['model'] = args.model
        if args.db:
            test_case['db'] = args.db
            
        result = await runner.run_single_test(test_case)
        
        print(f"\nTest Result: {'PASSED' if result.success else 'FAILED'}")
        print(f"Results: {result.result_count}")
        if result.error:
            print(f"Error: {result.error}")
        if args.show_results and result.results:
            runner.print_detailed_results(result.results)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())