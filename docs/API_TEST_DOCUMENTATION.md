# Multi-Participant Chat System - Comprehensive API Testing Documentation

## Overview

This document consolidates all APIs from the multi-participant chat system that require testing, including backend REST APIs, WebSocket protocols, and frontend service APIs. It provides detailed documentation for creating an automated test system.

## Backend APIs

### 1. REST API Endpoints

#### 1.1 Create Conversation
```
POST /chat/create
```

**Request Body:**
```json
{
  "title": "string",          // Optional: conversation title
  "sites": ["string"],        // Required: array of site IDs
  "mode": "string",           // Required: "list", "summarize", or "generate"
  "participant": {            // Required: creator participant info
    "participantId": "string",
    "displayName": "string",
    "email": "string"
  }
}
```

**Response:**
```json
{
  "id": "conv_abc123",
  "title": "Conversation Title",
  "sites": ["site1"],
  "mode": "summarize",
  "participants": [...],
  "created_at": "2024-01-01T12:00:00Z"
}
```

**Error Responses:**
- 400: Invalid input
- 401: Unauthorized
- 429: Too many requests

#### 1.2 Get All Conversations
```
GET /chat/my-conversations
```

**Response:**
```json
[
  {
    "id": "conv_abc123",
    "title": "Conversation Title",
    "sites": ["site1"],
    "mode": "summarize",
    "participants": [...],
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T13:00:00Z",
    "last_message_preview": "Latest message...",
    "participant_count": 3,
    "unread_count": 0
  }
]
```

**Error Responses:**
- 401: Unauthorized
- 404: Returns null (empty array)

#### 1.3 Get Specific Conversation
```
GET /chat/conversations/:id
```

**Response:**
```json
{
  "id": "conv_abc123",
  "title": "Conversation Title",
  "sites": ["site1"],
  "mode": "summarize",
  "participants": [
    {
      "participantId": "user123",
      "displayName": "User Name",
      "type": "human",
      "joinedAt": "2024-01-01T12:00:00Z",
      "isOnline": true
    }
  ],
  "messages": [
    {
      "id": "msg_123",
      "sequence_id": 1,
      "sender_id": "user123",
      "content": "Message content",
      "timestamp": "2024-01-01T12:00:00Z",
      "type": "message",
      "status": "delivered"
    }
  ],
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T13:00:00Z"
}
```

**Error Responses:**
- 401: Unauthorized
- 404: Returns null

#### 1.4 Join Conversation
```
POST /chat/:id/join
```

**Request Body:**
```json
{
  "participant": {
    "participantId": "user456",
    "displayName": "New User",
    "email": "user@example.com"
  }
}
```

**Response:**
```json
{
  "success": true,
  "conversation": { /* full conversation object */ }
}
```

**Error Responses:**
- 401: Unauthorized
- 404: Conversation not found
- 409: Already a participant
- 429: Participant limit reached

#### 1.5 Leave Conversation
```
DELETE /chat/:id/leave
```

**Response:**
```json
{
  "success": true
}
```

**Error Responses:**
- 401: Unauthorized
- 404: Conversation not found

#### 1.6 Health Check
```
GET /health/chat
```

**Response:**
```json
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

### 2. WebSocket API

#### 2.1 WebSocket Connection
```
GET /chat/ws/{conversation_id}
Upgrade: websocket
Sec-WebSocket-Protocol: chat
Authorization: Bearer {token}
```

#### 2.2 Client to Server Messages

##### Send Message
```json
{
  "type": "message",
  "content": "message text",
  "message_id": "client_generated_uuid",
  "sites": ["site1"],
  "mode": "list|summarize|generate"
}
```

##### Sync Request (after reconnection)
```json
{
  "type": "sync",
  "last_sequence_id": 123
}
```

##### Typing Indicator
```json
{
  "type": "typing",
  "isTyping": true
}
```

#### 2.3 Server to Client Messages

##### Regular Message
```json
{
  "type": "message",
  "id": "msg_456",
  "sequence_id": 789,
  "participant": {
    "participantId": "participant_123",
    "displayName": "User Name",
    "type": "human|ai"
  },
  "content": "message content",
  "timestamp": "2024-01-01T12:00:00Z",
  "conversation_id": "conv_123"
}
```

##### AI Response
```json
{
  "type": "ai_response",
  "message_type": "result_batch|summary|chart_result|nlws|ai_chunk",
  "sequence_id": 790,
  "conversation_id": "conv_123",
  "content": "AI generated content",
  "data": { /* type-specific data */ },
  "participant": {
    "participantId": "ai_assistant",
    "displayName": "AI Assistant",
    "type": "ai"
  }
}
```

##### Typing Indicator (Server to Client)
```json
{
  "type": "typing",
  "participant": {
    "participantId": "participant_123",
    "displayName": "User Name"
  },
  "isTyping": true,
  "conversation_id": "conv_123"
}
```

##### Participant Update
```json
{
  "type": "participant_update",
  "participants": [
    {
      "participantId": "participant_123",
      "displayName": "User Name",
      "type": "human",
      "isOnline": true,
      "joinedAt": "2024-01-01T12:00:00Z"
    }
  ],
  "conversation_id": "conv_123"
}
```

##### Error Message
```json
{
  "type": "error",
  "code": "QUEUE_FULL|AUTH_FAILED|RATE_LIMITED",
  "message": "Human readable error",
  "retry_after": 5
}
```

##### Sync Response
```json
{
  "type": "sync",
  "messages": [ /* array of missed messages */ ],
  "current_sequence_id": 150,
  "participants": [ /* current participant list */ ]
}
```

### 3. Legacy Endpoints (Must Not Break)

```
GET  /ask                    # Single query endpoint
POST /mcp/*                  # MCP protocol endpoints
GET  /sites?streaming=false  # Site configuration
```

## Frontend Service APIs

### 4. EventBus API

#### Methods
- `on(event: string, callback: function): function` - Returns unsubscribe function
- `off(event: string, callback: function): void`
- `emit(event: string, data: any): void`

#### Events to Test
- `config:loaded`
- `identity:loaded`
- `websocket:connected`
- `websocket:disconnected`
- `websocket:error`
- `websocket:message`
- `conversation:added`
- `conversation:updated`
- `message:added`
- `participants:updated`
- `typing:updated`
- `state:currentConversation`
- `state:conversations`
- `state:sites`
- `ui:sendMessage`
- `ui:typing`
- `ui:newConversation`
- `ui:selectConversation`
- `ui:shareConversation`

### 5. ConfigService API

#### Methods
- `initialize(): Promise<void>`
- `getSites(): Array<Site>`
- `getModes(): Array<string>`
- `getWebSocketUrl(): string`
- `isMultiParticipantEnabled(): boolean`

### 6. IdentityService API

#### Methods
- `initialize(): Promise<void>`
- `ensureIdentity(): Promise<Identity>`
- `getCurrentIdentity(): Identity`
- `getParticipantInfo(): ParticipantInfo`
- `promptForEmail(): Promise<Identity>`
- `clearIdentity(): void`

### 7. StateManager API

#### Methods
- `loadFromStorage(): void`
- `saveToStorage(): void`
- `addConversation(conversation): void`
- `updateConversation(id, updates): void`
- `addMessage(conversationId, message): void`
- `getMessages(conversationId, startSeq?, endSeq?): Array<Message>`
- `updateParticipants(conversationId, participants): void`
- `updateTypingState(conversationId, participantId, isTyping): void`
- `getTypingParticipants(conversationId): Array<string>`
- `getCurrentConversation(): Conversation`
- `getAllConversations(sortBy?): Array<Conversation>`
- `getConversationsForSite(site): Array<Conversation>`
- `getSitesSorted(mode): Array<[site, metadata]>`
- `setPreference(key, value): void`
- `getPreference(key): any`
- `clearAll(): void`

### 8. WebSocketService API

#### Methods
- `connect(conversationId, participantInfo): Promise<void>`
- `disconnect(): Promise<void>`
- `sendMessage(content, sites, mode): void`
- `sendTyping(isTyping): void`
- `getConnectionState(): string`
- `getLastSequenceId(): number`

### 9. ParticipantTracker API

#### Methods
- `updateParticipants(participantList): void`
- `setTyping(participantId, isTyping): void`
- `clearTyping(participantId): void`
- `clearAllTyping(): void`
- `getTypingParticipants(): Array<string>`
- `getActiveParticipants(): Array<Participant>`
- `isMultiParticipant(): boolean`
- `handleMessageSent(participantId): void`
- `destroy(): void`

## Performance Requirements

### Latency Targets
- Single participant (1 human + 1 AI): ≤105% of current /ask endpoint
- Multi-participant (2-5 humans): <200ms message delivery
- WebSocket handshake: ≤50ms overhead
- Message routing: ≤1ms (2 participants), ≤5ms (10 participants)
- Storage operations: <50ms for sequence ID assignment

### Throughput Targets
- 1000 concurrent WebSocket connections per server
- 100 messages/second per conversation
- 100 participants per conversation maximum

### Memory Targets
- ≤110% of current single-user memory usage
- 100 messages cached per conversation
- Automatic cache eviction under pressure

## Security Requirements

### Authentication
- Bearer token required for all REST endpoints
- WebSocket authentication on connection
- Token validation on every request
- Session continuity during reconnection

### Data Protection
- WSS (TLS) required in production
- All user content sanitized with DOMPurify
- XSS prevention on all rendered content
- CORS headers properly configured

### Rate Limiting
- Per-conversation queue limit (default 1000)
- 429 response when queue full
- Typing indicator throttled to 3 seconds
- Connection limit per user

## Test Categories

### 1. Unit Tests
- Schema validation
- Storage interface implementations
- Message ordering with sequence IDs
- Queue management and limits
- Participant tracking
- Typing state management

### 2. Integration Tests
- REST API endpoint functionality
- WebSocket connection lifecycle
- Message flow end-to-end
- Multi-participant scenarios
- Reconnection with state sync
- Authentication flow

### 3. Performance Tests
- Single participant latency
- Multi-participant broadcast timing
- Memory usage under load
- Queue overflow behavior
- Concurrent message handling
- WebSocket overhead measurement

### 4. Security Tests
- Input sanitization
- XSS prevention
- Authentication bypass attempts
- Rate limit enforcement
- CORS policy validation

### 5. Reliability Tests
- Network interruption recovery
- At-least-once delivery
- Message deduplication
- Sequence ID consistency
- Storage failure handling
- Participant disconnect/reconnect

### 6. UI Component Tests
- EventBus message propagation
- State persistence/recovery
- Typing indicator throttling
- Message rendering with sanitization
- Conversation switching
- Share link generation

## Test Data Requirements

### Mock Users
- OAuth users with tokens
- Email-based users
- Users with different permissions
- Users in multiple conversations

### Mock Conversations
- Single participant conversations
- Multi-participant (2-5 humans)
- Large conversations (50+ participants)
- Conversations with 1000+ messages
- Conversations near queue limit

### Mock Messages
- Text messages of various lengths
- Messages with special characters
- Messages with potential XSS content
- AI responses of different types
- System messages (join/leave)

## Automated Test Framework Requirements

1. **Test Runner**: Support for async/await patterns
2. **WebSocket Testing**: Mock WebSocket server capabilities
3. **Performance Monitoring**: Latency and memory tracking
4. **Security Testing**: XSS injection detection
5. **Load Testing**: Concurrent connection simulation
6. **State Verification**: localStorage/sessionStorage mocking
7. **Network Simulation**: Latency and disconnection

## Success Criteria

1. All REST endpoints return expected responses
2. WebSocket messages delivered in correct order
3. Performance within specified targets
4. Security vulnerabilities cannot be exploited
5. System recovers from all failure scenarios
6. UI updates reflect backend state accurately
7. Multi-participant scenarios work smoothly