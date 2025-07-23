# Code Structure

## Core Application
- **`app-file.py`** - Main application entry point
- **`chatbot_interface.py`** - Chatbot UI interface
- **`webserver/`** - Web server implementation and static file handling

## Core Modules
- **`core/`** - Core system components
  - `baseHandler.py` - Base request handler
  - `router.py` - Query routing logic
  - `llm.py` - LLM provider interface
  - `retriever.py` - Vector database interface
  - `prompts.py` - Prompt management and execution
  - `query_analysis/` - Query preprocessing (decontextualization, relevance detection)
  - `utils/` - JSON utilities and helper functions

## Providers
- **`llm_providers/`** - LLM service implementations (OpenAI, Azure, Anthropic, etc.)
- **`embedding_providers/`** - Embedding service implementations
- **`retrieval_providers/`** - Vector database implementations (Qdrant, Milvus, Azure Search)
  - `utils/` - Snowflake-specific utilities

## Methods
- **`methods/`** - Query processing methods
  - Item details, comparisons, accompaniments
  - Statistics handling, answer generation
  - Recipe substitutions

## Data & Configuration
- **`config/`** - YAML configuration files
- **`data/`** - Static data files (prompts.xml, tools.xml, mappings)

## Tools & Utilities
- **`data_loading/`** - Database loading tools for RSS, JSON, and web content
- **`scraping/`** - Web scraping and content extraction tools
- **`misc/`** - Miscellaneous utilities
  - `logger/` - Logging configuration and log files
  - JSON analysis, podcast scraping, and other tools

## Testing & Benchmarking
- **`testing/`** - Test suites and test data
  - `connectivity/` - Service connectivity tests
- **`benchmark/`** - Performance benchmarking tools

## Configuration Files
- **`requirements.txt`** - Python dependencies
- **`set_keys.sh`** - Environment variable setup
- **`azure-*.txt`** - Azure deployment configurations