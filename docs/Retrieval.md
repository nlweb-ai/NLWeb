# Retrieval

At this point, only one of the stores is queried. In future, we will query all the available stores. We do not assume that the backend is a vector store.

We do assume that the vector store will return a list of the database items encoded as json objects, preferably in a schema.org schema.

We are in the process of adding Restful vector stores, which will enable one NLWeb instance to treat another as its backend.

A significant improvement to retrieval would be the following. Consider
a query like "homes costing less than 500k which would be suitable
for a family with 2 small children and a large dog". The database
of items (real estate listings) will have structured fields like the
price. It would be good to translate this into a combination of 

## PostgreSQL with pgvector

NLWeb supports PostgreSQL with the pgvector extension for vector similarity search. This provides a powerful and scalable option for storing and retrieving vector embeddings using standard SQL database technology.

### Setup Requirements

1. PostgreSQL database (version 11 or higher recommended)
2. pgvector extension installed in the database
3. A table with the following schema (or compatible):

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,              -- Document ID (URL or other unique identifier)
    url TEXT NOT NULL,               -- URL of the document
    name TEXT NOT NULL,              -- Name of the document (title or similar)
    schema_json JSONB NOT NULL,      -- JSON schema of the document
    site TEXT NOT NULL,              -- Site or domain of the document
    embedding vector(1536) NOT NULL  -- Vector embedding (adjust dimension to match your model)
);

-- Create a vector index for faster similarity searches
CREATE INDEX IF NOT EXISTS embedding_cosine_idx 
ON documents USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 200);
```

### Configuration

Configure PostgreSQL in the `config_retrieval.yaml` file:

```yaml
preferred_endpoint: postgres_vector  # Set this to use PostgreSQL as default

endpoints:
  postgres:
    # Database connection details
    api_endpoint_env: POSTGRES_CONNECTION_STRING
    index_name: documents
    # Specify the database type
    db_type: postgres


```

You can provide credentials directly or via environment variables (recommended for security).

### Usage

The PostgreSQL vector client implements the full `VectorDBClientInterface` and supports all standard operations:

- Vector similarity search
- Document upload with vector embeddings
- URL-based document lookup
- Site-specific filtering
- Document deletion

### Testing and Troubleshooting

To test your PostgreSQL configuration, you can use the provided test scripts:

```bash
# Test basic connection
python code/retrieval/test_postgres_connection.py

# Run a more comprehensive example
python code/examples/postgres_example.py
```

Common issues:

1. **Connection errors**: Check host, port, username, and password settings
2. **pgvector extension missing**: Ensure the extension is properly installed in the database
3. **Table not found**: Make sure the table has been created with the proper schema
4. **Permissions**: Ensure the database user has sufficient privileges
5. **Configuration access**: If you get attribute errors, check that your configuration is properly formatted