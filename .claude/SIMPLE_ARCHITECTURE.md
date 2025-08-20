# Simple Architecture Design

## Core Principle
Achieve ≤105% performance for the 80% case (1 human + 1 NLWeb) while supporting multi-participant conversations.

## Minimal Component Set

### 1. ChatWebSocketHandler
- **Purpose**: Manage WebSocket connections and message routing
- **Location**: `chat/websocket.py`
- **Responsibilities**:
  - WebSocket lifecycle (connect, disconnect, reconnect)
  - Message validation and routing
  - Heartbeat/ping-pong for connection health
  - Auth token validation on connection

### 2. ConversationManager
- **Purpose**: Orchestrate conversations and message flow
- **Location**: `chat/conversation.py`
- **Responsibilities**:
  - Message sequencing (atomic ID assignment)
  - Participant management
  - Queue management and backpressure
  - Message broadcast to all participants

### 3. NLWebParticipant (Wrapper)
- **Purpose**: Wrap existing NLWebHandler without modification
- **Location**: `chat/participants.py`
- **Approach**:
  ```python
  class NLWebParticipant:
      def __init__(self, nlweb_handler):
          self.handler = nlweb_handler  # Reuse existing instance
      
      async def process_message(self, message, context):
          # Build context from recent messages
          # Call handler.ask() with context
          # Stream response back as chat messages
  ```

### 4. ChatStorage (Interface)
- **Purpose**: Abstract storage operations
- **Location**: `chat/storage.py`
- **Interface**:
  ```python
  class ChatStorage(ABC):
      async def save_message(self, message: ChatMessage) -> int
      async def get_messages(self, conv_id: str, after_seq: int) -> List
      async def get_next_sequence_id(self, conv_id: str) -> int
  ```

### 5. MemoryCache
- **Purpose**: Optimize performance for active conversations
- **Location**: `chat/cache.py`
- **Features**:
  - LRU cache for recent messages
  - In-memory sequence ID tracking
  - Write-through to storage

## Component Interactions

```
Human → WebSocket → ChatWebSocketHandler
                           ↓
                    ConversationManager
                     ↙            ↘
              MemoryCache    NLWebParticipant
                   ↓               ↓
              ChatStorage    NLWebHandler
                              (unchanged)
```

## Performance Optimizations

### For 80% Case (1 Human + 1 NLWeb)
1. **Direct routing**: Skip broadcast logic when only 2 participants
2. **Cache-first**: Recent messages stay in memory
3. **Minimal context**: Only include last 5 human messages
4. **Stream early**: Start streaming AI response immediately

### Memory Storage for Development
- Start with `MemoryStorage` implementation
- No external dependencies
- Perfect for development and testing
- Easy migration to persistent storage later

## Integration Points

### 1. Authentication Middleware
```python
# Reuse existing auth
from webserver.middleware import authenticate_request

class ChatWebSocketHandler:
    async def websocket_handler(self, request):
        # Validate auth token from existing middleware
        user = await authenticate_request(request)
```

### 2. NLWebHandler Reuse
```python
# Zero modification to NLWebHandler
nlweb = request.app['nlweb_handler']
participant = NLWebParticipant(nlweb)
```

### 3. Configuration
```yaml
# Extends existing config_nlweb.yaml
chat:
  storage:
    backend: "memory"
  context:
    human_messages: 5
```

## Message Flow Example

### Single Human + NLWeb (80% case)
1. Human sends: "What's the weather?"
2. Server assigns sequence_id: 1
3. Direct route to NLWebParticipant (no broadcast)
4. NLWeb processes with minimal context
5. Response streams back to human
6. Total latency: ~102% of current /ask

### Multi-Human Case (20%)
1. Alice sends: "What should we order for lunch?"
2. Server assigns sequence_id: 42
3. Broadcast to Bob, Charlie, and NLWeb
4. NLWeb might respond with suggestions
5. All humans see the response
6. Efficient O(N) broadcast

## Key Design Decisions

1. **No modification to NLWebHandler** - Wrap, don't change
2. **Memory-first storage** - Start simple, optimize later
3. **Single server** - No distributed complexity
4. **Reuse everything** - Auth, config, monitoring
5. **Stream early** - Don't wait for full responses
6. **Cache aggressively** - Most messages are recent

## Metrics Collection

Reuse existing metrics patterns:
```python
from webserver.metrics import track_metric

class ConversationManager:
    async def add_message(self, message):
        start = time.time()
        # ... process message
        track_metric('chat.message.latency', time.time() - start)
```

## Error Handling

Simple, clear errors:
- **429 Too Many Requests**: Queue full
- **401 Unauthorized**: Invalid auth token
- **400 Bad Request**: Invalid message format
- **500 Internal Error**: Storage failure (with retry)