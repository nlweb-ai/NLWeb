# Snowflake

The Snowflake AI Data Cloud provides:
* Various [LLM functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-llm-rest-api) and
* And [interactive search over unstructured data](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)

This guide walks you through how to use your Snowflake account for LLMs and/or for retrieval.

## Connect to your Snowflake account

The sample application can use a [programmatic access token](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

1. Login to your Snowflake account, e.g., https://<account_identifier>.snowflakecomputing.com/
2. Click on your user, then "Settings", then "Authentication"
3. Under "Programmatic access tokens" click "Generate new token"
4. Set `SNOWFLAKE_ACCOUNT_URL` and `SNOWFLAKE_PAT` in the `.env` file (as [README.md](../README.md) suggests).
5. (Optionally): Set `SNOWFLAKE_EMBEDDING_MODEL` to an [embedding model available in Snowflake](https://docs.snowflake.com/en/user-guide/snowflake-cortex/vector-embeddings#text-embedding-models)
6. (Optionally): Set `SNOWFLAKE_CORTEX_SEARCH_SERVICE` to the fully qualified name of the [Cortex Search Service](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview) to use for retrieval.

## Test connectivity

Run:

```
python snowflake-connectivity.py
```

You'll see a three line report on configuration whether configuration has been set correctly for Snowflake services.

## Use LLMs from Snowflake

1. Edit [config_llm.yaml](../code/config_llm.yaml) and change `preferred_provider` at the top to `preferred_provider: snowflake`
2. (Optionally) adjust the models to use by setting `snowflake.models.high` or `snowflake.models.low` in `config_llm.yaml` to any of [the models available to your Snowflake account](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions#availability)

## Use Cortex Search for retrieval

1. Edit [config_retrieval.yaml](../code/config_retrieval.yaml) and change `preferred_provider` at the top to `preferred_provider: snowflake_cortex_search_1`
2. (Optionally): To populate a Cortex Search Service with the SciFi Movies dataset included in this repository:
   a. Install the [snowflake cli](https://docs.snowflake.com/en/developer-guide/snowflake-cli/installation/installation) and [configure your connection](https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-cli). Make sure to set `role`, `database` and `schema` in the `connections.toml` file.
   b. Run the [snowflake.sql](../code/utils/snowflake.sql) script to index the scifi movies data (Cortex Search will automatically vectorize and also build a keyword index) using the `snow` command, for example:

   ```sh
   snow sql \
     -f ../code/utils/snowflake.sql \
     -D DATA_DIR=$(git rev-parse --show-toplevel)/data \
     -D WAREHOUSE=<name of the warehouse in your Snowflake account to use for compute> \
     -c <name of the configured connection>
   ```