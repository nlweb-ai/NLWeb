# Security Plan - Auth, Encryption, and PII Handling

## Authentication Strategy

### 1. WebSocket Authentication
```python
# Reuse existing auth middleware
async def authenticate_websocket(request):
    # Extract token from query params or headers
    token = request.headers.get('Authorization') or \
            request.query.get('token')
    
    # Validate using existing middleware
    user = await authenticate_request(request)
    if not user:
        raise web.HTTPUnauthorized()
    
    return user
```

### 2. Token Lifecycle
- **Initial Connection**: Validate auth token
- **Token Storage**: Store user context with connection
- **Reconnection**: Revalidate token (may have expired)
- **Expiration Handling**: Close connection on auth failure

### 3. Multi-Participant Auth
- Each human participant authenticates independently
- Separate WebSocket connection per human
- No shared auth tokens between participants
- Participant list tracks authenticated user IDs

## Encryption Strategy

### 1. Transport Encryption
```yaml
# Production config
chat:
  security:
    require_wss: true  # Enforce WSS in production
    tls_version: "1.2"  # Minimum TLS version
```

### 2. At-Rest Encryption
- **Storage Provider Responsibility**: Leverage provider encryption
  - Azure Search: Encryption at rest enabled by default
  - Elasticsearch: Enable encryption in cluster settings
  - Qdrant: Use encrypted disk volumes
- **No Custom Encryption**: Avoid complexity of key management

### 3. Message Validation
```python
def sanitize_message(content: str) -> str:
    # Remove potential XSS
    content = html.escape(content)
    
    # Limit message size
    max_length = 10000
    if len(content) > max_length:
        content = content[:max_length]
    
    # Validate UTF-8
    content = content.encode('utf-8', errors='ignore').decode('utf-8')
    
    return content
```

## PII Handling

### 1. Data Classification
```python
class PIILevel(Enum):
    PUBLIC = "public"          # No PII
    INTERNAL = "internal"      # User IDs, conversation IDs
    SENSITIVE = "sensitive"    # Names, email addresses
    RESTRICTED = "restricted"  # SSN, credit cards, health data
```

### 2. PII Detection
```python
class PIIDetector:
    patterns = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
    }
    
    async def scan_message(self, content: str) -> List[str]:
        found_pii = []
        for pii_type, pattern in self.patterns.items():
            if re.search(pattern, content):
                found_pii.append(pii_type)
        return found_pii
```

### 3. PII Redaction
```python
async def redact_message(message: ChatMessage, user_request: bool = False):
    if user_request:
        # User requested redaction
        message.content = "[REDACTED BY USER]"
        message.metadata['redacted'] = True
        message.metadata['redacted_at'] = datetime.utcnow()
    else:
        # Automatic PII redaction
        detector = PIIDetector()
        pii_types = await detector.scan_message(message.content)
        if pii_types:
            # Log but don't block
            logger.warning(f"PII detected in message: {pii_types}")
            message.metadata['pii_detected'] = pii_types
```

### 4. Data Retention
```yaml
chat:
  security:
    retention_days: 90  # Default retention
    pii_retention_days: 30  # Shorter for PII
    allow_user_deletion: true  # GDPR/CCPA compliance
```

## Access Control

### 1. Conversation Access
```python
async def check_conversation_access(user_id: str, conv_id: str) -> bool:
    # User must be a participant
    conversation = await storage.get_conversation(conv_id)
    return user_id in conversation.participant_ids
```

### 2. Message Visibility
- Participants see all messages in their conversations
- No partial visibility within a conversation
- Admin access for moderation (future feature)

### 3. API Security
```python
# REST endpoints
@auth_required
async def get_conversations(request):
    user_id = request['user'].id
    # Only return user's conversations
    return await storage.get_user_conversations(user_id)

@auth_required
async def get_messages(request):
    user_id = request['user'].id
    conv_id = request.match_info['conversation_id']
    
    # Verify access
    if not await check_conversation_access(user_id, conv_id):
        raise web.HTTPForbidden()
    
    return await storage.get_messages(conv_id)
```

## Rate Limiting

### 1. Connection Limits
```python
class ConnectionRateLimiter:
    def __init__(self):
        self.connections_per_user = defaultdict(int)
        self.max_connections = 5  # Per user
    
    async def check_limit(self, user_id: str) -> bool:
        if self.connections_per_user[user_id] >= self.max_connections:
            return False
        return True
```

### 2. Message Rate Limits
```python
class MessageRateLimiter:
    def __init__(self):
        self.user_buckets = {}  # Token bucket per user
        self.rate = 60  # Messages per minute
        self.burst = 10  # Burst allowance
    
    async def check_limit(self, user_id: str) -> bool:
        bucket = self.user_buckets.get(user_id)
        # Token bucket algorithm
        return bucket.consume(1)
```

### 3. Queue Protection
- Per-conversation queue limits (1000 messages)
- Return 429 when queue full
- Drop oldest unprocessed messages first

## Audit Logging

### 1. Security Events
```python
async def log_security_event(event_type: str, user_id: str, details: dict):
    event = {
        'timestamp': datetime.utcnow(),
        'event_type': event_type,
        'user_id': user_id,
        'details': details,
        'ip_address': get_client_ip(),
        'user_agent': get_user_agent()
    }
    await audit_logger.log(event)
```

### 2. Events to Log
- Authentication failures
- Authorization denials
- PII detection/redaction
- Rate limit violations
- Suspicious patterns

### 3. Log Retention
- Security logs: 1 year
- Access logs: 90 days
- Encrypted and access-controlled

## Implementation Checklist

### Phase 1: Basic Security
- [ ] WebSocket authentication
- [ ] Message sanitization
- [ ] Basic rate limiting
- [ ] HTTPS/WSS enforcement

### Phase 2: PII Protection
- [ ] PII detection patterns
- [ ] Redaction capability
- [ ] User deletion rights
- [ ] Retention policies

### Phase 3: Advanced Security
- [ ] Audit logging
- [ ] Anomaly detection
- [ ] IP-based filtering
- [ ] Advanced rate limiting

### Phase 4: Compliance
- [ ] GDPR compliance
- [ ] CCPA compliance
- [ ] Security scanning
- [ ] Penetration testing

## Security Best Practices

1. **Defense in Depth**: Multiple layers of security
2. **Least Privilege**: Minimal access rights
3. **Fail Secure**: Deny by default
4. **Log Everything**: But protect the logs
5. **Regular Updates**: Security patches and reviews

## Incident Response

### 1. Detection
- Monitor security events
- Alert on anomalies
- User reporting mechanism

### 2. Response
- Isolate affected conversations
- Revoke compromised tokens
- Notify affected users

### 3. Recovery
- Restore from backups
- Apply security patches
- Post-mortem analysis