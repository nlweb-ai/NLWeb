# Next Steps - Multi-Participant Chat System

## Immediate Priority: Fix Failing Tests

### 1. Fix Validation Errors (2 tests failing)
**Issue**: Server returns 500 instead of 400 for invalid data

**Tests to fix**:
- `test_invalid_participant_data` - Missing user_id causes KeyError
- `test_missing_required_fields` - Missing title validation

**Solution**: Add proper validation in `/code/python/webserver/routes/chat.py`:
```python
# Check for required participant fields
for p in participants:
    if 'user_id' not in p:
        return web.json_response({'error': 'user_id required'}, status=400)
```

### 2. Fix Endpoint Implementation (3 tests failing)
**Tests to fix**:
- `test_join_existing_conversation` - Join endpoint needs work
- `test_get_conversation_details` - Get endpoint needs work  
- `test_list_all_conversations_for_user` - List endpoint needs work

**Check**:
- Are these endpoints returning correct data format?
- Do they handle the authenticated user properly?
- Are they using the storage layer correctly?

## How to Resume Next Session

1. **Start with validation fixes** in `create_conversation_handler`:
   ```python
   # Add validation for participant data
   try:
       for p in participants:
           if 'user_id' not in p or 'name' not in p:
               return web.json_response({'error': 'Missing required fields'}, status=400)
   except Exception as e:
       return web.json_response({'error': str(e)}, status=400)
   ```

2. **Run the failing tests individually** to debug:
   ```bash
   python -m pytest tests/integration/test_rest_api.py::TestConversationCreation::test_invalid_participant_data -xvs
   ```

3. **Use the test runner script** to see server output:
   ```python
   # Already created at /tmp/run_server_with_tests.py
   # Shows server errors alongside test failures
   ```

## Current Status
- ✅ 10/15 integration tests passing (66.7%)
- ✅ Server runs properly with test infrastructure
- ✅ Test format matches server expectations
- ❌ Need to fix validation and endpoint bugs

## Success Metrics
- All 15 integration tests should pass
- No 500 errors - only proper 400/404 responses
- Then run full 249 test suite