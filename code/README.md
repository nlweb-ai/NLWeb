# NLWeb Azure Web App Deployment

This project has been adapted to run on Azure Web App. This README provides guidance on how to deploy and manage the application in Azure.

## Project Structure

```
code/
├── app-file.py                   # Entry point for Azure Web App
├── azure-connectivity.py         # Connectivity check utility (no longer just Azure)
├── .env.template                 # Template for environment variables
├── requirements.txt              # Python dependencies
├── snowflake-connectivity.py     # Will in future be in single connectivity checker 
├── config/
|   ├── config_embedding.yaml     #
|   ├── config_llm.yaml           #
|   ├── config_nlweb.yaml         #
|   ├── config_retrieval.yaml     #
|   ├── config_webserver.yaml     #
|   └── config.py                 #
├── core/
|   ├── baseHandler.py            # Request handler
|   ├── fastTrack.py              # Fast tracking
|   ├── generate_answer.py        # 
|   ├── mcp_handler.py            # 
|   ├── post_ranking.py           #
|   ├── ranking.py                # Result ranking
|   ├── state.py                  # State management
|   └── whoHandler.py             #
├── embedding/
|   ├── anthropic_embedding.py    #
|   ├── azure_oai_embedding.py    #
|   ├── embedding.py              #
|   ├── gemini_embedding.py       #
|   ├── openai_embedding.py       #
|   ├── snowflake_embedding.py    #
├── llm/
|   ├── anthropic.py              #
|   ├── azure_deepseek.py         #
|   ├── azure_llama.py            #
|   ├── azure_oai.py              #
|   ├── gemini.py                 #
|   ├── inception.py              #
|   ├── llm_provider.py           #
|   ├── llm.py                    #
|   ├── openai.py                 #
|   └── snowflake.py              #
├── logs/                         # folder to which all logs are sent
├── pre_retrieval/
|   ├── analyze_query.py          # Query analysis
|   ├── decontextualize.py        # Query decontextualization
|   ├── memory.py                 # Memory management
|   ├── relevance_detection.py    # Relevance detection
|   └── required_info.py          # Check for more information needed
├── prompts/
|   ├── prompt_runner.py          # 
|   ├── prompts.py                #
|   ├── site_type.xml             # Site type definitions
├── retrieval/                    # Static files directory
|   ├── azure_search_client.py    # Azure AI Search integration
|   ├── milvus_client.py          # Milvus Client integration (under development)
|   ├── qdrant_retrieve.py        # Qdrant vector database integration
|   ├── qdrant.py                 # Qdrant Client integration
|   ├── retriever.py              # Data retrieval
|   └── snowflake_retrieve.py     # Snowflake vector database integration
├── tools/
|   ├── db_load_utils.py          #
|   ├── db_load.py                #
|   ├── embedding.py              #
|   ├── extractMarkup.py          #
|   ├── json_analysis.py          #
|   ├── nlws.py                   #
|   ├── qdrant_load.py            #
|   ├── rss2schema.py             #
|   └── trim_schema_json.py       #
├── utils/
|   ├── logger.py                 #
|   ├── logging_config_helper.py  #
|   ├── set_log_level.py          #
|   ├── snowflake.py              #
|   ├── test_logging.py           #
|   ├── trim.py                   #
|   └── utils.py                  #
webserver/
|   ├── WebServer.py              #
|   ├── StreamingWrapper.py       # Streaming support
|   └── WebServer.py              # Modified WebServer for Azure
data/                             # Folder for local vector embeddings
demo/
|   ├── .env.example              # example .env file to reference in Build demo
|   ├── extract_github_data.py    # tool to extract user GitHub data
|   └── README.md                 # Build demo instructions
docs/
|   ├── Azure.md                  # Azure Services Guidance (Setup + Management)
|   ├── Claude-NLWeb.md           # Setup Claude to talk to NLWeb
|   ├── Configs.md                # How to set config file variables
|   ├── ControlFlow.md            #
|   ├── db_load.md                # How to use the data load utility
|   ├── LifeOfAChatQuery.md       # Explains how a chat flows through NLWeb
|   ├── Memory.md                 # How memory can be used
|   ├── NLWebCLI.md               # How the NLWeb CLI tool works
|   ├── Prompts.md                # How prompts are setup in NLWeb & how to customize
|   ├── Qdrant.md                 # Instructions to configure Qdrant
|   ├── RestAPI.md                # NLWeb & MCP API information
|   ├── Retreival.md              # How to configure your vector DB provider
|   ├── Snowflake.md              # Instructions to configure and use Snowflake
|   └── UserInterface.md          # Instructions to configure your user interface
images/                           # Folder for images in md files 
scripts/
static/                           # Static files directory
|   └──html/                        # HTML, CSS, JS files

```