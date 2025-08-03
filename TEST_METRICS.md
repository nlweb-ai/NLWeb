# Test Performance Metrics

## Performance Baselines

### Current System (/ask endpoint)
- **Baseline Latency**: NOT MEASURED
- **Measurement Date**: -
- **Test Conditions**: -
- **Average Response Time**: -
- **P50 Latency**: -
- **P95 Latency**: -
- **P99 Latency**: -

### Performance Targets

#### Single Participant (1 Human + 1 AI)
- **Target**: ≤105% of baseline /ask latency
- **Current**: NOT MEASURED
- **Status**: ⚪ Not Started

#### Multi-Participant (2-5 Humans)
- **Target**: <200ms message delivery
- **Current**: NOT MEASURED
- **Status**: ⚪ Not Started

#### WebSocket Overhead
- **Target**: ≤50ms handshake overhead
- **Current**: NOT MEASURED
- **Status**: ⚪ Not Started

#### Message Routing
- **Target (2 participants)**: ≤1ms
- **Target (10 participants)**: ≤5ms
- **Current**: NOT MEASURED
- **Status**: ⚪ Not Started

#### Storage Operations
- **Target**: <50ms for sequence ID assignment
- **Current**: NOT MEASURED
- **Status**: ⚪ Not Started

## Throughput Metrics

### WebSocket Connections
- **Target**: 1000 concurrent per server
- **Current**: NOT MEASURED
- **Status**: ⚪ Not Started

### Message Processing
- **Target**: 100 messages/second per conversation
- **Current**: NOT MEASURED
- **Status**: ⚪ Not Started

### Maximum Participants
- **Target**: 100 participants per conversation
- **Current**: NOT MEASURED
- **Status**: ⚪ Not Started

## Memory Usage

### Single User Baseline
- **Baseline Memory**: NOT MEASURED
- **Measurement Date**: -

### Multi-Participant Target
- **Target**: ≤110% of single-user memory
- **Current**: NOT MEASURED
- **Status**: ⚪ Not Started

### Cache Efficiency
- **Messages Cached**: 100 per conversation
- **Eviction Strategy**: LRU under pressure
- **Current Efficiency**: NOT MEASURED

## Test Execution Metrics

### Unit Tests
- **Total Tests**: 83 (schemas: 31, storage: 28, participants: 24)
- **Average Execution Time**: TBD
- **Slowest Test**: TBD
- **Fastest Test**: TBD

### Integration Tests
- **Total Tests**: 57 (REST API: 27, WebSocket: 30)
- **Average Execution Time**: TBD
- **Slowest Test**: TBD
- **Fastest Test**: TBD

### Performance Tests
- **Total Tests**: 32 (latency tests across 4 categories)
- **Average Execution Time**: TBD
- **Slowest Test**: TBD (likely large group tests)
- **Fastest Test**: TBD (likely single participant)

### E2E Tests
- **Total Tests**: 0 (not yet implemented)
- **Average Execution Time**: -
- **Slowest Test**: -
- **Fastest Test**: -

## Performance Regression History

| Date | Test Suite | Metric | Previous | Current | Change | Status |
|------|------------|--------|----------|---------|--------|---------|
| - | - | - | - | - | - | No data |

## Resource Usage During Tests

### CPU Usage
- **Idle**: NOT MEASURED
- **During Unit Tests**: -
- **During Integration Tests**: -
- **During Load Tests**: -

### Memory Usage
- **Idle**: NOT MEASURED
- **During Unit Tests**: -
- **During Integration Tests**: -
- **During Load Tests**: -

### Network Usage
- **WebSocket Bandwidth**: NOT MEASURED
- **HTTP API Bandwidth**: -
- **Total Bandwidth**: -

## Test Infrastructure Performance

### Test Database
- **Setup Time**: NOT MEASURED
- **Teardown Time**: -
- **Query Performance**: -

### Mock Services
- **Mock WebSocket Latency**: NOT MEASURED
- **Mock API Latency**: -
- **Mock Storage Latency**: -

## Performance Test Configuration

### Load Test Parameters
```yaml
# NOT YET CONFIGURED
concurrent_users: -
ramp_up_time: -
test_duration: -
think_time: -
```

### Stress Test Parameters
```yaml
# NOT YET CONFIGURED
max_connections: -
message_rate: -
burst_size: -
```

## Notes
- All metrics pending test framework initialization
- Baseline measurements required before setting final targets
- Performance tests should run nightly to catch regressions