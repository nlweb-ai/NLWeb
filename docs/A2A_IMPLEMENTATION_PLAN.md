# A2A (Agent-to-Agent) Protocol Implementation Plan for NLWeb

## Executive Summary

This document outlines the plan to implement A2A (Agent-to-Agent) protocol support in NLWeb alongside the existing MCP (Model Context Protocol) implementation. A2A enables direct communication between AI agents, allowing them to collaborate, share context, and coordinate actions.

## Current State Analysis

### Existing MCP Implementation
- **Location**: `code/python/webserver/mcp_wrapper.py` and `code/python/webserver/routes/mcp.py`
- **Protocol**: JSON-RPC 2.0 based
- **Key Features**:
  - Tools discovery (`tools/list`)
  - Tool execution (`tools/call`)
  - Streaming support via SSE
  - Main tool: `ask` for querying NLWeb

### Architecture Strengths
- Clean separation between protocol handling and business logic
- Existing abstraction through `NLWebHandler`
- Support for both streaming and non-streaming responses
- Modular route handling in aiohttp server

## A2A Protocol Overview

A2A is designed for agent-to-agent communication with these key concepts:

1. **Agent Identity**: Each agent has a unique identifier and capabilities
2. **Message Exchange**: Agents can send messages directly to other agents
3. **Context Sharing**: Agents can share conversation context and state
4. **Capability Discovery**: Agents can discover what other agents can do
5. **Coordination**: Support for multi-agent workflows and delegation

## Implementation Architecture

### 1. Protocol Handler Layer

Create a new A2A handler parallel to MCP:

```
webserver/
├── mcp_wrapper.py          (existing)
├── a2a_wrapper.py          (new)
├── protocol_manager.py     (new - unified protocol management)
└── routes/
    ├── mcp.py             (existing)
    └── a2a.py             (new)
```

### 2. Core Components

#### A. A2AHandler Class (`webserver/a2a_wrapper.py`)
```python
class A2AHandler:
    def __init__(self):
        self.agent_id = "nlweb-agent-{uuid}"
        self.capabilities = {}
        self.registered_agents = {}
        self.conversation_contexts = {}
    
    async def handle_request(self, request_data, query_params, send_response, send_chunk):
        # Route A2A protocol messages
        pass
    
    async def handle_agent_discovery(self, params):
        # Implement agent capability discovery
        pass
    
    async def handle_message_exchange(self, params):
        # Handle inter-agent messages
        pass
    
    async def handle_context_share(self, params):
        # Share conversation context between agents
        pass
```

#### B. Protocol Manager (`webserver/protocol_manager.py`)
```python
class ProtocolManager:
    def __init__(self):
        self.mcp_handler = MCPHandler()
        self.a2a_handler = A2AHandler()
        self.active_sessions = {}
    
    async def route_request(self, protocol, request_data, params):
        # Route to appropriate protocol handler
        pass
    
    async def bridge_protocols(self, source_protocol, target_protocol, message):
        # Enable cross-protocol communication
        pass
```

### 3. A2A-Specific Features

#### A. Agent Registry
- Maintain registry of known agents and their capabilities
- Support dynamic agent discovery
- Cache agent metadata for performance

#### B. Context Management
- Store and retrieve conversation contexts
- Support context merging from multiple agents
- Implement context expiry and cleanup

#### C. Message Router
- Route messages between agents
- Support broadcast and multicast patterns
- Handle message queuing and delivery guarantees

#### D. Security Layer
- Agent authentication and authorization
- Message encryption for sensitive data
- Rate limiting and abuse prevention

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
1. Create `a2a_wrapper.py` with basic A2A protocol structure
2. Implement agent registration and discovery
3. Set up A2A routes in `routes/a2a.py`
4. Create protocol detection logic

**Deliverables**:
- Basic A2A handler responding to discovery requests
- Agent registration endpoint
- Protocol version negotiation

### Phase 2: Core Messaging (Week 3-4)
1. Implement message exchange between agents
2. Add context sharing capabilities
3. Create message routing logic
4. Implement basic error handling

**Deliverables**:
- Agent-to-agent messaging
- Context storage and retrieval
- Message delivery confirmation

### Phase 3: Integration (Week 5-6)
1. Create Protocol Manager for unified handling
2. Bridge MCP and A2A protocols
3. Extend `ask` tool for A2A context
4. Add multi-agent coordination support

**Deliverables**:
- Unified protocol endpoint
- Cross-protocol communication
- Enhanced query handling with agent context

### Phase 4: Advanced Features (Week 7-8)
1. Implement agent capability composition
2. Add workflow orchestration
3. Create agent federation support
4. Implement caching and optimization

**Deliverables**:
- Multi-agent workflows
- Performance optimizations
- Agent capability aggregation

### Phase 5: Security & Testing (Week 9-10)
1. Implement authentication mechanisms
2. Add authorization policies
3. Create comprehensive test suite
4. Performance testing and optimization

**Deliverables**:
- Security layer implementation
- Test coverage > 80%
- Performance benchmarks

## Technical Implementation Details

### 1. Endpoint Structure

```
/a2a                    # Main A2A endpoint
/a2a/register          # Agent registration
/a2a/discover          # Capability discovery
/a2a/message           # Message exchange
/a2a/context           # Context operations
/a2a/health            # Health check
```

### 2. Message Format

```json
{
  "version": "1.0",
  "type": "agent_message",
  "from": "agent-id-1",
  "to": "agent-id-2",
  "conversation_id": "conv-123",
  "sequence_id": 1,
  "timestamp": "2025-01-17T10:00:00Z",
  "content": {
    "type": "query|response|context|capability",
    "data": {}
  },
  "metadata": {
    "priority": "normal",
    "ttl": 3600
  }
}
```

### 3. Capability Declaration

```json
{
  "agent_id": "nlweb-agent-123",
  "name": "NLWeb Query Agent",
  "version": "1.0.0",
  "capabilities": [
    {
      "name": "natural_language_query",
      "description": "Process natural language queries",
      "input_schema": {},
      "output_schema": {}
    },
    {
      "name": "site_search",
      "description": "Search specific sites",
      "parameters": ["site", "query", "mode"]
    }
  ],
  "protocols": ["a2a/1.0", "mcp/2024-11-05"]
}
```

### 4. Configuration Extension

Add to `config_nlweb.yaml`:

```yaml
a2a:
  enabled: true
  agent_id: "nlweb-{instance_id}"
  agent_name: "NLWeb Agent"
  max_context_size: 10000
  context_ttl: 3600
  discovery_cache_ttl: 300
  message_queue_size: 1000
  protocols:
    - version: "1.0"
      features: ["messaging", "context", "discovery"]
  security:
    require_auth: false
    allowed_agents: []
    rate_limit: 100
```

## Code Structure

### New Files to Create

1. **`code/python/webserver/a2a_wrapper.py`**
   - Main A2A protocol handler
   - Message routing logic
   - Context management

2. **`code/python/webserver/routes/a2a.py`**
   - A2A route definitions
   - Request/response handling
   - WebSocket support for real-time messaging

3. **`code/python/webserver/protocol_manager.py`**
   - Unified protocol management
   - Protocol detection and routing
   - Cross-protocol bridging

4. **`code/python/core/agent_registry.py`**
   - Agent registration and discovery
   - Capability caching
   - Agent metadata management

5. **`code/python/core/context_manager.py`**
   - Conversation context storage
   - Context merging algorithms
   - Context expiry management

### Modified Files

1. **`code/python/webserver/aiohttp_server.py`**
   - Add A2A route registration
   - Initialize Protocol Manager

2. **`code/python/core/baseHandler.py`**
   - Extend to accept agent context
   - Add agent-aware response formatting

3. **`config/config_nlweb.yaml`**
   - Add A2A configuration section

## Testing Strategy

### Unit Tests
- Protocol message parsing
- Agent registration/discovery
- Context management operations
- Message routing logic

### Integration Tests
- End-to-end agent communication
- Cross-protocol communication
- Multi-agent workflows
- Performance under load

### Test Files
```
tests/
├── test_a2a_protocol.py
├── test_agent_registry.py
├── test_context_manager.py
├── test_protocol_bridging.py
└── test_multi_agent_workflows.py
```

## Monitoring and Observability

### Metrics to Track
- Number of registered agents
- Message exchange rate
- Context storage size
- Protocol bridge usage
- Error rates by protocol

### Logging
- Agent registration/deregistration
- Message routing decisions
- Context operations
- Protocol negotiations
- Error conditions

## Migration and Compatibility

### Backward Compatibility
- MCP endpoints remain unchanged
- Existing tools continue to work
- No breaking changes to current API

### Protocol Detection
```python
async def detect_protocol(request):
    # Check headers
    if "A2A-Version" in request.headers:
        return "a2a"
    
    # Check request body
    if "jsonrpc" in request.json():
        return "mcp"
    
    # Check for A2A message structure
    if "agent_id" in request.json():
        return "a2a"
    
    # Default to MCP for compatibility
    return "mcp"
```

## Documentation Requirements

1. **A2A Protocol Specification** - Detailed protocol documentation
2. **Integration Guide** - How to integrate A2A agents with NLWeb
3. **API Reference** - Complete A2A endpoint documentation
4. **Examples** - Sample A2A agent implementations
5. **Migration Guide** - Moving from MCP to A2A

## Success Criteria

1. **Functional**
   - Agents can register and discover each other
   - Messages are successfully exchanged
   - Context sharing works across agents
   - MCP compatibility is maintained

2. **Performance**
   - Message latency < 100ms
   - Support 100+ concurrent agents
   - Context retrieval < 50ms

3. **Reliability**
   - 99.9% message delivery success
   - Graceful handling of agent failures
   - Automatic recovery from network issues

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Protocol complexity | High | Start with minimal viable protocol |
| Performance degradation | Medium | Implement caching and optimization early |
| Security vulnerabilities | High | Security review in Phase 5 |
| Breaking MCP compatibility | High | Extensive testing, gradual rollout |
| Agent coordination complexity | Medium | Simple coordination patterns first |

## Timeline Summary

- **Weeks 1-2**: Foundation and basic protocol
- **Weeks 3-4**: Core messaging implementation
- **Weeks 5-6**: Integration with existing systems
- **Weeks 7-8**: Advanced features
- **Weeks 9-10**: Security, testing, and polish

Total estimated time: 10 weeks for full implementation

## Next Steps

1. Review and approve implementation plan
2. Set up development branch for A2A
3. Begin Phase 1 implementation
4. Create detailed technical specifications
5. Establish testing infrastructure

## Appendix: Example A2A Interaction

```python
# Agent 1: Register
POST /a2a/register
{
  "agent_id": "search-agent-1",
  "capabilities": ["search", "summarize"]
}

# Agent 2: Discover agents
GET /a2a/discover?capability=search
Response: [{"agent_id": "search-agent-1", ...}]

# Agent 2: Send message to Agent 1
POST /a2a/message
{
  "from": "coordinator-agent",
  "to": "search-agent-1",
  "content": {
    "type": "query",
    "data": {"query": "latest AI news"}
  }
}

# Agent 1: Response
{
  "from": "search-agent-1",
  "to": "coordinator-agent",
  "content": {
    "type": "response",
    "data": {"results": [...]}
  }
}
```