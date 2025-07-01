# Milvus Configuration Guide

## Overview

This guide explains how to configure and connect to Milvus vector database in different deployment scenarios.

## Environment Variables

Configure your Milvus connection using these environment variables:

- `MILVUS_ENDPOINT`: The connection endpoint for your Milvus instance
- `MILVUS_TOKEN`: (Optional) Authentication token for secure connections

## Deployment Options

### 1. Milvus Lite (Local Development)
- **Best for**: Development, testing, and small datasets
- **Setup**: Set `MILVUS_ENDPOINT` to a local file path (e.g., `./milvus.db`)
- **Features**:
  - [Milvus Lite](https://milvus.io/docs/milvus_lite.md) is a vector database that runs directly in Python
  - Stores all data in a local file, ideal for quick prototyping
  - No additional infrastructure setup required

### 2. Milvus Server (Self-Hosted)
- **Best for**: Large-scale production deployments
- **Setup**: 
  - Set `MILVUS_ENDPOINT` to your server URI (e.g., `http://localhost:19530`)
  - Optionally set `MILVUS_TOKEN` for authentication
- **Features**:
  - Full functionality, scales to billion vectors
  - Supports Docker (Milvus Standalone) and Kubernetes (Milvus Distributed): [installation guide](https://milvus.io/docs/install-overview.md)

### 3. Zilliz Cloud (Fully Managed Milvus)
- **Best for**: Production deployments with managed infrastructure
- **Setup**:
  - Set `MILVUS_ENDPOINT` to your Zilliz Cloud public endpoint
  - Set `MILVUS_TOKEN` to your API key
- **Features**:
  - Fully managed service available on Azure, AWS and Google Cloud
  - Zero DevOps required with automatic scaling and high availability
  - [Start with a free trial](https://cloud.zilliz.com/signup)

## Additional Resources

- [Milvus Documentation](https://milvus.io/docs): Comprehensive guides and API references
- [Zilliz Cloud Documentation](https://docs.zilliz.com/): Managed service documentation
- [Milvus GitHub Repository](https://github.com/milvus-io/milvus): Source code and issues
- [Milvus Community](https://milvus.io/discord): Join our Discord community for support