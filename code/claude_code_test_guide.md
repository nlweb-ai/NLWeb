# Claude Code Test Implementation Guide - Multi-Participant Chat System

## 🚨 CRITICAL: How to Use This Guide with Claude Code

### Golden Rules
1. **NEVER paste this entire document** - Work in small test suites
2. **Start with Command 1** below to set up the test framework
3. **Use the Session Management commands** when context gets full
4. **Run tests frequently** - After each implementation phase
5. **Track test results** in TEST_RESULTS.md

### When Context Fills Up (Claude Code will warn you)
```
# Paste this exactly:
What's our current context usage?

If it's over 60%, please:
1. Update TEST_PROGRESS.md with completed test suites
2. Update FAILING_TESTS.md with any tests that need attention
3. Commit all test files with message "tests: [describe what we just tested]"
4. Run compact
5. Tell me exactly how to resume testing
```

### To Resume Testing After a Break
```
# Paste this exactly:
Continue the test implementation.
/cat TEST_PROGRESS.md
/cat FAILING_TESTS.md
pytest --tb=short -v --last-failed

Show me which test suite we should work on next.
```

---

## 📋 Command 1: Initialize Test Framework (ALWAYS START HERE)

```
Set up the testing framework and create tracking files:

1. Create test tracking files:
   - TEST_PROGRESS.md - Track completed test suites
   - FAILING_TESTS.md - Document failing tests and why
   - TEST_METRICS.md - Performance benchmarks
   - MOCK_DATA.md - Mock user and conversation data

2. Install test dependencies:
   - pytest and pytest-asyncio for async testing
   - pytest-benchmark for performance tests
   - aioresponses for mocking HTTP/WebSocket
   - pytest-timeout for timeout handling
   - pytest-cov for coverage reports

3. Create test configuration:
   - tests/conftest.py with shared fixtures
   - tests/config_test.yaml with test-specific settings
   - Set up mock storage backend
   - Configure test database/cache

4. Establish performance baseline:
   - Create tests/performance/test_baseline.py
   - Measure current /ask endpoint latency
   - Document baseline in TEST_METRICS.md
   - This will be our ≤105% target

5. Create the test structure:
   tests/
   ├── unit/           # Schema, storage, participant tests
   ├── integration/    # API endpoint, WebSocket flow tests
   ├── performance/    # Latency and throughput tests
   ├── security/       # Auth, XSS, rate limiting tests
   ├── reliability/    # Failure recovery tests
   ├── e2e/           # End-to-end multi-participant scenarios
   └── fixtures/      # Shared test data and mocks

Key requirements:
- Tests must support both single participant (80% case) and multi-participant scenarios
- Performance tests must verify ≤105% latency for 1 human + 1 AI
- All async operations must be properly tested
- WebSocket tests need mock server capability
```

---

## Phase 1: Unit Tests - Core Components

### Command 2: Schema and Data Model Tests

```
Create unit tests for the data models in tests/unit/test_schemas.py:

Test ChatMessage:
- Unique message_id generation
- sequence_id assignment (must be server-side only)
- sender_id correctly identifies different humans
- Timestamp in UTC
- Message content validation
- Maximum message size enforcement (10,000 chars)
- Message type enum validation
- Status transitions (pending → delivered → failed)

Test Conversation:
- Participant tracking with multiple humans
- Mode switching (SINGLE ↔ MULTI) based on participant count
- Queue size limit enforcement (default 1000)
- Last message tracking
- Participant join/leave events
- Maximum participant limit (100)

Test ParticipantInfo:
- Human vs AI type distinction
- Online status tracking
- Joined timestamp
- Unique participant IDs
- Display name validation

Include edge cases:
- Empty conversations
- Conversations at max capacity
- Invalid message types
- XSS attempts in content
- Unicode handling

Write property-based tests for:
- Message ordering by sequence_id
- Participant count accuracy
- Queue overflow behavior
```


### Command 3: Storage Interface Tests

```
Create comprehensive storage tests in tests/unit/test_storage.py:

Test ChatStorageInterface implementations:
- store_message idempotency (duplicate handling)
- get_next_sequence_id atomicity
- Concurrent sequence ID generation (critical for multi-human)
- Message retrieval with pagination
- Message ordering by sequence_id
- Storage backend switching via config

Test Memory Storage:
- In-memory implementation correctness
- Queue limit enforcement
- Sequence counter thread safety
- Message persistence across retrieval
- Conversation isolation

Test Cache Layer:
- LRU eviction at 100 messages
- Thread-safe operations
- Cache hit/miss tracking
- Memory pressure handling
- Participant list caching
- Performance: cache vs storage speed

Concurrent access tests:
- 10 humans sending messages simultaneously
- Sequence IDs remain sequential
- No message loss under load
- Cache consistency

Create helper fixtures:
- create_test_conversation()
- create_test_messages(count, participants)
- simulate_concurrent_writes()
```

### Command 4: Participant and NLWeb Integration Tests

```
Create participant tests in tests/unit/test_participants.py:

Test BaseParticipant interface:
- Abstract method enforcement
- Participant info correctness
- Message delivery mechanism

Test NLWebParticipant:
- NLWebHandler wrapping WITHOUT modification
- Context building with multi-human messages
- Timeout handling (20s default)
- Stream callback functionality
- Response filtering (when NLWeb chooses not to respond)
- Queue full handling

Test NLWebContextBuilder:
- Correct number of human messages included (configurable)
- Messages from ALL humans included, not just one
- Sender identification preserved
- prev_queries format correctness
- last_answers format with only AI responses
- Site and mode preservation

Mock NLWebHandler behavior:
- Successful response
- Timeout scenario
- No response decision
- Streaming response chunks
- Error during processing

Multi-participant scenarios:
- NLWeb sees messages from 3 different humans
- Context includes appropriate history from all
- Each human's identity preserved in context
```

---

## Phase 2: Integration Tests - API and WebSocket

### Command 5: REST API Integration Tests

```
Create API tests in tests/integration/test_rest_api.py:

Test conversation creation:
- Single participant conversation
- Multi-participant with 2-5 humans
- Invalid participant data
- Missing required fields
- Participant limit enforcement

Test conversation retrieval:
- List all conversations for user
- Get specific conversation with full history
- Pagination handling
- Access control (can't see others' conversations)
- Empty conversation list

Test join/leave operations:
- Join existing conversation
- Join when already participant (409)
- Join when at capacity (429)
- Leave conversation successfully
- Last participant leaving

Test health endpoint:
- All subsystems healthy
- Degraded state detection
- Metric accuracy
- Response time <100ms

Auth testing:
- Valid token acceptance
- Invalid token rejection
- Token expiry handling
- OAuth vs email-based users

Error scenarios:
- 404 for non-existent conversations
- 429 rate limiting
- 500 server errors with retry guidance
```

### Command 6: WebSocket Integration Tests

```
Create WebSocket tests in tests/integration/test_websocket.py:

Connection lifecycle:
- Successful handshake with auth
- Multiple humans connecting to same conversation
- Reconnection with exponential backoff
- Connection limit enforcement
- Dead connection detection

Message flow tests:
- Single human sends, NLWeb responds
- Multiple humans send simultaneously
- Message ordering via sequence_ids
- Typing indicators (throttled)
- AI response streaming

Sync mechanism:
- Reconnect with last_sequence_id
- Receive only missed messages
- Participant list sync
- No duplicate messages

Broadcast tests:
- 3 humans + 2 AI agents scenario
- All participants receive all messages
- O(N) broadcast performance
- Selective delivery failures

Error handling:
- Queue full (429) response
- Invalid message format
- Authentication failure
- Network interruption
- Participant limit exceeded

Create WebSocket test client:
- Mock handshake
- Message sending/receiving
- Reconnection simulation
- Latency measurement
```

---
NEXT
## Phase 3: Performance Tests

### Command 7: Latency and Throughput Tests

```
Create performance tests in tests/performance/test_latency.py:

Single participant performance (CRITICAL - 80% of usage):
- Measure: baseline /ask vs chat WebSocket
- Target: ≤105% of baseline latency
- Test with typical message sizes
- Include NLWeb processing time
- Measure memory overhead

Multi-participant scenarios (15% of usage):
- 2-5 humans + AI agents
- Message broadcast time
- Target: <200ms perceived latency
- Linear scaling verification

Large group tests (5% of usage):
- 50-100 total participants
- Broadcast performance
- Memory usage scaling
- Queue management overhead

Throughput tests:
- 100 messages/second per conversation
- 1000 concurrent connections
- 100 active conversations
- Memory usage under load

Create performance fixtures:
- measure_latency decorator
- memory_usage tracker
- concurrent_load generator

Output format for TEST_METRICS.md:
- p50, p95, p99 latencies
- Memory usage graphs
- Throughput curves
- Comparison to baseline
```

### Command 8: Load and Stress Tests

```
Create load tests in tests/performance/test_load.py:

Sustained load patterns:
- 500 concurrent single-participant chats
- 100 multi-participant conversations (3-5 humans each)
- 10 large conversations (50+ participants)
- Run for 15 minutes minimum

Spike patterns:
- Sudden influx of 200 connections
- Burst of 1000 messages in 10 seconds
- Mass reconnection scenario
- Participant join/leave storms

Resource limits:
- Queue overflow behavior
- Memory pressure response
- Connection limit handling
- Storage write throughput

Degradation tests:
- Performance with 90% memory used
- Storage latency increases
- Network packet loss
- CPU throttling

Monitor during tests:
- Response time percentiles
- Error rates
- Queue depths
- Memory/CPU usage
- Connection stability

Define failure criteria:
- >105% latency for single participant
- >500ms for multi-participant
- Any message loss
- System crash
```

---

## Phase 4: Security Tests

### Command 9: Authentication and Authorization Tests

```
Create security tests in tests/security/test_auth.py:

WebSocket authentication:
- Valid token accepts connection
- Invalid token rejects immediately
- Expired token handling
- Token refresh during connection
- Session hijacking prevention

REST endpoint auth:
- All endpoints require auth
- Token validation on every request
- Cross-user access prevention
- Admin vs regular user permissions

Multi-participant auth:
- Each human authenticates independently
- Can't impersonate other participants
- Join requests validate permissions
- Participant removal authorization

Token security:
- No tokens in URLs
- Secure storage (sessionStorage)
- Token rotation support
- Logout clears all tokens

Rate limiting:
- Per-user connection limits
- Message rate throttling
- Queue overflow returns 429
- Exponential backoff enforcement

Create auth test utilities:
- create_test_token()
- simulate_token_expiry()
- attempt_impersonation()
```

### Command 10: Input Validation and XSS Tests

```
Create security tests in tests/security/test_validation.py:

Input sanitization:
- XSS payloads in messages
- Script injection attempts
- SQL injection patterns
- Command injection tests
- Unicode exploits

Message content validation:
- Maximum size enforcement
- Binary data rejection
- Malformed JSON handling
- Special character escaping
- URL validation

File upload security (if applicable):
- File type restrictions
- Size limits
- Virus scanning hooks
- Path traversal prevention

WebSocket security:
- Frame size limits
- Compression bomb prevention
- Protocol downgrade attacks
- Origin header validation

Output encoding:
- HTML entity encoding
- JSON escaping
- Content-Type headers
- CSP header validation

Create security payloads:
- Common XSS vectors
- OWASP top 10 patterns
- Polyglot payloads
- Encoding bypass attempts
```

---

## Phase 5: Reliability and Failure Recovery Tests

### Command 11: Failure Recovery Tests

```
Create reliability tests in tests/reliability/test_recovery.py:

Network failures:
- Connection drop during message send
- Intermittent connectivity (flapping)
- High latency conditions (>1s)
- Packet loss simulation
- DNS resolution failures

Storage failures:
- Write failures during persistence
- Read timeouts
- Connection pool exhaustion
- Partial write scenarios
- Cache/storage inconsistency

Service failures:
- NLWeb timeout handling
- Partial participant failures
- WebSocket server restart
- Database failover
- Cache eviction under pressure

Message delivery guarantees:
- At-least-once verification
- Duplicate detection
- Order preservation
- No message loss proof
- Acknowledgment system

Recovery mechanisms:
- Automatic reconnection
- Message replay
- State synchronization
- Participant list recovery
- Queue state restoration

Create failure simulators:
- network_partition()
- storage_outage()
- random_disconnects()
- memory_pressure()
```

### Command 12: End-to-End Multi-Participant Tests

```
Create E2E tests in tests/e2e/test_multi_participant.py:

Real-world scenarios:

Scenario 1: Team collaboration
- 3 humans join conversation
- Each sends 5 messages
- 2 AI agents respond
- One human disconnects/reconnects
- Verify message ordering

Scenario 2: Large group chat
- Start with 2 participants
- Gradually add to 20 participants
- High message volume (10 msg/sec)
- Random disconnections
- Monitor performance degradation

Scenario 3: Edge cases
- Rapid join/leave
- Simultaneous typing
- Network partitions
- Storage delays
- Queue near limits

Scenario 4: Mode transitions
- Start with 1 human + 1 AI
- Add second human (mode change)
- Remove human (mode change back)
- Verify UI updates

Full conversation lifecycle:
- Create conversation
- Multiple participants join
- Active messaging
- Participant changes
- Conversation conclusion
- History retrieval

Measure end-to-end:
- Message latency
- UI responsiveness
- State consistency
- Error recovery
- User experience metrics
```

---

## 🚨 Test Debugging Commands

### When Tests Fail
```
A test is failing. Help me debug:
1. Run: pytest -xvs path/to/failing/test.py::test_name
2. Add print statements in the test
3. Check the mock setup
4. Verify async/await usage
5. Compare expected vs actual
```

### Performance Test Failures
```
Performance test exceeds 105% threshold:
1. Profile the slow operation
2. Check for unnecessary loops
3. Verify caching is working
4. Look for blocking I/O
5. Consider fast-path optimizations
```

### WebSocket Test Issues
```
WebSocket tests are flaky:
1. Increase timeout values
2. Add wait_for conditions
3. Check event ordering
4. Verify mock server state
5. Add retry mechanisms
```

---

## 📋 Reference Information for Testing

### Mock Data Creation
```python
# Standard test users
TEST_USERS = [
    {"id": "user1", "name": "Alice", "email": "alice@test.com"},
    {"id": "user2", "name": "Bob", "email": "bob@test.com"},
    {"id": "user3", "name": "Charlie", "email": "charlie@test.com"}
]

# Test conversation sizes
CONVERSATION_SIZES = {
    "single": 2,      # 1 human + 1 AI (80% of usage)
    "small": 5,       # 3 humans + 2 AI (15% of usage)  
    "medium": 20,     # Mixed participants
    "large": 100      # Max capacity (5% of usage)
}

# Performance thresholds
LATENCY_TARGETS = {
    "single_participant": 1.05,  # 105% of baseline
    "multi_participant": 200,    # 200ms absolute
    "large_group": 500          # 500ms absolute
}
```

### Test Execution Patterns
```bash
# Run specific test suites
pytest tests/unit/ -v                    # All unit tests
pytest tests/integration/ -v             # All integration tests
pytest tests/performance/ -v --benchmark # Performance with benchmarks

# Run with coverage
pytest --cov=chat --cov-report=html

# Run only failing tests
pytest --last-failed

# Run with specific markers
pytest -m "not slow"                     # Skip slow tests
pytest -m "security"                     # Only security tests
```

### CI/CD Integration
```yaml
# Example test stages
stages:
  - unit-tests      # Fast, run on every commit
  - integration     # Medium speed, run on PR
  - performance     # Slow, run on merge
  - security        # Thorough, run nightly
  - e2e            # Complete, run before release
```

---

## Context Management for Test Development

### Test Progress Tracking
```markdown
# TEST_PROGRESS.md format
- [x] Unit: Schemas (15 tests) ✓
- [x] Unit: Storage (23 tests) ✓
- [ ] Integration: REST API (0/18 tests)
- [ ] Performance: Baseline established
```

### Failing Tests Documentation
```markdown
# FAILING_TESTS.md format
## test_concurrent_sequence_ids
- Reason: Race condition in sequence generation
- Fix: Add mutex lock in get_next_sequence_id
- Priority: HIGH (affects message ordering)
```

### Test Metrics Tracking
```markdown
# TEST_METRICS.md format
## Baseline Performance
- /ask endpoint: 45ms (p50), 120ms (p95)
- Target: 47ms (p50), 126ms (p95)

## Current Performance  
- Single participant: 46ms (p50), 118ms (p95) ✓
- Multi participant: 180ms (p50), 210ms (p95) ✓
```

---

## Backend Internal API Testing

### Command 13: ConversationManager Tests

```
Create backend internal tests in tests/unit/test_conversation_manager.py:

Test participant management:
- Add participant to empty conversation → Mode = SINGLE
- Add second human → Mode switches to MULTI
- Remove participant → Mode updates correctly
- Exceed max participants → Raises error
- Participant list consistency

Test message processing:
- Process message with full queue → QueueFullError
- Concurrent message processing → Sequential sequence IDs
- Broadcast failure to one participant → Others receive
- Message acknowledgment tracking
- Async persistence triggering

Test conversation state:
- Mode transitions (SINGLE ↔ MULTI)
- Active participant tracking
- Queue depth monitoring
- Message count accuracy

Create test utilities:
- mock_conversation(participant_count)
- simulate_message_burst(count, interval)
- verify_broadcast_delivery()
```

### Command 14: NLWebParticipant Internal Tests

```
Create NLWeb internal tests in tests/unit/test_nlweb_internals.py:

Test context building:
- Correct number of messages included
- Multi-human message attribution
- Context format validation
- Metadata preservation

Test NLWeb integration:
- Timeout after 20s
- Stream callback ordering
- NLWeb no-response handling
- Multiple NLWeb participants
- Context isolation between NLWeb agents

Test error handling:
- NLWebHandler exceptions
- Partial response failures
- Queue full during response
- Invalid response format

Performance tests:
- Context building <5ms
- NLWeb wrapper overhead <1ms
- Streaming latency impact
```

### Command 15: Storage Backend Tests

```
Create storage backend tests in tests/unit/test_storage_backends.py:

Test atomic operations:
- Sequence ID generation under load
- No duplicates with 100 concurrent requests
- Rollback on failure
- Cross-conversation isolation

Test message operations:
- Pagination with before_sequence_id
- Message ordering guarantees
- Duplicate message idempotency
- Bulk retrieval performance

Test failure scenarios:
- Storage unavailable
- Partial write failures
- Connection timeouts
- Recovery after outage

Backend-specific tests:
- Memory: Thread safety
- Azure: Etag conflicts
- Qdrant: Version conflicts
- Elastic: Index consistency
```

---

## Test Execution and Debugging

### Running Tests Locally
```bash
# Initial setup
pip install -r requirements-test.txt
cp tests/config_test.yaml.example tests/config_test.yaml

# Run all tests
pytest -v

# Run with specific verbosity
pytest -v              # Verbose
pytest -vv             # Very verbose
pytest -q              # Quiet

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/performance/ --benchmark-only
pytest tests/security/
pytest tests/e2e/

# Debug specific test
pytest -xvs tests/unit/test_schemas.py::test_message_ordering

# Generate coverage report
pytest --cov=chat --cov-report=html --cov-report=term
```

### Continuous Integration Setup
```yaml
# .github/workflows/tests.yml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements-test.txt
      - run: pytest tests/unit/ -v --cov=chat

  integration-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements-test.txt
      - run: pytest tests/integration/ -v

  performance-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements-test.txt
      - run: pytest tests/performance/ -v --benchmark-json=benchmark.json
      - uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: benchmark.json
```

### Test Development Workflow
1. **Write test first** - Define expected behavior
2. **Run test** - Confirm it fails
3. **Implement feature** - Minimal code to pass
4. **Run test** - Confirm it passes
5. **Refactor** - Improve implementation
6. **Run all tests** - Ensure no regressions
7. **Check coverage** - Aim for >90%
8. **Update TEST_PROGRESS.md** - Track completion

Remember: **Tests are documentation of system behavior**