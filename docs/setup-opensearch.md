
# OpenSearch Configuration

OpenSearch supports two modes: with k-NN plugin (faster) and without (using script_score).

## Option 1: With k-NN Plugin

```yaml
opensearch_knn:
  enabled: false
  api_endpoint_env: OPENSEARCH_ENDPOINT
  api_key_env: OPENSEARCH_CREDENTIALS
  index_name: embeddings
  db_type: opensearch
  use_knn: true
```

## Option 2: Without k-NN Plugin (Fallback)

```yaml
opensearch_script:
  enabled: false
  api_endpoint_env: OPENSEARCH_ENDPOINT
  api_key_env: OPENSEARCH_CREDENTIALS
  index_name: embeddings
  db_type: opensearch
  use_knn: false
```

## `use_knn`

- **Purpose**: Determines whether to use the k-NN plugin for vector search
- **Type**: Boolean
- **Default**: `true`
- **Note**: 
  - `true`: Uses native k-NN plugin (faster, requires plugin installation)
  - `false`: Uses script_score for similarity (slower but works without plugins)

## `api_key_env`

- **Purpose**: Environment variable containing authentication credentials
- **Type**: String (environment variable name)
- **Format**: Can be either:
  - Basic auth: `username:password`
  - API key: Your OpenSearch API key
