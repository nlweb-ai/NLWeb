# Client-Side Technical Architecture - Multi-Participant Chat System

## System Overview

The client is a browser-based application that enables multi-participant real-time chat with AI agents. It replaces the existing EventSource-based single-user implementation with a WebSocket-based architecture supporting multiple concurrent users.

## Component Architecture

### Core Services (Singletons)

#### EventBus
- Centralized publish-subscribe message broker
- Methods: `on(event, callback)`, `off(event, callback)`, `emit(event, data)`
- Returns unsubscribe function from `on()` for cleanup
- Stores listeners in `Map<string, Set<function>>`

#### ConfigService
- Loads configuration from `/api/chat/config`
- Loads site list from `/sites?streaming=false`
- Caches configuration data
- Provides: `getSites()`, `getModes()`, `getWebSocketUrl()`, `isMultiParticipantEnabled()`

#### IdentityService
- Manages user identity (OAuth or email-based)
- Storage key: `nlweb_chat_identity`
- Methods: `initialize()`, `ensureIdentity()`, `getParticipantInfo()`, `promptForEmail()`
- Generates participant IDs: OAuth users use existing ID, email users get `email_${hash}`

#### StateManager
- Central state store for all conversation data
- Stores: conversations Map, current conversation ID, site metadata, user preferences
- Persists to localStorage with 50-message limit per conversation
- Methods: `addMessage()`, `updateParticipants()`, `getSitesSorted()`, `getConversationsForSite()`

#### WebSocketService
- Manages WebSocket connection lifecycle
- Handles reconnection with exponential backoff (1s, 2s, 4s... max 30s)
- Message queue for offline sending
- Tracks `lastSequenceId` for synchronization
- Sends heartbeat ping every 30 seconds
- Throttles typing events to max once per 3 seconds

### UI Components

#### ChatUI
- Renders messages using existing JSON renderers
- Sanitizes all user content with DOMPurify before rendering
- Handles input capture and sending
- Shows typing indicators
- Updates header with conversation metadata
- Batches DOM updates using requestAnimationFrame
- Throttles typing events during input

#### SidebarUI
- Groups conversations by site
- Dynamic message count based on viewport height
- Sort modes: recency or alphabetical
- Click handlers for creating new conversations

#### ShareUI
- Generates shareable links: `/chat/join/${conversationId}`
- Shows join confirmation dialog
- Manages participant panel display

## Data Flow

### Message Send Flow
```
User Input → ChatUI.handleSend() → WebSocketService.send() → Server
    ↓
Optimistic UI Update → StateManager.addMessage() → EventBus.emit('message:added')
    ↓
ChatUI.renderMessage()
```

### Message Receive Flow
```
WebSocket.onmessage → WebSocketService.handleMessage() → EventBus.emit(type, data)
    ↓
StateManager.addMessage() → EventBus.emit('message:added')
    ↓
ChatUI.renderMessage() → DOMPurify.sanitize() → DOM update
```

### AI Response Flow
```
Server AI Response → WebSocket → WebSocketService.handleAIResponse()
    ↓
EventBus.emit('ai:' + message_type) → ChatUI.handleAIMessage()
    ↓
DOMPurify.sanitize() → Existing renderers → DOM update
```

## WebSocket Protocol

### Client to Server Messages

```javascript
// Chat message
{
  type: "message",
  data: {
    content: "message text",
    client_id: "uuid-v4",
    conversation_id: "conv_123",
    context: {
      generate_mode: "list|summarize|generate",
      site: "site_name",
      prev_queries: ["previous", "queries"],
      last_answers: [{title: "...", url: "..."}]
    }
  }
}

// Sync request after reconnection
{
  type: "sync",
  data: {
    last_sequence_id: 123
  }
}

// Typing indicator (throttled client-side)
{
  type: "typing",
  data: {
    is_typing: true,
    conversation_id: "conv_123"
  }
}
```

### Server to Client Messages

```javascript
// Regular message
{
  type: "message",
  data: {
    id: "msg_456",
    sequence_id: 789,
    sender: {
      id: "participant_123",
      name: "User Name",
      type: "human|ai"
    },
    content: "message content",
    timestamp: "2024-01-01T12:00:00Z"
  }
}

// AI response wrapper
{
  type: "ai_response",
  data: {
    message_type: "result|summary|chart_result|etc",
    sequence_id: 790,
    conversation_id: "conv_123",
    // Original NLWeb response data based on message_type
  }
}

// Participant update
{
  type: "participant_update",
  data: {
    participants: [
      {
        id: "participant_123",
        name: "User Name",
        type: "human",
        status: "online|typing|offline"
      }
    ],
    participant_count: 3,
    input_mode: "single|multi"
  }
}
```

## Storage Schema

### localStorage Keys

#### `nlweb_chat_identity`
```javascript
{
  email: "user@example.com",
  name: "Display Name",
  created_at: "2024-01-01T10:00:00Z"
}
```

#### `nlweb_chat_state`
```javascript
{
  conversations: [
    ["conv_id", {
      id: "conv_123",
      title: "Conversation Title",
      site: "eventbrite",
      mode: "list",
      created_at: "2024-01-01T10:00:00Z",
      last_message_at: "2024-01-01T11:00:00Z",
      last_message_preview: "Message preview...",
      participant_count: 3,
      messages: [/* last 50 messages */]
    }]
  ],
  siteMetadata: [
    ["site_name", {
      lastUsed: 1704106200000,
      conversationCount: 15
    }]
  ],
  userPreferences: {
    sidebarSortMode: "recency|alphabetical",
    defaultMode: "list",
    defaultSite: "all"
  }
}
```

## Event Catalog

### System Events
- `config:loaded` - Configuration loaded successfully
- `identity:loaded` - User identity established
- `websocket:connected` - WebSocket connection established
- `websocket:disconnected` - Connection lost
- `websocket:error` - Connection error occurred

### Conversation Events
- `conversation:changed` - Current conversation switched
- `conversation:updated` - Conversation metadata updated
- `message:added` - New message added to conversation
- `participants:updated` - Participant list changed
- `typing:update` - Typing status changed

### AI Response Events
- `ai:result` - Search results received
- `ai:summary` - Summary text received
- `ai:chart_result` - Chart HTML received
- `ai:results_map` - Map locations received
- `ai:ensemble_result` - Grouped recommendations received
- `ai:nlws` - Natural language response received
- `ai:complete` - AI response stream completed

## URL Routing

- `/chat` - Conversation list
- `/chat/:conversationId` - Specific conversation
- `/chat/join/:conversationId` - Join conversation flow

## External Dependencies

### External Libraries
- DOMPurify - XSS sanitization for all user-generated content

### Reused Components
- `json-renderer.js` - Base JSON rendering engine
- `type-renderers.js` - Specialized content renderers
- `recipe-renderer.js` - Recipe card rendering
- `display_map.js` - Map initialization and display

### Browser APIs
- WebSocket API for real-time communication
- localStorage for persistence
- Clipboard API for share functionality
- Intersection Observer for virtual scrolling (future)

## Initialization Sequence

1. Load DOMPurify library
2. Load configuration from server
3. Initialize identity (check OAuth → check localStorage → prompt)
4. Load state from localStorage
5. Parse URL for conversation ID or join link
6. Initialize UI components
7. Establish WebSocket connection
8. Request sync if rejoining conversation
9. Begin message flow

## Security

### XSS Prevention
- All user-generated content sanitized with DOMPurify before rendering
- Sanitization applied before passing to any renderer (json-renderer, type-renderers, etc.)
- OAuth tokens stored in sessionStorage (not localStorage) to limit exposure
- Content Security Policy headers configured on server

### Token Storage
- OAuth tokens: sessionStorage only (cleared on tab close)
- Identity information: localStorage (non-sensitive only)
- No sensitive data in URLs or client-side routing
- Auth tokens retrieved from sessionStorage for WebSocket connections

## Rate Limiting

### Typing Indicator Throttling
- First typing event sent immediately
- Subsequent events throttled to maximum once every 3 seconds
- Typing state cleared on message send or after 5 seconds of inactivity
- Simple timestamp-based throttling (no external dependencies)

## Error Handling

### Connection Errors
- Exponential backoff reconnection
- Message queuing during disconnection
- Sync request on reconnection with last sequence ID

### Message Failures
- Client-generated IDs for deduplication
- Optimistic updates with failure states
- Manual retry option for failed messages

### Identity Errors
- Fall back to email prompt if OAuth fails
- Validation of email format
- Storage errors handled silently with console logging

## Performance Considerations

- Message batching using requestAnimationFrame
- DOM element recycling for large message lists
- 50-message limit in localStorage per conversation
- Lazy loading of conversation history
- Virtual scrolling for conversations with 1000+ messages