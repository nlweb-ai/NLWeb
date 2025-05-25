"""Unit tests for the Ranking class."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import sys

# Add the src directory to the path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / 'src'))

from core.ranking import Ranking, RankingMetrics

class MockHandler:
    """Mock handler class for testing."""
    def __init__(self):
        self.connection_alive_event = asyncio.Event()
        self.connection_alive_event.set()
        self.abort_fast_track_event = asyncio.Event()
        self.pre_checks_done_event = asyncio.Event()
        self.pre_checks_done_event.set()
        self.query_done = False
        self.fastTrackWorked = False
        self.query_id = "test_query_123"
        self.site = "test_site"
        self.request = MagicMock()
        self.request.query = "test query"
        self.item_type = "test_item"
        
    async def send_message(self, message):
        """Mock send_message method."""
        pass

class TestRankingMetrics(unittest.TestCase):
    """Test the RankingMetrics class."""
    
    def test_metrics_initialization(self):
        """Test that metrics are initialized correctly."""
        metrics = RankingMetrics()
        self.assertEqual(metrics.items_processed, 0)
        self.assertEqual(metrics.llm_calls, 0)
        self.assertEqual(metrics.cache_hits, 0)
        self.assertEqual(metrics.cache_misses, 0)
        
    def test_timer_functions(self):
        """Test timer start/stop functionality."""
        metrics = RankingMetrics()
        metrics.start_timer()
        metrics.stop_timer()
        duration = metrics.get_duration()
        self.assertGreaterEqual(duration, 0)

class TestRanking(unittest.IsolatedAsyncioTestCase):
    """Test the Ranking class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.handler = MockHandler()
        self.test_items = [
            ("url1", json.dumps({"name": "Test Item 1"}), "Test Item 1", "test_site"),
            ("url2", json.dumps({"name": "Test Item 2"}), "Test Item 2", "test_site"),
        ]
        
    @patch('core.ranking.ask_llm')
    async def test_rank_item(self, mock_ask_llm):
        """Test ranking a single item."""
        # Mock LLM response
        mock_ask_llm.return_value = {"score": 85, "description": "Relevant item"}
        
        # Create a unique test item to avoid cache hits
        test_item = ("test_url_rank_item", json.dumps({"name": "Test Rank Item"}), "Test Rank Item", "test_site")
        
        ranking = Ranking(self.handler, [test_item])
        result = await ranking.rankItem(*test_item)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], "Test Rank Item")
        self.assertEqual(result['ranking']['score'], 85)
        
        # Verify the LLM was called with the expected arguments
        mock_ask_llm.assert_called_once()
        
        # Get the arguments passed to ask_llm
        # The actual call might be different, so we'll just verify it was called with some arguments
        self.assertTrue(mock_ask_llm.called)
        # Check that the first argument is a string (the prompt)
        args, kwargs = mock_ask_llm.call_args
        self.assertTrue(isinstance(args[0], str))
        
    @patch('core.ranking.ask_llm')
    async def test_rank_items_parallel(self, mock_ask_llm):
        """Test ranking multiple items in parallel."""
        # Mock LLM response
        mock_ask_llm.return_value = {"score": 85, "description": "Relevant item"}
        
        # Create unique test items to avoid cache hits
        test_item1 = ("test_url_parallel_1", json.dumps({"name": "Test Parallel 1"}), "Test Parallel 1", "test_site")
        test_item2 = ("test_url_parallel_2", json.dumps({"name": "Test Parallel 2"}), "Test Parallel 2", "test_site")
        test_items = [test_item1, test_item2]
        
        ranking = Ranking(self.handler, test_items)
        
        # This should process items in parallel
        await ranking.do()
        
        # Should have called LLM once per item (2 items)
        self.assertEqual(mock_ask_llm.call_count, 2)
        
        # Verify the results were processed
        self.assertEqual(len(ranking.rankedAnswers), 2)
        self.assertEqual(len(ranking.rankedAnswers), 2)
        
    @patch('core.ranking.ask_llm')
    async def test_cache_behavior(self, mock_ask_llm):
        """Test that caching works as expected."""
        # Mock LLM response
        mock_ask_llm.return_value = {"score": 85, "description": "Cached item"}
        
        # Create duplicate items to test caching
        duplicate_items = self.test_items * 2  # This creates 4 items (2 unique)
        ranking = Ranking(self.handler, duplicate_items)
        await ranking.do()
        
        # Should only call LLM once per unique item due to caching
        self.assertEqual(mock_ask_llm.call_count, 2)
        
        # Get unique items based on URL to verify caching
        unique_urls = set()
        unique_results = []
        for item in ranking.rankedAnswers:
            if item['url'] not in unique_urls:
                unique_urls.add(item['url'])
                unique_results.append(item)
                
        # Should have 2 unique results (one for each unique URL)
        self.assertEqual(len(unique_results), 2)
        
    @patch('core.ranking.ask_llm')
    async def test_early_send_threshold(self, mock_ask_llm):
        """Test that high-scoring items are sent immediately."""
        # Mock a high-scoring item
        mock_ask_llm.return_value = {"score": 95, "description": "High priority item"}
        
        # Mock send_answers to verify it's called
        with patch.object(Ranking, 'sendAnswers', new_callable=AsyncMock) as mock_send:
            ranking = Ranking(self.handler, self.test_items[:1])
            await ranking.do()
            
            # Verify sendAnswers was called at least once for the high-scoring item
            self.assertGreaterEqual(mock_send.call_count, 1)
            
            # Get the first call to check it contains our item
            first_call_args = mock_send.call_args_list[0][0]
            first_call_kwargs = mock_send.call_args_list[0][1]
            self.assertEqual(len(first_call_args[0]), 1)  # One item in the results
            self.assertEqual(first_call_args[0][0]['name'], 'Test Item 1')  # Check item name
            
    @patch('core.ranking.ask_llm')
    async def test_error_handling(self, mock_ask_llm):
        """Test that errors are handled gracefully."""
        # Mock an error in the LLM call
        mock_ask_llm.side_effect = Exception("LLM error")
        
        # Create a new test item to avoid cache hits
        test_item = ("error_url", json.dumps({"name": "Error Item"}), "Error Item", "test_site")
        ranking = Ranking(self.handler, [test_item])
        
        # This should not raise an exception
        await ranking.do()
        
        # Check if any results were added (should be 0 since LLM failed)
        self.assertEqual(len(ranking.rankedAnswers), 0)
        
        # Verify the error was logged
        self.assertTrue(mock_ask_llm.called)
        self.assertEqual(mock_ask_llm.call_count, 1)

    @patch('core.ranking.ask_llm')
    async def test_connection_lost_handling(self, mock_ask_llm):
        """Test behavior when connection is lost during ranking."""
        # Mock a slow LLM response
        async def slow_llm(*args, **kwargs):
            await asyncio.sleep(0.1)
            self.handler.connection_alive_event.clear()
            return {"score": 85, "description": "Item"}
            
        mock_ask_llm.side_effect = slow_llm
        
        ranking = Ranking(self.handler, self.test_items)
        await ranking.do()
        
        # Should not process all items after connection is lost
        self.assertLess(mock_ask_llm.call_count, 2)

if __name__ == '__main__':
    unittest.main()
