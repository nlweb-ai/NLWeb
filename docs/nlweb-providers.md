# NLWeb Providers

NLWeb enables an open standard.  You will need a model and a retrieval option.

If you want to contribute a model or retrieval option, please see the following checklists to ensure that you have fully integrated into the solution. Please open an issue for guidance if you believe you need more new files than the lists below outline or within our [Contributor Guidelines](../CONTRIBUTING.md), which offer higher level principles.

[Model LLM Provider Checklist](#model-llm-provider-checklist)

[Retrieval Provider Checklist](#retrieval-provider-checklist)

## Model LLM Provider Checklist

Here is a checklist of items that you will need to add for support for a new model.

File updates:

- **config/config_llm.yaml:** Add an entry under "providers" in this file with the API key environment variable, API endpoint environment variable, and the default high and low models that need to be configured for your service.  You can provide the environment variable name to read from, or the value directly.  Here is an example:

```yaml
  openai:
    api_key_env: OPENAI_API_KEY
    api_endpoint_env: OPENAI_ENDPOINT
    models:
      high: gpt-4.1
      low: gpt-4.1-mini
```

- **code/env.template:** Make sure that the environment variables that you added are also added to this file, with default values if appropriate, so that new users getting started know what environment variables they will need.
- **code/python/llm_providers/llm_provider.py**: Add your model to the provider mapping here.

New files:

- **docs/setup-&lt;your-model-name&gt;.md:** Add any model-specific documentation here.
- **code/python/llm_providers/&lt;your_model_name&gt;.py:** Implement the LLMProvider interface for your model here.

Testing:

- **Connectivity check** tool - please test your integration with the [Check Connectivity](./code/python/testing/check_connectivity.py) script and ensure that it works when the configuration is set properly and fails when the API key is not set or other items are not configured properly, preferably with helpful error messages.

## Retrieval Provider Checklist

Here is a checklist of items that you will need to implement support for a new retrieval provider/vector database.

File updates:

- **config/config_retrieval.yaml:** Add an entry under "endpoints" in this file with the index name, database type, and then EITHER the database path if a local option or the API key environment variable and API endpoint environment variable if cloud-hosted that need to be configured for your service.  You can provide the environment variable name to read from, or the value directly.  Here are examples:

```yaml
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

- **code/env.template:** Make sure that the environment variables that you added are also added to this file, with default values if appropriate, so that new users getting started know what environment variables they will need.
- **code/python/core/retriever.py:** In the VectorDBClient class, add logic to route to your retrieval provider.

New files:

- **code/python/retrieval/&lt;your_retrieval_name&gt;_client.py:** Implement the VectorDBClientInterface for your retrieval provider here.
- **code/python/data_loading/&lt;your_retrieval_name&gt;_load.py:** Add logic to load embeddings into your vector database here and any other tools needed for maintaining the database. (Note: this is optional; you may be able to do this in your retrieval client file.)
- **docs/setup-&lt;your-retriever-name&gt;.md:** Add any retriever-specific documentation here.  Please ensure to document any tooling you provide.

Testing:

- **Connectivity check** tool - please test your integration with the [Check Connectivity](./code/python/testing/check_connectivity.py) script and ensure that it works when the configuration is set properly and fails when the API key is not set or other items are not configured properly, preferably with helpful error messages.
