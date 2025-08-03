# Mock Data for Testing

## Mock Users

### OAuth Users
```python
OAUTH_USERS = [
    {
        "user_id": "oauth_google_123",
        "email": "alice@example.com",
        "name": "Alice Johnson",
        "provider": "google",
        "token": "mock_google_token_123",
        "expires_at": "2024-12-31T23:59:59Z"
    },
    {
        "user_id": "oauth_github_456",
        "email": "bob@example.com", 
        "name": "Bob Smith",
        "provider": "github",
        "token": "mock_github_token_456",
        "expires_at": "2024-12-31T23:59:59Z"
    },
    {
        "user_id": "oauth_microsoft_789",
        "email": "charlie@example.com",
        "name": "Charlie Brown",
        "provider": "microsoft",
        "token": "mock_ms_token_789",
        "expires_at": "2024-12-31T23:59:59Z"
    }
]
```

### Email Users
```python
EMAIL_USERS = [
    {
        "user_id": "email_user_001",
        "email": "david@example.com",
        "name": "David Wilson",
        "provider": "email"
    },
    {
        "user_id": "email_user_002", 
        "email": "emma@example.com",
        "name": "Emma Davis",
        "provider": "email"
    }
]
```

### Test User Scenarios
```python
TEST_USER_SCENARIOS = {
    "expired_token": {
        "user_id": "oauth_expired_123",
        "email": "expired@example.com",
        "name": "Expired Token User",
        "provider": "google",
        "token": "expired_token",
        "expires_at": "2023-01-01T00:00:00Z"
    },
    "invalid_token": {
        "user_id": "oauth_invalid_123",
        "email": "invalid@example.com",
        "name": "Invalid Token User",
        "provider": "google",
        "token": "invalid_token_xyz"
    },
    "no_email": {
        "user_id": "oauth_noemail_123",
        "name": "No Email User",
        "provider": "facebook",
        "token": "mock_fb_token"
    }
}
```

## Mock Conversations

### Single Participant Conversations
```python
SINGLE_CONVERSATIONS = [
    {
        "id": "conv_single_001",
        "title": "Weather Query",
        "sites": ["weather.com"],
        "mode": "list",
        "participants": ["oauth_google_123", "nlweb_1"],
        "message_count": 5,
        "created_at": "2024-01-01T10:00:00Z"
    },
    {
        "id": "conv_single_002",
        "title": "News Summary",
        "sites": ["reuters.com", "bbc.com"],
        "mode": "summarize",
        "participants": ["email_user_001", "nlweb_1"],
        "message_count": 10,
        "created_at": "2024-01-01T11:00:00Z"
    }
]
```

### Multi-Participant Conversations
```python
MULTI_CONVERSATIONS = [
    {
        "id": "conv_multi_001",
        "title": "Team Discussion",
        "sites": ["docs.google.com"],
        "mode": "generate",
        "participants": ["oauth_google_123", "oauth_github_456", "email_user_001", "nlweb_1"],
        "message_count": 50,
        "created_at": "2024-01-01T09:00:00Z"
    },
    {
        "id": "conv_multi_002",
        "title": "Large Group Chat",
        "sites": ["wikipedia.org"],
        "mode": "list",
        "participants": ["oauth_google_123", "oauth_github_456", "oauth_microsoft_789", 
                        "email_user_001", "email_user_002", "nlweb_1", "nlweb_2"],
        "message_count": 200,
        "created_at": "2024-01-01T08:00:00Z"
    }
]
```

### Edge Case Conversations
```python
EDGE_CASE_CONVERSATIONS = [
    {
        "id": "conv_near_limit",
        "title": "Near Queue Limit",
        "sites": ["example.com"],
        "mode": "list",
        "participants": ["oauth_google_123", "nlweb_1"],
        "message_count": 998,  # Near 1000 limit
        "created_at": "2024-01-01T07:00:00Z"
    },
    {
        "id": "conv_max_participants",
        "title": "Maximum Participants",
        "sites": ["example.com"],
        "mode": "list",
        "participants": [f"user_{i}" for i in range(100)],  # 100 participants
        "message_count": 50,
        "created_at": "2024-01-01T06:00:00Z"
    }
]
```

## Mock Messages

### Text Messages
```python
TEXT_MESSAGES = [
    {
        "id": "msg_001",
        "content": "What's the weather today?",
        "sender_id": "oauth_google_123",
        "timestamp": "2024-01-01T10:00:01Z"
    },
    {
        "id": "msg_002", 
        "content": "Can you summarize the latest news?",
        "sender_id": "email_user_001",
        "timestamp": "2024-01-01T10:00:02Z"
    },
    {
        "id": "msg_long",
        "content": "A" * 2000,  # Very long message
        "sender_id": "oauth_github_456",
        "timestamp": "2024-01-01T10:00:03Z"
    }
]
```

### Special Character Messages
```python
SPECIAL_CHAR_MESSAGES = [
    {
        "id": "msg_emoji",
        "content": "Hello! 👋 How are you? 😊",
        "sender_id": "oauth_google_123"
    },
    {
        "id": "msg_unicode",
        "content": "Testing unicode: こんにちは 🇯🇵",
        "sender_id": "email_user_001"
    },
    {
        "id": "msg_rtl",
        "content": "Testing RTL: مرحبا بالعالم",
        "sender_id": "oauth_github_456"
    }
]
```

### XSS Test Messages
```python
XSS_TEST_MESSAGES = [
    {
        "id": "xss_001",
        "content": "<script>alert('XSS')</script>",
        "sender_id": "oauth_google_123"
    },
    {
        "id": "xss_002",
        "content": '<img src="x" onerror="alert(1)">',
        "sender_id": "email_user_001"
    },
    {
        "id": "xss_003",
        "content": '<a href="javascript:alert(1)">Click me</a>',
        "sender_id": "oauth_github_456"
    },
    {
        "id": "xss_004",
        "content": '"><script>alert(String.fromCharCode(88,83,83))</script>',
        "sender_id": "email_user_002"
    }
]
```

### AI Response Messages
```python
AI_RESPONSES = {
    "result_batch": {
        "id": "ai_result_001",
        "type": "ai_response",
        "message_type": "result_batch",
        "content": "Found 5 results",
        "data": {
            "results": [
                {"title": "Result 1", "url": "https://example.com/1"},
                {"title": "Result 2", "url": "https://example.com/2"}
            ]
        }
    },
    "summary": {
        "id": "ai_summary_001",
        "type": "ai_response", 
        "message_type": "summary",
        "content": "Here's a summary of the search results...",
        "data": {
            "sources": ["https://example.com/1", "https://example.com/2"]
        }
    },
    "nlws": {
        "id": "ai_nlws_001",
        "type": "ai_response",
        "message_type": "nlws",
        "content": "The weather today is sunny with a high of 75°F",
        "data": {
            "confidence": 0.95
        }
    }
]
```

## Mock WebSocket Messages

### Connection Messages
```python
WS_CONNECTION_MESSAGES = [
    {
        "type": "connection_established",
        "conversation_id": "conv_single_001",
        "participant_id": "oauth_google_123"
    },
    {
        "type": "sync",
        "last_sequence_id": 10,
        "messages": [],  # Would contain missed messages
        "current_sequence_id": 15
    }
]
```

### Typing Indicators
```python
TYPING_MESSAGES = [
    {
        "type": "typing",
        "participant": {
            "participantId": "oauth_google_123",
            "displayName": "Alice Johnson"
        },
        "isTyping": True,
        "conversation_id": "conv_multi_001"
    },
    {
        "type": "typing",
        "participant": {
            "participantId": "oauth_google_123",
            "displayName": "Alice Johnson"
        },
        "isTyping": False,
        "conversation_id": "conv_multi_001"
    }
]
```

### Error Messages
```python
ERROR_MESSAGES = [
    {
        "type": "error",
        "code": "QUEUE_FULL",
        "message": "Conversation queue is full. Please try again later.",
        "retry_after": 5
    },
    {
        "type": "error",
        "code": "AUTH_FAILED",
        "message": "Authentication failed. Please reconnect.",
        "retry_after": 0
    },
    {
        "type": "error",
        "code": "RATE_LIMITED",
        "message": "Too many requests. Please slow down.",
        "retry_after": 30
    }
]
```

## Performance Test Data

### Message Patterns
```python
PERFORMANCE_PATTERNS = {
    "burst": {
        "description": "10 messages in 1 second",
        "messages": [{"content": f"Burst message {i}", "delay": 0.1} for i in range(10)]
    },
    "sustained": {
        "description": "1 message per second for 60 seconds",
        "messages": [{"content": f"Sustained message {i}", "delay": 1} for i in range(60)]
    },
    "concurrent": {
        "description": "5 users sending simultaneously",
        "users": ["user_1", "user_2", "user_3", "user_4", "user_5"],
        "messages_per_user": 10
    }
}
```

### Load Test Scenarios
```python
LOAD_SCENARIOS = {
    "normal_load": {
        "concurrent_users": 50,
        "messages_per_minute": 100,
        "duration_minutes": 10
    },
    "peak_load": {
        "concurrent_users": 200,
        "messages_per_minute": 500,
        "duration_minutes": 5
    },
    "stress_test": {
        "concurrent_users": 1000,
        "messages_per_minute": 2000,
        "duration_minutes": 2
    }
}
```

## Mock Storage Data

### Sequence IDs
```python
MOCK_SEQUENCES = {
    "conv_single_001": 15,
    "conv_single_002": 10,
    "conv_multi_001": 50,
    "conv_multi_002": 200,
    "conv_near_limit": 998
}
```

### Storage Failures
```python
STORAGE_FAILURE_SCENARIOS = [
    {
        "type": "connection_timeout",
        "error": "Storage backend timeout after 5000ms"
    },
    {
        "type": "write_failure",
        "error": "Failed to persist message: disk full"
    },
    {
        "type": "sequence_conflict",
        "error": "Sequence ID already exists"
    }
]
```