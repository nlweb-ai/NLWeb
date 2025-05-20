# Qdrant Setup

qdrant:
  # To connect to a Qdrant server, set the `QDRANT_URL` and optionally `QDRANT_API_KEY`.
  # > docker run -p 6333:6333 qdrant/qdrant
  # QDRANT_URL="http://localhost:6333"
  api_endpoint_env: QDRANT_URL
  api_key_env: QDRANT_API_KEY

  # To use a local persistent instance for prototyping,
  # set database_path to a local directory
  database_path: ""

  # Set the name of the collection to use as `index_name`
  index_name: nlweb_collection
  db_type: qdrant