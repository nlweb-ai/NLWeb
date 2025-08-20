#!/bin/bash

# Startup script for aiohttp server

# Get the base directory (where this script is located)
BASE_DIR="$(dirname "$0")"

# Load environment variables from set_keys.sh if it exists
if [ -f "$BASE_DIR/code/set_keys.sh" ]; then
    echo "Loading environment variables from set_keys.sh..."
    source "$BASE_DIR/code/set_keys.sh"
elif [ -f "$BASE_DIR/set_keys.sh" ]; then
    echo "Loading environment variables from set_keys.sh..."
    source "$BASE_DIR/set_keys.sh"
else
    echo "WARNING: set_keys.sh not found. API keys may not be configured."
fi

# Change to the application directory
cd "$BASE_DIR/code/python" || exit 1

echo "Python version:"
python --version

# Install required Python packages from requirements.txt
if [ -f "requirements.txt" ]; then
    echo "Installing packages from requirements.txt..."
    pip install -r requirements.txt
else
    echo "ERROR: requirements.txt not found!"
    echo "Please ensure requirements.txt exists in code/python/"
    exit 1
fi

# Verify critical packages are installed
echo "Verifying critical packages..."
python -c "import aiohttp; print(f'aiohttp version: {aiohttp.__version__}')" || exit 1

echo "Starting aiohttp server..."
python -m webserver.aiohttp_server
