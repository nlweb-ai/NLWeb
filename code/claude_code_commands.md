# Final Claude Code Implementation Guide - Multi-Participant Chat System (v3)

## 🚨 CRITICAL: How to Use This Guide with Claude Code

### Golden Rules
1. **NEVER paste this entire document** - Work in small chunks
2. **Start with Command 1** below, then follow the phases
3. **Use the Session Management commands** when context gets full
4. **Keep the Reference Info handy** for when Claude Code asks questions

### When Context Fills Up (Claude Code will warn you)
```
# Paste this exactly:
What's our current context usage?

If it's over 60%, please:
1. Update CURRENT_STATE.md with our current progress
2. Update NEXT_STEPS.md with the immediate next task
3. Commit all changes with message "WIP: [describe what we just did]" without attribution
4. compact
5. Continue with what you were doing
```

### To Resume Work After a Break
```
# Paste this exactly:
Continue the chat implementation.
/cat CURRENT_STATE.md
/cat PROGRESS.md
git log --oneline -10

Show me where we left off and what the next step should be.
```

---

## 📋 Command 1: Start the Project (ALWAYS START HERE)

```
Create the following state tracking files:
- CURRENT_STATE.md - what we're working on right now
- PROGRESS.md - completed tasks with commit hashes
- DECISIONS.md - architecture decisions
- BASELINE_PERFORMANCE.md - performance metrics

Then measure the current /ask endpoint performance:
1. Find the /ask endpoint in webserver/routes/api.py
2. Write a simple benchmark script that times how long a typical request takes
3. Document the average latency in BASELINE_PERFORMANCE.md

We're building a multi-participant chat system that supports:
- Multiple humans in the same conversation (each with their own WebSocket)
- Multiple AI agents (NLWeb) participating
- 80% of usage: 1 human + 1 NLWeb agent
- 15% of usage: 2-5 humans + NLWeb agents
- 5% of usage: larger groups up to 100 total participants

Key constraint: Performance must be ≤105% of current /ask endpoint latency.

Also add these settings to config_nlweb.yaml:
```yaml
chat:
  storage:
    backend: "memory"  # Start with memory for development
  context:
    human_messages: 5
    nlweb_timeout: 20
    ws_max_retries: 10
  limits:
    max_participants: 100
    queue_size: 1000  # Messages per conversation
```
```

---

## Phase 1: Foundation & Research

### After Command 1 completes, paste this:

```
Now let's understand the architecture which is in docs/chat_system_architecture.md
That document covers the following points. Make sure you understand it.

1. How to achieve ≤105% performance for 1 human + 1 NLWeb (80% of usage)?
2. What's the minimal set of components needed?
3. How to wrap NLWebHandler without modification?
4. How does MCP currently integrate with NLWebHandler?
5. How to leverage existing retrieval storage patterns?
6. How to implement queue limits and backpressure?
7. What metrics are critical for operations?

Create these files:
- SIMPLE_ARCHITECTURE.md with component design
- IMPLEMENTATION_STRATEGY.md with 5-phase plan
- MCP_INTEGRATION.md documenting current MCP behavior
- STORAGE_ANALYSIS.md analyzing retrieval patterns for chat
- SECURITY_PLAN.md with auth, encryption, and PII handling

Focus on simplicity. Single server per conversation is fine.
Note: While 80% of chats are 1 human + 1 NLWeb, the system supports multiple humans (up to 100 total participants).
```

---

## Phase 2: Core System (TDD)

### Command 2: Data Models

```
Let's implement the chat data models. We're doing TDD.

First, create tests/test_chat_schemas.py with tests for:
- ChatMessage with sequence_id for ordering
- Conversation with participant tracking (supporting multiple humans)
- Message types (TEXT, SYSTEM, NLWEB_RESPONSE, etc.)
- Queue overflow behavior
- Participant join/leave events

Then create chat/schemas.py with:
- Frozen dataclass for ChatMessage including sequence_id field and sender_id
- Conversation dataclass with active_participants set (humans and AI)
- ParticipantInfo to track human vs AI participants
- MessageType and MessageStatus enums
- QueueFullError for backpressure

Key requirements: 
- Messages must have server-assigned sequence IDs for ordering
- Conversations must support multiple human participants
- Each human identified by unique sender_id
- Conversations enforce queue_size limit from config
```

### Command 3: Storage System with Monitoring

```
Implement the chat storage system. Create these files:

1. chat/storage.py - merged interface and client:
   - Abstract ChatStorageInterface class with methods: store_message, get_conversation_messages, get_next_sequence_id
   - ChatStorageClient class that routes to backends based on config
   - Must support atomic sequence ID generation (critical for multi-human message ordering)
   - Track sender_id to distinguish between multiple humans
   - Read backend type from config_nlweb.yaml chat.storage section
   - Add metrics collection for storage operations

2. chat/cache.py:
   - In-memory cache for active conversations
   - Keep only last 100 messages under memory pressure
   - Thread-safe operations (critical for concurrent human messages)
   - Queue size enforcement per conversation
   - Track all active participants (multiple humans + AI)
   - Metrics for cache hit/miss rates

3. Create directory chat_storage_providers/ with memory_storage.py:
   - Implements ChatStorageInterface
   - In-memory storage for development
   - Simple sequence counter (atomic increment)
   - Enforce queue limits (return error when full)
   - Store participant metadata

4. chat/metrics.py:
   - Simple metrics collection (connections per human, latency, queue depth)
   - Track multi-human conversation patterns
   - Use existing monitoring patterns from the codebase

Remember: 
- Messages are persisted AFTER delivery to ALL participants (async)
- At-least-once delivery: store message ID for deduplication
- Queue full returns specific error for 429 response
- Multiple humans can send messages simultaneously

Write tests first in tests/test_chat_storage.py
Include tests for concurrent message storage from multiple humans.
```

---

## Phase 3: Real-time Communication (TDD)

### Command 4: WebSocket Infrastructure with Security

```
Implement WebSocket infrastructure in chat/websocket.py:

Requirements:
- Support multiple humans, each with their own WebSocket connection
- Client reconnection with exponential backoff (1s, 2s, 4s... max 30s)
- Configurable max retries via chat.context.ws_max_retries
- WebSocket ping/pong every 30-60 seconds
- Connection dead after 10 minutes without pong
- Participant limit: max from chat.limits.max_participants
- Use WSS (TLS) in production environments

Include:
- WebSocketManager class that tracks all human connections per conversation
- join_conversation that enforces participant limit
- Efficient O(N) broadcast to all participants (humans + AI)
- Queue size checking before accepting messages
- Client-side reconnection logic with exponential backoff
- Reuse existing auth middleware for WebSocket authentication
- Metrics: active connections, messages/second, queue depth

Write tests first. On connection failure, show error and require refresh.
```

### Command 5: NLWeb Integration

```
Implement NLWeb integration in chat/participants.py:

Create NLWebParticipant class that:
- Wraps existing NLWebHandler WITHOUT modifying it
- Processes EVERY message (from any human or other NLWeb)
- NLWeb decides internally whether to respond
- Builds context with: last N messages from ALL humans (configurable) + last 1 NLWeb message
- Adds user_id parameter to identify which human/participant sent the message
- Has configurable timeout (from chat.context.nlweb_timeout)
- Streams responses back as chat messages visible to ALL participants
- Handles queue full gracefully (drop old NLWeb responses first)

Also create NLWebContextBuilder that:
- Reads chat.context.human_messages from config
- Collects messages from all human participants (not just one)
- Preserves sender information in context
- Converts chat history to NLWeb format with prev_queries and last_answers

Critical: Use NLWebHandler exactly as-is, no modifications. Write tests first.
Test multi-human scenarios where NLWeb sees messages from different humans.
```

---

## Phase 4: Conversation Orchestration

### Command 6: Conversation Manager with Reliability


```
Implement conversation orchestration in chat/conversation.py:

Create ConversationManager that:
- Routes messages between ALL participants (multiple humans + multiple AI)
- Tracks active human WebSocket connections
- Assigns sequence IDs to incoming messages
- Delivers to participants immediately (broadcast to all)
- Triggers async persistence after delivery
- Triggers ALL NLWeb participants for EVERY message
- Handles participant failures gracefully
- Enforces queue limits (reject with 429 when full)
- Implements at-least-once delivery with acknowledgments

Smart input completion:
- Single mode (1 human + 1 NLWeb): 100ms timeout
- Multi mode (2+ humans or 3+ total): 2000ms timeout
- Server tracks mode based on active participant count
- Mode changes broadcast to all humans when participants join/leave

Queue management:
- Check queue size before accepting new messages
- When full, prefer dropping oldest NLWeb processing jobs
- Return clear error for client 429 handling

Write tests first. Focus on 1 human + 1 NLWeb performance while supporting multi-human scenarios.
```
---

## Phase 5: Integration & Deployment

### Command 7: API Routes with Health Checks

```
Add chat API endpoints in webserver/routes/chat.py:

POST /chat/conversations    # Create conversation (with multiple humans)
GET  /chat/conversations    # List user conversations  
GET  /chat/ws/{conv_id}     # WebSocket upgrade (one per human)
GET  /health/chat          # Health check endpoint

Health check should return:
{
  "status": "healthy",
  "connections": <total_active_websockets>,
  "conversations": <active_conversation_count>,
  "participants_by_conversation": {
    "<conv_id>": {"humans": 3, "ai_agents": 2}
  },
  "queue_depths": {<conv_id>: <depth>},
  "storage": "connected"
}

Requirements:
- Support creating conversations with multiple initial participants
- Each human gets their own WebSocket connection
- Reuse existing auth middleware exactly
- Follow existing aiohttp patterns
- No conflicts with /ask or /mcp endpoints
- Clean error handling (especially 429 for queue full)
- Security: validate all inputs, use WSS in production

Also add chat-specific metrics endpoint if not covered by existing monitoring.

Keep the API minimal and focused.
```

### Command 8: Performance Verification & Security Audit

```
Run comprehensive verification:

1. Performance tests:
   - Single user chat latency vs /ask endpoint latency
   - Multi-human scenarios: 2-5 humans + NLWeb performance
   - Memory usage comparison
   - WebSocket overhead measurement
   - Queue limit behavior under load
   - Message broadcast timing with 10+ participants

2. Security audit:
   - Verify WSS encryption enabled
   - Check auth token validation on each WebSocket
   - Test message content sanitization
   - Verify PII can be redacted on request
   - Ensure humans can only see conversations they're in
   - Document data retention policy

3. Reliability tests:
   - At-least-once delivery with network interruption
   - Queue overflow returns 429 properly
   - Sequence IDs remain ordered after reconnection
   - Multiple humans reconnecting simultaneously
   - Metrics accurately track system state

4. Multi-human specific tests:
   - 3 humans sending messages simultaneously
   - Participant join/leave during active conversation
   - Message ordering consistency across all humans
   - Input mode switching (single → multi) on participant changes

5. Update documentation:
   - Add security section to README
   - Document metrics and monitoring
   - Multi-human setup instructions
   - Note scaling path (future Redis pub/sub)

If performance > 105% of baseline for 1 human + 1 NLWeb, we need to optimize.
Multi-human scenarios can have slightly relaxed requirements but must feel real-time.
```

---

## 🚨 Emergency Recovery Command

```
I lost context. Please help me recover:
1. Run: git log --oneline -20
2. Run: ls *.md
3. Load any state files found
4. Check: git status
5. Tell me what we were working on and what's next
```

---

## 📋 Reference Information (Paste When Claude Code Asks)

### When Asked About Architecture:
```
Architecture decisions already made:
- Single server per conversation (no distributed complexity)
- Supports multiple humans per conversation (each with own WebSocket)
- Sequence IDs for message ordering (not timestamps)
- Async persistence after message delivery
- 100 message cache limit under memory pressure
- Client-side reconnection with exponential backoff
- Queue limits with 429 on overflow
- At-least-once delivery with acknowledgments
- 80% of usage is 1 human + 1 NLWeb
- 15% of usage is 2-5 humans + NLWeb agents
- Configuration via YAML (hierarchical, well-documented)
```

### When Asked What to Preserve:
```
MUST preserve exactly (no modifications):
- /ask endpoint in webserver/routes/api.py
- /mcp endpoints in webserver/routes/mcp.py
- NLWebHandler class in core/baseHandler.py
- MCP interface in webserver/mcp_wrapper.py
- Existing auth middleware
```

### When Asked About Performance:
```
Performance requirements:
- 1 human + 1 NLWeb conversations: ≤105% of current /ask latency
- 2-5 humans + NLWeb: Still maintain <200ms message delivery
- WebSocket handshake: ≤50ms overhead
- Message routing: ≤1ms for 2-participant case, ≤5ms for 10 participants
- Context building: ≤5ms regardless of participant count
- This is the #1 priority - fail the build if we exceed 105% for primary case

Note: Multi-human scenarios (15% of usage) can have slightly relaxed latency
requirements, but must still feel real-time (<200ms perceived latency).

All settings configured in config_nlweb.yaml
```

### When Asked About Security:
```
Security requirements:
- Use WSS (TLS WebSockets) in production
- Reuse existing auth middleware
- Validate and sanitize all inputs
- Support PII redaction on request
- Log security events for audit
- Document data retention policies
```

### When Asked About Operations:
```
Operational requirements:
- Health check endpoint (/health/chat)
- Metrics: connections, latency (p50/p95), queue depth
- Queue limits with proper 429 responses
- At-least-once message delivery
- Graceful handling of storage failures
```

---

## Context Management Instructions for Claude Code

### Core Commands Claude Code Should Know
- **`ultrathink`** - Use for complex architecture decisions
- **`think`** - Use for standard implementation logic
- **`/compact`** - Use proactively when context reaches ~60%
- **`/save [filename]`** - Save critical state for later reference
- **`/cat [filename]`** - Retrieve saved content

### Files to Maintain
```bash
CURRENT_STATE.md      # What we're working on right now
PROGRESS.md          # Completed tasks with commit hashes
DECISIONS.md         # Architecture decisions and rationale
NEXT_STEPS.md        # Immediate next actions
```

### Commit Pattern
```bash
git commit -m "Task 2.1: Add sequence IDs to ChatMessage schema"
git commit -m "Task 3.1: Add WebSocket reconnection with exponential backoff"
git commit -m "MILESTONE: Complete storage layer with sequence IDs"
```

### TDD Pattern
1. Write failing tests first
2. Run tests to confirm they fail
3. Implement minimal code to pass
4. Include performance benchmarks
5. Verify preservation requirements

### Performance First
- How does this affect single-participant latency?
- Can we add a fast-path optimization?
- Is this complexity necessary for MVP?
- What can we defer to "future iterations"?

Remember: **The goal is ≤105% of /ask performance for 1 human + 1 NLWeb.**