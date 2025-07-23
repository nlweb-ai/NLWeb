# NLWeb Retrieval System

This document explains the configuration options available in `config_retrieval.yaml` for setting up and managing retrieval endpoints in NLWeb.

## Overview

The `config_retrieval.yaml` file configures the vector database endpoints that NLWeb uses for searching and retrieving documents. NLWeb supports multiple retrieval endpoints simultaneously and can aggregate results from all enabled endpoints.

## Contents
[Multi-Backend Architecture](#multi-backend-architecture)
[Write Configuration](#write-configuration)
[Endpoint Configuration](#endpoint-configuration)
[Multiple Endpoints](#multiple-endpoints)
[Example Configuration](#example-configuration)
[Implementation Details](#implementation-details)
[Adding a New Backend](#adding-a-new-backend)
[Best Practices](#best-practices)
[Troubleshooting](#troubleshooting)
[Migration Guide (from single provider version)](#migration-guide)

## Multi-Backend Architecture

 The new architecture allows multiple backends to be concurrently active:

- **Concurrent Queries**: All enabled backends are queried in parallel for every search request
- **Duplicate Removal**: Results are automatically deduplicated across backends
- **Result Ranking**: The top-N results are selected and returned based on relevance
- **Write Operations**: Data writes continue to target a single backend specified by `write_endpoint`

## Write Configuration

The retrieval configuration is managed through `code/config/config_retrieval.yaml`:

### `write_endpoint`
```yaml
write_endpoint: qdrant_local
```
- **Purpose**: Specifies which endpoint should be used for write operations (document upload and deletion)
- **Type**: String (must match one of the endpoint names defined in the `endpoints` section)
- **Note**: Only one endpoint can be designated for write operations at a time

## Endpoint Configuration

Below the write configuration, the `endpoints` section defines all available retrieval endpoints. Each endpoint is identified by a unique name and contains configuration specific to its database type. You must set at least one retrieval provider to get started.

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

## Implementation Details

### Backend Client Architecture

Each retrieval backend extends the base `VectorDBClient` class: (as defined in code/python/core/retriever.py)

```python
class VectorDBClient:
    async def search(self, query: str, site: str, num_results: int) -> List[Tuple[str, str, str, str]]:
        """Returns list of (url, json_str, name, site) tuples"""
        pass
    
    async def search_by_url(self, url: str) -> Optional[Dict]:
        """Returns item data for the given URL"""
        pass
    
    async def search_all_sites(self, query: str, top_n: int) -> List[Tuple[str, str, str, str]]:
        """Returns results across all sites"""
        pass
```

### Result Format

All search methods return results as 4-tuples containing:
1. **url**: The item's URL
2. **json_str**: JSON representation of the item data
3. **name**: Display name of the item
4. **site**: The site this item belongs to

### Concurrent Query Execution

When a search request is received:

1. The system identifies all enabled backends
2. Queries are sent to all backends in parallel using `asyncio`
3. Results are collected and duplicates are removed based on URL
4. The combined results are ranked and the top-N are returned

## Adding a New Backend

To add support for a new retrieval backend, see our [instructions for adding a new provider](docs/nlweb-providers.md)

## Best Practices

1. **Environment Variables**: Always use environment variables for sensitive configuration
2. **Error Handling**: Backends should gracefully handle failures without affecting other backends
3. **Timeouts**: Implement appropriate timeouts to prevent slow backends from blocking requests
4. **Logging**: Use the configured logger for debugging and monitoring
5. **Testing**: Test each backend independently and in combination with others

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

## Migration Guide

In our early releases, `config_retrieval.yaml` supported only a single active backend at any time.

If upgrading from a single-backend system:

1. Update your `config_retrieval.yaml` to the new format
2. Set `enabled: true` for your existing backend
3. Ensure `write_endpoint` points to your primary backend
4. Test thoroughly before enabling additional backends