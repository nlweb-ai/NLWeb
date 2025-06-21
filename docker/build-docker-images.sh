#!/bin/bash
# Script to build Docker images for NLWeb

# Exit on error
set -e

# Enable verbose output
set -x

# Navigate to the project root directory (one level up from docker folder)
cd "$(dirname "$0")/.."
ROOT_DIR=$(pwd)
echo "Building from root directory: $ROOT_DIR"

# Check if we need to use sudo for docker commands
DOCKER_CMD="docker"
if ! docker info > /dev/null 2>&1; then
    echo "Using sudo for Docker commands..."
    DOCKER_CMD="sudo docker"
fi

# Verify requirements file exists
if [ ! -f "$ROOT_DIR/code/requirements.txt" ]; then
    echo "ERROR: requirements.txt not found at $ROOT_DIR/code/requirements.txt"
    exit 1
fi

# Build the base image
echo "Building NLWeb base image..."
$DOCKER_CMD build -t nlweb-base:latest -f docker/Dockerfile.base .

# Verify base image was created
if ! $DOCKER_CMD image inspect nlweb-base:latest > /dev/null 2>&1; then
    echo "ERROR: Failed to build nlweb-base:latest"
    exit 1
else
    echo "✅ Successfully built nlweb-base:latest"
fi

# Build the application image
echo "Building NLWeb application image..."
$DOCKER_CMD build -t nlweb:latest -f docker/Dockerfile.app .

# Build the development container image
echo "Building NLWeb development image..."
$DOCKER_CMD build --no-cache -t nlweb-dev:latest -f docker/Dockerfile.dev .

# Clean up any unintended or duplicate tags
echo "Cleaning up unused tags..."
if $DOCKER_CMD images | grep "nlweb-dev" | grep "base" > /dev/null; then
    echo "Removing unneeded nlweb-dev:base image..."
    $DOCKER_CMD rmi nlweb-dev:base || true
fi

# List the images we've built
echo "Docker images created:"
$DOCKER_CMD images | grep nlweb

echo "All images built successfully!"
echo "You can now use:"
echo "  - nlweb:latest for running the application"
echo "  - nlweb-dev:latest for development containers"
