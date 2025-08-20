#!/bin/bash

# Azure Web App startup script for aiohttp server
echo "Starting NLWeb application..."

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

# Start the aiohttp server
echo "Starting aiohttp server..."
python -m webserver.aiohttp_server