# Failing Tests

## Current Status
No tests have been written yet. This file will track failing tests once test implementation begins.

## Test Implementation Priority

### Critical Tests Needed
1. **WebSocket Reconnection** - Must handle disconnects gracefully
2. **Message Ordering** - Sequence IDs must be sequential
3. **State Persistence** - localStorage save/load must work
4. **XSS Prevention** - DOMPurify must sanitize all user content
5. **Queue Limits** - 429 responses when queue full

### Known Issues to Test
1. **Concurrent Messages** - Multiple users sending simultaneously
2. **Large Message Volumes** - Performance with 1000+ messages
3. **Network Failures** - Reconnection with message sync
4. **Identity Loss** - Handle cleared localStorage
5. **API Failures** - Graceful degradation

## Test Infrastructure Needed
- Mock WebSocket server
- Mock API responses
- localStorage mock
- DOMPurify test setup
- Performance measurement tools