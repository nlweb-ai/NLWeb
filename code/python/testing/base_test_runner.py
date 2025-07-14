# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Base test runner module for NLWeb testing framework.

This module provides the base functionality shared across different test types.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG
from core.llm import get_available_providers

logger = get_configured_logger("nlweb_base_test")


class TestType(Enum):
    """Enumeration of test types."""
    END_TO_END = "end_to_end"
    SITE_RETRIEVAL = "site_retrieval"
    QUERY_RETRIEVAL = "query_retrieval"


@dataclass
class TestCase:
    """Base test case data structure."""
    test_type: TestType
    test_id: int
    original_case_num: int
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert test case to dictionary."""
        return {
            'test_type': self.test_type.value,
            'test_id': self.test_id,
            'original_case_num': self.original_case_num,
            'description': self.description
        }


@dataclass
class TestResult:
    """Base test result data structure."""
    test_case: TestCase
    success: bool
    error: Optional[str] = None
    execution_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert test result to dictionary."""
        result_dict = {
            **self.test_case.to_dict(),
            'success': self.success,
            'error': self.error,
            'execution_time': self.execution_time
        }
        
        # Add all additional attributes from the test case
        if hasattr(self.test_case, '__dict__'):
            for key, value in self.test_case.__dict__.items():
                if key not in result_dict and not key.startswith('_'):
                    result_dict[key] = value
                    
        # Add all additional attributes from the result
        for key, value in self.__dict__.items():
            if key not in ['test_case', 'success', 'error', 'execution_time'] and not key.startswith('_'):
                result_dict[key] = value
                
        return result_dict


class BaseTestRunner(ABC):
    """Abstract base class for test runners."""
    
    def __init__(self, test_type: TestType):
        """Initialize base test runner."""
        self.test_type = test_type
        self.logger = get_configured_logger(f"nlweb_{test_type.value}_test")
        
    @abstractmethod
    async def run_single_test(self, test_case: Dict[str, Any]) -> TestResult:
        """
        Run a single test case.
        
        Args:
            test_case: Dictionary containing test case data
            
        Returns:
            TestResult object
        """
        pass
    
    @abstractmethod
    def validate_test_case(self, test_case: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a test case has required fields.
        
        Args:
            test_case: Dictionary containing test case data
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    def load_test_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load test cases from JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            List of test case dictionaries
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If JSON is invalid
        """
        self.logger.info(f"Loading test cases from: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                test_cases = json.load(f)
                
            if not isinstance(test_cases, list):
                raise ValueError("JSON file must contain an array of test cases")
                
            # Filter test cases by type if test_type field exists
            filtered_cases = []
            for case in test_cases:
                if 'test_type' in case:
                    if case['test_type'] == self.test_type.value:
                        filtered_cases.append(case)
                else:
                    # If no test_type field, include all cases (backward compatibility)
                    filtered_cases.append(case)
                    
            self.logger.info(f"Loaded {len(filtered_cases)} test cases of type {self.test_type.value}")
            return filtered_cases
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Test file not found: {file_path}")
        except Exception as e:
            raise ValueError(f"Error loading test file: {e}")
    
    async def run_tests(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run multiple test cases and return summary.
        
        Args:
            test_cases: List of test case dictionaries
            
        Returns:
            Dictionary with test summary and results
        """
        results = []
        passed = 0
        failed = 0
        
        self.logger.info(f"Running {len(test_cases)} tests of type {self.test_type.value}")
        
        for idx, test_case in enumerate(test_cases, 1):
            # Validate test case
            is_valid, error_msg = self.validate_test_case(test_case)
            
            if not is_valid:
                self.logger.error(f"Invalid test case {idx}: {error_msg}")
                result = TestResult(
                    test_case=TestCase(
                        test_type=self.test_type,
                        test_id=idx,
                        original_case_num=test_case.get('original_case_num', idx)
                    ),
                    success=False,
                    error=f"Validation error: {error_msg}"
                )
                failed += 1
            else:
                # Run the test
                try:
                    result = await self.run_single_test(test_case)
                    if result.success:
                        passed += 1
                    else:
                        failed += 1
                except Exception as e:
                    self.logger.exception(f"Error running test {idx}: {e}")
                    result = TestResult(
                        test_case=TestCase(
                            test_type=self.test_type,
                            test_id=idx,
                            original_case_num=test_case.get('original_case_num', idx)
                        ),
                        success=False,
                        error=str(e)
                    )
                    failed += 1
                    
            results.append(result)
            
        # Generate summary
        summary = {
            'test_type': self.test_type.value,
            'total_tests': len(test_cases),
            'passed_tests': passed,
            'failed_tests': failed,
            'success_rate': (passed / len(test_cases) * 100) if len(test_cases) > 0 else 0,
            'results': [r.to_dict() for r in results]
        }
        
        return summary
    
    def print_summary(self, summary: Dict[str, Any]) -> None:
        """Print test summary in a formatted way."""
        print(f"\n{'=' * 80}")
        print(f"TEST SUMMARY - {summary['test_type'].upper()}")
        print(f"{'=' * 80}")
        print(f"Total tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Success rate: {summary['success_rate']:.1f}%")
        
        # Print failed tests with detailed information
        failed_results = [r for r in summary['results'] if not r['success']]
        if failed_results:
            print(f"\nFAILED TESTS ({len(failed_results)} total):")
            print("=" * 80)
            
            for idx, result in enumerate(failed_results, 1):
                print(f"\n[{idx}] Test {result['test_id']} (Original case #{result.get('original_case_num', result['test_id'])})")
                print("-" * 60)
                
                # Print test description
                print(f"Description: {result.get('description', 'No description')}")
                
                # Print test parameters based on test type
                if result['test_type'] == 'end_to_end':
                    if 'query' in result:
                        print(f"Query: {result['query']}")
                    if 'site' in result:
                        print(f"Site: {result['site']}")
                    if 'llm_provider' in result:
                        print(f"LLM Provider: {result['llm_provider']}")
                    if 'model' in result:
                        print(f"Model: {result['model']}")
                    if 'generate_mode' in result:
                        print(f"Generate Mode: {result['generate_mode']}")
                    if 'retrieval_backend' in result:
                        print(f"Retrieval Backend: {result['retrieval_backend']}")
                    if 'prev' in result and result['prev']:
                        print(f"Previous queries: {result['prev']}")
                        
                elif result['test_type'] == 'site_retrieval':
                    if 'retrieval_backend' in result:
                        print(f"Retrieval Backend: {result['retrieval_backend']}")
                        
                elif result['test_type'] == 'query_retrieval':
                    if 'query' in result:
                        print(f"Query: {result['query']}")
                    if 'retrieval_backend' in result:
                        print(f"Retrieval Backend: {result['retrieval_backend']}")
                    if 'site' in result:
                        print(f"Site: {result['site']}")
                    if 'num_results' in result:
                        print(f"Num Results: {result['num_results']}")
                    elif 'top_k' in result:  # Backwards compatibility
                        print(f"Top K: {result['top_k']}")
                    if 'min_score' in result:
                        print(f"Min Score: {result['min_score']}")
                
                # Print error details
                print(f"\nError: {result['error']}")
                
                # Print execution time if available
                if 'execution_time' in result and result['execution_time'] is not None:
                    print(f"Execution time: {result['execution_time']:.2f}s")
                
                # Show additional details based on test type
                if result['test_type'] == 'end_to_end':
                    if 'result_count' in result:
                        print(f"Results received: {result['result_count']}")
                    if 'expected_min_results' in result and result['expected_min_results'] is not None:
                        print(f"Expected min results: {result['expected_min_results']}")
                    if 'expected_max_results' in result and result['expected_max_results'] is not None:
                        print(f"Expected max results: {result['expected_max_results']}")
                        
                elif result['test_type'] == 'site_retrieval':
                    if 'site_count' in result:
                        print(f"Sites found: {result['site_count']}")
                    if 'sites' in result and result['sites']:
                        print(f"Sites: {', '.join(result['sites'][:10])}")
                        if len(result['sites']) > 10:
                            print(f"  ... and {len(result['sites']) - 10} more")
                            
                elif result['test_type'] == 'query_retrieval':
                    if 'result_count' in result:
                        print(f"Results retrieved: {result['result_count']}")
                    if 'expected_min_results' in result and result['expected_min_results'] is not None:
                        print(f"Expected min results: {result['expected_min_results']}")
                
            print("\n" + "=" * 80)
                
    def expand_test_cases_for_providers(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Expand test cases that have llm_provider: "all" to test all available providers.
        
        Args:
            test_cases: Original test cases
            
        Returns:
            Expanded list of test cases
        """
        expanded_cases = []
        
        for case_num, case in enumerate(test_cases, 1):
            llm_provider = case.get('llm_provider', '').strip() if case.get('llm_provider') else None
            
            if llm_provider == 'all':
                # Expand to test all available providers
                available_providers = get_available_providers()
                if not available_providers:
                    self.logger.warning(f"No LLM providers available for test case {case_num}")
                    available_providers = [None]  # Use default
                
                for provider in available_providers:
                    expanded_case = case.copy()
                    expanded_case['original_case_num'] = case_num
                    expanded_case['llm_provider'] = provider
                    expanded_cases.append(expanded_case)
            else:
                # Single test case
                case['original_case_num'] = case_num
                expanded_cases.append(case)
                
        return expanded_cases