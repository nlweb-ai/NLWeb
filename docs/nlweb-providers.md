# NLWeb Providers

NLWeb enables an open standard.  You will need a model and a retrieval option. 

If you want to contribute a model or retrieval option, please see the following checklists to ensure that you have fully integrated into the solution. Please open an issue for guidance if you believe you need more new files than the lists below outline or within our [Contributor Guidelines](../CONTRIBUTING.md), which offer higher level principles.

[Model LLM Provider Checklist](#model-llm-provider-checklist)

[Retrieval Provider Checklist](#retrieval-provider-checklist)

## Model LLM Provider Checklist

Here is a checklist of items that you will need to add for support for a new model.

File updates:
- **code\config\config_llm.yaml:** Add an entry under "providers" in this file with the API key environment variable, API endpoint environment variable, and the default high and low models that need to be configured for your service.  You can provide the environment variable name to read from, or the value directly.  Here is an example:

```yml
  openai:
    api_key_env: OPENAI_API_KEY
    api_endpoint_env: OPENAI_ENDPOINT
    models:
      high: gpt-4.1
      low: gpt-4.1-mini
```
- **code\env.template:** Make sure that the environment variables that you added are also added to this file, with default values if appropriate, so that new users getting started know what environment variables they will need.
- **code\llm\llm.py**: Add your model to the provider mapping here.
- **Connectivity check** tool - please add this in [Azure Connectivity](../code/azure_connectivity.py) for now; later this file will be updated to hold all connectivity checks.

New files:
- **docs\\setup-\<your-model-name>.md:** Add any model-specific documentation here.
- **code\llm\\<your_model_name>.py:** Implement the LLMProvider interface for your model here.

## Retrieval Provider Checklist

Here is a checklist of items that you will need to implement support for a new retrieval provider/vector database.

File updates:
- **code\config\config_retrieval.yaml:** Add an entry under "endpoints" in this file with the index name, database type, and then EITHER the database path if a local option or the API key environment variable and API endpoint environment variable if cloud-hosted that need to be configured for your service.  You can provide the environment variable name to read from, or the value directly.  Here are examples:

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
- **code\retrieval\retriever.py:** In the VectorDBClient class, add logic to route to your retrieval provider.

New files:
- **code\retrieval\\\<your_retrieval_name>_client.py:** Implement the VectorDBClientInterface for your retrieval provider here.
- **code\tools\\\<your_retrieval_name>_load.py:** Add logic to load embeddings into your vector database here and any other tools needed for maintaining the database.
- **docs\\setup-\<your-retriever-name>.md:** Add any retriever-specific documentation here.  Please ensure to document any tooling you provide.
