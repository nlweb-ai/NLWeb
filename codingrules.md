# NLWeb Coding Rules and Conventions

## Code Structure

### Python Backend Structure

#### Directory Organization
```
code/python/
├── core/                  # Core system functionality
│   ├── query_analysis/    # Query understanding modules
│   ├── baseHandler.py     # Base handler class
│   ├── config.py          # Configuration management
│   ├── retriever.py       # Vector DB interface
│   └── ...
├── methods/               # Specialized query handlers
│   ├── generate_answer.py # RAG generation
│   ├── compare_items.py   # Comparison logic
│   └── ...
├── data_loading/          # Data ingestion utilities
├── llm_providers/         # LLM provider wrappers
├── webserver/             # HTTP server
└── llm_batch_handler.py   # Batch LLM processing
```

#### Class Organization
- **Single Responsibility**: Each class handles one primary concern
- **Base Classes**: Abstract base classes define interfaces (e.g., `BaseHandler`)
- **Inheritance**: Specialized handlers inherit from base classes
- **Composition**: Complex functionality built through composition

### JavaScript Frontend Structure

#### Module Organization
```
static/
├── fp-chat-interface.js   # Modern chat interface (main)
├── managed-event-source.js # SSE handling
├── conversation-manager.js # Conversation state
├── json-renderer.js       # Content rendering
├── type-renderers.js      # Type-specific renderers
├── oauth-login.js         # Authentication
└── utils.js              # Shared utilities
```

#### Class Structure
- **ES6 Classes**: All major components use ES6 class syntax
- **Module Pattern**: Each file exports specific classes/functions
- **Event-Driven**: Components communicate via events
- **Separation of Concerns**: UI, state, and API logic separated

## Naming Conventions

### Python Naming

#### Files and Modules
- **snake_case**: `base_handler.py`, `query_analysis.py`
- **Descriptive names**: File name matches primary class/function

#### Classes
- **PascalCase**: `NLWebHandler`, `VectorDBClient`, `AppConfig`
- **Descriptive**: Class name indicates purpose
- **Suffix patterns**:
  - `Handler` - Request handlers
  - `Client` - External service clients
  - `Manager` - State/resource managers

#### Functions and Methods
- **snake_case**: `process_query()`, `get_embeddings()`
- **Verb prefixes**: `get_`, `set_`, `process_`, `handle_`
- **Async prefix**: `async_` for async functions
- **Private prefix**: `_` for internal methods

#### Variables
- **snake_case**: `query_text`, `result_count`
- **Constants**: `UPPERCASE_WITH_UNDERSCORES`
- **Configuration**: Loaded into class attributes

### JavaScript Naming

#### Files
- **kebab-case**: `chat-interface.js`, `managed-event-source.js`
- **Descriptive**: File name indicates component/module

#### Classes
- **PascalCase**: `ModernChatInterface`, `ConversationManager`
- **Descriptive**: Clear indication of purpose

#### Methods and Functions
- **camelCase**: `sendMessage()`, `handleStreamingData()`
- **Event handlers**: `on` prefix (e.g., `onMessage`)
- **Private methods**: `_` prefix (e.g., `_processData`)

#### Variables
- **camelCase**: `currentQuery`, `isStreaming`
- **Constants**: `UPPERCASE_WITH_UNDERSCORES`
- **DOM elements**: Descriptive names (e.g., `sendButton`, `messagesContainer`)

## Edge-Case Rules

### Query Processing
1. **Empty Queries**: Return helpful message, don't process
2. **Malformed JSON**: Log error, return error message to user
3. **Missing Parameters**: Use sensible defaults
4. **Large Queries**: Truncate at reasonable length (e.g., 1000 chars)
5. **Invalid Sites**: Default to 'all' sites

### Error Handling

#### Python Backend
```python
# Always catch specific exceptions
try:
    result = await vector_db.search(query)
except ConnectionError as e:
    logger.error(f"Vector DB connection failed: {e}")
    # Return partial results or fallback
except TimeoutError as e:
    logger.warning(f"Vector DB timeout: {e}")
    # Use cached results if available
```

#### JavaScript Frontend
```javascript
// Always provide user feedback
try {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
} catch (error) {
    console.error('API call failed:', error);
    this.showErrorMessage('Unable to process request. Please try again.');
}
```

### Streaming Responses
1. **Connection Loss**: Implement retry with exponential backoff
2. **Partial Data**: Buffer and validate JSON before parsing
3. **Timeout**: Close stream after reasonable time (e.g., 5 minutes)
4. **Memory Management**: Clear old messages/results periodically

### Authentication
1. **Token Expiry**: Refresh tokens automatically
2. **Invalid Tokens**: Clear and redirect to login
3. **Network Errors**: Cache auth state locally
4. **Multiple Tabs**: Sync auth state across tabs

### Data Validation

#### Input Sanitization
```javascript
// Always escape HTML in user content
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
```

#### Result Validation
```python
# Validate result structure
def validate_result(result):
    required_fields = ['url', 'name', 'site']
    if not all(field in result for field in required_fields):
        logger.warning(f"Invalid result structure: {result}")
        return None
    return result
```

## Code Quality Rules

### General Principles
1. **DRY (Don't Repeat Yourself)**: Extract common functionality
2. **SOLID Principles**: Especially Single Responsibility
3. **Fail Fast**: Validate inputs early
4. **Explicit is Better**: Clear variable names over brevity

### Python-Specific
1. **Type Hints**: Use for function signatures
2. **Docstrings**: Required for public methods
3. **Async/Await**: Prefer over callbacks
4. **Context Managers**: Use for resource management

### JavaScript-Specific
1. **Strict Mode**: Always use 'use strict'
2. **Const by Default**: Use const unless reassignment needed
3. **Arrow Functions**: For callbacks and short functions
4. **Template Literals**: For string interpolation

### Testing Conventions
1. **Unit Tests**: Test individual functions/methods
2. **Integration Tests**: Test API endpoints
3. **Mock External Services**: Don't rely on external APIs in tests
4. **Test Edge Cases**: Empty inputs, large inputs, invalid data

### Configuration Management
1. **Environment Variables**: For secrets and deployment-specific values
2. **YAML Files**: For structured configuration
3. **Defaults**: Always provide sensible defaults
4. **Validation**: Validate configuration on startup

### Logging
1. **Structured Logging**: Use consistent format
2. **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
3. **Context**: Include relevant context (user_id, query_id)
4. **No Sensitive Data**: Never log passwords, tokens, or PII

### Security
1. **Input Validation**: Always validate user input
2. **SQL Injection**: Use parameterized queries
3. **XSS Prevention**: Escape HTML content
4. **CORS**: Configure appropriately for production
5. **Authentication**: Verify tokens on every request

### Performance
1. **Caching**: Cache expensive operations
2. **Pagination**: Limit result sets
3. **Lazy Loading**: Load data as needed
4. **Connection Pooling**: Reuse database connections
5. **Parallel Processing**: Use asyncio for I/O operations

### Documentation
1. **README**: Keep updated with setup instructions
2. **API Docs**: Document all endpoints
3. **Code Comments**: Explain "why", not "what"
4. **Examples**: Provide usage examples