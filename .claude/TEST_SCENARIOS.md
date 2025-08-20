# Multi-Chat Integration Test Scenarios

This document outlines manual test scenarios for the multi-participant chat system. Each scenario includes steps to perform and expected behavior.

## Test Environment Setup

1. Open `test-multi-chat.html` in a browser
2. Open browser developer console to monitor for errors
3. Use test harness controls at bottom of page
4. Monitor debug panels for WebSocket messages and events

---

## 1. Single User Flow Tests

### 1.1 Create Conversation
**Steps:**
1. Load the application
2. Click on a site name in the sidebar
3. Select mode (list/summarize/generate) from dropdown

**Expected Behavior:**
- Identity prompt appears if no identity exists
- After identity established, new conversation created
- WebSocket connects to conversation
- Chat UI displays conversation title and site info
- Input field becomes enabled
- URL updates with conversation ID parameter

### 1.2 Send Message
**Steps:**
1. Type "Hello, this is a test message" in input field
2. Press Enter or click Send button

**Expected Behavior:**
- Message appears immediately with "sending" state (70% opacity)
- Typing indicator clears
- Message sent via WebSocket
- After server acknowledgment, message status updates to "delivered"
- Message shows with user attribution and timestamp

### 1.3 Receive AI Response
**Steps:**
1. After sending user message, wait for AI response

**Expected Behavior:**
- AI response appears with "AI Assistant" attribution
- Response formatted based on message_type (text, result, etc.)
- Content properly rendered (lists, links, etc.)
- All HTML content sanitized
- Timestamp shown

### 1.4 Change Site/Mode
**Steps:**
1. Click mode selector dropdown
2. Select different mode (e.g., from "summarize" to "list")
3. Send another message

**Expected Behavior:**
- Mode updates in UI
- Mode preference saved to localStorage
- Next message uses new mode
- AI response format matches selected mode

---

## 2. Multi-User Flow Tests

### 2.1 User A Creates and Shares
**Steps:**
1. User A creates new conversation
2. User A clicks share button
3. Copy share link from clipboard

**Expected Behavior:**
- Share button visible in chat header
- Click copies link in format: `https://domain/chat/join/{conversation_id}`
- Success notification appears: "Share link copied to clipboard!"
- Link contains valid conversation ID

### 2.2 User B Joins Conversation
**Steps:**
1. User B opens share link in new browser/tab
2. Join dialog appears
3. User B confirms join

**Expected Behavior:**
- Join dialog shows conversation ID
- Identity prompt if User B has no identity
- After confirm, WebSocket connects
- User B sees conversation history
- Participant count updates for both users
- User A sees participant update

### 2.3 Message Exchange
**Steps:**
1. User A types and sends "Hello from User A"
2. User B types and sends "Hello from User B"
3. Both users observe messages

**Expected Behavior:**
- Each user sees own message immediately (optimistic update)
- Other user's message appears after WebSocket broadcast
- Messages show correct sender attribution
- Messages ordered by sequence ID
- No duplicate messages

### 2.4 AI Response to Multiple Users
**Steps:**
1. Either user sends message triggering AI response
2. Both users observe AI response

**Expected Behavior:**
- AI response appears for both users simultaneously
- Same response content and formatting
- Response attributed to "AI Assistant"
- Both users can continue conversation

---

## 3. Security Tests

### 3.1 XSS Script Tag Test
**Steps:**
1. Send message: `<script>alert('XSS')</script>`
2. Observe rendered output

**Expected Behavior:**
- No alert dialog appears
- Message renders as plain text: `<script>alert('XSS')</script>`
- Script tags stripped or escaped
- Console shows no script execution

### 3.2 Event Handler Test
**Steps:**
1. Send: `<div onclick="alert('XSS')">Click me</div>`
2. Click on rendered message

**Expected Behavior:**
- No alert on click
- onclick attribute removed
- Renders as: `<div>Click me</div>` or plain text
- No event handlers attached

### 3.3 OAuth Token Storage
**Steps:**
1. Authenticate with OAuth provider
2. Open browser developer tools
3. Check Application > Local Storage
4. Check Application > Session Storage

**Expected Behavior:**
- localStorage contains only:
  - `nlweb_chat_identity` (email identity if used)
  - `nlweb_chat_mode` (last used mode)
  - `userInfo` (non-sensitive user info)
- sessionStorage contains:
  - `authToken` (OAuth token)
- Token cleared when tab closed

### 3.4 AI Response HTML Sanitization
**Steps:**
1. Trigger AI response with HTML content
2. Use test harness "Simulate AI Response" with HTML

**Expected Behavior:**
- Safe HTML tags preserved (b, i, a, p, etc.)
- Dangerous tags removed (script, iframe, object)
- Event attributes stripped
- Links have rel="noopener" for external URLs

### 3.5 Image Tag XSS Test
**Steps:**
1. Send: `<img src=x onerror="alert('XSS')">`
2. Observe output

**Expected Behavior:**
- No alert appears
- Image tag removed or onerror stripped
- Broken image doesn't trigger JavaScript

---

## 4. Throttling Tests

### 4.1 Typing Indicator Throttle
**Steps:**
1. Type continuously for 5 seconds
2. Monitor WebSocket messages in debug panel

**Expected Behavior:**
- First keystroke sends typing indicator immediately
- Subsequent keystrokes don't send for 3 seconds
- After 3 seconds, next keystroke sends typing indicator
- Maximum one typing event per 3 seconds

### 4.2 Typing Cleared on Send
**Steps:**
1. Start typing to trigger indicator
2. Send message
3. Observe typing indicators

**Expected Behavior:**
- Typing indicator sent on first keystroke
- On message send, typing indicator cleared
- Other users see typing indicator disappear
- Next keystroke starts new typing session

### 4.3 Multiple Users Typing
**Steps:**
1. User A starts typing
2. User B starts typing
3. User C starts typing
4. Observe typing indicators

**Expected Behavior:**
- Shows "User A is typing..."
- Updates to "User A and User B are typing..."
- With 3+: "3 people are typing..."
- Each user removed after 5 seconds of inactivity
- Smooth transitions between states

---

## 5. Edge Cases

### 5.1 Reconnection During Conversation
**Steps:**
1. Connect to conversation
2. Send messages
3. Click "Disconnect WebSocket" in test harness
4. Wait 2 seconds
5. Observe reconnection

**Expected Behavior:**
- Disconnect shows connection status indicator
- Automatic reconnection attempt after 1 second
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
- On reconnect:
  - Sends join message
  - Sends sync request with last sequence ID
  - Queued messages sent
  - Missing messages retrieved

### 5.2 Join with No Identity
**Steps:**
1. Clear all browser storage
2. Open join link directly
3. Observe identity flow

**Expected Behavior:**
- Join dialog appears first
- On confirm, identity modal appears
- Must provide email to continue
- After identity, join proceeds
- Can't join without identity

### 5.3 Network Failure Simulation
**Steps:**
1. Connect to conversation
2. Open browser dev tools
3. Set network to "Offline"
4. Try to send message
5. Set network back to "Online"

**Expected Behavior:**
- Message queued with "sending" state
- Connection status shows disconnected
- Reconnection attempts begin
- When online, WebSocket reconnects
- Queued messages sent automatically
- Sync request retrieves missed messages

### 5.4 Large Message Handling
**Steps:**
1. Paste very long text (>5000 characters)
2. Send message

**Expected Behavior:**
- Input field expands to max height (120px)
- Scrollbar appears in input
- Message sends normally
- Message displays with word wrap
- No UI breaking

### 5.5 Rapid Message Sending
**Steps:**
1. Send 10 messages rapidly

**Expected Behavior:**
- Each message gets unique client ID
- All messages appear immediately
- No messages lost
- Server assigns unique IDs
- Proper ordering maintained

---

## Performance Benchmarks

### Expected Performance Metrics:
- Initial load: < 2 seconds
- WebSocket connection: < 500ms
- Message send to display: < 100ms (optimistic update)
- Typing indicator latency: < 200ms
- Reconnection time: 1-2 seconds
- UI remains responsive during all operations

---

## Browser Compatibility

Test in:
- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)
- Mobile Safari (iOS)
- Chrome Mobile (Android)

All features should work consistently across browsers.

---

## Accessibility Checks

- Keyboard navigation works throughout UI
- Screen reader announces messages
- Focus indicators visible
- Color contrast meets WCAG AA standards
- Error messages clearly communicated
- Modal dialogs trap focus appropriately