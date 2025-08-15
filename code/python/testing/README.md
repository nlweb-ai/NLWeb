# NLWeb Testing Framework

This testing framework provides a modular system for testing different aspects of NLWeb functionality. It supports three types of tests: end-to-end query tests, site retrieval tests, and query retrieval tests.

These commands should be run from the code/python directory.

## Architecture

The testing framework consists of:

- `run_tests.py` - Main test dispatcher that routes tests to appropriate runners
- `base_test_runner.py` - Base class providing shared functionality for all test types
- `end_to_end_tests.py` - Tests the full query-to-results pipeline
- `site_retrieval_tests.py` - Tests the `get_sites` functionality
- `query_retrieval_tests.py` - Tests the retrieval search without LLM processing

## Test Files

- `end_to_end_tests.json` - End-to-end test cases
- `site_retrieval_tests.json` - Site retrieval test cases
- `query_retrieval_tests.json` - Query retrieval test cases
- `all_tests_example.json` - Example file showing all test types

## Quick Start - Test Scripts

The testing framework includes convenient shell scripts for running tests:

### Simple Test Runner - `run_all_tests.sh` (Linux/Mac) / `run_all_tests.bat` (Windows)

The simplest way to run all tests:

```bash
# Linux/Mac
cd code/python
./testing/run_all_tests.sh

# Windows
cd code\python
testing\run_all_tests.bat
```

This script runs all test types and provides a simple pass/fail summary.

### Advanced Test Runner - `run_tests_comprehensive.sh` (Linux/Mac)

For more control over test execution:

```bash
# Run from code/python directory

# Run all tests (default)
./testing/run_tests_comprehensive.sh

# Run only specific test types
./testing/run_tests_comprehensive.sh -m end_to_end       # Only end-to-end tests
./testing/run_tests_comprehensive.sh -m site_retrieval   # Only site retrieval tests
./testing/run_tests_comprehensive.sh -m query_retrieval  # Only query retrieval tests

# Run quick smoke tests (minimal set for rapid validation)
./testing/run_tests_comprehensive.sh --quick

# Run tests from a custom file
./testing/run_tests_comprehensive.sh -f testing/custom_tests.json

# Use specific Python version
./testing/run_tests_comprehensive.sh -p python3.11

# Enable verbose output (shows actual commands)
./testing/run_tests_comprehensive.sh -v

# Combine options
./testing/run_tests_comprehensive.sh -m end_to_end -p python3.11 -v

# Show help
./testing/run_tests_comprehensive.sh -h
```

Features of the comprehensive script:
- **Colored output**: Green for success, red for errors, yellow for warnings
- **Mode selection**: Run only specific test types
- **Quick tests**: Minimal smoke tests for rapid validation
- **Python version control**: Specify which Python to use
- **Verbose mode**: See actual commands being executed
- **Exit codes**: Proper exit codes for CI/CD integration

## Usage

### Running All Default Test Files

```bash
python -m testing.run_tests --all
```

### Running Tests from a Specific File

```bash
# Run all tests in a file (auto-detects test types)
python -m testing.run_tests --file testing/all_tests_example.json

# Run only specific test type from a file
python -m testing.run_tests --file testing/end_to_end_tests.json --type end_to_end
```

### Running Single Tests

#### End-to-End Tests
```bash
# Basic end-to-end test
python -m testing.run_tests --single --type end_to_end --query "pasta recipes"

# With specific parameters
python -m testing.run_tests --single --type end_to_end --query "pasta recipes" --site seriouseats --model gpt-4o --generate_mode summarize

# With previous queries for context
python -m testing.run_tests --single --type end_to_end --query "with more protein" --prev "pasta recipes"

# Show detailed results
python -m testing.run_tests --single --type end_to_end --query "pasta recipes" --show_results

# Test all available LLM providers
python -m testing.run_tests --single --type end_to_end --query "pasta recipes" --llm_provider all

# Test specific LLM provider with high-level model
python -m testing.run_tests --single --type end_to_end --query "pasta recipes" --llm_provider anthropic --llm_level high
```

#### Site Retrieval Tests
```bash
# Test site retrieval from a backend
python -m testing.run_tests --single --type site_retrieval --db azure_ai_search

# Show retrieved sites
python -m testing.run_tests --single --type site_retrieval --db qdrant --show_results
```

#### Query Retrieval Tests
```bash
# Test retrieval search
python -m testing.run_tests --single --type query_retrieval --query "chocolate cake" --db azure_ai_search

# With custom parameters
python -m testing.run_tests --single --type query_retrieval --query "vegetarian recipes" --db qdrant --site all --top_k 20 --min_score 0.7

# Show detailed retrieval results
python -m testing.run_tests --single --type query_retrieval --query "pasta" --db azure_ai_search --show_results
```

## Test JSON Format

All test files use JSON arrays with objects containing a `test_type` field and type-specific fields.

### End-to-End Test Format

```json
{
  "test_type": "end_to_end",
  "description": "Test full pipeline",
  "query": "pasta recipes",
  "prev": "",
  "site": "all",
  "generate_mode": "list",
  "db": "azure_ai_search",
  "llm_provider": "openai",
  "expected_min_results": 1,
  "expected_max_results": 10
}
```

#### Fields:
- `test_type` (required) - Must be "end_to_end"
- `query` (required) - The user query to test
- `prev` (optional) - Previous queries for context (string, comma-separated or empty)
- `site` (optional) - Site to search (default: "all")
- `generate_mode` (optional) - Generation mode: "list", "summarize", "generate" (default: "list")
- `db` (optional) - Retrieval backend (default: from config)
- `llm_provider` (optional) - LLM provider or "all" to test all providers (default: from config_llm.yaml preferred_endpoint, currently "azure_openai")
- `expected_min_results` (optional) - Minimum expected results
- `expected_max_results` (optional) - Maximum expected results

### Site Retrieval Test Format

```json
{
  "test_type": "site_retrieval",
  "description": "Test get_sites functionality",
  "retrieval_backend": "azure_ai_search",
  "expected_min_sites": 1,
  "expected_max_sites": 100,
  "contains_sites": ["all", "seriouseats"],
  "excludes_sites": ["invalid_site"]
}
```

#### Fields:
- `test_type` (required) - Must be "site_retrieval"
- `retrieval_backend` (required) - Backend to test
- `expected_sites` (optional) - Exact list of expected sites
- `expected_min_sites` (optional) - Minimum number of sites
- `expected_max_sites` (optional) - Maximum number of sites
- `contains_sites` (optional) - Sites that must be present
- `excludes_sites` (optional) - Sites that must not be present

### Query Retrieval Test Format

```json
{
  "test_type": "query_retrieval",
  "description": "Test retrieval search",
  "query": "chocolate cake recipe",
  "retrieval_backend": "qdrant",
  "site": "all",
  "top_k": 10,
  "expected_min_results": 5,
  "min_score": 0.6
}
```

#### Fields:
- `test_type` (required) - Must be "query_retrieval"
- `query` (required) - Search query
- `retrieval_backend` (required) - Backend to test
- `site` (optional) - Site to search (default: "all")
- `top_k` (optional) - Number of results to retrieve (default: 10)
- `expected_min_results` (optional) - Minimum expected results
- `expected_max_results` (optional) - Maximum expected results
- `min_score` (optional) - Minimum acceptable relevance score

## Command Line Options

### Mode Selection
- `--all` - Run all default test files
- `--file, -f` - Path to JSON file containing test cases
- `--single` - Run a single test (requires --type)

### Test Type
- `--type, -t` - Test type: "end_to_end", "site_retrieval", "query_retrieval"

### Common Parameters
- `--query, -q` - Query to test
- `--db, -d` - Retrieval backend
- `--site, -s` - Site to search (default: "all")
- `--show_results` - Show detailed results

### End-to-End Specific
- `--model, -m` - LLM model to use
- `--generate_mode, -g` - Generation mode
- `--prev, -p` - Previous queries (space-separated)
- `--llm_provider` - LLM provider or "all"

### Query Retrieval Specific
- `--top_k, -k` - Number of results (default: 10)
- `--min_score` - Minimum relevance score

### Other Options
- `--mode` - Application mode: "development", "production", "testing" (default: "testing")

## Output

The test runner provides:

1. **Individual test results** - Shows pass/fail status with relevant metrics
2. **Type-specific details** - Result counts, execution times, site lists, etc.
3. **Summary statistics** - Total tests, passed/failed counts, success rates
4. **Aggregated summaries** - When running multiple test types

### Example Output

```
Running in testing mode

TEST SUMMARY - SITE_RETRIEVAL
================================================================================
Total tests: 4
Passed: 4
Failed: 0
Success rate: 100.0%

SUCCESSFUL TESTS:
----------------------------------------
Test 1: Test get_sites from Azure AI Search
  Sites found: 5
  Sites: all, seriouseats, wikipedia, github, medium

OVERALL TEST SUMMARY
================================================================================
Total tests: 12
Passed: 11
Failed: 1
Success rate: 91.7%

RESULTS BY TYPE:
----------------------------------------

END_TO_END:
  Total: 3
  Passed: 2
  Failed: 1
  Success rate: 66.7%

SITE_RETRIEVAL:
  Total: 4
  Passed: 4
  Failed: 0
  Success rate: 100.0%

QUERY_RETRIEVAL:
  Total: 5
  Passed: 5
  Failed: 0
  Success rate: 100.0%
```

## Notes

- Tests run in non-streaming mode for consistent results
- The `llm_provider: "all"` option expands to test all available providers
- Default values are pulled from the NLWeb configuration files
- Each test type has its own validation and result structure
- Execution times are tracked for performance monitoring
- Test files can mix different test types in a single file