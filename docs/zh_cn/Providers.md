NLWeb 支持开放标准。 您将需要一个模型和一个检索选项。 如果要提供模型或检索选项，请参阅以下清单，以确保您已完全集成到解决方案中。  

[Model/LLM 提供商清单](#model-llm-provider-checklist)

[检索提供程序清单](#retrieval-provider-checklist)

# Model/LLM 提供商清单
以下是为支持新模型而需要添加的项目清单。  
+ **config\config_llm.yaml：** 在此文件的“providers”下添加一个条目，其中包含 API 密钥环境变量、API 终端节点环境变量以及需要为您的服务配置的默认高低模型。 您可以提供要从中读取的环境变量名称，也可以直接提供值。 下面是一个示例：
```
  openai:
    api_key_env: OPENAI_API_KEY
    api_endpoint_env: OPENAI_ENDPOINT
    models:
      high: gpt-4.1
      low: gpt-4.1-mini
```
+ **code\env.template：** 确保您添加的环境变量也已添加到此文件中，并在适当时使用默认值，以便入门的新用户知道他们需要哪些环境变量。  
+ **code\llm\your_model_name.py：** 在此处为您的模型实现 LLMProvider 接口。  
+ **code\llm\llm.py**： 在此处将您的模型添加到提供程序映射中。  
+ **docs\YourModelName.md：** 在此处添加任何特定于模型的文档。  

# 检索提供程序清单
以下是实现对新检索提供程序/向量数据库的支持所需的项目清单。  
+ **config\config_retrieval.yaml：** 在此文件的“endpoints”下添加一个条目，其中包含索引名称、数据库类型，然后是数据库路径（如果是本地选项）或 API 密钥环境变量和 API 终端节点环境变量（如果是云托管的），需要为您的服务配置。 您可以提供要从中读取的环境变量名称，也可以直接提供值。 以下是示例：
```
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
+ **code\env.template：** 确保您添加的环境变量也已添加到此文件中，并在适当时使用默认值，以便入门的新用户知道他们需要哪些环境变量。  
+ **code\retrieval\yourRetrievalName_client.py：** 在此处为您的检索提供程序实现 VectorDBClientInterface。  
+ **code\retrieval\retriever.py：** 在 VectorDBClient 类中，添加要路由到检索提供程序的逻辑。  
+ **tools\yourRetrievalName_load.py：** 在此处添加用于将嵌入加载到向量数据库的逻辑。  
+ **docs\YourRetrieverName.md：** 在此处添加任何特定于检索器的文档。  
