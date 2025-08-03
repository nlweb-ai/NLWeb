# Next Steps for Frontend Chat Client Implementation

## Current Status
Phase 1 (Foundation) complete. Ready for Phase 2 (Core Services).

## Immediate Next Task: Event Bus Service

### Create `/static/chat/event-bus.js`

Requirements:
- Singleton event emitter for component communication
- Subscribe to events with on() method
- Emit events with emit() method  
- Unsubscribe with off() method
- Error handling for broken listeners
- Debug mode with console logging

Events to support:
- `navigate:conversation` - Load a conversation
- `create:conversation` - Create new conversation
- `send:message` - Send chat message
- `user:typing` - User is typing
- `ws:message` - WebSocket message received
- `ws:connected` - WebSocket connected
- `ws:disconnected` - WebSocket disconnected
- `share:conversation` - Share current conversation

### After Event Bus, continue with:
1. API Service (api-service.js)
2. Identity Service (identity-service.js) 
3. State Manager (state-manager.js)
4. WebSocket Service (websocket-service.js)
5. UI Components (sidebar-ui.js, chat-ui.js, share-ui.js)

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