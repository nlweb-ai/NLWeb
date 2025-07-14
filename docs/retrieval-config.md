# Configuration Guide for config_retrieval.yaml

This document explains the configuration options available in `config_retrieval.yaml` for setting up and managing retrieval endpoints in NLWeb.

## Overview

The `config_retrieval.yaml` file configures the vector database endpoints that NLWeb uses for searching and retrieving documents. NLWeb supports multiple retrieval endpoints simultaneously and can aggregate results from all enabled endpoints.

## Top-Level Configuration

### `write_endpoint`
```yaml
write_endpoint: qdrant_local
```
- **Purpose**: Specifies which endpoint should be used for write operations (document upload and deletion)
- **Type**: String (must match one of the endpoint names defined in the `endpoints` section)
- **Note**: Only one endpoint can be designated for write operations at a time

## Endpoints Configuration

The `endpoints` section defines all available retrieval endpoints. Each endpoint is identified by a unique name and contains configuration specific to its database type.

### Common Fields

These fields are common across most endpoint types:

#### `enabled`
- **Purpose**: Controls whether this endpoint is active
- **Type**: Boolean (`true` or `false`)
- **Default**: `false`
- **Example**: `enabled: true`

#### `db_type`
- **Purpose**: Specifies the type of vector database
- **Type**: String
- **Valid values**: 
  - `azure_ai_search`
  - `qdrant`
  - `milvus`
  - `snowflake_cortex_search`
  - `opensearch`
- **Example**: `db_type: azure_ai_search`

#### `index_name`
- **Purpose**: The name of the index/collection to use in the database
- **Type**: String
- **Example**: `index_name: embeddings1536`

### Azure AI Search Configuration

```yaml
azure_ai_search:
  enabled: true
  api_key_env: AZURE_VECTOR_SEARCH_API_KEY
  api_endpoint_env: AZURE_VECTOR_SEARCH_ENDPOINT
  index_name: embeddings1536
  db_type: azure_ai_search
```

#### `api_key_env`
- **Purpose**: Environment variable name containing the Azure AI Search API key
- **Type**: String (environment variable name)
- **Example**: `api_key_env: AZURE_VECTOR_SEARCH_API_KEY`

#### `api_endpoint_env`
- **Purpose**: Environment variable name containing the Azure AI Search endpoint URL
- **Type**: String (environment variable name)
- **Format**: Should contain a URL like `https://your-search-service.search.windows.net`
- **Example**: `api_endpoint_env: AZURE_VECTOR_SEARCH_ENDPOINT`

### Qdrant Configuration

Qdrant supports two modes: local file-based storage and remote server connection.

#### Option 1: Local File-Based Storage
```yaml
qdrant_local:
  enabled: true
  database_path: "../data/db"
  index_name: nlweb_collection
  db_type: qdrant
```

#### `database_path`
- **Purpose**: Path to the local directory where Qdrant stores its data
- **Type**: String (file path)
- **Note**: Path is relative to the code directory
- **Example**: `database_path: "../data/db"`

#### Option 2: Remote Qdrant Server
```yaml
qdrant_url:
  enabled: false
  api_endpoint_env: QDRANT_URL
  api_key_env: QDRANT_API_KEY  # Optional
  index_name: nlweb_collection
  db_type: qdrant
```

#### `api_endpoint_env`
- **Purpose**: Environment variable containing the Qdrant server URL
- **Type**: String (environment variable name)
- **Example**: `api_endpoint_env: QDRANT_URL`

#### `api_key_env` (Optional)
- **Purpose**: Environment variable containing the API key for authenticated Qdrant servers
- **Type**: String (environment variable name)
- **Note**: Only required if your Qdrant server uses authentication

### Milvus Configuration

```yaml
milvus_1:
  enabled: false
  database_path: ../milvus/milvus_prod.db
  index_name: prod_collection
  db_type: milvus
```

**Note**: Milvus support is currently under development and not fully functional.

### Snowflake Cortex Search Configuration

```yaml
snowflake_cortex_search_1:
  enabled: false
  api_key_env: SNOWFLAKE_PAT
  api_endpoint_env: SNOWFLAKE_ACCOUNT_URL
  index_name: SNOWFLAKE_CORTEX_SEARCH_SERVICE
  db_type: snowflake_cortex_search
```

#### `api_key_env`
- **Purpose**: Environment variable containing the Snowflake Personal Access Token (PAT)
- **Type**: String (environment variable name)

#### `api_endpoint_env`
- **Purpose**: Environment variable containing the Snowflake account URL
- **Type**: String (environment variable name)
- **Format**: Should be your Snowflake account URL

### OpenSearch Configuration

OpenSearch supports two modes: with k-NN plugin (faster) and without (using script_score).

#### Option 1: With k-NN Plugin
```yaml
opensearch_knn:
  enabled: false
  api_endpoint_env: OPENSEARCH_ENDPOINT
  api_key_env: OPENSEARCH_CREDENTIALS
  index_name: embeddings
  db_type: opensearch
  use_knn: true
```

#### Option 2: Without k-NN Plugin (Fallback)
```yaml
opensearch_script:
  enabled: false
  api_endpoint_env: OPENSEARCH_ENDPOINT
  api_key_env: OPENSEARCH_CREDENTIALS
  index_name: embeddings
  db_type: opensearch
  use_knn: false
```

#### `use_knn`
- **Purpose**: Determines whether to use the k-NN plugin for vector search
- **Type**: Boolean
- **Default**: `true`
- **Note**: 
  - `true`: Uses native k-NN plugin (faster, requires plugin installation)
  - `false`: Uses script_score for similarity (slower but works without plugins)

#### `api_key_env`
- **Purpose**: Environment variable containing authentication credentials
- **Type**: String (environment variable name)
- **Format**: Can be either:
  - Basic auth: `username:password`
  - API key: Your OpenSearch API key

## Multiple Endpoints

NLWeb can query multiple enabled endpoints simultaneously and aggregate the results. This provides:

1. **Redundancy**: If one endpoint fails, others can still provide results
2. **Comprehensive results**: Different endpoints may have different data
3. **Performance**: Parallel queries to multiple endpoints

### How It Works

1. When multiple endpoints are enabled, NLWeb queries all of them in parallel
2. Results are aggregated and deduplicated by URL
3. If the same URL appears in multiple endpoints, the JSON data is merged
4. The `write_endpoint` is used for all write operations

## Example Configuration

Here's an example with multiple endpoints enabled:

```yaml
write_endpoint: qdrant_local

endpoints:
  # Primary Azure endpoint
  azure_primary:
    enabled: true
    api_key_env: AZURE_API_KEY_PRIMARY
    api_endpoint_env: AZURE_ENDPOINT_PRIMARY
    index_name: embeddings1536
    db_type: azure_ai_search
  
  # Local Qdrant for testing
  qdrant_local:
    enabled: true
    database_path: "../data/db"
    index_name: test_collection
    db_type: qdrant
  
  # Backup Azure endpoint
  azure_backup:
    enabled: true
    api_key_env: AZURE_API_KEY_BACKUP
    api_endpoint_env: AZURE_ENDPOINT_BACKUP
    index_name: embeddings1536
    db_type: azure_ai_search
```

## Setting Environment Variables

Before running NLWeb, set the required environment variables:

```bash
# Azure AI Search
export AZURE_VECTOR_SEARCH_API_KEY="your-api-key"
export AZURE_VECTOR_SEARCH_ENDPOINT="https://your-service.search.windows.net"

# Qdrant (if using remote)
export QDRANT_URL="http://localhost:6333"
export QDRANT_API_KEY="your-api-key"  # Optional

# OpenSearch
export OPENSEARCH_ENDPOINT="https://your-opensearch-domain.region.es.amazonaws.com"
export OPENSEARCH_CREDENTIALS="username:password"

# Snowflake
export SNOWFLAKE_PAT="your-personal-access-token"
export SNOWFLAKE_ACCOUNT_URL="https://your-account.snowflakecomputing.com"
```

## Troubleshooting

1. **Endpoint not working**: Check that:
   - `enabled: true` is set
   - Required environment variables are set
   - API keys and endpoints are valid
   - The index/collection exists in the database

2. **Write operations failing**: Ensure:
   - `write_endpoint` points to a valid, enabled endpoint
   - The endpoint has write permissions
   - The specified index/collection exists

3. **No results returned**: Verify:
   - At least one endpoint is enabled
   - The endpoints contain data for the queried sites
   - Network connectivity to remote endpoints

4. **Authentication errors**: Confirm:
   - Environment variables are correctly named
   - API keys are valid and not expired
   - Credentials have necessary permissions