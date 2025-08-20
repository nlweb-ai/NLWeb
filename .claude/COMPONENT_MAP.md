# Component Architecture Map

## Core Services (Singletons)

### EventBus
- **Purpose**: Central communication hub
- **Events Emitted**:
  - `navigate:conversation` - Load a conversation
  - `create:conversation` - Create new conversation
  - `send:message` - Send chat message
  - `user:typing` - User is typing
  - `ws:message` - WebSocket message received
  - `ws:connected` - WebSocket connected
  - `ws:disconnected` - WebSocket disconnected
  - `share:conversation` - Share current conversation

### ApiService
- **Purpose**: REST API communication
- **Dependencies**: IdentityService (for auth)
- **Methods**:
  - `getConfig()` - Get chat configuration
  - `getSites()` - Get available sites
  - `getConversations()` - Get user's conversations
  - `createConversation()` - Create new conversation
  - `getConversation(id)` - Get conversation details
  - `joinConversation(id)` - Join existing conversation
  - `leaveConversation(id)` - Leave conversation

### IdentityService
- **Purpose**: Manage user identity
- **Storage**: 
  - sessionStorage: OAuth tokens (security)
  - localStorage: Email identity, user info
- **Methods**:
  - `ensureIdentity()` - Get or prompt for identity
  - `getIdentity()` - Get current identity
  - `getParticipantInfo()` - Format for participant
  - `promptForEmail()` - Show email modal
  - `clear()` - Clear identity

### StateManager
- **Purpose**: Central state management
- **Storage**: Memory + localStorage cache
- **State**:
  - Sites list
  - Conversations map
  - Active conversation
  - Messages by conversation
  - Participants by conversation
  - Typing users
- **Methods**:
  - `addMessage()` - Add/update message
  - `getMessage()` - Get message by ID
  - `addConversation()` - Add conversation
  - `setActiveConversation()` - Set current conversation
  - `addTypingUser()` - Add user to typing list
  - `removeTypingUser()` - Remove from typing list

### WebSocketService
- **Purpose**: Real-time communication
- **Dependencies**: EventBus, IdentityService
- **Features**:
  - Auto-reconnection with exponential backoff
  - Message queue for offline
  - Heartbeat/ping mechanism
  - Typing throttle (3s)
- **Methods**:
  - `connect(conversationId, participant)` - Connect to conversation
  - `disconnect()` - Close connection
  - `sendMessage(data)` - Send message
  - `sendTyping()` - Send typing indicator

## UI Components

### SidebarUI
- **Purpose**: Navigation and conversation list
- **Dependencies**: EventBus, StateManager
- **Responsibilities**:
  - Render sites list
  - Render conversations list
  - Handle navigation clicks
  - Show active states
  - Update on state changes

### ChatUI
- **Purpose**: Main chat interface
- **Dependencies**: EventBus, StateManager, DOMPurify
- **Responsibilities**:
  - Render messages (with sanitization)
  - Show typing indicators
  - Handle message input
  - Update header info
  - Integrate existing renderers

### ShareUI
- **Purpose**: Share conversation modal
- **Dependencies**: EventBus
- **Responsibilities**:
  - Generate share link
  - Copy to clipboard
  - Show QR code (optional)
  - Display participant info

## Data Flow

### Message Send Flow
1. User types in ChatUI
2. ChatUI emits `user:typing` (throttled)
3. WebSocketService sends typing indicator
4. User presses Enter
5. ChatUI emits `send:message`
6. App creates message object
7. StateManager stores (optimistic)
8. ChatUI renders immediately
9. WebSocketService sends to server
10. Server broadcasts to all participants
11. WebSocket receives confirmation
12. StateManager updates with server data

### Message Receive Flow
1. WebSocketService receives message
2. Emits `ws:message` event
3. App handles based on type
4. StateManager stores message
5. ChatUI renders (with sanitization)

### Connection Flow
1. User selects conversation
2. SidebarUI emits `navigate:conversation`
3. App loads conversation data
4. WebSocketService connects
5. Receives sync data
6. StateManager populates
7. ChatUI renders all content

## Security Layers

### Input Security
- **Location**: ChatUI before display
- **Method**: DOMPurify.sanitize()
- **Applied to**: All user messages, AI responses

### Auth Security
- **OAuth tokens**: sessionStorage only
- **Identity info**: localStorage (non-sensitive)
- **WebSocket**: Token in connection params

### Content Security
- **XSS Prevention**: All content sanitized
- **HTML Whitelist**: Safe tags only
- **Event Handlers**: All stripped

## Performance Optimizations

### Throttling
- Typing indicators: Max once per 3 seconds
- Render batching: requestAnimationFrame

### Caching
- Conversations: localStorage
- Messages: Memory + localStorage (last 50)
- Sites: Memory

### Lazy Loading
- Messages: Load on demand
- Conversations: Paginated

## Module Dependencies

```
multi-chat-app.js
├── event-bus.js (no deps)
├── api-service.js
│   └── identity-service.js
├── identity-service.js (no deps)
├── state-manager.js (no deps)
├── websocket-service.js
│   ├── event-bus.js
│   └── identity-service.js
├── sidebar-ui.js
│   ├── event-bus.js
│   └── state-manager.js
├── chat-ui.js
│   ├── event-bus.js
│   ├── state-manager.js
│   └── DOMPurify
└── share-ui.js
    └── event-bus.js
```