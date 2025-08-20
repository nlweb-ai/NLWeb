# Test Fix Plan

## Failing Tests Analysis & Fix Strategy

### 1. Unit Test Failures (4 tests)

#### a) `TestNLWebParticipant::test_queue_full_handling`
**Issue**: Test expects `None` when queue is full, but NLWebParticipant returns a message
**Root Cause**: The test mocks `add_to_queue` to raise `QueueFullError`, but NLWebParticipant catches this and still returns a response
**Fix**: Update NLWebParticipant to return `None` when QueueFullError is raised

#### b) `TestMultiParticipantScenarios::test_context_includes_appropriate_history_from_all`
**Issue**: Context building doesn't include messages from all participants correctly
**Root Cause**: NLWebParticipant context builder may not be filtering messages properly
**Fix**: Update context building logic to include messages from all human participants

#### c) `TestConversation::test_conversation_serialization`
**Issue**: Test expects `participant_count` in serialized dict, but it's not included
**Root Cause**: `to_dict()` method doesn't include `participant_count`
**Fix**: Add `participant_count` to the `to_dict()` method output

#### d) `TestConversationCache::test_memory_pressure_handling`
**Issue**: Cache eviction not working under memory pressure
**Root Cause**: Cache implementation may not have memory pressure handling
**Fix**: Implement proper LRU eviction or memory limit handling

### 2. Integration Test Failures (35/37 tests)

**Issue**: All tests use `aioresponses` mock library expecting fake endpoints
**Example**: Tests mock responses like:
```python
mock.post('http://localhost:8080/chat/create', payload={...})
```

**Fix Strategy**:
1. Replace all `aioresponses` usage with real HTTP client calls
2. Update test fixtures to start/stop server or use existing server
3. Update URLs from 8080 to 8000 (actual server port)
4. Remove all mock response definitions
5. Add proper cleanup between tests

### 3. E2E Test Failures in `test_multi_participant.py` (11 tests)

**Issue**: Tests expect non-existent endpoints like `POST /chat/{id}/message`
**Root Cause**: Original test design assumed REST endpoints for messaging, but implementation uses WebSocket

**Fix Strategy**:
1. **Option A**: Update tests to use WebSocket for messaging (like we did in `test_multi_participant_real.py`)
2. **Option B**: Mark these as future features and skip them
3. **Option C**: Implement the missing REST endpoints (not recommended - WebSocket is better)

**Specific failing features**:
- Share link generation (`/chat/{id}/share`) - Not implemented
- Message REST endpoint (`/chat/{id}/message`) - Not implemented
- High volume testing - Needs performance infrastructure

### 4. Performance Test Failures

**Issue**: Tests require performance testing infrastructure
**Fix Strategy**:
1. Set up performance testing harness
2. Create baseline measurements
3. Implement load generation tools
4. Add metrics collection

### 5. Security Test Failures

**Issue**: Tests require security testing infrastructure
**Fix Strategy**:
1. Implement authentication bypass detection
2. Add SQL injection testing
3. Implement rate limiting tests
4. Add authorization boundary tests

### 6. Reliability Test Failures

**Issue**: Tests require chaos engineering setup
**Fix Strategy**:
1. Implement connection drop simulation
2. Add server restart recovery tests
3. Implement network partition tests
4. Add data consistency checks

## Implementation Order

### Phase 1: Quick Fixes (1-2 hours)
1. Fix unit test failures (4 tests)
   - Update NLWebParticipant queue handling
   - Fix conversation serialization
   - Update context building
   - Implement cache eviction

### Phase 2: Integration Test Rewrite (4-6 hours)
1. Create base test class with server management
2. Rewrite REST API tests without mocks
3. Rewrite WebSocket tests without mocks
4. Add proper test isolation

### Phase 3: E2E Test Updates (2-3 hours)
1. Decide on approach for old E2E tests
2. Either update to use WebSocket or mark as future
3. Document missing features for product roadmap

### Phase 4: Test Infrastructure (1-2 days)
1. Set up performance testing framework
2. Implement security testing tools
3. Create reliability testing harness
4. Add continuous monitoring

## Quick Win Implementation

Let's start with the unit test fixes since they're the quickest:

### Fix 1: Queue Full Handling
```python
# In chat/participants.py, update process_message:
async def process_message(self, message: ChatMessage, add_to_queue_func) -> Optional[ChatMessage]:
    try:
        # ... existing code ...
        nlweb_message = ChatMessage(...)
        await add_to_queue_func(nlweb_message)
        return nlweb_message
    except QueueFullError:
        logger.warning(f"Queue full, dropping NLWeb response")
        return None  # Return None when queue is full
```

### Fix 2: Conversation Serialization
```python
# In chat/schemas.py, update Conversation.to_dict():
def to_dict(self) -> Dict[str, Any]:
    return {
        "conversation_id": self.conversation_id,
        "created_at": self.created_at.isoformat(),
        "active_participants": [p.to_dict() for p in self.active_participants],
        "queue_size_limit": self.queue_size_limit,
        "message_count": self.message_count,
        "participant_count": len(self.active_participants),  # Add this line
        "metadata": self.metadata
    }
```

### Fix 3: Context Building
```python
# In chat/participants.py, update _build_context:
def _build_context(self, recent_messages: List[ChatMessage]) -> List[Dict[str, Any]]:
    # Include messages from all human participants, not just the last one
    human_messages = [
        msg for msg in recent_messages 
        if msg.sender_id != self.participant_id  # All non-NLWeb messages
    ]
    # ... rest of implementation
```

### Fix 4: Cache Eviction
```python
# Implement basic LRU eviction in cache class
# This depends on the actual cache implementation
```