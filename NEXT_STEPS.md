# Next Steps for Frontend Chat Client Implementation

## Current Status
Phase 2 (Core Services) in progress. Event Bus, Config Service, and Identity Service complete.

## Immediate Next Task: API Service

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

### After API Service, continue with:
1. State Manager (state-manager.js) - Central state management
2. WebSocket Service (websocket-service.js) - Real-time communication
3. UI Components (sidebar-ui.js, chat-ui.js, share-ui.js)

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