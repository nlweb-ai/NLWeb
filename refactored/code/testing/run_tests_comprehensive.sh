#!/bin/bash

# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

# Comprehensive test runner for NLWeb
# This script should be run from the code directory

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
PYTHON_CMD=${PYTHON_CMD:-python}
TEST_MODE="all"
VERBOSE=false

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "info")
            echo -e "${GREEN}[INFO]${NC} $message"
            ;;
        "error")
            echo -e "${RED}[ERROR]${NC} $message"
            ;;
        "warning")
            echo -e "${YELLOW}[WARNING]${NC} $message"
            ;;
    esac
}

# Function to show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -m, --mode MODE         Test mode: all, end_to_end, site_retrieval, query_retrieval (default: all)"
    echo "  -f, --file FILE         Run tests from specific file"
    echo "  -p, --python PYTHON     Python command to use (default: python)"
    echo "  -v, --verbose           Enable verbose output"
    echo "  --llm-provider PROVIDER Test with specific LLM provider or 'all'"
    echo "  --quick                 Run quick smoke tests only"
    echo ""
    echo "Examples:"
    echo "  $0                      # Run all tests"
    echo "  $0 -m end_to_end        # Run only end-to-end tests"
    echo "  $0 -f custom_tests.json # Run tests from custom file"
    echo "  $0 --llm-provider all   # Test all LLM providers"
    echo "  $0 --quick              # Run quick smoke tests"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -m|--mode)
            TEST_MODE="$2"
            shift 2
            ;;
        -f|--file)
            TEST_FILE="$2"
            shift 2
            ;;
        -p|--python)
            PYTHON_CMD="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --llm-provider)
            LLM_PROVIDER="$2"
            shift 2
            ;;
        --quick)
            QUICK_TEST=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Check if we're in the correct directory
if [ ! -f "testing/run_tests.py" ]; then
    print_status "error" "This script must be run from the code directory."
    echo "Please navigate to the code directory and run: ./testing/run_tests_comprehensive.sh"
    exit 1
fi

# Check if Python is available
if ! command -v $PYTHON_CMD &> /dev/null; then
    print_status "error" "Python not found at: $PYTHON_CMD"
    echo "Please ensure Python is installed and in your PATH, or specify with -p option"
    exit 1
fi

print_status "info" "Using Python: $PYTHON_CMD"
echo ""

# Function to run tests
run_tests() {
    local cmd="$1"
    local description="$2"
    
    echo "==============================================="
    echo "$description"
    echo "==============================================="
    
    if [ "$VERBOSE" = true ]; then
        print_status "info" "Command: $cmd"
    fi
    
    # Run the command
    if $cmd; then
        print_status "info" "✓ Test completed successfully"
        return 0
    else
        print_status "error" "✗ Test failed"
        return 1
    fi
    echo ""
}

# Track overall success
OVERALL_SUCCESS=true

# Quick smoke tests
if [ "$QUICK_TEST" = true ]; then
    print_status "info" "Running quick smoke tests..."
    
    # Quick end-to-end test
    if ! run_tests "$PYTHON_CMD -m testing.run_tests --single --type end_to_end --query 'pasta recipes'" "Quick End-to-End Test"; then
        OVERALL_SUCCESS=false
    fi
    
    # Quick site retrieval test
    if ! run_tests "$PYTHON_CMD -m testing.run_tests --single --type site_retrieval --db azure_ai_search" "Quick Site Retrieval Test"; then
        OVERALL_SUCCESS=false
    fi
    
    # Quick query retrieval test
    if ! run_tests "$PYTHON_CMD -m testing.run_tests --single --type query_retrieval --query 'chocolate cake' --db azure_ai_search" "Quick Query Retrieval Test"; then
        OVERALL_SUCCESS=false
    fi
    
elif [ ! -z "$TEST_FILE" ]; then
    # Run tests from specific file
    cmd="$PYTHON_CMD -m testing.run_tests --file $TEST_FILE"
    if [ ! -z "$LLM_PROVIDER" ]; then
        # Note: When using file mode with LLM provider, it needs to be in the JSON
        print_status "warning" "LLM provider should be specified in the test file when using --file mode"
    fi
    if ! run_tests "$cmd" "Running tests from $TEST_FILE"; then
        OVERALL_SUCCESS=false
    fi
    
else
    # Run based on mode
    case $TEST_MODE in
        "all")
            if ! run_tests "$PYTHON_CMD -m testing.run_tests --all" "Running all test types"; then
                OVERALL_SUCCESS=false
            fi
            ;;
        "end_to_end")
            cmd="$PYTHON_CMD -m testing.run_tests --file testing/end_to_end_tests.json --type end_to_end"
            if ! run_tests "$cmd" "Running End-to-End tests"; then
                OVERALL_SUCCESS=false
            fi
            ;;
        "site_retrieval")
            cmd="$PYTHON_CMD -m testing.run_tests --file testing/site_retrieval_tests.json --type site_retrieval"
            if ! run_tests "$cmd" "Running Site Retrieval tests"; then
                OVERALL_SUCCESS=false
            fi
            ;;
        "query_retrieval")
            cmd="$PYTHON_CMD -m testing.run_tests --file testing/query_retrieval_tests.json --type query_retrieval"
            if ! run_tests "$cmd" "Running Query Retrieval tests"; then
                OVERALL_SUCCESS=false
            fi
            ;;
        *)
            print_status "error" "Unknown test mode: $TEST_MODE"
            usage
            exit 1
            ;;
    esac
fi

# Final summary
echo ""
echo "==============================================="
if [ "$OVERALL_SUCCESS" = true ]; then
    print_status "info" "All tests completed successfully! ✓"
    echo "==============================================="
    exit 0
else
    print_status "error" "Some tests failed. Please check the output above."
    echo "==============================================="
    exit 1
fi