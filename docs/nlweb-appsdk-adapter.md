# NLWeb → AppSDK Adapter Service

This document describes the lightweight proxy that converts NLWeb’s `/ask` responses into the `{ structuredContent, content }` envelope expected by OpenAI’s AppSDK without changing the core NLWeb server.

---

## Why a Separate Adapter?

- **Preserve existing clients** – the NLWeb UI and tooling can keep calling `http://<nlweb-host>:8000/ask` and receive the legacy message list.
- **Expose AppSDK-compatible output** – AppSDK or any new consumer can call the adapter on port `8100` and get the transformed payload.
- **Isolation** – transformation logic lives in a tiny service (`AskAgent/python/webserver/appsdk_adapter_server.py`) that you can deploy, scale, or retire independently.

---

## Architecture Overview

```text
AppSDK client ──► Adapter (/ask) ──► NLWeb (/ask) ──► Adapter transforms ──► AppSDK payload
                      ↑                                           │
                      └────────────── Legacy NLWeb UI ────────────┘ (calls NLWeb directly)
```

Key behaviors:

1. Adapter forwards the request to NLWeb, preserving `streaming=true` by default (so SSE/NDJSON flows are supported) and aggregating chunks before responding.
2. It collects the legacy NLWeb message list (or result dict).
3. Messages with `content` of `null` or `""` are filtered out.
4. The helper function `convert_messages_to_appsdk_response` builds:
   ```json
   {
     "structuredContent": { "messages": [...], "results": [...], ... },
     "content": [{ "type": "text", "text": "..." }]
   }
   ```
5. Legacy NLWeb result blocks are merged into `structuredContent.results`, so the widget always sees the full item list even when the message stream is empty.
6. The original payload is preserved under `structuredContent.legacyResponse` for debugging.

---

## Running Locally

1. **Start the NLWeb server (unchanged):**
   ```bash
   cd /path/to/NLWeb/AskAgent/python
   python -m webserver.aiohttp_server
   ```

2. **Launch the adapter in a second shell:**
   ```bash
   cd /path/to/NLWeb/AskAgent/python
   APPSDK_ADAPTER_PORT=8100 \
   NLWEB_BASE_URL=http://localhost:8000 \
   python -m webserver.appsdk_adapter_server
   ```

3. **Query through the adapter:**
   ```bash
   curl -s "http://localhost:8100/ask?query=spicy%20crunchy%20snacks&mode=list" | jq
   ```

   Output now matches the AppSDK contract while the NLWeb instance continues to serve the legacy schema on port `8000`.

---

## Mock / Integration Testing

### 1. CLI Harness

```bash
python -m testing.mock_appsdk_tool \
  --query "spicy crunchy snacks" \
  --output ../static/test-wedge-ui/sample_output.json
```

- Hits the adapter (default `http://localhost:8100`) and prints AppSDK-formatted JSON.  
- Non-streaming by default; add `--streaming` to exercise the SSE path.  
- Automatically merges any legacy NLWeb `result` messages into `structuredContent.results`.

### 2. Widget Harness

- Serve `static/` (e.g., `cd static && python -m http.server 8200`).  
- Visit `http://localhost:8200/test-wedge-ui/widget-test.html`.  
- Click **Load Latest output.json** (served over HTTP) or pick a captured JSON file.  
- The harness posts the payload into `static/test-wedge-ui/nlweb_widget.html`, which renders:
  * Clickable item names (when URLs exist)  
  * Descriptions  
  * The NLWeb-provided HTML block with deduped external scripts


### 4. Suggested Testing Workflow

1. Regenerate payload:  
   `python -m testing.mock_appsdk_tool --query "..." --output ../static/test-wedge-ui/sample_output.json`
2. Refresh `widget-test.html` to visually inspect the results.  

---

## Configuration

| Environment Variable      | Default              | Description                                                                    |
| ------------------------- | -------------------- | ------------------------------------------------------------------------------ |
| `NLWEB_BASE_URL`          | `http://localhost:8000` | Base URL of the upstream NLWeb server (no trailing slash).                    |
| `APPSDK_ADAPTER_HOST`     | `0.0.0.0`            | Host/interface the adapter binds to.                                           |
| `APPSDK_ADAPTER_PORT`     | `8100`               | Port for the adapter server.                                                   |

The adapter uses a shared `aiohttp.ClientSession` with a 60s timeout. HTTP headers are forwarded except for `Host` and `Content-Length`.

---

## Error Handling & Limitations

- **Streaming**: SSE/NDJSON responses are buffered, converted, and returned as a single AppSDK payload. If the stream terminates early, the adapter appends a warning message while still surfacing any partial results.
- **Non-JSON upstream responses**: If NLWeb returns non-JSON, the adapter returns a `502` with the raw text snippet.
- **Status propagation**: Upstream HTTP codes are preserved; the body is wrapped via `build_appsdk_error_response(...)`.

---

## Testing

Unit tests covering the adapter helpers live in `AskAgent/python/tests/test_appsdk_adapter.py`. Run them (after installing pytest) with:

```bash
python -m pytest AskAgent/python/tests/test_appsdk_adapter.py
```

This verifies the filtering logic and error payload formatting used by the adapter service.

---

## Next Steps

- If you need incremental delivery to clients, refactor the adapter to stream AppSDK-compatible chunks instead of buffering the entire response.
- Harden authentication/rate limiting if exposing the adapter publicly.
- Deploy the adapter alongside NLWeb (e.g., as a sidecar container) and point AppSDK tools to the adapter’s `/ask`.
