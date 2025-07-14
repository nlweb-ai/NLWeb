# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Query retrieval test runner for NLWeb.

This module tests the search functionality of the retrieval system
without running the full LLM pipeline.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from testing.base_test_runner import BaseTestRunner, TestType, TestCase, TestResult
from core.retriever import VectorDBClient
from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG

logger = get_configured_logger("nlweb_query_retrieval_test")


@dataclass
class QueryRetrievalTestCase(TestCase):
    """Test case for query retrieval tests."""
    query: str
    retrieval_backend: str
    site: str = "all"
    num_results: int = 10
    expected_min_results: Optional[int] = None
    expected_max_results: Optional[int] = None
    expected_urls: Optional[List[str]] = None
    contains_urls: Optional[List[str]] = None
    excludes_urls: Optional[List[str]] = None
    min_score: Optional[float] = None


@dataclass
class QueryRetrievalTestResult(TestResult):
    """Test result for query retrieval tests."""
    results: List[Dict[str, Any]] = None
    result_count: int = 0
    
    def __post_init__(self):
        if self.results is None:
            self.results = []


class QueryRetrievalTestRunner(BaseTestRunner):
    """Test runner for query retrieval tests."""
    
    def __init__(self):
        """Initialize query retrieval test runner."""
        super().__init__(TestType.QUERY_RETRIEVAL)
        
    def validate_test_case(self, test_case: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate query retrieval test case has required fields."""
        required_fields = ['query', 'retrieval_backend']
        missing_fields = [field for field in required_fields if field not in test_case or not test_case[field]]
        
        if missing_fields:
            return False, f"Missing required fields: {missing_fields}"
            
        # Validate expected_urls format if present
        if 'expected_urls' in test_case and test_case['expected_urls']:
            if not isinstance(test_case['expected_urls'], list):
                return False, "expected_urls must be a list"
                
        # Validate contains_urls format if present
        if 'contains_urls' in test_case and test_case['contains_urls']:
            if not isinstance(test_case['contains_urls'], list):
                return False, "contains_urls must be a list"
                
        # Validate excludes_urls format if present
        if 'excludes_urls' in test_case and test_case['excludes_urls']:
            if not isinstance(test_case['excludes_urls'], list):
                return False, "excludes_urls must be a list"
                
        return True, None
    
    async def run_single_test(self, test_case: Dict[str, Any]) -> QueryRetrievalTestResult:
        """Run a single query retrieval test."""
        start_time = time.time()
        
        # Create test case object
        query_case = QueryRetrievalTestCase(
            test_type=self.test_type,
            test_id=test_case.get('test_id', 0),
            original_case_num=test_case.get('original_case_num', 0),
            query=test_case['query'],
            retrieval_backend=test_case.get('db', test_case.get('retrieval_backend')),
            site=test_case.get('site', 'all'),
            num_results=test_case.get('num_results', test_case.get('top_k', 10)),  # Support both for backwards compatibility
            expected_min_results=test_case.get('expected_min_results'),
            expected_max_results=test_case.get('expected_max_results'),
            expected_urls=test_case.get('expected_urls'),
            contains_urls=test_case.get('contains_urls'),
            excludes_urls=test_case.get('excludes_urls'),
            min_score=test_case.get('min_score'),
            description=test_case.get('description', f"Query: {test_case['query'][:50]}...")
        )
        
        try:
            logger.info(f"Starting query retrieval test for: '{query_case.query}'")
            logger.debug(f"Parameters: backend={query_case.retrieval_backend}, site={query_case.site}, num_results={query_case.num_results}")
            
            # Create VectorDBClient instance
            client = VectorDBClient(endpoint_name=query_case.retrieval_backend)
            
            # Perform search
            results = await client.search(
                query=query_case.query,
                site=query_case.site,
                num_results=query_case.num_results
            )
            
            result_count = len(results)
            logger.info(f"Retrieved {result_count} results for query '{query_case.query}'")
            
            # Extract URLs from results for validation
            result_urls = []
            for result in results:
                if isinstance(result, dict):
                    url = result.get('url', result.get('link', ''))
                elif isinstance(result, list) and len(result) >= 3:
                    url = result[2]  # Assuming [name, description, url, score, ...]
                else:
                    url = ''
                if url:
                    result_urls.append(url)
            
            # Validate results
            error = None
            success = True
            
            # Check minimum result count
            if query_case.expected_min_results is not None and result_count < query_case.expected_min_results:
                error = f"Expected at least {query_case.expected_min_results} results, got {result_count}"
                success = False
                
            # Check maximum result count
            if query_case.expected_max_results is not None and result_count > query_case.expected_max_results:
                error = f"Expected at most {query_case.expected_max_results} results, got {result_count}"
                success = False
                
            # Check exact URLs if provided
            if query_case.expected_urls is not None:
                if set(result_urls) != set(query_case.expected_urls):
                    error = f"URL mismatch. Expected: {query_case.expected_urls}, Got: {result_urls}"
                    success = False
                    
            # Check contains_urls
            if query_case.contains_urls:
                missing_urls = [u for u in query_case.contains_urls if u not in result_urls]
                if missing_urls:
                    error = f"Missing expected URLs: {missing_urls}"
                    success = False
                    
            # Check excludes_urls
            if query_case.excludes_urls:
                unexpected_urls = [u for u in query_case.excludes_urls if u in result_urls]
                if unexpected_urls:
                    error = f"Found unexpected URLs: {unexpected_urls}"
                    success = False
                    
            # Check minimum score if specified
            if query_case.min_score is not None:
                low_score_results = []
                for i, result in enumerate(results):
                    score = None
                    if isinstance(result, dict):
                        score = result.get('score', result.get('relevance_score'))
                    elif isinstance(result, list) and len(result) >= 4:
                        score = result[3]  # Assuming [name, description, url, score, ...]
                    
                    if score is not None and score < query_case.min_score:
                        low_score_results.append(f"Result {i+1}: score={score}")
                        
                if low_score_results:
                    error = f"Results below minimum score {query_case.min_score}: {', '.join(low_score_results)}"
                    success = False
                    
            return QueryRetrievalTestResult(
                test_case=query_case,
                success=success,
                error=error,
                results=results,
                result_count=result_count,
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.exception(f"Error during query retrieval test: {e}")
            return QueryRetrievalTestResult(
                test_case=query_case,
                success=False,
                error=str(e),
                results=[],
                result_count=0,
                execution_time=time.time() - start_time
            )
    
    def print_summary(self, summary: Dict[str, Any]) -> None:
        """Print test summary with retrieval-specific details."""
        super().print_summary(summary)
        
        # Print successful tests with result details
        successful_results = [r for r in summary['results'] if r['success']]
        if successful_results:
            print(f"\nSUCCESSFUL TESTS:")
            print("-" * 40)
            for result in successful_results:
                print(f"Test {result['test_id']}: {result.get('description', 'No description')}")
                if 'result_count' in result:
                    print(f"  Results retrieved: {result['result_count']}")
                if 'execution_time' in result:
                    print(f"  Execution time: {result['execution_time']:.2f}s")
    
    def print_detailed_results(self, results: List[Dict[str, Any]]) -> None:
        """Print detailed retrieval results."""
        if not results:
            print("No results found.")
            return
        
        print(f"\nDetailed Retrieval Results ({len(results)} items):")
        print("=" * 80)
        
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print("-" * 40)
            
            # Extract fields based on result format
            if isinstance(result, dict):
                name = result.get('name', result.get('title', 'N/A'))
                description = result.get('description', result.get('summary', result.get('content', 'N/A')))
                url = result.get('url', result.get('link', 'N/A'))
                score = result.get('score', result.get('relevance_score', 'N/A'))
                site = result.get('site', 'N/A')
            elif isinstance(result, list) and len(result) >= 4:
                # Handle list format: [name, description, url, score, ...]
                name = result[0] if len(result) > 0 else 'N/A'
                description = result[1] if len(result) > 1 else 'N/A'
                url = result[2] if len(result) > 2 else 'N/A'
                score = result[3] if len(result) > 3 else 'N/A'
                site = result[4] if len(result) > 4 else 'N/A'
            else:
                name = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                description = 'N/A'
                url = 'N/A'
                score = 'N/A'
                site = 'N/A'
            
            print(f"Name: {name}")
            print(f"Description: {description[:200]}{'...' if len(str(description)) > 200 else ''}")
            print(f"URL: {url}")
            print(f"Score: {score}")
            print(f"Site: {site}")


async def main():
    """Main function for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Query retrieval test runner for NLWeb")
    parser.add_argument('--file', '-f', type=str, help='JSON file with test cases')
    parser.add_argument('--query', '-q', type=str, help='Query to test')
    parser.add_argument('--db', '-d', type=str, help='Retrieval backend')
    parser.add_argument('--site', '-s', type=str, default='all', help='Site to search')
    parser.add_argument('--top_k', '-k', type=int, default=10, help='Number of results to retrieve')
    parser.add_argument('--min_results', type=int, help='Minimum expected results')
    parser.add_argument('--max_results', type=int, help='Maximum expected results')
    parser.add_argument('--min_score', type=float, help='Minimum score for results')
    parser.add_argument('--show_results', action='store_true', help='Show detailed results')
    
    args = parser.parse_args()
    
    # Set testing mode
    CONFIG.set_mode('testing')
    
    runner = QueryRetrievalTestRunner()
    
    if args.file:
        # Run tests from file
        test_cases = runner.load_test_file(args.file)
        summary = await runner.run_tests(test_cases)
        runner.print_summary(summary)
    elif args.query and args.db:
        # Run single test
        test_case = {
            'query': args.query,
            'retrieval_backend': args.db,
            'site': args.site,
            'top_k': args.top_k
        }
        
        if args.min_results is not None:
            test_case['expected_min_results'] = args.min_results
        if args.max_results is not None:
            test_case['expected_max_results'] = args.max_results
        if args.min_score is not None:
            test_case['min_score'] = args.min_score
            
        result = await runner.run_single_test(test_case)
        
        print(f"\nTest Result: {'PASSED' if result.success else 'FAILED'}")
        print(f"Results retrieved: {result.result_count}")
        print(f"Execution time: {result.execution_time:.2f}s")
        if result.error:
            print(f"Error: {result.error}")
        if args.show_results and result.results:
            runner.print_detailed_results(result.results)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())