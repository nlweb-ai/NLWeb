# NLWeb Retrieval System

## Overview

NLWeb's retrieval system has been significantly enhanced to support multiple concurrent retrieval backends. This architecture enables improved performance, redundancy, and flexibility in how data is stored and retrieved.

## Multi-Backend Architecture

Prior to this release, `config_retrieval.yaml` supported only a single active backend at any time. The new architecture allows multiple backends to be concurrently active:

- **Concurrent Queries**: All enabled backends are queried in parallel for every search request
- **Duplicate Removal**: Results are automatically deduplicated across backends
- **Result Ranking**: The top-N results are selected and returned based on relevance
- **Write Operations**: Data writes continue to target a single backend specified by `write_endpoint`

## Configuration

The retrieval configuration is managed through `code/config/config_retrieval.yaml`:

```yaml
# Specify the backend for write operations
write_endpoint: qdrant_local

endpoints:
 
 
  # Production Azure AI Search endpoint
  nlweb_west:
    enabled: true
    api_key_env: NLWEB_WEST_API_KEY
    api_endpoint_env: NLWEB_WEST_ENDPOINT
    index_name: embeddings1536
    db_type: azure_ai_search

  # Local Qdrant instance for development
  qdrant_local:
    enabled: true
    database_path: "../data/db"
    index_name: nlweb_collection
    db_type: qdrant

  # Snowflake Cortex Search integration
  snowflake_cortex:
    enabled: false
    account_env: SNOWFLAKE_ACCOUNT
    username_env: SNOWFLAKE_USERNAME
    password_env: SNOWFLAKE_PASSWORD
    database: NLWEB_DB
    schema: PUBLIC
    table: EMBEDDINGS
    index_name: nlweb_embeddings
    db_type: snowflake
```

### Key Configuration Elements

- **write_endpoint**: Specifies which backend receives write operations
- **enabled**: Boolean flag to enable/disable each backend
- **db_type**: Supported types include `azure_ai_search`, `qdrant`, `milvus`, `opensearch`, and `snowflake`
- **Environment Variables**: API keys and endpoints are configured via environment variables for security

## Retrieval APIs

Each backend must implement the following core retrieval APIs:

### Search APIs
- **Search by Site and Query**: `search(query, site, num_results)`
  - Returns items matching the query within a specific site
- **Search by URL**: `search_by_url(url)`
  - Retrieves items associated with a specific URL
- **Search All Sites**: `search_all_sites(query, top_n)`
  - Searches across all sites in the database
- **Get Sites**: `get_sites()`
  - Returns a list of all available sites in the database

### Data Management APIs (Optional)
- **Upload Items**: `upload_item_site_pairs(items)`
  - Adds new item-site pairs to the database
- **Delete Site**: `delete_site(site_name)`
  - Removes all data associated with a specific site

## Implementation Details

### Backend Client Architecture

Each retrieval backend extends the base `VectorDBClient` class:

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

To add support for a new retrieval backend:

1. Create a new client class in `code/retrieval/` that extends `VectorDBClient`
2. Implement all required search methods
3. Add configuration support in `config_retrieval.yaml`
4. Register the backend type in the retriever factory

## Best Practices

1. **Environment Variables**: Always use environment variables for sensitive configuration
2. **Error Handling**: Backends should gracefully handle failures without affecting other backends
3. **Timeouts**: Implement appropriate timeouts to prevent slow backends from blocking requests
4. **Logging**: Use the configured logger for debugging and monitoring
5. **Testing**: Test each backend independently and in combination with others

## Migration Guide

If upgrading from a single-backend system:

1. Update your `config_retrieval.yaml` to the new format
2. Set `enabled: true` for your existing backend
3. Ensure `write_endpoint` points to your primary backend
4. Test thoroughly before enabling additional backends