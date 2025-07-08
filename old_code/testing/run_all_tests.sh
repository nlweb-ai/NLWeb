#!/bin/bash

# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

# Script to run all NLWeb tests
# This script should be run from the code directory

echo "==============================================="
echo "Running NLWeb Test Suite"
echo "==============================================="
echo ""

# Check if we're in the correct directory
if [ ! -f "testing/run_tests.py" ]; then
    echo "Error: This script must be run from the code directory."
    echo "Please navigate to the code directory and run: ./testing/run_all_tests.sh"
    exit 1
fi

# Set default Python command
PYTHON_CMD=${PYTHON_CMD:-python}

# Check if Python is available
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "Error: Python not found. Please ensure Python is installed and in your PATH."
    exit 1
fi

echo "Using Python: $PYTHON_CMD"
echo ""

# Run all default test files
echo "Running all test types..."
echo "----------------------------------------"
$PYTHON_CMD -m testing.run_tests --all

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "==============================================="
    echo "All tests completed successfully!"
    echo "==============================================="
else
    echo ""
    echo "==============================================="
    echo "Tests completed with errors. Please check the output above."
    echo "==============================================="
    exit 1
fi