#!/bin/bash

# Startup script for aiohttp server

# Change to the application directory
cd "$(dirname "$0")/code/python" || exit 1

echo "Python version:"
python --version

# Check if we should use aiohttp server (default) or legacy server
USE_AIOHTTP="${USE_AIOHTTP:-true}"

if [ "$USE_AIOHTTP" = "true" ]; then
    echo "Starting aiohttp server..."
    python -m webserver.aiohttp_server
else
    echo "Starting legacy server..."
    python -m webserver.WebServer
fi