# Running Tests with Real Server

## Step 1: Start the Server

In one terminal, start the server:

```bash
cd /Users/rvguha/code/conv
python code/python/webserver/aiohttp_server.py
```

The server will start on `http://localhost:8000` (or port 8080 if configured).

## Step 2: Run Tests

In another terminal, run the tests:

```bash
# Run all integration tests
python -m pytest tests/integration/ -v

# Run specific test
python -m pytest tests/integration/test_rest_api.py::TestJoinLeaveOperations::test_join_existing_conversation -xvs

# Run all tests
python -m pytest tests/ -v
```

## Key Points

1. **The tests already use real endpoints** - We've updated the critical tests to use:
   - `auth_client` fixture - HTTP client with auth headers
   - `test_server` fixture - Starts a test server instance
   - Real API calls to implemented endpoints

2. **Implemented Endpoints** that tests can use:
   - `POST /chat/create` - Create conversation
   - `POST /chat/{id}/join` - Join conversation ✅ (NEW)
   - `DELETE /chat/{id}/leave` - Leave conversation ✅ (NEW)
   - `GET /chat/conversations/{id}` - Get conversation details ✅ (NEW)
   - `GET /chat/my-conversations` - List user's conversations
   - `GET /chat/ws/{id}` - WebSocket connection
   - `GET /health/chat` - Health check

3. **Test Configuration** (`tests/config_test.yaml`):
   - Uses memory storage backend
   - Disabled authentication for easier testing
   - Lower limits for testing edge cases
   - Faster timeouts

## Running Tests Without Test Fixtures

If you want to run tests against your manually started server (not using test fixtures):

1. Start your server on port 8000
2. Set environment variable to use external server:
   ```bash
   export TEST_SERVER_URL="http://localhost:8000"
   ```
3. Run tests that use the external server

## Example Test Pattern

Here's how the tests work with real endpoints:

```python
async def test_join_existing_conversation(self, auth_client, test_conversation):
    """Test joining an existing conversation."""
    conversation_id = test_conversation['conversation_id']
    
    # This makes a REAL HTTP request to the server
    response = await auth_client.post(
        f"/chat/{conversation_id}/join",
        json={
            "participant": {
                "participantId": "new_user_123",
                "displayName": "New User",
                "type": "human"
            }
        }
    )
    
    # Verify real response from server
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
```

## Debugging Connection Issues

If tests can't connect:

1. Check server is running: `curl http://localhost:8000/health/chat`
2. Check port in `tests/config_test.yaml` matches your server
3. Check no firewall blocking localhost connections
4. Try using `127.0.0.1` instead of `localhost` if needed

## Test Results

When we run with the real server:
- ✅ Join conversation test - PASSES
- ✅ Leave conversation test - PASSES  
- ✅ Get conversation test - PASSES
- ✅ WebSocket broadcast tests - ALL PASS

The failing tests are ones that haven't been updated to use real endpoints yet.