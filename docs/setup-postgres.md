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

### Setup Schema

To setup you PostgreSQL configuration, you can use the provided setup scripts:

In the `code` directory run
```bash
# Test basic connection
python utils/setup_postgres_schema.py
```

### Dependencies

Make sure you have the required Python packages installed:

```bash
# Install PostgreSQL client libraries
pip install "psycopg[binary]" "psycopg[pool]" pgvector
```

The following packages are needed:
- `psycopg` - The PostgreSQL adapter for Python (psycopg3)
- `psycopg[binary]` - Binary dependencies for psycopg
- `psycopg[pool]` - Connection pooling support
- `pgvector` - Support for pgvector operations (vector types and indexing)

### Configuration

Configure PostgreSQL in the `config_retrieval.yaml` file:

```yaml
preferred_endpoint: postgres  # Set this to use PostgreSQL as default

endpoints:
  postgres:
    # Database connection details
    api_endpoint_env: POSTGRES_CONNECTION_STRING #The Postgres connection string (e.g., `postgresql://<USERNAME>:<PASSWORD>@<HOST>:<PORT>/<DATABASE>?sslmode=require`).
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

In the `code` directory run
```bash
# Test basic connection
python utils/test_postgres_connection.py

# Run a more comprehensive example
python utils/postgres_example.py

# Run diagonostics
python utils/postgres_diagnostics.py 

# Test if pgvector version is functioning as expected
python utils/test_pgvector.py
```

Common issues:

1. **Connection errors**: Check host, port, username, and password settings
2. **pgvector extension missing**: Ensure the extension is properly installed in the database
3. **Table not found**: Make sure the table has been created with the proper schema
4. **Permissions**: Ensure the database user has sufficient privileges
5. **Configuration access**: If you get attribute errors, check that your configuration is properly formatted