#!/bin/bash

# Script to create a Dockerfile that properly builds hnswlib
echo "Creating Dockerfile with hnswlib support..."

cat > Dockerfile.hnswlib << 'EOF'
# Use Python 3.11 as base (3.12 also works, but 3.11 is more stable)
FROM python:3.11-slim

# Install build dependencies required for hnswlib
# g++ is essential for compiling hnswlib
RUN apt-get update && apt-get install -y \
    g++ \
    gcc \
    make \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file first (for better Docker layer caching)
COPY code/python/requirements.txt /app/requirements.txt

# Install Python dependencies including hnswlib
# This will compile hnswlib from source using the g++ we just installed
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY code/ /app/code/
COPY static/ /app/static/
COPY config/ /app/config/

# Copy the HNSW index data
COPY code/python/data/hnswlib /app/code/python/data/hnswlib

# Set environment variables
ENV PYTHONPATH=/app/code/python:$PYTHONPATH
ENV NLWEB_OUTPUT_DIR=/app
ENV PORT=8000
ENV NLWEB_CONFIG_DIR=/app/config

# Change to Python directory
WORKDIR /app/code/python

# Verify hnswlib is installed correctly
RUN python -c "import hnswlib; print('hnswlib version:', hnswlib.__version__)"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run as non-root user for security
RUN useradd -m -u 1000 nlweb && chown -R nlweb:nlweb /app
USER nlweb

# Start the aiohttp server
CMD ["python", "-m", "webserver.aiohttp_server"]
EOF

echo "Dockerfile.hnswlib created successfully!"
echo ""
echo "To build and test locally:"
echo "  docker build -f Dockerfile.hnswlib -t nlweb-hnswlib ."
echo "  docker run -p 8000:8000 --env-file .env nlweb-hnswlib"
echo ""
echo "To deploy to Azure Container Registry:"
echo "  az acr build --registry <your-registry> --image nlweb-hnswlib:latest -f Dockerfile.hnswlib ."
echo ""
echo "To deploy to Azure Container Apps:"
echo "  az containerapp create --name nlweb-app --resource-group <rg-name> \\"
echo "    --image <your-registry>.azurecr.io/nlweb-hnswlib:latest \\"
echo "    --target-port 8000 --ingress external --query properties.configuration.ingress.fqdn"