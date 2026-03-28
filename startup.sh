#!/bin/bash

# Azure Web App startup script for aiohttp server
echo "Starting NLWeb application..."

# Set Python path
export PYTHONPATH=/home/site/wwwroot:$PYTHONPATH

# Ensure Python output is unbuffered for immediate log visibility
export PYTHONUNBUFFERED=1

# Set pip cache directory for persistence across restarts
export PIP_CACHE_DIR=/home/site/wwwroot/.pip-cache
mkdir -p "$PIP_CACHE_DIR"

# Navigate to app directory
cd /home/site/wwwroot

# Load environment variables from set_keys.sh if it exists
if [ -f "AskAgent/set_keys.sh" ]; then
    echo "Loading environment variables..."
    source AskAgent/set_keys.sh
fi

# Navigate to Python directory
cd AskAgent/python || exit 1

# Check Python version once
PYTHON_VERSION=$(python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
echo "Python version: $PYTHON_VERSION"

# Quick check if main packages are already installed
PACKAGES_INSTALLED=true
python -c "import aiohttp, openai, azure.search.documents" 2>/dev/null || PACKAGES_INSTALLED=false

if [ "$PACKAGES_INSTALLED" = "false" ] && [ -f requirements.txt ]; then
    echo "Installing Python dependencies (this may take a moment on first run)..."
    
    if pip install -q --cache-dir="$PIP_CACHE_DIR" -r requirements.txt; then
        echo "Dependencies installed successfully."
    else
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi
else
    echo "Dependencies already installed, skipping pip install."
fi

# Quick verification without verbose output
python -c "import aiohttp" || { echo "ERROR: aiohttp not installed"; exit 1; }

# Start the aiohttp server
echo "Starting aiohttp server on port 8000..."
python -m webserver.aiohttp_server