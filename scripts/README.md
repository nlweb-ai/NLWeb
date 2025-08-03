# Test Scripts

This directory contains utility scripts for testing the NLWeb conversation system.

## run_tests_with_server.py

A persistent test runner that manages a background server for integration testing.

### Features
- Automatically starts server in background thread
- Kills any existing server on port 8000
- Shows server output during test execution
- Supports different test categories
- Can keep server running after tests complete

### Usage

```bash
# Run all tests
python scripts/run_tests_with_server.py

# Run only integration tests
python scripts/run_tests_with_server.py integration

# Run only unit tests
python scripts/run_tests_with_server.py unit

# Run specific test file
python scripts/run_tests_with_server.py tests/integration/test_rest_api.py

# Keep server running after tests
python scripts/run_tests_with_server.py integration --keep-server

# Use existing server (don't start a new one)
python scripts/run_tests_with_server.py integration --no-server
```

### Test Categories
- `all` - Run entire test suite
- `integration` - Integration tests (REST API, WebSocket)
- `unit` - Unit tests
- `e2e` - End-to-end tests
- `websocket` - WebSocket tests only
- `rest` - REST API tests only
- `performance` - Performance tests
- `security` - Security tests
- `reliability` - Reliability tests

### Examples

```bash
# Quick integration test run
python scripts/run_tests_with_server.py integration

# Debug a specific failing test
python scripts/run_tests_with_server.py tests/integration/test_websocket.py::TestWebSocketConnectionLifecycle::test_dead_connection_detection

# Run tests while keeping server for manual testing
python scripts/run_tests_with_server.py integration --keep-server
```

### Requirements
- Python 3.8+
- All project dependencies installed
- Port 8000 available