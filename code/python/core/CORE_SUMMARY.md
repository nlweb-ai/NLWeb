# Core Directory Summary

## Overview
The core directory contains the central processing engine for NLWeb, handling query analysis, retrieval, ranking, conversation management, and LLM integration.

## Main Components

### Base Handler (`baseHandler.py`)
- **NLWebHandler class**: Main request processing orchestrator
  - Initializes with query parameters and HTTP handler
  - Manages complete query processing pipeline
  - Coordinates between all subsystems
  - Handles streaming and regular responses
  - Session and user context management
  - Time tracking for performance metrics

### State Management (`state.py`)
- **NLWebHandlerState class**: Request state container
  - Tracks processing stages
  - Maintains context throughout request lifecycle
  - Stores intermediate results

### Configuration (`config.py`)
- Central configuration management
- Environment variable integration
- Service endpoints and API keys
- Database connections
- Model configurations

## Query Analysis Module (`query_analysis/`)

### Query Analyzer (`analyze_query.py`)
- Analyzes user queries for intent and structure
- Extracts entities and keywords
- Determines query type and complexity

### Decontextualization (`decontextualize.py`)
- Converts context-dependent queries to standalone
- Resolves pronouns and references
- Maintains conversation continuity

### Memory Management (`memory.py`)
- Conversation history tracking
- Context window management
- Short-term memory for multi-turn conversations

### Query Rewriting (`query_rewrite.py`)
- Optimizes queries for better retrieval
- Expands abbreviations and synonyms
- Handles typos and variations

### Relevance Detection (`relevance_detection.py`)
- Filters irrelevant queries
- Detects off-topic requests
- Safety and content filtering

### Required Information (`required_info.py`)
- Identifies missing information in queries
- Prompts for clarification
- Validates query completeness

## Data Retrieval and Ranking

### Retriever (`retriever.py`)
- Vector database search interface
- Multiple retrieval strategies:
  - Semantic search
  - Keyword matching
  - Hybrid approaches
- Database abstraction layer
- Supports multiple vector stores

### Ranking (`ranking.py`)
- **Ranking class**: Result scoring and ordering
  - Relevance scoring algorithms
  - Multi-factor ranking
  - Personalization support
  - Re-ranking strategies

### Post-Ranking (`post_ranking.py`)
- **PostRanking class**: Result refinement
- **SummarizeResults class**: Response generation
  - Result aggregation
  - Summary generation
  - Answer extraction
  - Citation formatting

## Conversation Management

### Conversation (`conversation.py`)
- **ConversationEvent dataclass**: Single exchange representation
- **ConversationParticipant dataclass**: User/agent representation
- **Conversation dataclass**: Multi-participant conversation
- **StorageProvider abstract class**: Storage interface
  - Add/retrieve conversations
  - Search conversation history
  - Thread management

### Storage (`storage.py`)
- **ConversationEntry dataclass**: Storage record
- **StorageProvider implementations**: 
  - Database persistence
  - Cache management
  - Migration utilities
- Async storage operations
- User conversation management

## LLM Integration

### LLM Interface (`llm.py`)
- Language model abstraction
- Multiple provider support:
  - OpenAI
  - Anthropic
  - Azure OpenAI
  - Custom models
- Streaming response handling
- Token management
- Retry logic

### Prompts (`prompts.py`)
- **PromptRunner class**: Prompt execution framework
- Dynamic prompt loading from XML
- Variable substitution
- Site-specific prompts
- Caching for performance
- Prompt versioning

### Embeddings (`embedding.py`)
- Text embedding generation
- Multiple embedding models
- Batch processing
- Caching layer
- Dimension management

## Routing and Fast Track

### Router (`router.py`)
- **Tool class**: External tool representation
- **ToolSelector class**: Tool selection logic
  - Query to tool mapping
  - Capability matching
  - Load balancing

### Fast Track (`fastTrack.py`)
- **FastTrack class**: Quick response generation
  - Cached responses
  - Common query patterns
  - Direct answers
  - Bypass full pipeline when appropriate

## Utilities (`utils/`)

### JSON Utilities (`json_utils.py`)
- JSON manipulation functions
- Object merging and trimming
- Schema-specific processors
- Format conversions

### Schema Trimming (`trim_schema_json.py`)
- Schema.org JSON-LD processing
- Content extraction
- Metadata removal
- Size optimization

### General Utilities (`utils.py`)
- Site to item type mapping
- URL formatting
- Parameter extraction
- Logging helpers

### Trimming (`trim.py`)
- Response size management
- Content truncation
- Priority-based trimming

## Processing Pipeline

1. **Request Initialization**
   - NLWebHandler creation
   - Parameter validation
   - User context setup

2. **Query Analysis**
   - Decontextualization
   - Intent detection
   - Entity extraction
   - Relevance checking

3. **Information Retrieval**
   - Fast track check
   - Vector search
   - Database queries
   - Result collection

4. **Ranking and Selection**
   - Initial ranking
   - Re-ranking
   - Filtering
   - Top-K selection

5. **Response Generation**
   - Post-ranking processing
   - Summary generation
   - Format conversion
   - Streaming setup

6. **Storage and Logging**
   - Conversation recording
   - Analytics tracking
   - Error logging

## Integration Points

### With Webserver
- Receives requests via handler
- Returns responses through callbacks
- Manages streaming connections

### With Methods
- Calls specialized processors
- Delegates domain-specific logic
- Aggregates method results

### With External Services
- Vector databases
- LLM providers
- Storage systems
- Cache layers

## Error Handling
- Graceful degradation
- Fallback strategies
- Retry mechanisms
- User-friendly error messages
- Detailed logging

## Performance Optimizations
- Async/await throughout
- Parallel processing where possible
- Caching at multiple levels
- Lazy loading
- Connection pooling

## Key Features
- Multi-turn conversation support
- Streaming response capability
- Multiple retrieval strategies
- Flexible prompt system
- Extensible architecture
- Provider abstraction