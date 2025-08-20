# Client Implementation Guide for Claude Code - Multi-Participant Chat Frontend

## 🚨 CRITICAL: How to Use This Guide with Claude Code

### Golden Rules
1. **NEVER paste this entire document** - Work in small chunks
2. **Start with Command 1** below, then follow the phases
3. **Test after each component** using the test page
4. **Keep the Reference Info handy** for when Claude Code asks questions

### When Context Fills Up (Claude Code will warn you)
```
# Paste this exactly:
What's our current context usage?

If it's over 60%, please:
1. Update CLIENT_STATE.md with our current progress
2. Update NEXT_STEPS.md with the immediate next task
3. Commit all changes with message "WIP: [describe what we just did]"
4. Compact the context
5. Tell me exactly how to resume
```

### To Resume Work After a Break
```
# Paste this exactly:
Continue the client implementation.
/cat CLIENT_STATE.md
/cat NEXT_STEPS.md
git log --oneline -10

Show me where we left off and what the next step should be.
```

---

## 📋 Command 1: Start the Client Project

```
Create the following structure and state files:

/static/
  /chat/
    (empty for now)
  - multi-chat.html
  - multi-chat-styles.css
  - multi-chat-app.js

State tracking files:
- CLIENT_STATE.md - what component we're working on
- API_ENDPOINTS.md - all endpoints the client will use
- TEST_SCENARIOS.md - manual testing checklist
- COMPONENT_MAP.md - how components connect

Also copy these existing files (we'll reuse them):
- json-renderer.js
- type-renderers.js  
- recipe-renderer.js
- display_map.js

Add DOMPurify for XSS prevention:
- Download from: https://github.com/cure53/DOMPurify/releases
- Add to /static/dompurify.min.js
- Will be used to sanitize all user content before rendering

Document in API_ENDPOINTS.md:
GET    /api/chat/config
GET    /api/chat/conversations
POST   /api/chat/conversations
GET    /api/chat/conversations/:id
POST   /api/chat/conversations/:id/join
DELETE /api/chat/conversations/:id/leave
GET    /sites?streaming=false
WebSocket /chat/ws

We're building a WebSocket-based multi-participant chat that:
- Replaces EventSource with WebSockets for all communication
- Supports multiple humans in same conversation
- Shows enhanced sidebar with sites and recent messages
- Enables conversation sharing via links
- Reuses existing message renderers
- Sanitizes all user content for security
- Throttles typing indicators to prevent spam
```

---

## Phase 1: Foundation

### After Command 1 completes, paste this:

```
Now let's create the HTML structure. Create multi-chat.html with:

1. Same head section as existing index.html (copy favicon, viewport, etc)
2. App container with three main sections:
   - Enhanced sidebar (left)
   - Main chat area (center)  
   - Participant panel (right, hidden by default)

Sidebar needs:
- Header with "Conversations" title
- Sort toggle button
- New conversation button
- Sites container for grouped conversations

Main chat area needs:
- Header showing: title, site, mode, participant count
- Action buttons: Share, Change Site, Change Mode
- Messages container
- Typing indicators area (hidden by default)
- Input area with textarea and send button

Include these element IDs:
- sidebar, sites-container, sort-toggle
- chat-title, current-site, current-mode, participant-count
- share-button, site-selector, mode-selector
- messages-container, typing-indicators
- chat-input, send-button
- participant-panel

Add script tags for:
- dompurify.min.js (before other scripts)
- multi-chat-app.js as module
- Existing renderers

Store OAuth tokens in sessionStorage, not localStorage.
```

---

## Phase 2: Core Services

### Command 2: Event Bus

```
Create /static/chat/event-bus.js - a simple pub/sub system:

Requirements:
- on(event, callback) method that returns unsubscribe function
- off(event, callback) method
- emit(event, data) method with error handling
- events stored in a Map of Sets
- Export as singleton instance

This will be imported by all other components for communication.
Keep it simple - under 50 lines.
```

### Command 3: Configuration Service

```
Create /static/chat/config-service.js:

Requirements:
- Load config from /api/chat/config on initialization
- Load sites list from /sites?streaming=false
- Store config, sites array, and modes array
- Provide getters: getSites(), getModes(), getWebSocketUrl()
- Handle errors with sensible defaults
- Emit 'config:loaded' event when ready

Default modes: ['list', 'summarize', 'generate']
WebSocket URL should handle both ws:// and wss:// based on protocol
Export as singleton
```

### Command 4: Identity Service

```
Create /static/chat/identity-service.js:

Requirements:
- Check for OAuth identity first (authToken in sessionStorage, userInfo in localStorage)
- OAuth tokens must be in sessionStorage for security (cleared on tab close)
- Fall back to email identity from localStorage ('nlweb_chat_identity')
- promptForEmail() method that shows modal dialog
- ensureIdentity() method that returns identity or prompts
- getParticipantInfo() method returns formatted participant data
- hashEmail() for privacy when creating participant IDs
- save() and clear() methods

Modal should have:
- Email input (required)
- Display name input (optional)
- Form validation
- Returns promise that resolves to identity object or null

Important: Only non-sensitive identity info goes in localStorage.
OAuth tokens must use sessionStorage.

Export as singleton
```

---
## Phase 3: State Management

### Command 5: State Manager

```
Create /static/chat/state-manager.js:

Core responsibilities:
- Store conversations Map (id -> conversation object)
- Store current conversation ID
- Store site metadata Map (site -> {lastUsed, conversationCount})
- User preferences (sidebarSortMode, defaultMode, defaultSite)

Key methods:
- setCurrentConversation(conversationId)
- getCurrentConversation()
- addConversation(conversation)
- updateConversation(conversationId, updates)
- addMessage(conversationId, message) - store by sequence_id
- getMessages(conversationId, startSeq, endSeq)
- updateParticipants(conversationId, participants)
- updateSiteUsage(site) - track last used time
- getSitesSorted(mode) - by recency or alphabetical
- getConversationsForSite(site) - filtered list
- saveToStorage() and loadFromStorage() - localStorage persistence

Events to emit:
- 'conversation:changed' when switching conversations
- 'conversation:updated' when conversation data changes
- 'message:added' when new message arrives
- 'participants:updated' when participants change

Storage limits:
- Keep only last 50 messages per conversation in memory
- Persist to localStorage with key 'nlweb_chat_state'
- Clean up old conversations (>30 days) on load

Export as singleton.
```

### Command 5a: Participant Tracker

```
Create /static/chat/participant-tracker.js:

This is a utility class (not a service) used by StateManager:

Constructor takes conversation object reference.

Methods:
- updateParticipants(participantList) - sync with server list
- setTyping(participantId, isTyping) - update typing state
- clearTyping(participantId) - remove typing state
- clearAllTyping() - reset all typing states
- getTypingParticipants() - return array of typing participant IDs
- getActiveParticipants() - filter by online status
- isMultiParticipant() - returns true if >2 participants

Typing state management:
- Store typing states in Map<participantId, timeoutId>
- Auto-clear typing after 5 seconds using setTimeout
- Clear typing when participant sends message

This is instantiated per conversation, not a singleton.
```

### Command 5b: API Service

```
Create /static/chat/api-service.js:

Handle all REST API calls with proper error handling:

Methods:
- async createConversation(site, mode, participantIds = [])
  POST /api/chat/conversations
  Returns: { conversation_id, created_at }

- async getConversations()
  GET /api/chat/conversations
  Returns: array of conversation objects

- async getConversation(conversationId)
  GET /api/chat/conversations/:id
  Returns: full conversation with messages

- async joinConversation(conversationId, participantInfo)
  POST /api/chat/conversations/:id/join
  Returns: { success: true, conversation }

- async leaveConversation(conversationId)
  DELETE /api/chat/conversations/:id/leave
  Returns: { success: true }

For all methods:
- Get auth token from sessionStorage
- Add Authorization header if token exists
- Handle errors with proper status codes
- Return null on 404, throw on other errors
- Use eventBus.emit('api:error', error) for errors

Base URL handling:
- Use relative URLs that work with any origin
- Support optional baseUrl config parameter

Export as singleton instance.
```

### Command 5c: Wire State Management

```
After creating the state management components, update initialization:

In multi-chat-app.js initialization sequence, add:

1. Import the new services:
   import { stateManager } from './chat/state-manager.js';
   import { apiService } from './chat/api-service.js';

2. In initialization sequence (after config, before WebSocket):
   // Load saved state
   stateManager.loadFromStorage();
   
   // Load conversations from API
   try {
     const conversations = await apiService.getConversations();
     conversations.forEach(conv => stateManager.addConversation(conv));
   } catch (error) {
     console.error('Failed to load conversations:', error);
   }

3. Wire up WebSocket events to state:
   eventBus.on('message:received', (message) => {
     stateManager.addMessage(message.conversation_id, message);
   });
   
   eventBus.on('participants:update', (data) => {
     stateManager.updateParticipants(data.conversation_id, data.participants);
   });

4. Wire up state events to UI:
   eventBus.on('message:added', ({ conversationId, message }) => {
     if (conversationId === stateManager.currentConversationId) {
       chatUI.renderMessage(message);
     }
   });

5. Save state periodically:
   setInterval(() => {
     stateManager.saveToStorage();
   }, 30000); // Every 30 seconds

This connects the state layer between WebSocket and UI.
```

### Command 5d: Update UI Components to Use State

```
Update existing UI components to use stateManager:

In sidebar-ui.js:
- Change render() to get conversations from stateManager
- Use stateManager.getConversationsForSite()
- Use stateManager.getSitesSorted()

In chat-ui.js:
- Get current conversation from stateManager
- Use stateManager.getMessages() for initial render
- Update header from stateManager.getCurrentConversation()

In share-ui.js:
- Get conversation data from stateManager for sharing

Example pattern:
// Old: this.conversations.get(id)
// New: stateManager.getCurrentConversation()

// Old: this.messages.push(message)  
// New: stateManager.addMessage(conversationId, message)

This ensures all components use centralized state.
```


## Phase 4: WebSocket Communication

### Command 6: WebSocket Service

```
Create /static/chat/websocket-service.js:

Core features:
- connect(conversationId, participantInfo) method
- Get auth token from sessionStorage (not localStorage)
- Automatic reconnection with exponential backoff
- Message queue for offline sending
- Heartbeat/ping mechanism
- Track lastSequenceId for sync after reconnection

Message handling:
- Parse incoming JSON messages
- Route by type: message, ai_response, participant_update, typing, sync, error
- For ai_response, further route by message_type (result, summary, etc)
- Emit events for each message type

Reconnection:
- Start at 1 second delay
- Double each attempt up to 30 seconds max
- Send sync request with lastSequenceId on reconnect
- Flush queued messages after connection

Typing throttle:
- Track lastTypingSent timestamp
- Only send if >3 seconds since last or first typing event
- Clear typing state on message send

Export as singleton
```

---

## Phase 5: UI Components  

### Command 7: Sidebar UI

```
Create /static/chat/sidebar-ui.js:

Features:
- Render sites with recent conversations grouped under each
- Dynamic message count based on viewport height
- Sort toggle (recency vs alphabetical)
- Click site name to start new conversation with that site
- Show last message preview and timestamp
- Highlight current conversation

Methods:
- initialize(container) - set up DOM and events
- render() - full sidebar render
- calculateMessagesPerSite() - based on viewport
- renderSiteGroup(site, conversations) - single site section
- handleSiteClick(site) - create new conversation
- handleSortToggle() - switch sort modes

Listen for state manager events to update display.
No need to export as singleton - will be instantiated in main app.
```

### Command 8: Chat UI

```
Create /static/chat/chat-ui.js:

Core responsibilities:
- Message rendering with sender attribution
- SANITIZE all user content with DOMPurify before rendering
- Reuse existing json-renderer for rich content (after sanitization)
- Show typing indicators
- Handle input and sending
- Update header info (title, site, mode, participants)

Key methods:
- initialize(container) - set up DOM structure
- renderMessage(message) - sanitize content, then use existing renderers
- sanitizeContent(content) - use DOMPurify.sanitize()
- showTypingIndicators(typingUsers)
- updateChatHeader(conversation)
- handleInputKeydown(event) - throttle typing events
- setInputMode(mode) - adjust for single vs multi participant

Typing throttle logic:
- Track lastTypingEventTime
- On keypress: if no lastTypingEventTime OR >3 seconds passed, emit typing event
- Clear typing on message send

For AI responses (result, chart_result, etc), sanitize before
passing to existing renderers. AI-generated HTML must also be sanitized.

Include message batching with requestAnimationFrame for performance.
```

### Command 9: Share UI

```
Create /static/chat/share-ui.js:

Components:
1. Share button handler - copies link to clipboard
2. Join dialog for incoming shared links
3. Participant panel for multi-participant conversations

Methods:
- generateShareLink(conversationId)
- showJoinDialog(conversationId) - returns promise
- showParticipantPanel(participants)
- handleIncomingShareLink() - check URL for /chat/join/:id

Join dialog shows:
- Conversation title
- Current identity
- Confirm/Cancel buttons

Use native clipboard API with fallback.
Show success feedback after copy.
```

---



## Phase 6: Site Management

### Command 10: Site Selector

```
Create UI for site selection in chat-ui.js or separate file:

Requirements:
- Modal with grid of available sites
- Show all sites from configService.getSites()
- Click to create new conversation with selected site
- Visual indication of current site
- Search/filter functionality for many sites

Also implement:
- Mode selector dropdown (list/summarize/generate)
- Update conversation when mode changes
- Store last used mode preference
```

---

## Phase 7: Main Application

### Command 11: Application Bootstrap

```
Create the main app in multi-chat-app.js:

1. Import all services and UI components
2. Create initialization sequence:
   - Load config
   - Initialize identity
   - Initialize state manager
   - Check URL for shared conversation link
   - Create UI components
   - Connect WebSocket

3. Wire up all events between components:
   - WebSocket events → State Manager → UI updates
   - UI actions → WebSocket sends
   - Identity changes → WebSocket reconnect

4. Handle conversation creation/loading:
   - If URL has conversation ID, load it
   - If URL has join link, show join flow
   - Otherwise show conversation list or create new

Export initializeChat function for testing.
```

### Command 12: Message Flow Integration

```
Complete the message flow in multi-chat-app.js:

Sending messages:
1. User types → Chat UI captures
2. Throttle typing indicator (3 second minimum between events)
3. Create message with client ID
4. Add optimistic UI update
5. Send via WebSocket
6. Update with server response

Receiving messages:
1. WebSocket receives → emits event
2. State manager stores by sequence ID
3. SANITIZE content with DOMPurify
4. UI updates with sanitized message
5. Handle sender attribution

AI responses:
1. Route by message_type to appropriate renderer
2. SANITIZE all content before rendering
3. For HTML responses (charts, etc), use DOMPurify with safe config
4. Support streaming updates for ai_chunk type
5. Show in conversation with AI attribution

Security notes:
- Never trust any user-generated content
- Sanitize at the rendering layer, not storage
- AI responses may contain HTML - sanitize those too

Test with single user first, then multiple users.
```

### Command 13: Security Wrapper

```
Create a security wrapper for all renderers:

In chat-ui.js or separate secure-renderer.js:
- Wrap all existing renderers (json-renderer, type-renderers, etc)
- Apply DOMPurify.sanitize() to all text content
- For HTML content, use DOMPurify with configuration:
  {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 
                   'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'code', 
                   'blockquote', 'img', 'div', 'span'],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'class', 'id', 'style'],
    ALLOW_DATA_ATTR: false
  }
- Special handling for chart_result and results_map (may need specific tags)

This ensures no XSS can occur through stored messages or AI responses.
```

---

## Phase 8: Styling

### Command 13: Core Styles

```
Create multi-chat-styles.css with:

1. Layout styles:
   - Flexbox/Grid for main layout
   - Responsive sidebar (collapsible on mobile)
   - Fixed header and input areas
   - Scrollable messages area

2. Component styles:
   - Enhanced sidebar with site groups
   - Message bubbles with sender info
   - Typing indicators
   - Connection status
   - Modals and dialogs

3. States:
   - Message states (sending, sent, failed)
   - Online/offline participants
   - Active conversation highlight
   - Hover states

Reuse existing color schemes and variables.
Mobile-first responsive design.
```

---

## Phase 9: Testing

### Command 14: Test Harness

```
Create test-multi-chat.html for development testing:

Include scripts:
- DOMPurify
- All chat components
- Test utilities

Add buttons to:
- Connect/disconnect WebSocket
- Send test message
- Send XSS test: <script>alert('XSS')</script>
- Simulate AI response  
- Add/remove participants
- Trigger typing indicator
- Test reconnection
- Create conversation
- Load conversation

Add textarea for viewing:
- WebSocket messages
- Current state
- Event log
- Sanitization results

This helps test without full server integration.
```

### Command 15: Integration Testing

```
Create manual test scenarios in TEST_SCENARIOS.md:

1. Single user flow:
   - Create conversation
   - Send message
   - Receive AI response
   - Change site/mode

2. Multi-user flow:
   - User A creates conversation
   - User A shares link
   - User B joins
   - Both exchange messages
   - AI responds to both

3. Security tests:
   - Send message with <script>alert('XSS')</script>
   - Send message with onclick handlers
   - Verify OAuth token not in localStorage
   - Check all rendered content is sanitized
   - Test AI responses with HTML are sanitized

4. Throttling tests:
   - Type rapidly and verify typing events throttled
   - Verify typing cleared on message send
   - Check multiple users typing simultaneously

5. Edge cases:
   - Reconnection during conversation
   - Join with no identity
   - Network failures

Document expected behavior for each scenario.
```

---
NEXT
## 🚨 Emergency Recovery Command

```
I lost context. Please help me recover:
1. Run: ls -la /static/chat/
2. Check: git status
3. Load: cat CLIENT_STATE.md
4. Show me what component we were implementing
5. Tell me the next logical step
```

---

## 📋 Reference Information (Paste When Claude Code Asks)

### When Asked About Message Types:
```
WebSocket message types from server:
- message: Regular chat message with sequence_id
- ai_response: Contains message_type field with NLWeb response
- participant_update: List of current participants  
- typing: Typing indicator update
- sync: Response to sync request with missed messages
- error: Error message

AI response message_types (in ai_response.data.message_type):
- result: Search results to render
- summary: Summary text
- chart_result: Data Commons chart HTML
- results_map: Location data for map
- ensemble_result: Grouped recommendations
- nlws: Natural language response with items
- item_details: Detailed item information
- compare_items: Comparison data
- intermediate_message: Progress updates
- complete: Stream complete signal
```

### When Asked About Existing Code to Reuse:
```
Reuse these files without modification:
- json-renderer.js - Base JSON rendering
- type-renderers.js - Specialized type renderers
- recipe-renderer.js - Recipe cards
- display_map.js - Map initialization

Adapt this logic from managed-event-source.js:
- handleResultBatch()
- handleNLWS() 
- handleEnsembleResult()
- handleChartResult()
- handleResultsMap()
- All other handle* methods

But convert from EventSource events to WebSocket events.
```

### When Asked About State Structure:
```
Conversation object structure:
{
  id: "conv_123",
  title: "Conversation title",
  site: "eventbrite",
  mode: "list",
  created_at: "2024-01-01T10:00:00Z",
  last_message_at: "2024-01-01T11:00:00Z", 
  last_message_preview: "Found 5 results...",
  participants: [...],
  participant_count: 3,
  is_multi_participant: true,
  messages: Map<sequence_id, message>
}

Site metadata structure:
{
  lastUsed: 1704106200000,
  conversationCount: 15
}
```

### When Asked About Authentication:
```
Two authentication modes:

1. OAuth (check first):
   - authToken in sessionStorage (for security)
   - userInfo in localStorage (non-sensitive)
   - Use as-is for identity

2. Email (fallback):
   - Prompt for email if not in localStorage
   - Store in 'nlweb_chat_identity' key
   - Generate participant_id by hashing email
   - Optional display name

Security notes:
- OAuth tokens MUST be in sessionStorage (cleared on tab close)
- Only non-sensitive data in localStorage
- Never put tokens in URLs

Participant info format:
{
  participant_id: "oauth_123" or "email_hash",
  display_name: "User Name",
  email: "user@example.com",
  auth_type: "oauth" or "email"
}
```

### When Asked About Performance:
```
Performance requirements:
- Message rendering: <16ms (60fps)
- WebSocket connection: <100ms
- Message delivery: <200ms
- Use requestAnimationFrame for batching
- Virtual scroll for 1000+ messages
- Keep max 50 messages per conversation in localStorage
- Lazy load conversation history

Throttling:
- Typing indicators: Max once per 3 seconds
- No throttling on actual message sends
- Clear typing state on message send

Security performance:
- DOMPurify sanitization is fast (~1ms per message)
- Sanitize during render, not storage
- Cache sanitized content if needed

This is a complete rewrite, so no need to maintain
compatibility with the EventSource implementation.
```

Remember: **The goal is a real-time multi-participant chat with WebSockets throughout.**