# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

MOST IMPORTANT GUIDELINE: Only implement exactly what you have been asked to. Do not add additional functionality. You tend to over complicate.

## Project Overview

NLWeb is a conversational interface platform that enables natural language interactions with websites. It leverages Schema.org markup and supports MCP (Model Context Protocol) for AI agent interactions.

## Common Development Commands

### Running the Server
```bash
# Start aiohttp server (recommended)
./startup_aiohttp.sh

# Or directly from code/python
cd code/python
python -m webserver.aiohttp_server
```

### Running Tests
```bash
# Quick test suite (from code directory)
cd code
./python/testing/run_all_tests.sh

# Comprehensive test runner with options
./python/testing/run_tests_comprehensive.sh -m end_to_end  # Specific test type
./python/testing/run_tests_comprehensive.sh --quick        # Quick smoke tests

# Run specific Python tests
cd code/python
python -m pytest testing/ -v

# Single test execution
python -m testing.run_tests --single --type end_to_end --query "test query"
```

### Linting and Type Checking
```bash
# No standard lint/typecheck commands found in codebase
# Suggest adding these to the project if needed
```

## Architecture Overview

### Backend Architecture (code/python/)

**Core Flow**: Query → Pre-retrieval Analysis → Tool Selection → Retrieval → Ranking → Response Generation

1. **Entry Point**: `webserver/aiohttp_server.py` - Async HTTP server handling REST API and WebSocket connections

2. **Request Processing Pipeline**:
   - `core/baseHandler.py` - Main request handler orchestrating the flow
   - `pre_retrieval/` - Query analysis, decontextualization, relevance detection
   - `methods/` - Tool implementations (search, item details, ensemble queries)
   - `retrieval/` - Vector database clients (Qdrant, Azure AI Search, Milvus, Snowflake, Elasticsearch)
   - `core/ranking.py` - Result scoring and ranking
   - `llm/` - LLM provider integrations (OpenAI, Anthropic, Gemini, Azure, etc.)

3. **Chat/Conversation System** (In Development):
   - `chat/websocket.py` - WebSocket connection management
   - `chat/conversation.py` - Conversation orchestration
   - `chat/participants.py` - Participant management (Human, NLWeb agents)
   - `chat/storage.py` - Message persistence interface

4. **Configuration**: YAML files in `config/` directory control all aspects:
   - `config_nlweb.yaml` - Core settings
   - `config_llm.yaml` - LLM provider configuration
   - `config_retrieval.yaml` - Vector database settings
   - `config_webserver.yaml` - Server configuration

### Frontend Architecture (static/)

**Main Components**:
- `fp-chat-interface.js` - Primary chat interface
- `conversation-manager.js` - Conversation state management
- `chat-ui-common.js` - Shared UI components
- ES6 modules with clear separation of concerns

### Key Design Patterns

1. **Streaming Responses**: SSE (Server-Sent Events) for real-time AI responses
2. **Parallel Processing**: Multiple pre-retrieval checks run concurrently
3. **Fast Track Path**: Optimized path for simple queries
4. **Wrapper Pattern**: NLWebParticipant wraps existing handlers without modification
5. **Cache-First**: Memory cache for active conversations

## Important Implementation Details

### Message Flow
1. User query arrives via WebSocket/HTTP
2. Parallel pre-retrieval analysis (relevance, decontextualization, memory)
3. Tool selection based on tools.xml manifest
4. Vector database retrieval with embedding search
5. LLM-based ranking and snippet generation
6. Optional post-processing (summarization, generation)
7. Streaming response back to client

### Error Handling
- HTTP status codes: 429 (queue full), 401 (unauthorized), 400 (bad request), 500 (storage failure with retry)
- Extensive retry logic throughout the system
- Clear error messages in response payloads

### Performance Optimizations
- Direct routing for 2-participant conversations
- In-memory caching for recent messages
- Fast track for simple queries
- Minimal context inclusion (last 5 human messages)

## Testing Strategy

The testing framework (`code/python/testing/`) supports three test types:
- **end_to_end**: Full pipeline testing
- **site_retrieval**: Site discovery testing
- **query_retrieval**: Vector search testing

Test files use JSON format with test_type field and type-specific parameters.

## Current Development Focus

The codebase is on the `conversation-api-implementation` branch, focusing on:
- WebSocket-based real-time conversations
- Multi-participant support
- Message persistence and retrieval
- Maintaining backward compatibility with existing NLWebHandler

## Notes for Development

- Always check existing patterns in neighboring files before implementing new features
- The system makes 50+ LLM calls per query - optimize carefully
- Results are guaranteed to come from the database (no hallucination in list mode)
- Frontend and backend are designed to be independently deployable
- Configuration changes require server restart