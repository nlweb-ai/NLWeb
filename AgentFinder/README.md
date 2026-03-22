# WHO Standalone Handler

A high-performance, modular service for finding the most relevant agents to answer user queries. This standalone implementation supports both REST and MCP (Model Context Protocol) interfaces with swappable search and LLM backends.



## Architecture

The system is composed of 4 modular Python files:

- **`agent_finder.py`**: Web server with REST and MCP endpoints
- **`who_handler.py`**: Core orchestration logic with caching
- **`search_backend.py`**: Swappable search interface (Azure Search, Elasticsearch, etc.)
- **`llm_backend.py`**: Swappable LLM interface (Azure OpenAI, OpenAI, Anthropic, etc.)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
# Search Backend Configuration
export SEARCH_PROVIDER=azure  # Options: azure, elasticsearch, qdrant
export SEARCH_ENDPOINT="https://your-search.search.windows.net"
export SEARCH_API_KEY="your-search-api-key"
export SEARCH_INDEX="nlweb_sites"

# LLM Backend Configuration
export LLM_PROVIDER=azure_openai  # Options: azure_openai, openai, anthropic
export LLM_ENDPOINT="https://your-openai.openai.azure.com"
export LLM_API_KEY="your-llm-api-key"
export LLM_MODEL="gpt-4"
export LLM_EMBEDDING_MODEL="text-embedding-3-large"
export LLM_MAX_CONCURRENT=50

# Optional: Server Configuration
export WHO_SERVER_PORT=8080
export WHO_SERVER_HOST=0.0.0.0

# Optional: WHO Handler Settings
export WHO_SCORE_THRESHOLD=70
export WHO_MAX_RESULTS=10
export WHO_SEARCH_TOP_K=50
export WHO_CACHE_TTL=3600
```

### 3. Run the Server

```bash
python agent_finder.py
```

The server will start on `http://localhost:8080` by default.

## API Usage

### REST Endpoint

**Request:**
```bash
curl -X POST http://localhost:8080/who \
  -H "Content-Type: application/json" \
  -d '{"query": "where can I buy running shoes?"}'
```

**Response:**
```json
{
  "results": [
    {
      "name": "Nike.com",
      "url": "https://www.nike.com",
      "score": 95,
      "description": "Official Nike store with extensive running shoe collection"
    },
    {
      "name": "Adidas.com",
      "url": "https://www.adidas.com",
      "score": 92,
      "description": "Adidas official store featuring running footwear"
    }
  ],
  "query": "where can I buy running shoes?"
}
```

### MCP Endpoint

The MCP endpoint follows the Model Context Protocol specification for tool-based interactions.

**Initialize:**
```bash
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {"protocolVersion": "2024-11-05"},
    "id": 1
  }'
```

**List Tools:**
```bash
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2
  }'
```

**Call WHO Tool:**
```bash
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "who",
      "arguments": {"query": "where can I buy running shoes?"}
    },
    "id": 3
  }'
```

### Admin Endpoints

**Health Check:**
```bash
curl http://localhost:8080/health
```

**Statistics:**
```bash
curl http://localhost:8080/stats
```

**Clear Caches:**
```bash
curl -X POST http://localhost:8080/clear-cache
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| **Search Backend** | | |
| `SEARCH_PROVIDER` | Search backend provider | `azure` |
| `SEARCH_ENDPOINT` | Search service endpoint | Required |
| `SEARCH_API_KEY` | Search service API key | Required |
| `SEARCH_INDEX` | Search index name | `nlweb_sites` |
| **LLM Backend** | | |
| `LLM_PROVIDER` | LLM provider | `azure_openai` |
| `LLM_ENDPOINT` | LLM service endpoint | Required |
| `LLM_API_KEY` | LLM service API key | Required |
| `LLM_MODEL` | LLM model name | `gpt-4` |
| `LLM_EMBEDDING_MODEL` | Embedding model name | `text-embedding-3-large` |
| `LLM_MAX_CONCURRENT` | Max concurrent LLM calls | `50` |
| **Server** | | |
| `WHO_SERVER_PORT` | Server port | `8080` |
| `WHO_SERVER_HOST` | Server host | `0.0.0.0` |
| **WHO Handler** | | |
| `WHO_SCORE_THRESHOLD` | Min score to include site | `70` |
| `WHO_MAX_RESULTS` | Max results to return | `10` |
| `WHO_SEARCH_TOP_K` | Sites to retrieve from search | `50` |
| `WHO_CACHE_TTL` | Cache TTL in seconds | `3600` |
| `WHO_MAX_CACHE_ENTRIES` | Max search cache entries | `10000` |
| `WHO_RANKING_CACHE_ENTRIES` | Max ranking cache entries | `100000` |

## Adding New Backends

### Adding a New Search Backend

Edit `search_backend.py` and implement the `SearchBackend` interface:

```python
class MySearchBackend(SearchBackend):
    async def initialize(self):
        # Initialize your client
        pass

    async def search(self, query: str, vector: List[float], top_k: int = 30) -> List[Dict[str, Any]]:
        # Return list of {"url", "json_ld", "name", "site"}
        pass

    async def close(self):
        # Cleanup connections
        pass
```

Then update the factory function:
```python
def get_search_backend() -> SearchBackend:
    if SEARCH_CONFIG["provider"] == "mysearch":
        return MySearchBackend()
```

### Adding a New LLM Backend

Edit `llm_backend.py` and implement the `LLMBackend` interface:

```python
class MyLLMBackend(LLMBackend):
    async def initialize(self):
        # Initialize your client
        pass

    async def get_embedding(self, text: str) -> List[float]:
        # Return embedding vector
        pass

    async def rank_site(self, query: str, site_json: str) -> Dict[str, Any]:
        # Return {"score": 0-100, "description": "..."}
        pass

    async def close(self):
        # Cleanup
        pass
```

## Performance Optimization

### Caching Strategy

The system uses three levels of caching:

1. **Embedding Cache**: Never expires, embeddings are stable
2. **Search Cache**: TTL-based, caches query → search results
3. **Ranking Cache**: TTL-based, caches (query, site) → ranking

### Concurrency Control

- **Search**: Up to 50 concurrent connections to search backend
- **LLM**: Configurable concurrent calls (default 25)
- **Request Handling**: Fully async, supports 50+ concurrent requests

### Memory Usage

With default settings:
- Base: ~200MB
- Full caches: 2-4GB
- Can scale to 16GB+ with increased cache sizes

## Monitoring

The `/stats` endpoint provides real-time metrics:

```json
{
  "queries_processed": 1234,
  "cache_hits": 890,
  "cache_misses": 344,
  "total_sites_ranked": 10280,
  "embedding_cache_size": 567,
  "search_cache_size": 234,
  "ranking_cache_size": 8901
}
```

## Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

CMD ["python", "server.py"]
```

Build and run:

```bash
docker build -t who-handler .
docker run -p 8080:8080 --env-file .env who-handler
```

## Production Deployment

### Systemd Service

Create `/etc/systemd/system/who-handler.service`:

```ini
[Unit]
Description=WHO Handler Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/who-handler
EnvironmentFile=/opt/who-handler/.env
ExecStart=/usr/bin/python3 /opt/who-handler/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Nginx Proxy

```nginx
server {
    listen 80;
    server_name who.example.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
```

## Troubleshooting

### Common Issues

1. **"No search results found"**
   - Check search index name and credentials
   - Verify the index contains data

2. **"Embedding error"**
   - Verify LLM endpoint and API key
   - Check embedding model name is correct

3. **Slow responses**
   - Check `LLM_MAX_CONCURRENT` setting
   - Monitor `/stats` for cache effectiveness
   - Consider increasing cache sizes

4. **High memory usage**
   - Reduce cache sizes via environment variables
   - Monitor `/stats` endpoint for cache sizes

## License

This is a standalone implementation for the WHO handler functionality is made available under the MIT License

## Support

For issues or questions, please refer to the main NLWeb project documentation.
