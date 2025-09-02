#!/bin/bash

# Azure Web App startup script with build tools installation for hnswlib
echo "Starting NLWeb application with build tools setup..."

# Install build-essential if not present (needed for hnswlib)
echo "Checking for C++ compiler..."
if ! command -v g++ &> /dev/null; then
    echo "Installing build tools for hnswlib..."
    apt-get update && apt-get install -y g++ build-essential
    echo "Build tools installed."
else
    echo "C++ compiler already available."
fi

# Set Python path
export PYTHONPATH=/home/site/wwwroot:$PYTHONPATH

# Navigate to app directory
cd /home/site/wwwroot

# Load environment variables from set_keys.sh if it exists
if [ -f "code/set_keys.sh" ]; then
    echo "Loading environment variables from set_keys.sh..."
    source code/set_keys.sh
fi

# Navigate to Python directory
cd code/python || exit 1

echo "Python version:"
python --version

# Install dependencies if requirements.txt exists
if [ -f requirements.txt ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
fi

# Verify critical packages are installed
echo "Verifying critical packages..."
python -c "import aiohttp; print(f'aiohttp version: {aiohttp.__version__}')" || exit 1

# Try to verify hnswlib
echo "Checking hnswlib installation..."
python -c "import hnswlib; print('hnswlib is installed successfully')" || echo "Warning: hnswlib not available, HNSW features will be disabled"

# Start the aiohttp server
echo "Starting aiohttp server..."
python -m webserver.aiohttp_server