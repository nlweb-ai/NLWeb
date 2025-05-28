# NLWeb Testing Framework

This testing framework allows you to run system tests for NLWeb to validate query responses and system functionality. 

These commands should be run from the code directory.  

## Files

- `run_tests.py` - Main test runner script
- `tests.json` - Test case definitions in JSON format

## Usage

### Running Tests from JSON File

```bash
python -m testing.run_tests --file testing\tests.json
```

### Running Single Tests

```bash
# Basic single test (uses config defaults)
python -m testing.run_tests --query "give me spicy crunchy snacks"

# Single test with specific site
python -m testing.run_tests --query "give me spicy crunchy snacks" --site seriouseats

# Single test with all sites
python -m testing.run_tests --query "give me spicy crunchy snacks" --site all

# Single test with custom parameters
python -m testing.run_tests --query "give me spicy crunchy snacks" --site seriouseats --model gpt-4o --generate_mode summarize

# Single test with previous queries for context
python -m testing.run_tests --query "with more protein" --prev "give me spicy crunchy snacks" --site seriouseats

# Show detailed results (name, description, url, score)
python -m testing.run_tests --query "give me spicy crunchy snacks" --site seriouseats --show_results
```

### Testing Multiple Configurations

```bash
# Test all available LLM providers
python -m testing.run_tests --query "give me spicy crunchy snacks" --site seriouseats --llm_provider all

# Test all generation modes
python -m testing.run_tests --query "give me spicy crunchy snacks" --site seriouseats --generate_mode all

# Test all providers and all modes
python -m testing.run_tests --query "give me spicy crunchy snacks" --site seriouseats --llm_provider all --generate_mode all
```

### Running Example Test

```bash
python -m testing.run_tests --example
```

## Test JSON Format

The `tests.json` file should contain an array of test case objects with the following structure:

### Required Fields

- `query` (string) - The user query to test
- `prev` (string) - Previous queries for context, comma-separated or empty string
- `site` (string) - The site to search (e.g., "all", "seriouseats")
- `generate_mode` (string) - Generation mode ("list", "summarize", "generate")
- `db` (string) - Retrieval backend to use (e.g., "azure_ai_search_backup", "qdrant")

### Optional Fields

- `llm_provider` (string) - LLM provider to use ("openai", "anthropic", "gemini", "inception", or "all")
- `streaming` (string) - Ignored for tests (always set to false)

### Example JSON Structure

```json
[
  {
    "query": "spicy crunchy snacks",
    "prev": "",
    "site": "all",
    "generate_mode": "list",
    "streaming": "false",
    "db": "azure_ai_search_backup",
    "llm_provider": "all"
  },
  {
    "query": "with more protein",
    "prev": "spicy crunchy snacks",
    "site": "all", 
    "generate_mode": "list",
    "streaming": "false",
    "db": "azure_ai_search_backup",
    "llm_provider": "inception"
  },
  {
    "query": "I am vegetarian",
    "prev": "spicy crunchy snacks, with more protein",
    "site": "all",
    "generate_mode": "list",
    "streaming": "false",
    "db": "azure_ai_search_backup",
    "llm_provider": "openai"
  }
]
```

## Command Line Options

- `--file, -f` - Path to JSON file containing test cases
- `--query, -q` - Single query to test
- `--site, -s` - Site to search (default from config)
- `--model, -m` - Model to use (default from config)
- `--generate_mode, -g` - Generation mode ("list", "summarize", "generate", "all")
- `--retrieval_backend, --db, -d` - Retrieval backend to use
- `--prev, -p` - Previous queries for context (space-separated)
- `--llm_provider` - LLM provider override ("openai", "anthropic", "gemini", "inception", "all")
- `--llm_level` - LLM model level ("low", "high")
- `--show_results` - Show detailed results for single tests
- `--example` - Run a predefined example test

## Output

The test runner provides:

1. **Individual test results** - Shows success/failure and result count for each test
2. **Summary statistics** - Total tests, passed/failed counts, success rate
3. **Failed test details** - Lists failed tests with error messages
4. **Successful test details** - Lists passed tests with result counts

## Return Values

- `0 or positive integer` - Number of results found (success)
- `-1` - Error occurred during test execution

## Notes

- Tests run in non-streaming mode for consistent results
- Previous queries maintain conversation context across related tests
- LLM provider "all" expands to test all available configured providers
- Generate mode "all" tests list, summarize, and generate modes
- Default values are pulled from the NLWeb configuration files