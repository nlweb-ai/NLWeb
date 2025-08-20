# MCP Integration Analysis

## Current MCP Behavior

### Overview
The Model Context Protocol (MCP) implementation provides a JSON-RPC 2.0 interface to NLWeb functionality, allowing external tools to query the system programmatically.

### Key Components

#### 1. MCP Routes (`webserver/routes/mcp.py`)
- **Endpoints**:
  - `/mcp/health`, `/mcp/healthz` - Health checks
  - `/mcp` (GET/POST) - Main MCP endpoint
  - `/mcp/{path:.*}` - MCP with path support
- **Features**:
  - Supports both GET and POST requests
  - Merges query parameters and JSON body
  - Routes to streaming or regular handlers

#### 2. MCP Handler (`webserver/mcp_wrapper.py`)
- **Protocol**: JSON-RPC 2.0 with MCP extensions
- **Version**: `2024-11-05`
- **Methods Supported**:
  - `initialize` - Client handshake
  - `initialized` - Server ready notification
  - `tools/list` - List available tools
  - `tools/call` - Execute a tool
  - `notifications/cancelled` - Handle cancellations

#### 3. Available Tools
1. **ask** - Main query tool
   - Parameters: `query`, `site[]`, `generate_mode`
   - Supports streaming responses via SSE
   - 10-second timeout for non-streaming calls

2. **list_sites** - List available sites
   - No parameters required
   - Returns configured sites from retriever

### Integration with NLWebHandler

#### Direct Usage
```python
# MCP creates NLWebHandler directly
handler = NLWebHandler(query_params, capture_chunk)
await handler.runQuery()
```

#### Key Points:
1. **No Modification**: MCP wraps NLWebHandler without changing it
2. **Parameter Translation**: MCP arguments → query params
3. **Response Capture**: Custom write_stream implementation
4. **Timeout Handling**: 10-second timeout for MCP requests

### Streaming Support

#### SSE (Server-Sent Events) for Streaming
- Enabled when `streaming=true` in query params
- Sends `function_stream_event` messages
- Ends with `function_stream_end` status

#### Response Format
```javascript
// Non-streaming
{
  "content": [{
    "type": "text",
    "text": "response content"
  }],
  "isError": false
}

// Streaming SSE events
data: {"type": "function_stream_event", "content": {"partial_response": "..."}}
data: {"type": "function_stream_end", "status": "success"}
```

### Authentication & Security
- Uses existing aiohttp request authentication
- No MCP-specific authentication layer
- Relies on middleware for auth validation

### State Management
- Single global `MCPHandler` instance
- Tracks initialization state
- No per-connection state
- Thread-safe for concurrent requests

## Integration Patterns for Chat

### 1. Reuse MCP's NLWebHandler Wrapper Pattern
```python
# Like MCP's ChunkCapture, create MessageCapture
class MessageCapture:
    def __init__(self, conversation):
        self.conversation = conversation
    
    async def write_stream(self, data, end_response=False):
        # Convert to chat message
        message = format_as_chat_message(data)
        await self.conversation.add_message(message)
```

### 2. Share Tool Definitions
- MCP already defines "ask" tool schema
- Chat can reuse these definitions
- Consistent interface across protocols

### 3. Timeout and Error Handling
- MCP uses 10-second timeout
- Chat should use similar patterns
- Consistent error responses

### 4. Streaming Architecture
- MCP uses SSE for streaming
- Chat uses WebSocket messages
- Both need chunk-to-message conversion

## Key Learnings for Chat Implementation

1. **Wrapper Pattern Works**: MCP successfully wraps NLWebHandler without modification
2. **Parameter Mapping**: Clean translation from protocol format to query params
3. **Response Streaming**: Custom write_stream handles different output formats
4. **Global State OK**: Single handler instance works for stateless operations
5. **Timeout Critical**: 10-second timeout prevents hanging requests
6. **No Auth Changes**: Existing middleware handles authentication

## Recommendations for Chat

1. **Follow MCP's Wrapper Pattern**: Create `NLWebParticipant` similar to MCP's approach
2. **Reuse Tool Schemas**: Import MCP tool definitions for consistency
3. **Similar Timeout Logic**: Use 10-20 second timeouts for NLWeb calls
4. **Stream Conversion**: Convert NLWeb chunks to chat messages like MCP converts to SSE
5. **Stateless Design**: Each message processed independently, no per-connection state
6. **Error Consistency**: Use similar error codes and messages as MCP