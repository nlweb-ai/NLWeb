# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Test dispatcher for NLWeb testing framework.

This module serves as the main entry point for running different types of tests.
It dispatches to the appropriate test runner based on the test type.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import asyncio
import argparse
import sys
from typing import Dict, Any, Optional
from pathlib import Path

from testing.base_test_runner import TestType
from testing.end_to_end_tests import EndToEndTestRunner
from testing.site_retrieval_tests import SiteRetrievalTestRunner
from testing.query_retrieval_tests import QueryRetrievalTestRunner
from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG

logger = get_configured_logger("nlweb_test_dispatcher")


class TestDispatcher:
    """Main test dispatcher that routes tests to appropriate runners."""
    
    def __init__(self):
        """Initialize test dispatcher with available runners."""
        self.runners = {
            TestType.END_TO_END: EndToEndTestRunner(),
            TestType.SITE_RETRIEVAL: SiteRetrievalTestRunner(),
            TestType.QUERY_RETRIEVAL: QueryRetrievalTestRunner()
        }
        
    async def run_test_file(self, file_path: str, test_type: Optional[TestType] = None) -> Dict[str, Any]:
        """
        Run tests from a JSON file.
        
        Args:
            file_path: Path to JSON test file
            test_type: Optional test type override (if None, uses test_type field in JSON)
            
        Returns:
            Dictionary with aggregated test results
        """
        logger.info(f"Running tests from file: {file_path}")
        
        # If test type is specified, use the specific runner
        if test_type:
            runner = self.runners[test_type]
            test_cases = runner.load_test_file(file_path)
            expanded_cases = runner.expand_test_cases_for_providers(test_cases)
            return await runner.run_tests(expanded_cases)
        
        # Otherwise, load all tests and dispatch by type
        all_results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'results_by_type': {}
        }
        
        # Load tests for each runner type
        for runner_type, runner in self.runners.items():
            try:
                test_cases = runner.load_test_file(file_path)
                if test_cases:
                    expanded_cases = runner.expand_test_cases_for_providers(test_cases)
                    summary = await runner.run_tests(expanded_cases)
                    
                    all_results['results_by_type'][runner_type.value] = summary
                    all_results['total_tests'] += summary['total_tests']
                    all_results['passed_tests'] += summary['passed_tests']
                    all_results['failed_tests'] += summary['failed_tests']
                    
            except Exception as e:
                logger.error(f"Error running {runner_type.value} tests: {e}")
                
        return all_results
    
    async def run_single_test(self, test_type: TestType, test_case: Dict[str, Any]) -> Any:
        """
        Run a single test of the specified type.
        
        Args:
            test_type: Type of test to run
            test_case: Test case data
            
        Returns:
            Test result from the specific runner
        """
        if test_type not in self.runners:
            raise ValueError(f"Unknown test type: {test_type}")
            
        runner = self.runners[test_type]
        return await runner.run_single_test(test_case)
    
    def print_aggregated_summary(self, results: Dict[str, Any]) -> None:
        """Print summary of aggregated test results."""
        print(f"\n{'=' * 80}")
        print("OVERALL TEST SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total tests: {results['total_tests']}")
        print(f"Passed: {results['passed_tests']}")
        print(f"Failed: {results['failed_tests']}")
        
        if results['total_tests'] > 0:
            success_rate = (results['passed_tests'] / results['total_tests'] * 100)
            print(f"Success rate: {success_rate:.1f}%")
        
        # Print summary by type
        if results.get('results_by_type'):
            print(f"\nRESULTS BY TYPE:")
            print("-" * 40)
            for test_type, summary in results['results_by_type'].items():
                print(f"\n{test_type.upper()}:")
                print(f"  Total: {summary['total_tests']}")
                print(f"  Passed: {summary['passed_tests']}")
                print(f"  Failed: {summary['failed_tests']}")
                print(f"  Success rate: {summary['success_rate']:.1f}%")
                
            # Print detailed failed test information for each type
            print(f"\n{'=' * 80}")
            for test_type, summary in results['results_by_type'].items():
                failed_count = summary.get('failed_tests', 0)
                if failed_count > 0:
                    runner = self.runners[TestType(test_type)]
                    runner.print_summary(summary)


def create_argument_parser():
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="NLWeb Test Dispatcher - Run different types of tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Types:
===========
1. end_to_end    - Full query-to-results tests via NLWebHandler
2. site_retrieval - Test get_sites functionality
3. query_retrieval - Test retrieval.search without LLM

File Formats:
=============
Test files should be JSON arrays with objects containing:
- test_type: Type of test (end_to_end, site_retrieval, query_retrieval)
- Other fields specific to each test type

Default Test Files:
==================
- end_to_end_tests.json - End-to-end test cases
- site_retrieval_tests.json - Site retrieval test cases  
- query_retrieval_tests.json - Query retrieval test cases

Examples:
=========
# Run all tests from a file
python run_tests.py --file all_tests.json

# Run only end-to-end tests from a file
python run_tests.py --file end_to_end_tests.json --type end_to_end

# Run a single end-to-end test
python run_tests.py --type end_to_end --query "pasta recipes" --site all

# Run a single site retrieval test
python run_tests.py --type site_retrieval --db azure_ai_search

# Run a single query retrieval test
python run_tests.py --type query_retrieval --query "chocolate cake" --db qdrant

# Run all default test files
python run_tests.py --all
        """)
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    
    mode_group.add_argument(
        '--file', '-f',
        type=str,
        help='JSON file containing test cases'
    )
    
    mode_group.add_argument(
        '--all',
        action='store_true',
        help='Run all default test files'
    )
    
    mode_group.add_argument(
        '--single',
        action='store_true',
        help='Run a single test (requires --type and test-specific args)'
    )
    
    # Test type selection
    parser.add_argument(
        '--type', '-t',
        type=str,
        choices=['end_to_end', 'site_retrieval', 'query_retrieval'],
        help='Test type (required for --single, optional for --file)'
    )
    
    # Common arguments for single tests
    parser.add_argument('--query', '-q', type=str, help='Query to test')
    parser.add_argument('--db', '-d', type=str, help='Retrieval backend')
    parser.add_argument('--site', '-s', type=str, default='all', help='Site to search')
    
    # End-to-end specific arguments
    parser.add_argument('--model', '-m', type=str, help='Model to use')
    parser.add_argument('--generate_mode', '-g', type=str, 
                       choices=['list', 'none', 'summarize', 'generate'],
                       help='Generation mode')
    parser.add_argument('--prev', '-p', nargs='*', default=[], help='Previous queries')
    parser.add_argument('--llm_provider', type=str, help='LLM provider')
    
    # Query retrieval specific arguments
    parser.add_argument('--top_k', '-k', type=int, default=10, help='Number of results')
    parser.add_argument('--min_score', type=float, help='Minimum score')
    
    # Output options
    parser.add_argument('--show_results', action='store_true', 
                       help='Show detailed results for single tests')
    
    # Mode override
    parser.add_argument(
        '--mode',
        choices=['development', 'production', 'testing'],
        default='testing',
        help='Application mode (default: testing)'
    )
    
    return parser


async def main():
    """Main entry point for test dispatcher."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Set application mode
    CONFIG.set_mode(args.mode)
    logger.info(f"Running in {args.mode} mode")
    
    dispatcher = TestDispatcher()
    
    try:
        if args.all:
            # Run all default test files
            test_files = [
                'end_to_end_tests.json',
                'site_retrieval_tests.json',
                'query_retrieval_tests.json'
            ]
            
            all_results = {
                'total_tests': 0,
                'passed_tests': 0,
                'failed_tests': 0,
                'results_by_type': {}
            }
            
            for test_file in test_files:
                file_path = Path(__file__).parent / test_file
                if file_path.exists():
                    logger.info(f"Running tests from {test_file}")
                    results = await dispatcher.run_test_file(str(file_path))
                    
                    # Aggregate results
                    for test_type, summary in results.get('results_by_type', {}).items():
                        all_results['results_by_type'][test_type] = summary
                        all_results['total_tests'] += summary['total_tests']
                        all_results['passed_tests'] += summary['passed_tests']
                        all_results['failed_tests'] += summary['failed_tests']
                else:
                    logger.warning(f"Test file not found: {test_file}")
                    
            dispatcher.print_aggregated_summary(all_results)
            
        elif args.file:
            # Run tests from specified file
            test_type = TestType(args.type) if args.type else None
            results = await dispatcher.run_test_file(args.file, test_type)
            
            if 'results_by_type' in results:
                dispatcher.print_aggregated_summary(results)
            else:
                # Single type results
                runner = dispatcher.runners[test_type]
                runner.print_summary(results)
                
        elif args.single:
            # Run single test
            if not args.type:
                parser.error("--type is required when using --single")
                
            test_type = TestType(args.type)
            
            # Build test case based on type
            test_case = {}
            
            if test_type == TestType.END_TO_END:
                if not args.query:
                    parser.error("--query is required for end_to_end tests")
                test_case['query'] = args.query
                test_case['site'] = args.site
                if args.model:
                    test_case['model'] = args.model
                if args.generate_mode:
                    test_case['generate_mode'] = args.generate_mode
                if args.db:
                    test_case['db'] = args.db
                if args.prev:
                    test_case['prev'] = args.prev
                if args.llm_provider:
                    test_case['llm_provider'] = args.llm_provider
                    
            elif test_type == TestType.SITE_RETRIEVAL:
                if not args.db:
                    parser.error("--db is required for site_retrieval tests")
                test_case['retrieval_backend'] = args.db
                
            elif test_type == TestType.QUERY_RETRIEVAL:
                if not args.query or not args.db:
                    parser.error("--query and --db are required for query_retrieval tests")
                test_case['query'] = args.query
                test_case['retrieval_backend'] = args.db
                test_case['site'] = args.site
                test_case['top_k'] = args.top_k
                if args.min_score is not None:
                    test_case['min_score'] = args.min_score
                    
            # Run the single test
            result = await dispatcher.run_single_test(test_type, test_case)
            
            # Print result
            print(f"\nTest Result: {'PASSED' if result.success else 'FAILED'}")
            if hasattr(result, 'result_count'):
                print(f"Results: {result.result_count}")
            if hasattr(result, 'site_count'):
                print(f"Sites: {result.site_count}")
            if hasattr(result, 'execution_time'):
                print(f"Execution time: {result.execution_time:.2f}s")
            if result.error:
                print(f"Error: {result.error}")
                
            # Show detailed results if requested
            if args.show_results:
                runner = dispatcher.runners[test_type]
                if hasattr(result, 'results') and result.results:
                    if hasattr(runner, 'print_detailed_results'):
                        runner.print_detailed_results(result.results)
                elif hasattr(result, 'sites') and result.sites:
                    print(f"Sites: {', '.join(result.sites)}")
                    
    except Exception as e:
        logger.exception(f"Error running tests: {e}")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())