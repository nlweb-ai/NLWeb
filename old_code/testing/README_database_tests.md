# Database Operations Tests

This directory contains tests for verifying database operations including upload, search, and delete functionality.

## Test Files

### test_database_operations.py
Comprehensive test that:
- Tests upload/search/delete operations on ALL enabled database endpoints
- Downloads and parses an NPR podcast RSS feed
- Generates embeddings for podcast episodes
- Uploads documents to each endpoint
- Searches for "Tom Papa" to verify upload
- Deletes the test data
- Tests production search on nlweb_west endpoint

### test_database_operations_simple.py
Simplified test that:
- Tests only the configured write_endpoint (to avoid overwhelming all endpoints)
- Uses fewer documents (5 episodes instead of 10)
- Tests production search on nlweb_west endpoint

## Running the Tests

```bash
# Run the simple test (recommended for regular testing)
python code/testing/test_database_operations_simple.py

# Run the comprehensive test (use sparingly)
python code/testing/test_database_operations.py
```

## Test Data

- **RSS Feed**: https://feeds.npr.org/344098539/podcast.xml (NPR's Bullseye podcast)
- **Test Site**: "test_npr_podcast" (temporary site created and deleted during test)
- **Test Query**: "Tom Papa" (should find results in the podcast feed)
- **Production Query**: "spicy crunchy snacks" (tests against existing nlweb_west data)

## Expected Results

### Write Endpoint Test
1. Downloads RSS feed successfully
2. Parses podcast episodes
3. Generates embeddings
4. Uploads documents to write endpoint
5. Finds results for "Tom Papa"
6. Successfully deletes all test data

### Production Search Test
1. Finds results for "spicy crunchy snacks" using search()
2. Finds results for "spicy crunchy snacks" using search_all_sites()

## Troubleshooting

If tests fail:
1. Check that CONFIG.write_endpoint is properly configured
2. Verify that nlweb_west endpoint is enabled and accessible
3. Ensure embedding service is available
4. Check network connectivity to download RSS feed

## Clean Up

The tests automatically clean up after themselves by deleting the test site. If a test fails mid-execution, you may need to manually delete the "test_npr_podcast" site from the database.