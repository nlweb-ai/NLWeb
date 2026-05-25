# NLWeb → ChatGPT Integration via MCP Server

This document provides a high-level overview of the integration stack that connects NLWeb to OpenAI ChatGPT.

**For detailed setup, usage, and deployment instructions, see:**
- [Main README](../openai-apps-sdk-integration/README.md) - Quick start and development guide
- [NLWeb Server README](../openai-apps-sdk-integration/nlweb_server_node/README.md) - Server usage and testing
- [Deployment Guide](../openai-apps-sdk-integration/DEPLOYMENT.md) - Production deployment

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        ChatGPT Desktop App                      │
│                  (OpenAI AppSDK Client)                         │
└────────────────────┬────────────────────────────────────────────┘
                     │ MCP Protocol (HTTP/SSE or stdio)
                     │ Tool: nlweb-list
                     │ Resource: ui://widget/nlweb-list.html
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      NLWeb MCP Server                           │
│                    (Node.js/TypeScript)                         │
│   Location: /openai-apps-sdk-integration/nlweb_server_node/    │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTP GET/POST to /ask
                     │ JSON Request/Response
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                   NLWeb AppSDK Adapter                          │
│              (Python aiohttp Server)                            │
                   │
│   Location: AskAgent/python/webserver/appsdk_adapter_server.py     │
└────────────────────┬────────────────────────────────────────────┘
                     │ Proxies to NLWeb Core
                     │ Transforms response format
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NLWeb Core Server                            │
│              (Python aiohttp Server)                            │
│          Location: AskAgent/python/webserver/                       │
└────────────────────┬────────────────────────────────────────────┘
                     │ Queries and processes
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Sources                               │
│   • Schema.org websites                                         │
│   • Vector databases (Milvus, Elasticsearch, OpenSearch)        │
│   • Custom retrieval providers                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. ChatGPT Desktop App
- User interface and AppSDK client
- Calls `nlweb-list` tool via MCP
- Renders results using interactive widget

### 2. NLWeb MCP Server
- **Location**: `/openai-apps-sdk-integration/nlweb_server_node/`
- **Protocol**: MCP over HTTP/SSE or stdio
- Registers `nlweb-list` tool with ChatGPT
- Provides UI widget for search results
- Forwards queries to AppSDK adapter

See [NLWeb Server README](../openai-apps-sdk-integration/nlweb_server_node/README.md) for details.

### 3. NLWeb AppSDK Adapter
- **Location**: `AskAgent/python/webserver/appsdk_adapter_server.py`
- **Responsibilities**:
  - Proxies requests to NLWeb core `/ask` endpoint
  - Transforms NLWeb response to AppSDK format
  - Handles streaming and non-streaming responses
  - Filters empty messages
  - Wraps responses in AppSDK envelope

**Response Format**:
```json
{
  "structuredContent": {
    "query": "...",
    "results": [...],
    "messages": [...],
    "metadata": {...}
  },
  "content": [
    {"type": "text", "text": "..."}
  ]
}
```

### 4. NLWeb Core Server
- Processes natural language queries
- Retrieves data from configured sources
- Returns structured results

### 5. Data Sources
- Schema.org-marked websites
- Vector databases (Milvus, Elasticsearch, OpenSearch)
- Custom retrieval providers

## Data Flow

### Query Flow

1. **User → ChatGPT**: "Find spicy snacks on seriouseats site"
2. **ChatGPT → MCP Server**: MCP tool call with parameters
   ```json
   {
     "name": "nlweb-list",
     "arguments": {
       "query": "spicy snacks",
       "site": "seriouseats",
       "mode": "list"
     }
   }
   ```
3. **MCP Server → AppSDK Adapter**: HTTP GET to `/ask`
   ```
   GET /ask?query=spicy%20snacks&site=seriouseats&mode=list&streaming=false
   ```
4. **AppSDK Adapter → NLWeb Core**: Proxied request
5. **NLWeb Core**: 
   - Processes query
   - Retrieves data from sources
   - Generates visualizations
   - Returns results
6. **AppSDK Adapter**: Transforms to AppSDK format
7. **MCP Server**: Adds UI template metadata
8. **ChatGPT**: Renders visualizations using widget

### Response Flow

**NLWeb Core Output**:
```json
{
  "messages": [
    {
      "message_type": "result",
      "content": [
        {
          "@type": "Recipe",
          "name": "Spicy Buffalo Cauliflower Wings",
          "description": "Crispy baked cauliflower with spicy buffalo sauce...",
          "image": "https://example.com/image.jpg",
          "url": "https://seriouseats.com/spicy-buffalo-wings"
        }
      ]
    }
  ]
}
```

**AppSDK Adapter Output**:
```json
{
  "structuredContent": {
    "query": "spicy snacks",
    "results": [
      {
        "name": "Spicy Buffalo Cauliflower Wings",
        "description": "Crispy baked cauliflower with spicy buffalo sauce...",
        "schema_object": {
          "@type": "Recipe",
          "image": "https://example.com/image.jpg",
          "url": "https://seriouseats.com/spicy-buffalo-wings"
        },
        "score": 0.92
      }
    ],
    "messages": [...],
    "metadata": {...}
  },
  "content": [
    {"type": "text", "text": "Found 5 results for 'spicy snacks' on seriouseats.com"}
  ]
}
```

**MCP Server Output**:
```json
{
  "content": [
    {"type": "text", "text": "Found 5 results for 'spicy snacks'."}
  ],
  "structuredContent": {
    "query": "spicy snacks",
    "results": [...],
    "messages": [...],
    "metadata": {...}
  },
  "_meta": {
    "openai/outputTemplate": "ui://widget/nlweb-list.html",
    "openai/toolInvocation/invoking": "Searching NLWeb",
    "openai/toolInvocation/invoked": "Found results",
    "openai/widgetAccessible": true,
    "openai/resultCanProduceWidget": true,
    "openai.com/widget": {
      "type": "resource",
      "resource": {
        "uri": "ui://widget/nlweb-list.html",
        "mimeType": "text/html+skybridge",
        "text": "<div id=\"nlweb-list-root\"></div>..."
      }
    }
  }
}
```

## Setup & Usage

**See [Main README](../openai-apps-sdk-integration/README.md) for complete setup instructions.**

Quick summary:
1. Build and serve widget assets
2. Start MCP server (HTTP/SSE or stdio)
3. Configure ChatGPT or Claude Desktop
4. Test with queries like "Find spicy snacks on seriouseats.com"

## UI Widget

The MCP server includes an interactive React-based widget that displays NLWeb search results with:
- Images, ratings, and expandable descriptions
- Schema.org support (Products, Places, Articles)
- Responsive design with Tailwind CSS

**See [Main README](../openai-apps-sdk-integration/README.md) for widget details.**

## Configuration

Key environment variables:
- `NLWEB_APPSDK_BASE_URL`: NLWeb AppSDK adapter URL (default: `https://localhost:8100`)
- `REQUEST_TIMEOUT`: Request timeout in ms (default: `30000`)

**See [Main README](../openai-apps-sdk-integration/README.md) for complete configuration details.**

## Deployment

**See [DEPLOYMENT.md](../openai-apps-sdk-integration/DEPLOYMENT.md) for complete production deployment guide.**

Production deployment involves:
1. Upload widget assets to CDN (CloudFlare, AWS S3, Azure Blob)
2. Deploy MCP server to Azure App Service, AWS, or run locally
3. Update server to point to CDN URLs
4. Configure ChatGPT with production MCP endpoint

## Testing & Troubleshooting

**See [NLWeb Server README](../openai-apps-sdk-integration/nlweb_server_node/README.md) for testing instructions and troubleshooting tips.**

Quick test commands:
```bash
# Test MCP server, make sure MCP server has started before testing
cd openai-apps-sdk-integration/nlweb_server_node
npm run test

# Test AppSDK adapter hosted endpoint or localhost:8100
curl "https://localhost:8100/ask?query=test&mode=list&streaming=false"
```

## Related Documentation

### MCP Server
- [Main README](../openai-apps-sdk-integration/README.md) - Setup and usage
- [Server README](../openai-apps-sdk-integration/nlweb_server_node/README.md) - Testing and troubleshooting
- [Deployment Guide](../openai-apps-sdk-integration/DEPLOYMENT.md) - Production deployment

### NLWeb Core
- [NLWeb REST API](nlweb-rest-api.md)
- [AppSDK Adapter](nlweb-appsdk-adapter.md)
- [Control Flow](nlweb-control-flow.md)
- [Life of a Chat Query](life-of-a-chat-query.md)
