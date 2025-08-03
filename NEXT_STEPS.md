# Next Steps for Frontend Chat Client Implementation

## Current Status
Implemented WebSocket Service (Phase 4) and all UI Components (Phase 5). Need to complete remaining Phase 2 services.

## Immediate Next Tasks (In Order):

### Create `/static/chat/api-service.js`

Requirements:
- Handle all HTTP API calls to backend
- Methods for: createConversation(), getConversations(), sendMessage()
- Include authentication headers from identity service
- Handle errors with proper HTTP status codes
- Retry logic for network failures
- Export as singleton

API endpoints to support:
- `POST /chat/create` - Create new conversation
- `GET /chat/my-conversations` - List user's conversations
- `POST /chat/{conv_id}/messages` - Send message to conversation
- `GET /health/chat` - Health check

### 2. Create `/static/chat/state-manager.js` (Phase 2)
- Central state management for conversations and messages
- Track current conversation, all conversations, sites
- Handle message ordering and deduplication
- Emit state change events via EventBus

### 3. Complete Main App Integration (Phase 3)
- Wire up all components in multi-chat-app.js
- Initialize services in correct order
- Connect UI components to state manager
- Set up event flow between components

### 4. Download Dependencies
- Download DOMPurify.js to /static/
- Copy existing renderer files from current chat implementation

## Backend Tasks (Separate)
- [ ] Complete reliability tests
- [ ] Fix storage provider implementations
- [ ] Run full test suite
- [ ] Integration testing

## Resume Instructions

To resume development:

1. **Check test status**:
   ```bash
   cd /Users/rvguha/code/conv/code/python
   python -m pytest tests/test_chat_performance.py -v
   python -m pytest tests/test_chat_security.py -v
   ```

2. **Continue with reliability tests**:
   ```bash
   # Create test_chat_reliability.py
   # Focus on network interruption and reconnection scenarios
   ```

3. **Fix any failing tests**:
   - Most likely issues: missing imports, storage method implementations
   - Check conversation access control in WebSocket handler

4. **Key files to reference**:
   - `/Users/rvguha/code/conv/code/python/chat/` - Core chat implementation
   - `/Users/rvguha/code/conv/code/python/webserver/routes/chat.py` - API endpoints
   - `/Users/rvguha/code/conv/code/python/tests/test_chat_*.py` - Test suites

5. **Architecture reminders**:
   - WebSocket per human, messages broadcast to all
   - ConversationManager is the central orchestrator
   - At-least-once delivery with async persistence
   - Mode switching: SINGLE (100ms) vs MULTI (2000ms)