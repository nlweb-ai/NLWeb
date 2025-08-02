# Storage Analysis - Retrieval Patterns for Chat

## Existing Storage Patterns

### 1. Retrieval Provider Architecture
The system uses a plugin architecture for retrieval providers:

#### Provider Interface Pattern
```python
# Base pattern from retrieval providers
class BaseRetriever(ABC):
    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[Result]
    
    @abstractmethod
    async def get_sites(self) -> List[str]
```

#### Available Providers
- **Azure Search** (`azure_search_client.py`)
- **Elasticsearch** (`elasticsearch_client.py`)
- **Qdrant** (`qdrant.py`, `qdrant_retrieve.py`)
- **PostgreSQL** (`postgres_client.py`)
- **OpenSearch** (`opensearch_client.py`)
- **Milvus** (`milvus_client.py`)
- **Snowflake** (`snowflake_client.py`)

### 2. Conversation Storage Pattern

#### Existing Implementation
```python
# From core/conversation.py
class StorageProvider(ABC):
    async def add_conversation(self, user_id, site, thread_id, 
                             user_prompt, response) -> ConversationEvent
    async def get_last_conversation(self, user_id, site) -> ConversationEvent
    async def get_conversations(self, user_id, site, thread_id) -> List
    async def search_conversations(self, query, **kwargs) -> List
```

#### Data Model
```python
@dataclass
class ConversationEvent:
    user_id: str
    site: str
    thread_id: str
    user_prompt: str
    response: str
    time_of_creation: datetime
    conversation_id: str
    event_type: str
    embedding: Optional[List[float]]
```

### 3. Storage Selection Pattern

#### Configuration-Based Selection
```yaml
# config.yaml pattern
retrieval:
  provider: "azure_search"  # or "qdrant", "elastic", etc.
  azure_search:
    endpoint: "..."
    key: "..."

conversation_storage:
  provider: "azure_search"  # Same providers available
  azure_search:
    # Reuse same config structure
```

#### Factory Pattern
```python
def get_storage_provider(config):
    provider_type = config.get("provider")
    if provider_type == "azure_search":
        return AzureSearchStorageProvider(config)
    elif provider_type == "qdrant":
        return QdrantStorageProvider(config)
    # etc.
```

## Chat Storage Requirements

### 1. Message Storage
- Store individual messages (not just request/response pairs)
- Support multiple participants per message
- Maintain strict ordering via sequence IDs
- Enable fast retrieval of recent messages

### 2. Conversation Management
- Track active participants
- Store conversation metadata
- Support conversation search
- Enable participant-based filtering

### 3. Performance Patterns
- Cache recent messages in memory
- Batch writes for efficiency
- Read-through caching
- Optimistic locking for sequence IDs

## Recommended Storage Schema

### Messages Table/Index
```python
{
    "message_id": "msg_123",
    "conversation_id": "conv_abc",
    "sequence_id": 42,
    "sender_id": "user_123",
    "sender_type": "human",  # or "ai"
    "content": "message text",
    "timestamp": "2024-01-01T12:00:00Z",
    "metadata": {}
}
```

### Conversations Table/Index
```python
{
    "conversation_id": "conv_abc",
    "participant_ids": ["user_123", "nlweb_1"],
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:05:00Z",
    "message_count": 10,
    "metadata": {}
}
```

### Participants Table/Index
```python
{
    "participant_id": "user_123",
    "conversation_ids": ["conv_abc", "conv_def"],
    "type": "human",
    "name": "Alice",
    "joined_at": "2024-01-01T12:00:00Z"
}
```

## Implementation Strategy

### 1. Extend Existing Patterns
```python
# Reuse storage provider pattern
class ChatStorageProvider(StorageProvider):
    async def save_message(self, message: ChatMessage) -> int
    async def get_messages(self, conv_id: str, after_seq: int) -> List
    async def get_next_sequence_id(self, conv_id: str) -> int
    async def update_participants(self, conv_id: str, participants: List)
```

### 2. Provider-Specific Optimizations

#### Azure Search
- Use `@search.score` for relevance
- Leverage faceting for participant filtering
- Use `$orderby` for sequence ordering

#### Qdrant
- Store messages as points with metadata
- Use payload filtering for conversations
- Leverage versioning for sequence IDs

#### Elasticsearch
- Use `_seq_no` for ordering
- Leverage aggregations for stats
- Use percolator for real-time alerts

### 3. Caching Strategy
```python
class MessageCache:
    def __init__(self, max_conversations=1000):
        self.conversations = LRUCache(max_conversations)
    
    async def get_recent_messages(self, conv_id: str, limit: int):
        if conv_id in self.conversations:
            return self.conversations[conv_id][-limit:]
        return None
```

## Migration Path

### Phase 1: Memory Storage
- Start with in-memory implementation
- Perfect for development/testing
- No external dependencies

### Phase 2: Single Provider
- Choose primary storage (e.g., Azure Search)
- Implement full functionality
- Test at scale

### Phase 3: Multi-Provider
- Add additional providers based on need
- Ensure consistent behavior
- Performance benchmarks

## Key Insights

1. **Reuse Existing Patterns**: The retrieval provider pattern works well for chat storage
2. **Schema Flexibility**: Different providers need different schemas but same interface
3. **Performance First**: Cache aggressively, write asynchronously
4. **Sequence Consistency**: Critical for message ordering across providers
5. **Search Capabilities**: Leverage each provider's strengths (vector search, facets, etc.)

## Recommendations

1. **Start Simple**: Use memory storage for MVP
2. **Match Deployment**: Use same storage as retrieval for simplicity
3. **Plan for Scale**: Design interfaces that support pagination and filtering
4. **Monitor Everything**: Track storage latency, cache hit rates, queue depths
5. **Test Failover**: Ensure graceful degradation when storage is slow/down