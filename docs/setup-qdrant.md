# Qdrant Setup

To configure Qdrant for use with NLWeb, you'll need to set a few environment variables or update your configuration.

## Connecting to a Qdrant Server

To connect to a running Qdrant server (e.g., one started with `docker run -p 6333:6333 qdrant/qdrant`), set the following environment variables:

* `QDRANT_URL`: The URL of your Qdrant instance (e.g., `http://localhost:6333`).
* `QDRANT_API_KEY`: (Optional) Your Qdrant API key, if required.

Alternatively, you can specify these in your configuration file:

```yaml
qdrant:
  api_endpoint_env: QDRANT_URL
  api_key_env: QDRANT_API_KEY
  # ... other qdrant settings
```

## Using a Local Persistent Instance

For prototyping, you can use a local persistent Qdrant instance. To do this, specify the `database_path` in your configuration to point to a local directory where Qdrant can store its data.

```yaml
qdrant:
  # To use a local persistent instance for prototyping,
  # set database_path to a local directory
  database_path: "/path/to/your/qdrant_data" # Example path
  # ... other qdrant settings
```

If `database_path` is empty or not set, NLWeb will attempt to connect to a Qdrant server specified by `QDRANT_URL`.

## Collection Name

You need to specify the name of the Qdrant collection that NLWeb will use. This is done via the `index_name` setting in your configuration.

```yaml
qdrant:
  # Set the name of the collection to use as `index_name`
  index_name: nlweb_collection
  db_type: qdrant # This specifies that Qdrant is the database type
  # ... other qdrant settings
```

Here is an example of a complete `qdrant` configuration block:

```yaml
qdrant:
  # To connect to a Qdrant server, set the `QDRANT_URL` and optionally `QDRANT_API_KEY`.
  # Example if using environment variables:
  # QDRANT_URL="http://localhost:6333"
  # QDRANT_API_KEY="your_api_key_if_any"
  api_endpoint_env: QDRANT_URL
  api_key_env: QDRANT_API_KEY

  # To use a local persistent instance for prototyping,
  # set database_path to a local directory.
  # If this is set, QDRANT_URL and QDRANT_API_KEY might be ignored.
  database_path: "" # e.g., "qdrant_data_local"

  # Set the name of the collection to use as `index_name`
  index_name: nlweb_collection
  db_type: qdrant
