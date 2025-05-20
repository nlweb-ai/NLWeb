# 雪花

Snowflake AI 数据云提供：
* 各种 [LLM 函数](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-llm-rest-api) 和
* 以及 [对非结构化数据的交互式搜索](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)

本指南将指导您了解如何将 Snowflake 帐户用于 LLM 和/或检索。

## 连接到您的 Snowflake 帐户

示例应用程序可以使用 [编程访问令牌](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

1. 登录您的 Snowflake 帐户，例如 https://<account_identifier>.snowflakecomputing.com/
2. 单击您的用户，然后单击“设置”，然后单击“身份验证”
3. 在“Programmatic access tokens（编程访问令牌）”下，单击“Generate new token”（生成新令牌）
4. set `SNOWFLAKE_ACCOUNT_URL` 和 `SNOWFLAKE_PAT` in `.env` 文件中（如 [README.md](../../README.md) 所建议的那样）。
5. （可选）：设置为 `SNOWFLAKE_EMBEDDING_MODEL` [Snowflake 中可用的嵌入模型](https://docs.snowflake.com/en/user-guide/snowflake-cortex/vector-embeddings#text-embedding-models)
6. （可选）：设置为 `SNOWFLAKE_CORTEX_SEARCH_SERVICE` 用于检索的 [Cortex 搜索服务的](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)完全限定名称。

## 测试连接性

跑：

```
python snowflake-connectivity.py
```

您将看到一个三行报告，说明是否已为 Snowflake 服务正确设置配置。

## 使用 Snowflake 中的 LLM

1. 编辑 [config_llm.yaml](../../code/config_llm.yaml) 并将 `preferred_provider` 顶部的 `preferred_provider: snowflake`
2. （可选）通过设置 `snowflake.models.high` 或 `snowflake.models.low` 调整 `config_llm.yaml`Snowflake 账户可用的[任何模型来调整要使用的模型](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions#availability)

## 使用 Cortex Search 进行检索

1. 编辑 [config_retrieval.yaml](../../code/config_retrieval.yaml) 并将 `preferred_provider` 顶部的 `preferred_provider: snowflake_cortex_search_1`
2. （可选）：要使用此存储库中包含的 SciFi Movies 数据集填充 Cortex 搜索服务：
   一个。安装 [snowflake CLI](https://docs.snowflake.com/en/developer-guide/snowflake-cli/installation/installation) 并 [配置您的连接](https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-cli)。确保在文件中设置 `role`、 `database` 和 `schema` `connections.toml` 。
   b.使用以下命令运行 [snowflake.sql](../../code/utils/snowflake.sql) 脚本以索引科幻电影数据（Cortex Search 将自动矢量化并构建关键字索引）， `snow` 例如：

   ```sh
   snow sql \
     -f ../code/utils/snowflake.sql \
     -D DATA_DIR=$(git rev-parse --show-toplevel)/data \
     -D WAREHOUSE=<name of the warehouse in your Snowflake account to use for compute> \
     -c <name of the configured connection>
   ```