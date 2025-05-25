"""Pytest configuration and fixtures for tests."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

# This makes event loop available in async tests
@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_handler():
    """Create a mock handler for testing."""
    handler = MagicMock()
    handler.connection_alive_event = asyncio.Event()
    handler.connection_alive_event.set()
    handler.abort_fast_track_event = asyncio.Event()
    handler.pre_checks_done_event = asyncio.Event()
    handler.pre_checks_done_event.set()
    handler.query_done = False
    handler.fastTrackWorked = False
    handler.query_id = "test_query_123"
    handler.site = "test_site"
    handler.request = MagicMock()
    handler.request.query = "test query"
    handler.send_message = AsyncMock()
    return handler

@pytest.fixture
def test_items():
    """Create test items for ranking."""
    return [
        ("url1", '{"name": "Test Item 1"}', "Test Item 1", "test_site"),
        ("url2", '{"name": "Test Item 2"}', "Test Item 2", "test_site"),
    ]
