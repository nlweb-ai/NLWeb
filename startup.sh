#!/bin/bash

# Azure Web App startup script for aiohttp server
echo "Starting NLWeb application..."

# Set Python path
export PYTHONPATH=/home/site/wwwroot:$PYTHONPATH

# Set pip cache directory for persistence across restarts
export PIP_CACHE_DIR=/home/site/wwwroot/.pip-cache
mkdir -p $PIP_CACHE_DIR

# Navigate to app directory
cd /home/site/wwwroot

# Load environment variables from set_keys.sh if it exists
if [ -f "code/set_keys.sh" ]; then
    echo "Loading environment variables..."
    source code/set_keys.sh
fi

# Navigate to Python directory
cd code/python || exit 1

# Check Python version once
PYTHON_VERSION=$(python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
echo "Python version: $PYTHON_VERSION"

# Quick check if main packages are already installed
PACKAGES_INSTALLED=true
python -c "import aiohttp, openai, azure.search.documents" 2>/dev/null || PACKAGES_INSTALLED=false

if [ "$PACKAGES_INSTALLED" = "false" ] && [ -f requirements.txt ]; then
    echo "Installing Python dependencies (this may take a moment on first run)..."
    
    # Install all dependencies except chroma-hnswlib quietly
    grep -v "chroma-hnswlib" requirements.txt > requirements_temp.txt
    pip install -q --cache-dir=$PIP_CACHE_DIR -r requirements_temp.txt
    
    # Install chroma-hnswlib from prebuilt wheel based on Python version
    echo "Installing chroma-hnswlib..."
    if [[ "$PYTHON_VERSION" == "3.11" ]]; then
        pip install -q --cache-dir=$PIP_CACHE_DIR \
            https://files.pythonhosted.org/packages/c7/2d/d5663e134436e5933bc63516a20b5edc08b4c1b1588b9680908a5f1afd04/chroma_hnswlib-0.7.6-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
    elif [[ "$PYTHON_VERSION" == "3.12" ]]; then
        pip install -q --cache-dir=$PIP_CACHE_DIR \
            https://files.pythonhosted.org/packages/20/41/1a0c96de5e4f7d091c3b68ad31c4797c60c97e6b12e1e96f228c24fa88e0/chroma_hnswlib-0.7.6-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
    else
        pip install -q --cache-dir=$PIP_CACHE_DIR chroma-hnswlib
    fi
    
    rm -f requirements_temp.txt
    echo "Dependencies installed successfully."
else
    echo "Dependencies already installed, skipping pip install."
fi

# Quick verification without verbose output
python -c "import aiohttp" || { echo "ERROR: aiohttp not installed"; exit 1; }

# Start the aiohttp server
echo "Starting aiohttp server on port 8000..."
python -m webserver.aiohttp_server