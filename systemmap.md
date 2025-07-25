# NLWeb System Map

## Overview
NLWeb is a natural language search system that provides intelligent query processing, multi-source retrieval, and AI-powered response generation. The system consists of a Python backend serving a modern JavaScript frontend via HTTP/HTTPS.

## Key APIs Exposed

### Primary HTTP Endpoints

#### Query Processing
- **`GET/POST /ask`** - Main query endpoint
  - Parameters:
    - `query` (string): User's natural language query
    - `site` (string/array): Target site(s) to search
    - `generate_mode` (string): "list", "summarize", or "generate"
    - `streaming` (boolean): Enable server-sent events streaming
    - `prev` (array): Previous queries for context
    - `last_ans` (array): Previous answers for context
    - `item_to_remember` (string): Items to remember in conversation
    - `model` (string): LLM model to use
    - `oauth_id` (string): User ID for authenticated storage
    - `thread_id` (string): Conversation thread ID
  - Returns: JSON response or SSE stream of results

#### Information Endpoints
- **`GET /sites`** - Get list of available sites
  - Parameters: `streaming` (boolean)
  - Returns: Array of site names

- **`GET /who`** - Handle "who" queries
  - Parameters: Same as `/ask`
  - Returns: Person/entity information

#### Authentication
- **`GET /api/oauth/config`** - Get OAuth configuration
  - Returns: Enabled providers and client IDs

- **`POST /api/oauth/token`** - Exchange OAuth code for token
  - Body: `{ code, provider }`
  - Returns: User info and auth token

#### Conversation Management
- **`GET /api/conversations`** - Get user's conversations
  - Headers: `Authorization: Bearer <token>`
  - Returns: Array of conversations

- **`POST /api/conversations`** - Create/update conversation
  - Headers: `Authorization: Bearer <token>`
  - Body: Conversation object
  - Returns: Saved conversation

- **`DELETE /api/conversations/{id}`** - Delete conversation
  - Headers: `Authorization: Bearer <token>`
  - Returns: Success status

### Streaming Message Types (SSE)
- `api_version` - API version information
- `query_analysis` - Query understanding results
- `decontextualized_query` - Reformulated query for context
- `remember` - Items to remember
- `asking_sites` - Sites being queried
- `result_batch` - Batch of search results
- `summary` - Summarized response
- `nlws` - Natural language web search response (for generate mode)
- `ensemble_result` - Multi-source recommendations
- `chart_result` - Data visualization HTML
- `results_map` - Location-based results for mapping
- `intermediate_message` - Progress updates
- `complete` - Stream completion signal
- `error` - Error messages

## Key Data Structures

### Query Request Structure
```python
{
    "query": str,                    # User's query text
    "site": Union[str, List[str]],   # Target site(s)
    "generate_mode": str,            # "list", "summarize", "generate"
    "streaming": bool,               # Enable SSE streaming
    "prev": List[str],              # Previous queries
    "last_ans": List[Dict],         # Previous answers [{title, url}]
    "item_to_remember": str,        # Memory items
    "model": str,                   # LLM model name
    "oauth_id": str,                # User identifier
    "thread_id": str,               # Conversation thread
    "display_mode": str,            # "full" or other display modes
}
```

### Search Result Format
```python
# Internal representation
[url, json_data, name, site]  # Tuple format

# API response format
{
    "url": str,
    "name": str,
    "site": str,
    "score": float,
    "description": str,
    "schema_object": dict,  # Schema.org structured data
    "details": dict,        # Additional details
}
```

### Conversation Structure
```python
{
    "id": str,                      # Unique conversation ID
    "title": str,                   # Conversation title
    "messages": List[{
        "content": str,             # Message content
        "type": str,                # "user" or "assistant"
        "timestamp": int,           # Unix timestamp
        "parsedAnswers": List[{     # For assistant messages
            "title": str,
            "url": str
        }]
    }],
    "timestamp": int,               # Last update timestamp
    "site": str,                    # Associated site
    "user_id": str,                # Owner user ID
}
```

### Streaming Message Format
```python
{
    "message_type": str,            # Type of message
    "query_id": str,               # Query identifier
    # Type-specific fields:
    "message": str,                # For text messages
    "results": List[dict],         # For result batches
    "answer": str,                 # For nlws responses
    "items": List[dict],           # For nlws items
    "html": str,                   # For chart results
    "locations": List[{            # For map results
        "title": str,
        "address": str
    }]
}
```

## Logical Flow of Queries to NLWebHandler

### 1. Request Reception (WebServer.py)
```
HTTP Request → Route Matching → Handler Selection → Parameter Parsing
```

### 2. Handler Initialization (baseHandler.py)
```
NLWebHandler Creation → State Initialization → Streaming Setup
```

### 3. Query Preparation Phase
Parallel execution of:

#### Fast Track Path:
```
Direct Vector Search → Early Results → Stream if Available
```

#### Analysis Path:
```
1. Decontextualization (if prev queries exist)
   - Use LLM to reformulate query with context
   
2. Query Analysis
   - Item type detection
   - Relevance checking
   - Memory processing
   
3. Tool Selection
   - Load tool definitions
   - Evaluate tools against query
   - Route to specialized handler if matched
```

### 4. Retrieval Phase (retriever.py)
```
1. Prepare Query
   - Apply site filters
   - Format for vector DB
   
2. Parallel Search
   - Query multiple vector DB endpoints
   - Aggregate results
   - Deduplicate by URL
   
3. Result Processing
   - Convert to standard format
   - Apply initial filtering
```

### 5. Ranking Phase (ranking.py)
```
1. LLM-based Ranking (if enabled)
   - Score results for relevance
   - Apply query-specific criteria
   
2. Post-Ranking Tasks
   - Additional filtering
   - Result enrichment
   - Score normalization
```

### 6. Response Generation
Based on `generate_mode`:

#### List Mode:
```
Format Results → Stream result_batch messages → Complete
```

#### Summarize Mode:
```
Results → LLM Summarization → Stream summary + results → Complete
```

#### Generate Mode:
```
Results → GenerateAnswer Handler → RAG Generation → Stream nlws message → Complete
```

### 7. Storage Phase (if authenticated)
```
Collect Results → Format Conversation → Store to Database
```

## System Components Interaction

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Browser   │────▶│  WebServer   │────▶│   Router    │
│ (JS Client) │◀────│   (HTTP)     │◀────│   (Tools)   │
└─────────────┘     └──────────────┘     └─────────────┘
                            │                     │
                            ▼                     ▼
                    ┌──────────────┐     ┌─────────────┐
                    │ NLWebHandler │────▶│ Specialized │
                    │    (Base)    │     │  Handlers   │
                    └──────────────┘     └─────────────┘
                            │
                    ┌───────┴───────┐
                    ▼               ▼
            ┌─────────────┐ ┌─────────────┐
            │  Retriever  │ │     LLM     │
            │ (Vector DB) │ │  Provider   │
            └─────────────┘ └─────────────┘
```

## Configuration System
- **config.yaml** - Main configuration
- **config_retrieval.yaml** - Retrieval endpoints
- **config_llm.yaml** - LLM provider settings
- **oauth_config.yaml** - OAuth provider configuration
- **Site-specific configs** - Per-site customization

The system is designed for extensibility, supporting multiple vector databases, LLM providers, and specialized tools while maintaining a consistent API interface.