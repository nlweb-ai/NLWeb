# Final Architecture Document - Multi-Participant Chat System (v3)

## Project Overview

This open source project extends an AI-powered web assistant (NLWeb) with real-time multi-participant chat capabilities. The system enables multiple humans to collaborate with AI agents in shared conversations, while maintaining the performance characteristics that make single-user interactions feel instant.

### Core Vision
- **Enable true multi-participant conversations** - Multiple humans and AI agents communicating naturally
- **Bring AI collaboration to the Web** through real-time WebSocket connections
- **Support human-to-human communication** with AI agents as intelligent participants
- **Preserve existing functionality** while adding powerful new capabilities
- **Optimize for the common case** (80% of usage is one human with one AI agent)
- **Scale gracefully** to support team collaborations (2-5 humans is 15% of usage) and larger groups (up to 100 total participants)

## Architecture Overview

### System Design Philosophy

We chose a **simple, proven architecture** that prioritizes performance and reliability:

**Multi-Participant Support**: While 80% of conversations involve just 1 human + 1 NLWeb agent, the system fully supports multiple human participants (2-5 humans is common at 15% of usage) and can scale up to 100 total participants per conversation. The hub-and-spoke architecture ensures efficient O(N) message broadcast regardless of participant count.

**Key Principles:**
1. **Hub-and-spoke messaging** - Server mediates all communication (O(N) complexity, not O(N²))
2. **Single server per conversation** - No distributed complexity in MVP
3. **Performance-first** - Must stay within 105% of current single-user latency
4. **Preservation** - Existing endpoints and handlers remain completely unchanged
5. **Production-ready** - Security, monitoring, and failure handling built-in

### Component Architecture

```
chat/                           # Core chat system
├── schemas.py                  # Data models (messages, conversations)
├── storage.py                  # Storage interface and routing
├── websocket.py               # Real-time communication
├── participants.py            # Human and AI participant abstractions
├── conversation.py            # Message orchestration
├── cache.py                   # Performance optimization
├── metrics.py                 # Operational monitoring
└── api.py                     # REST endpoints

chat_storage_providers/         # Pluggable storage backends
├── azure_storage.py           # Azure AI Search
├── qdrant_storage.py          # Qdrant vector DB
├── elastic_storage.py         # Elasticsearch
└── memory_storage.py          # Development/testing

webserver/routes/
├── api.py                     # PRESERVED - Existing /ask endpoint
├── mcp.py                     # PRESERVED - MCP protocol endpoints
└── chat.py                    # NEW - WebSocket chat routes
```

### Message Flow

1. **Any human sends message** → WebSocket → Server
2. **Server assigns sequence ID** → Ensures strict ordering
3. **Queue check** → Reject if conversation queue full (429)
4. **Server broadcasts to ALL participants** → All other humans + all NLWeb agents
5. **Async persistence** → Message saved after delivery
6. **NLWeb agents process** → Each decides whether to respond
7. **AI responses stream back** → Appear as new messages to all humans

**Example with 3 humans + 2 NLWeb agents**:
- Alice sends "What's the weather?"
- Server assigns sequence_id: 42
- Bob and Charlie receive the message immediately
- Both NLWeb agents receive the message
- NLWeb-1 responds with weather info
- All humans see the response
- Total messages delivered: 4 (broadcast) + 4 (response) = 8 messages for 5 participants

### Performance Characteristics

- **Primary use case (80%)**: 1 human + 1 AI agent = Direct message routing
- **Multi-human groups (15%)**: 2-5 humans + AI agents = Efficient broadcast to all humans
- **Large groups (5%)**: 7-100 participants (mix of humans and AI) = Still responsive

**Target Metrics:**
- WebSocket handshake: ≤50ms overhead
- Message routing: ≤1ms for primary use case
- Memory usage: ≤110% of current single-user equivalent
- End-to-end latency: ≤105% of current /ask endpoint

**Note on Multi-Human Conversations**: When multiple humans are in a conversation, each sends messages via their own WebSocket connection. The server broadcasts each message to all other participants (both humans and AI agents). This hub-and-spoke model maintains O(N) complexity and ensures consistent message ordering via sequence IDs.

## Security & Privacy

### Authentication & Authorization
- **Reuses existing auth middleware** - No chat-specific ACLs needed
- **WebSocket authentication** - Token validated on connection establishment
- **Conversation access control** - Leverages existing user permissions
- **Session management** - Auth tokens reused during reconnection

### Data Protection
- **Encryption in transit** - WSS (TLS-encrypted WebSockets) required in production
- **Encryption at rest** - Follows deployment's database encryption standards
- **Input validation** - All message content sanitized before processing
- **PII handling** - Messages can be redacted upon user request
- **Data retention** - Configurable per deployment (GDPR/CCPA compliant)

### Security Model
- **Who can join**: Users with valid auth tokens and appropriate conversation access
- **Multi-human conversations**: Each human must authenticate separately via their own WebSocket
- **Token lifecycle**: Follows existing application authentication patterns
- **Audit trail**: All messages include sender_id for accountability
- **Rate limiting**: Per-conversation queue limits prevent abuse
- **Privacy**: Humans only see conversations they're participants in

## Observability & Operations

### Required Metrics
The system collects these metrics using existing monitoring patterns:

- **WebSocket connections** 
  - Current active connections
  - Connection rate (connects/disconnects per minute)
  - Connection duration distribution
  
- **Message performance**
  - Latency percentiles (p50, p95, p99)
  - Messages per second by conversation
  - Message size distribution
  
- **Queue health**
  - Queue depth per conversation
  - Queue overflow rate (429 responses)
  - Message drop rate (when prioritizing)
  
- **Storage operations**
  - Sequence ID assignment latency
  - Persistence success/failure rate
  - Cache hit/miss ratio
  
- **NLWeb integration**
  - Response timeout rate
  - Context building time
  - Active NLWeb participants

### Health Check Endpoint
```
GET /health/chat
{
  "status": "healthy",
  "checks": {
    "websocket": {
      "status": "healthy",
      "connections": 142,
      "connection_limit": 10000
    },
    "storage": {
      "status": "healthy",
      "backend": "azure",
      "latency_ms": 12
    },
    "queues": {
      "status": "healthy",
      "total_conversations": 89,
      "queues_near_limit": 2
    }
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Monitoring Integration
- Metrics exposed in format compatible with existing monitoring stack
- Alerts configured for queue overflow, high latency, storage failures
- Dashboard templates provided for common visualizations

## Reliability & Failure Handling

### Message Delivery Guarantees

**At-least-once delivery** with the following implementation:
- Client assigns unique message ID before sending
- Server acknowledges receipt with sequence ID
- Client retries with same ID if no acknowledgment
- Server deduplicates by message ID
- Persistence happens after participant delivery

### Backpressure & Rate Limiting

**Queue Management:**
- Per-conversation message queue with configurable limit (default 1000)
- Queue size checked before accepting new messages
- HTTP 429 returned when queue full
- Metrics track queue depth and overflow rate

**Prioritization when queue near limit:**
1. Human messages always accepted (up to hard limit) - from ANY human participant
2. Drop oldest pending NLWeb processing jobs first
3. System messages (join/leave) have lower priority
4. Clear error messages guide client behavior

**Multi-human fairness**: When multiple humans are typing simultaneously, the server processes messages in order of arrival at the server (first-come, first-served), ensuring no human dominates the conversation.

### Failure Scenarios & Recovery

| Failure Type | Detection | Behavior | Recovery |
|--------------|-----------|----------|----------|
| Network partition | WebSocket ping timeout | Client auto-reconnects | Exponential backoff with max retries |
| Server crash | Health check fails | Conversations persist | Resume from storage, <30s restart |
| Storage outage | Write timeout | Cache continues, writes queued | Retry with backoff, alert operators |
| NLWeb timeout | Response time > limit | Mark as failed, continue | Client can retry message |
| Queue overflow | Queue size > limit | Return 429 | Client backs off, shows user error |
| Auth failure | Token validation fails | Close connection | Client must re-authenticate |
| Memory pressure | Cache size > limit | Evict old conversations | Reload from storage on demand |

### Connection Resilience

- **Heartbeat mechanism**: WebSocket ping/pong every 30-60 seconds
- **Dead connection detection**: Close after 10 minutes without pong
- **Reconnection protocol**: 
  - Client provides last sequence ID
  - Server sends only missed messages
  - Exponential backoff: 1s, 2s, 4s... max 30s
- **Session continuity**: Auth tokens reused during reconnection

### Multi-Human Connection Management

When multiple humans participate in a conversation:
- **Independent connections**: Each human has their own WebSocket connection
- **Participant tracking**: Server maintains list of active connections per conversation
- **Join notifications**: When a human joins, others receive a participant_update message
- **Leave notifications**: Clean disconnection or timeout triggers participant_update
- **Message ordering**: All humans see messages in same sequence ID order
- **Fair queuing**: Each human's messages get equal priority in the queue

## Configuration

All settings managed via hierarchical YAML configuration:

```yaml
# config_nlweb.yaml
chat:
  storage:
    backend: "azure"  # or "qdrant", "elastic", "memory"
    azure:
      endpoint: "${AZURE_SEARCH_ENDPOINT}"
      key: "${AZURE_SEARCH_KEY}"
      index: "chat_messages"
    cache:
      max_conversations: 1000
      max_messages_per_conversation: 100
      ttl_seconds: 3600
  
  context:
    human_messages: 5       # Messages included in NLWeb context
    nlweb_timeout: 20       # Seconds before abandoning NLWeb response
    ws_max_retries: 10      # WebSocket reconnection attempts
    heartbeat_interval: 30  # Seconds between ping/pong
  
  limits:
    max_participants: 100   # Per conversation
    queue_size: 1000        # Messages per conversation
    max_message_size: 10000 # Characters
    
  security:
    require_wss: true       # Enforce TLS in production
    retention_days: 90      # Default data retention
```

### Configuration Philosophy
- **YAML over environment variables**: Hierarchical, self-documenting
- **Environment-specific files**: config_dev.yaml, config_prod.yaml
- **Sensitive values**: Can reference environment variables
- **Validation on startup**: Fail fast with clear errors
- **Hot reload**: Not needed for MVP, configuration is stable

## Scaling Strategy

### Current Architecture (MVP)
- Single server handles all conversations
- Each conversation lives on one server
- Storage backend handles persistence
- Good for hundreds of concurrent conversations

### Future Scaling Path

When scaling is needed, the architecture supports evolution:

**Phase 1: Vertical Scaling**
- Increase server resources
- Optimize hot paths
- Add read replicas for storage

**Phase 2: Sticky Sessions** (No code changes)
- Load balancer with session affinity
- Conversations stay on assigned server
- Simple deployment, rolling updates work

**Phase 3: Redis Pub/Sub** (Minor changes)
- Add Redis for cross-server messaging
- Conversations can migrate between servers
- Enables zero-downtime deployments

**Phase 4: Full Distribution** (If needed)
- Partition conversations by ID
- Dedicated message queue service
- Horizontal scaling with consistent hashing

The key is that the current architecture doesn't prevent this evolution.

## API Design

### Core Endpoints

```
POST /chat/conversations
{
  "participant_ids": ["user123", "user456"]  // Can include multiple humans
}
Response: {"conversation_id": "conv_abc123"}

GET /chat/conversations
Response: [{"id": "conv_abc123", "updated_at": "...", "participant_count": 3}]

GET /chat/ws/{conversation_id}
Upgrade: websocket
Sec-WebSocket-Protocol: chat

GET /health/chat
Response: <see health check section>
```

**Multi-Human Example**: When creating a conversation with `participant_ids: ["alice", "bob", "charlie"]`, all three humans can connect via WebSocket. The system automatically adds NLWeb agents based on configuration. Each human sees all messages from other humans and AI responses.

### WebSocket Protocol

```javascript
// Client → Server (from any human participant)
{
  "type": "message",
  "content": "Hello everyone",
  "message_id": "client_generated_uuid"  // For deduplication
}

// Server → All Clients (broadcast to all humans + trigger AI agents)
{
  "type": "message",
  "id": "msg_123",
  "sequence_id": 45,
  "sender_id": "alice_456",      // Which human sent it
  "sender_name": "Alice",
  "content": "Hello everyone",
  "server_timestamp": "2024-01-01T12:00:01Z"
}

// Server → All Clients (when participant count changes)
{
  "type": "participant_update",
  "participants": ["alice_456", "bob_789", "nlweb_1"],
  "participant_count": 3,
  "input_mode": "multi"  // or "single" when only 2 participants
}

// Server → Specific Client (on reconnect)
{
  "type": "sync",
  "messages": [...],  // Messages after last_sequence_id
  "current_sequence_id": 50,
  "participants": ["alice_456", "bob_789", "nlweb_1"]
}

// Server → All Clients (error)
{
  "type": "error",
  "code": "QUEUE_FULL",
  "message": "Conversation queue limit reached",
  "retry_after": 5  // Seconds
}
```

## Frequently Asked Questions

### Storage & Persistence

**Q: Why support multiple storage backends from the start?**
A: Open source projects need flexibility. Organizations already have preferred databases - forcing PostgreSQL only would exclude many users. The clean abstraction adds minimal complexity.

**Q: What happens if two messages arrive at the exact same time?**
A: The server assigns sequence IDs atomically. Each backend implements this differently (Azure: etag, Qdrant: version, etc.). Messages get unique, ordered IDs regardless of arrival time.

**Q: How is message persistence handled?**
A: Messages are delivered to participants first, then persisted asynchronously. This ensures real-time performance. Occasional persistence failures are acceptable (this is chat, not banking).

**Q: What about message retention?**
A: Configurable per deployment via `chat.security.retention_days`. The system supports GDPR/CCPA compliance through configurable retention and PII redaction.

### WebSocket & Connectivity

**Q: Why not use socket.io?**
A: Our aiohttp-based WebSocket implementation is only ~200 lines and gives us full control. Socket.io would add unnecessary weight and complexity for features we don't need.

**Q: How does reconnection work?**
A: Clients automatically reconnect with exponential backoff. They provide their last sequence ID, and the server sends only missed messages. Auth tokens are reused.

**Q: What about corporate proxies that block WebSockets?**
A: In practice, WSS (port 443) works everywhere HTTPS works. For the rare exception, the clean API design allows adding long-polling later if needed.

### Configuration & Operations

**Q: Why YAML instead of environment variables?**
A: YAML provides hierarchical configuration, inline documentation, and validation. Reading once at startup has no performance impact. Environment variables become unwieldy with 20+ settings.

**Q: How do you handle queue overflow?**
A: Return HTTP 429 with a clear error. Clients implement exponential backoff. When queues are nearly full, we drop oldest NLWeb processing jobs first since they can be regenerated.

**Q: What metrics are absolutely required?**
A: Connection count, message latency (p50/p95), queue depth, and sequence ID lag. These catch most operational issues early.

### Architecture & Scale

**Q: How do multiple humans participate in the same conversation?**
A: Each human connects via their own WebSocket connection. The server maintains a participant list and broadcasts messages to all connected participants. With 2-5 humans (15% of usage), this is still very efficient. Sequence IDs ensure all participants see messages in the same order regardless of network latency differences.

**Q: Why separate components instead of one ChatHub class?**
A: Separation of concerns leads to more maintainable code. WebSocket management, conversation orchestration, and participant handling have different responsibilities and testing needs.

**Q: How does this scale beyond one server?**
A: The architecture supports evolution: sticky sessions (no code change) → Redis pub/sub (minimal change) → full distribution (when needed). Most deployments won't need this.

**Q: Why five phases instead of three?**
A: Each phase builds logically on the previous one. This prevents rework and ensures clean interfaces between components. The phases also align with natural testing boundaries.

## Summary of Key Decisions

1. **Performance First**: 80% of usage is 1 human + 1 NLWeb - optimize aggressively for this case
2. **Multi-Human Support**: 15% of usage is 2-5 humans collaborating with AI agents
3. **Simplicity with Flexibility**: Clean abstractions that support multiple backends without complexity
4. **Reliability Built-in**: At-least-once delivery, queue limits, comprehensive metrics
5. **Preservation**: Never modify /ask, /mcp, or NLWebHandler - reuse existing middleware
6. **YAML Configuration**: Hierarchical, self-documenting, environment-specific
7. **Test-Driven Development**: Ensures reliability and catches regressions early
8. **Operational Excellence**: Health checks, metrics, and clear failure handling from day one
9. **Clear Scaling Path**: Architecture supports growth without rewrites

## Contributing

This open source project welcomes contributions! Key areas for community involvement:

1. **Storage backends** - Add support for your favorite database
2. **Performance optimizations** - Help us stay under the 105% latency target
3. **AI agent patterns** - Develop new ways for AI agents to collaborate
4. **Monitoring & observability** - Dashboards, alerts, and debugging tools
5. **Security enhancements** - Penetration testing, audit logging, compliance

### Getting Started
1. Review the implementation plan for detailed technical specifications
2. Check CURRENT_STATE.md for active development status
3. Run performance benchmarks before and after changes
4. Ensure /ask, /mcp, and NLWebHandler remain unmodified
5. Write tests first (TDD approach)

### Design Constraints
- **Performance**: Must maintain ≤105% latency vs current /ask endpoint
- **Preservation**: Cannot modify existing endpoints or handlers
- **Simplicity**: Avoid distributed complexity in MVP
- **80% optimization**: Focus on 1 human + 1 AI use case
- **Configuration**: Use YAML following existing patterns

## Future Roadmap

### Near Term
- Additional storage backends based on community needs
- Performance optimizations for the 80% case
- Enhanced monitoring dashboards
- Client libraries (JavaScript, Python)
- Typing indicators for multi-human conversations
- Presence awareness (who's online)

### Medium Term
- Horizontal scaling with Redis pub/sub
- Conversation summarization for context
- Rich media message support
- Advanced AI collaboration patterns
- Human-to-human private messages within group chats
- @mentions for directing messages to specific participants

### Long Term
- Federated conversations across organizations
- AI agent marketplace
- Custom AI agent development framework
- Multi-modal communication support
- Conversation branching and threading
- Advanced moderation tools for large groups

---

*This architecture brings real-time AI collaboration to the web while maintaining the performance and simplicity that makes great software. We're excited to see what the community builds with it!*