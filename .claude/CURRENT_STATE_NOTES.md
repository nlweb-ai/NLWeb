# Current State Notes - Conversation API Implementation

## Recent Changes Committed
1. **WebSocket Connection Management**
   - Added `getWebSocketConnection(createIfNeeded)` method to centralize connection logic
   - Prevents multiple simultaneous WebSocket connections
   - Properly handles connection states (CONNECTING, OPEN, CLOSED)

2. **OAuth User ID Handling**
   - Fixed to prefer GitHub username over numeric ID
   - Checks for login/username fields before falling back to ID
   - Updates user ID when auth state changes

3. **Bug Fixes**
   - Fixed SSE endpoint from `/stream` to `/ask` (line 482)
   - Made sites loading non-blocking
   - Fixed syntax errors (async/await, extra braces)
   - Replaced deprecated substr() with substring()

## Known Issues to Fix

### High Priority
1. **Join Flow Issues**
   - Conversation history not being added to localStorage when joining
   - Messages from joined conversations not displaying for joining users
   - The join message is sent but conversation history handling needs work

### Medium Priority  
1. **Code Duplication** (see todos in code)
   - Site dropdown logic duplicated in 2 places (lines 887-915, 1092-1120)
   - Conversation object creation duplicated in 3 places
   - Message tracking initialization duplicated

## Current Architecture

### Connection Types
- **WebSocket**: Used for multi-user chat (`multi-chat-index.html`)
- **SSE**: Used for single-user chat (default)

### Key Functions
- `getWebSocketConnection(createIfNeeded)`: Get or create WebSocket
- `connectWebSocket()`: Create new WebSocket connection
- `joinServerConversation(conversationId)`: Handle joining shared conversations
- `handleStreamData(data)`: Process all incoming messages

### Message Flow
1. User sends message → `sendMessage()` 
2. → `sendThroughConnection()` 
3. → WebSocket or SSE
4. Server response → `handleStreamData()`
5. → UI update

## Next Steps
1. Fix conversation history storage on join
2. Ensure joined messages display properly
3. Refactor duplicated code (see TodoWrite items)
4. Test multi-user conversation flow end-to-end

## Testing Notes
- Main page: http://localhost:8000/static/multi-chat-index.html
- Join URL format: http://localhost:8000/chat/join/{conversation_id}
- OAuth login required for joining conversations
- GitHub OAuth returns numeric ID, need to get username from API

## File Locations
- Main UI: `/static/chat-interface-unified.js`
- HTML: `/static/multi-chat-index.html`
- OAuth: `/static/oauth-login.js`
- Conversation management: `/static/conversation-manager.js`