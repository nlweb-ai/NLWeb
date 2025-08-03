# Manual Test Scenarios

## 1. Single User Flow

### 1.1 First Time User
- [ ] Open multi-chat.html
- [ ] Should prompt for email/identity
- [ ] Enter email and optional display name
- [ ] Should save to localStorage
- [ ] Create new conversation
- [ ] Send message
- [ ] Should see message appear
- [ ] AI should respond
- [ ] Refresh page
- [ ] Should remember identity
- [ ] Should reload conversation

### 1.2 OAuth User
- [ ] Have authToken in sessionStorage
- [ ] Have userInfo in localStorage
- [ ] Open multi-chat.html
- [ ] Should NOT prompt for identity
- [ ] Should use OAuth identity
- [ ] Create conversation
- [ ] Close tab
- [ ] Open new tab
- [ ] Should prompt for identity (sessionStorage cleared)

## 2. Multi-User Flow

### 2.1 Basic Two Users
- [ ] User A creates conversation
- [ ] User A copies share link
- [ ] User B opens link in different browser
- [ ] User B prompted for identity
- [ ] User B joins conversation
- [ ] User A sees "User B joined" message
- [ ] User B sends message
- [ ] User A sees message immediately
- [ ] User A sends message
- [ ] User B sees message immediately
- [ ] AI responds
- [ ] Both users see AI response

### 2.2 Three+ Users
- [ ] Start with 2 users in conversation
- [ ] User C joins via share link
- [ ] All users see "User C joined"
- [ ] Input timeout changes to 2000ms (multi mode)
- [ ] User A types message
- [ ] Users B and C see "User A is typing..."
- [ ] User A sends message
- [ ] All users receive message
- [ ] Multiple users type simultaneously
- [ ] Each sees correct typing indicators

## 3. Security Tests

### 3.1 XSS Prevention
- [ ] Send message: `<script>alert('XSS')</script>`
- [ ] Should display as text, not execute
- [ ] Send message: `<img src=x onerror='alert(1)'>`
- [ ] Should display as text, not execute
- [ ] Send message with onclick: `<div onclick='alert(1)'>Click me</div>`
- [ ] Should strip onclick handler
- [ ] AI response with HTML should also be sanitized

### 3.2 Token Security
- [ ] Check localStorage - should NOT contain authToken
- [ ] Check sessionStorage - should contain authToken if OAuth
- [ ] Copy conversation URL - should NOT contain token
- [ ] WebSocket connection - token sent in connection params only

## 4. Typing Indicator Tests

### 4.1 Throttling
- [ ] Type continuously for 10 seconds
- [ ] Other users should see typing indicator
- [ ] Should only send typing event every 3 seconds
- [ ] Stop typing
- [ ] Send message
- [ ] Typing indicator should clear immediately

### 4.2 Multiple Typers
- [ ] User A starts typing
- [ ] User B sees "User A is typing..."
- [ ] User B starts typing
- [ ] User A sees "User B is typing..."
- [ ] User C sees "User A and User B are typing..."
- [ ] User A sends message
- [ ] User C now sees only "User B is typing..."

## 5. Connection Tests

### 5.1 Reconnection
- [ ] In active conversation
- [ ] Disconnect network
- [ ] Should show disconnected state
- [ ] Send message while disconnected
- [ ] Message should queue (show as pending)
- [ ] Reconnect network
- [ ] Should auto-reconnect
- [ ] Queued message should send
- [ ] Should sync any missed messages

### 5.2 Page Reload
- [ ] In conversation with messages
- [ ] Note last message
- [ ] Reload page
- [ ] Should reconnect to same conversation
- [ ] Should show all previous messages
- [ ] Should maintain scroll position

## 6. UI Tests

### 6.1 Responsive Design
- [ ] Desktop view - sidebar visible
- [ ] Tablet view - sidebar toggleable
- [ ] Mobile view - sidebar hidden, swipe to show
- [ ] All views - messages readable
- [ ] All views - input accessible

### 6.2 Message Rendering
- [ ] Text message - displays correctly
- [ ] Long message - wraps properly
- [ ] Code block - formatted with syntax highlighting
- [ ] Links - clickable and styled
- [ ] AI search results - formatted cards
- [ ] AI charts - render properly
- [ ] Timestamps - show relative time

## 7. Performance Tests

### 7.1 Message Load
- [ ] Conversation with 100+ messages
- [ ] Should load quickly (<1s)
- [ ] Scrolling should be smooth
- [ ] Search should be responsive

### 7.2 Rapid Messaging
- [ ] Send 10 messages rapidly
- [ ] All should appear in order
- [ ] No messages lost
- [ ] UI remains responsive

## 8. Error Handling

### 8.1 Network Errors
- [ ] Start with no network
- [ ] Try to create conversation
- [ ] Should show error message
- [ ] Should not crash

### 8.2 Invalid Actions
- [ ] Try to join non-existent conversation
- [ ] Should show error
- [ ] Try to send empty message
- [ ] Should not send
- [ ] Try to send very long message (10000+ chars)
- [ ] Should show error or truncate

## 9. Edge Cases

### 9.1 Simultaneous Actions
- [ ] Two users send message at exact same time
- [ ] Both messages should appear
- [ ] Order should be consistent for all users

### 9.2 Conversation Limits
- [ ] Try to add 11th participant (if limit is 10)
- [ ] Should show error
- [ ] Queue full scenario
- [ ] Should show appropriate error

## Test Result Summary

- Total Scenarios: 9
- Total Test Cases: ~60
- Passed: ___
- Failed: ___
- Blocked: ___

Notes:
_________________________________
_________________________________
_________________________________