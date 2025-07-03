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

NOTE: If you are using Azure Postgres Flexible server make sure you have `vector` [extension allow-listed](https://learn.microsoft.com/azure/postgresql/flexible-server/how-to-use-pgvector#enable-extension)

To setup you PostgreSQL configuration, you can use the provided setup scripts:

In the `code` directory run
```bash
# Setup the Postgres server
python tools/postgres_load.py
```

### Dependencies

Make sure you have the required Python packages installed:

```bash
# Install PostgreSQL client libraries
pip install psycopg
pip install psycopg-binary  # PostgreSQL adapter (psycopg3)
pip install psycopg-pool  # Connection pooling for psycopg3
pip install pgvector
```

The following packages are needed:
- `psycopg` - The PostgreSQL adapter for Python (psycopg3)
- `psycopg[binary]` - Binary dependencies for psycopg
- `psycopg[pool]` - Connection pooling support
- `pgvector` - Support for pgvector operations (vector types and indexing)

### Configuration

Update the `.env` file:

```bash
# If using Postgres connection string
POSTGRES_CONNECTION_STRING="postgresql://<HOST>:<PORT>/<DATABASE>?user=<USERNAME>&sslmode=require"
POSTGRES_PASSWORD="<PASSWORD>"
```

Configure PostgreSQL in the `config_retrieval.yaml` file:

```yaml
preferred_endpoint: postgres  # Set this to use PostgreSQL as default

endpoints:
  postgres:
    # Database connection details
    api_endpoint_env: POSTGRES_CONNECTION_STRING # Database connection details (i.e. "postgresql://<HOST>:<PORT>/<DATABASE>?user=<USERNAME>&sslmode=require")
    # Password for authentication 
    api_key_env: POSTGRES_PASSWORD
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