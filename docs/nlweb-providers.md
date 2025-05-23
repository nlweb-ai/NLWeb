# NLWEB Providers

NLWeb enables an open standard.  You will need a model and a retrieval option.  If you want to contribute a model or retrieval option, please see the following checklists to ensure that you have fully integrated into the solution.

[Model LLM Provider Checklist](#model-llm-provider-checklist)

[Retrieval Provider Checklist](#retrieval-provider-checklist)

## Model LLM Provider Checklist

Here is a checklist of items that you will need to add for support for a new model.

- **config\config_llm.yaml:** Add an entry under "providers" in this file with the API key environment variable, API endpoint environment variable, and the default high and low models that need to be configured for your service.  You can provide the environment variable name to read from, or the value directly.  Here is an example:

```yml
  openai:
    api_key_env: OPENAI_API_KEY
    api_endpoint_env: OPENAI_ENDPOINT
    models:
      high: gpt-4.1
      low: gpt-4.1-mini
```

- **code\env.template:** Make sure that the environment variables that you added are also added to this file, with default values if appropriate, so that new users getting started know what environment variables they will need.
- **code\llm\your_model_name.py:** Implement the LLMProvider interface for your model here.
- **code\llm\llm.py**: Add your model to the provider mapping here.
- **docs\YourModelName.md:** Add any model-specific documentation here.

## Retrieval Provider Checklist

Here is a checklist of items that you will need to implement support for a new retrieval provider/vector database.

- **config\config_retrieval.yaml:** Add an entry under "endpoints" in this file with the index name, database type, and then EITHER the database path if a local option or the API key environment variable and API endpoint environment variable if cloud-hosted that need to be configured for your service.  You can provide the environment variable name to read from, or the value directly.  Here are examples:

```yml
  qdrant_local:
    database_path: "../data/db"
    index_name: nlweb_collection
    db_type: qdrant

  snowflake_cortex_search_1:
    api_key_env: SNOWFLAKE_PAT
    api_endpoint_env: SNOWFLAKE_ACCOUNT_URL
    index_name: SNOWFLAKE_CORTEX_SEARCH_SERVICE
    db_type: snowflake_cortex_search
```

- **code\env.template:** Make sure that the environment variables that you added are also added to this file, with default values if appropriate, so that new users getting started know what environment variables they will need.
- **code\retrieval\yourRetrievalName_client.py:** Implement the VectorDBClientInterface for your retrieval provider here.
- **code\retrieval\retriever.py:** In the VectorDBClient class, add logic to route to your retrieval provider.
- **tools\yourRetrievalName_load.py:** Add logic to load embeddings into your vector database here.
- **docs\YourRetrieverName.md:** Add any retriever-specific documentation here.
