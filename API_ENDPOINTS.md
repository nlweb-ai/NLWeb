# API Endpoints Documentation

## Chat Configuration
### GET /health/chat
Get chat system health and configuration.

**Response:**
```json
{
  "status": "healthy",
  "connections": 5,
  "conversations": 2,
  "participants_by_conversation": {
    "conv_abc": {"humans": 3, "ai_agents": 1}
  },
  "queue_depths": {"conv_abc": 10},
  "storage": "connected"
}
```

## Conversations

### GET /chat/my-conversations
Get list of user's conversations.

**Query Parameters:**
- `limit` (optional): Number of conversations to return (default: 20)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "conversations": [
    {
      "id": "conv_abc123",
      "title": "Project Discussion",
      "site": "all",
      "participantCount": 3,
      "lastMessage": {
        "content": "Looking good!",
        "timestamp": "2024-01-15T10:30:00Z"
      },
      "createdAt": "2024-01-15T09:00:00Z",
      "updatedAt": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

### POST /chat/create
Create a new conversation.

**Request Body:**
```json
{
  "title": "New Chat",
  "participants": [
    {
      "user_id": "user_123", 
      "name": "Alice"
    }
  ],
  "enable_ai": true
}
```

**Response:**
```json
{
  "id": "conv_xyz789",
  "title": "New Chat",
  "site": "hackernews",
  "participants": [...],
  "createdAt": "2024-01-15T11:00:00Z"
}
```

Note: Conversation details are loaded via WebSocket connection after joining.
Joining is handled by including the conversation ID in the WebSocket URL.

## Sites
### GET /sites?streaming=false
Get available sites for search/chat context.

**Response:**
```json
{
  "sites": [
    {
      "id": "hackernews",
      "name": "Hacker News",
      "domain": "news.ycombinator.com"
    },
    {
      "id": "reddit",
      "name": "Reddit",
      "domain": "reddit.com"
    }
  ]
}
```

## WebSocket Connection
### WebSocket /chat/ws/{conv_id}
Real-time bidirectional communication for chat.

**Connection URL:**
```
wss://example.com/chat/ws/conv_abc123
```
Note: Authentication handled via cookies/headers from the HTTP upgrade request.

**Outgoing Message Types:**

1. **Message**
```json
{
  "type": "message",
  "content": "Hello everyone!"
}
```

2. **Typing Indicator**
```json
{
  "type": "typing",
  "isTyping": true
}
```

3. **Sync Request** (after reconnection)
```json
{
  "type": "sync",
  "lastSequenceId": 42
}
```

**Incoming Message Types:**

1. **Chat Message**
```json
{
  "type": "message",
  "data": {
    "id": "msg_123",
    "content": "Hello!",
    "senderId": "user_123",
    "senderName": "Alice",
    "timestamp": "2024-01-15T10:00:00Z",
    "sequenceId": 43
  }
}
```

2. **AI Response**
```json
{
  "type": "ai_response",
  "data": {
    "id": "ai_msg_456",
    "content": "Based on my search...",
    "responseType": "search_results",
    "metadata": {
      "sources": ["hackernews", "reddit"]
    },
    "timestamp": "2024-01-15T10:01:00Z"
  }
}
```

3. **Participant Update**
```json
{
  "type": "participant_update",
  "data": {
    "action": "joined",
    "participant": {
      "id": "user_789",
      "displayName": "Charlie",
      "joinedAt": "2024-01-15T10:05:00Z"
    }
  }
}
```

4. **Typing Indicator**
```json
{
  "type": "typing",
  "data": {
    "participantId": "user_456",
    "participantName": "Bob",
    "isTyping": true
  }
}
```

5. **Error**
```json
{
  "type": "error",
  "data": {
    "code": "QUEUE_FULL",
    "message": "Message queue is full. Please wait."
  }
}
```

## Authentication
All endpoints require authentication via:
- Bearer token in Authorization header
- Token in sessionStorage for WebSocket connection
- OAuth user info in localStorage (non-sensitive only)