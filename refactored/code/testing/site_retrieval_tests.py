# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Site retrieval test runner for NLWeb.

This module tests the get_sites functionality of the retrieval system.

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

logger = get_configured_logger("nlweb_site_retrieval_test")


@dataclass
class SiteRetrievalTestCase(TestCase):
    """Test case for site retrieval tests."""
    retrieval_backend: str
    expected_sites: Optional[List[str]] = None
    expected_min_sites: Optional[int] = None
    expected_max_sites: Optional[int] = None
    contains_sites: Optional[List[str]] = None
    excludes_sites: Optional[List[str]] = None


@dataclass 
class SiteRetrievalTestResult(TestResult):
    """Test result for site retrieval tests."""
    sites: List[str] = None
    site_count: int = 0
    
    def __post_init__(self):
        if self.sites is None:
            self.sites = []


class SiteRetrievalTestRunner(BaseTestRunner):
    """Test runner for site retrieval tests."""
    
    def __init__(self):
        """Initialize site retrieval test runner."""
        super().__init__(TestType.SITE_RETRIEVAL)
        
    def validate_test_case(self, test_case: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate site retrieval test case has required fields."""
        required_fields = ['retrieval_backend']
        missing_fields = [field for field in required_fields if field not in test_case or not test_case[field]]
        
        if missing_fields:
            return False, f"Missing required fields: {missing_fields}"
            
        # Validate expected_sites format if present
        if 'expected_sites' in test_case and test_case['expected_sites']:
            if not isinstance(test_case['expected_sites'], list):
                return False, "expected_sites must be a list"
                
        # Validate contains_sites format if present
        if 'contains_sites' in test_case and test_case['contains_sites']:
            if not isinstance(test_case['contains_sites'], list):
                return False, "contains_sites must be a list"
                
        # Validate excludes_sites format if present
        if 'excludes_sites' in test_case and test_case['excludes_sites']:
            if not isinstance(test_case['excludes_sites'], list):
                return False, "excludes_sites must be a list"
                
        return True, None
    
    async def run_single_test(self, test_case: Dict[str, Any]) -> SiteRetrievalTestResult:
        """Run a single site retrieval test."""
        start_time = time.time()
        
        # Create test case object
        site_case = SiteRetrievalTestCase(
            test_type=self.test_type,
            test_id=test_case.get('test_id', 0),
            original_case_num=test_case.get('original_case_num', 0),
            retrieval_backend=test_case.get('db', test_case.get('retrieval_backend')),
            expected_sites=test_case.get('expected_sites'),
            expected_min_sites=test_case.get('expected_min_sites'),
            expected_max_sites=test_case.get('expected_max_sites'),
            contains_sites=test_case.get('contains_sites'),
            excludes_sites=test_case.get('excludes_sites'),
            description=test_case.get('description', f"Site retrieval test for {test_case.get('retrieval_backend')}")
        )
        
        try:
            logger.info(f"Starting site retrieval test for backend: {site_case.retrieval_backend}")
            
            # Create VectorDBClient instance
            client = VectorDBClient(endpoint_name=site_case.retrieval_backend)
            
            # Get sites
            sites = await client.get_sites()
            site_count = len(sites)
            
            logger.info(f"Retrieved {site_count} sites from {site_case.retrieval_backend}")
            logger.debug(f"Sites: {sites}")
            
            # Validate results
            error = None
            success = True
            
            # Check exact match if expected_sites is provided
            if site_case.expected_sites is not None:
                if set(sites) != set(site_case.expected_sites):
                    error = f"Expected sites {site_case.expected_sites}, got {sites}"
                    success = False
                    
            # Check minimum site count
            if site_case.expected_min_sites is not None and site_count < site_case.expected_min_sites:
                error = f"Expected at least {site_case.expected_min_sites} sites, got {site_count}"
                success = False
                
            # Check maximum site count
            if site_case.expected_max_sites is not None and site_count > site_case.expected_max_sites:
                error = f"Expected at most {site_case.expected_max_sites} sites, got {site_count}"
                success = False
                
            # Check contains_sites
            if site_case.contains_sites:
                missing_sites = [s for s in site_case.contains_sites if s not in sites]
                if missing_sites:
                    error = f"Missing expected sites: {missing_sites}"
                    success = False
                    
            # Check excludes_sites
            if site_case.excludes_sites:
                unexpected_sites = [s for s in site_case.excludes_sites if s in sites]
                if unexpected_sites:
                    error = f"Found unexpected sites: {unexpected_sites}"
                    success = False
                    
            return SiteRetrievalTestResult(
                test_case=site_case,
                success=success,
                error=error,
                sites=sites,
                site_count=site_count,
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.exception(f"Error during site retrieval test: {e}")
            return SiteRetrievalTestResult(
                test_case=site_case,
                success=False,
                error=str(e),
                sites=[],
                site_count=0,
                execution_time=time.time() - start_time
            )
    
    def print_summary(self, summary: Dict[str, Any]) -> None:
        """Print test summary with site-specific details."""
        super().print_summary(summary)
        
        # Print successful tests with site details
        successful_results = [r for r in summary['results'] if r['success']]
        if successful_results:
            print(f"\nSUCCESSFUL TESTS:")
            print("-" * 40)
            for result in successful_results:
                print(f"Test {result['test_id']}: {result.get('description', 'No description')}")
                if 'site_count' in result:
                    print(f"  Sites found: {result['site_count']}")
                if 'sites' in result and result['sites']:
                    print(f"  Sites: {', '.join(result['sites'][:5])}")
                    if len(result['sites']) > 5:
                        print(f"         ... and {len(result['sites']) - 5} more")


async def main():
    """Main function for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Site retrieval test runner for NLWeb")
    parser.add_argument('--file', '-f', type=str, help='JSON file with test cases')
    parser.add_argument('--db', '-d', type=str, help='Retrieval backend to test')
    parser.add_argument('--expected_sites', nargs='*', help='Expected sites (exact match)')
    parser.add_argument('--min_sites', type=int, help='Minimum expected sites')
    parser.add_argument('--max_sites', type=int, help='Maximum expected sites')
    parser.add_argument('--contains', nargs='*', help='Sites that must be present')
    parser.add_argument('--excludes', nargs='*', help='Sites that must not be present')
    
    args = parser.parse_args()
    
    # Set testing mode
    CONFIG.set_mode('testing')
    
    runner = SiteRetrievalTestRunner()
    
    if args.file:
        # Run tests from file
        test_cases = runner.load_test_file(args.file)
        summary = await runner.run_tests(test_cases)
        runner.print_summary(summary)
    elif args.db:
        # Run single test
        test_case = {
            'retrieval_backend': args.db
        }
        
        if args.expected_sites:
            test_case['expected_sites'] = args.expected_sites
        if args.min_sites is not None:
            test_case['expected_min_sites'] = args.min_sites
        if args.max_sites is not None:
            test_case['expected_max_sites'] = args.max_sites
        if args.contains:
            test_case['contains_sites'] = args.contains
        if args.excludes:
            test_case['excludes_sites'] = args.excludes
            
        result = await runner.run_single_test(test_case)
        
        print(f"\nTest Result: {'PASSED' if result.success else 'FAILED'}")
        print(f"Sites found: {result.site_count}")
        if result.sites:
            print(f"Sites: {', '.join(result.sites)}")
        if result.error:
            print(f"Error: {result.error}")
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())