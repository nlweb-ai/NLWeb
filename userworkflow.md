# NLWeb User Workflows and UX Flow

## Primary User Paths

### 1. First-Time User Flow
```
Landing Page → Centered Input → Type Query → View Results → Explore
```

**Steps:**
1. User lands on index.html
2. Sees centered input with placeholder "Ask"
3. Optional: Select site from dropdown (defaults to "all")
4. Optional: Select mode (list/summarize/generate)
5. Types natural language query
6. Presses Enter or clicks send button
7. Views streaming results
8. Can continue conversation or start new

**UI Elements:**
- Centered input box with site/mode selectors
- Loading animation (three dots)
- Results stream in real-time
- Sidebar hidden initially on mobile

### 2. Authenticated User Flow
```
Login → OAuth Provider → Return → Conversations Sync → Enhanced Experience
```

**Steps:**
1. Click "Login" button in header
2. Select OAuth provider (Google/Facebook/Microsoft/GitHub)
3. Authenticate with provider
4. Return to app with token
5. Previous conversations load in sidebar
6. User info displayed in header
7. Conversations auto-save to server

**UI Elements:**
- Login button → User menu (when authenticated)
- OAuth popup window
- Provider selection interface
- Loading state during sync
- Conversation list in sidebar

### 3. Search and Browse Flow

#### List Mode (Default)
```
Query → Results List → Click Item → New Tab with Source
```
- Results ranked by relevance
- Rich snippets with descriptions
- Schema.org data rendered appropriately
- External links open in new tabs

#### Summarize Mode
```
Query → Summary Text → Supporting Results → Explore Sources
```
- AI-generated summary appears first
- Relevant results listed below
- Summary based on retrieved content
- Citations link to sources

#### Generate Mode
```
Query → AI Response → Referenced Items → Deep Exploration
```
- Comprehensive AI-generated answer
- Items used for generation listed
- More conversational response
- Supports follow-up questions

### 4. Multi-Turn Conversation Flow
```
Initial Query → Response → Follow-up Query → Contextual Response
```

**Features:**
- Previous queries provide context
- Pronouns resolved (e.g., "it", "that")
- Conversation history in sidebar
- Can switch between conversations
- Delete unwanted conversations

### 5. Site-Specific Search Flow
```
Select Site → Targeted Query → Filtered Results → Site-Specific Features
```

**Examples:**
- Recipe sites: Ingredient lists, cook time, ratings
- Real estate: Price, location, amenities with map
- News: Publication date, author, summary
- E-commerce: Price, reviews, availability

## User Interface States

### Loading States
1. **Initial Query**: Animated three dots
2. **Streaming**: Results appear as received
3. **Images**: Lazy loaded with placeholders
4. **Maps**: "Loading map..." placeholder

### Error States
1. **No Results**
   - Message: "No results were found"
   - Suggestions for refining query
   
2. **Connection Error**
   - Message: "Unable to connect to server"
   - Retry button
   - Offline indicator

3. **Authentication Error**
   - Message: "Authentication failed"
   - Clear login state
   - Redirect to login

4. **Rate Limiting**
   - Message: "Too many requests"
   - Countdown timer
   - Suggestion to wait

### Empty States
1. **No Conversations**: 
   - "Start a new conversation" prompt
   - Centered input visible

2. **No Sites Available**:
   - Default to "all" sites
   - Error message in console

3. **No Remembered Items**:
   - Section hidden
   - Appears when items added

## Failure States and Recovery

### Network Failures
```
Request Fails → Retry Logic → User Feedback → Fallback Options
```

**Handling:**
1. Automatic retry with exponential backoff
2. Show user-friendly error message
3. Maintain partial results if available
4. Allow manual retry
5. Cache results locally when possible

### Streaming Interruptions
```
Stream Breaks → Reconnect Attempt → Resume or Show Partial
```

**Recovery:**
1. EventSource error triggers reconnect
2. Maximum 3 retry attempts
3. Show partial results received
4. "Load more" option if stream incomplete
5. Complete signal ensures finalization

### Authentication Failures

#### OAuth Flow Failure
```
OAuth Fails → Clear State → Show Error → Remain Anonymous
```
1. OAuth popup blocked: Instruction to allow popups
2. Provider error: Return to provider selection
3. Token invalid: Clear and re-authenticate
4. Network error: Retry with timeout

#### Session Expiry
```
Token Expires → Refresh Attempt → Re-login if Needed
```
1. 401 response triggers token refresh
2. Refresh fails: Clear auth state
3. Redirect to login with return URL
4. Preserve current conversation locally

### Data Validation Failures

#### Malformed Responses
```
Invalid JSON → Parse Error → Show Error → Continue Service
```
1. Log parsing error
2. Skip malformed message
3. Continue processing stream
4. Show partial results

#### Missing Required Fields
```
Incomplete Data → Validation → Default Values → Degraded Display
```
1. Missing title: Use URL as fallback
2. Missing description: Show "No description"
3. Missing score: Default sorting
4. Missing site: Categorize as "unknown"

## Accessibility Considerations

### Keyboard Navigation
- Tab through all interactive elements
- Enter to send message
- Escape to close dropdowns
- Arrow keys in dropdown lists

### Screen Reader Support
- ARIA labels for icons
- Alt text for images
- Semantic HTML structure
- Status announcements for loading

### Visual Accessibility
- High contrast text
- Focus indicators
- Sufficient touch targets (44x44px)
- Responsive text sizing

## Performance Optimizations

### Initial Load
1. Critical CSS inlined
2. JavaScript modules lazy loaded
3. Fonts loaded asynchronously
4. Images lazy loaded below fold

### Runtime Performance
1. Virtual scrolling for long result lists
2. Debounced search input
3. Result deduplication
4. Memory cleanup for old messages

### Mobile Optimizations
1. Sidebar collapsed by default
2. Touch-optimized controls
3. Reduced animation on low-end devices
4. Offline detection and messaging

## User Feedback Mechanisms

### Visual Feedback
- Loading animations
- Hover states
- Active states
- Success/error colors

### Interactive Feedback
- Click feedback
- Drag indicators (future)
- Progress indicators
- Completion signals

### Error Communication
- User-friendly messages
- Actionable suggestions
- Technical details in console
- Support contact options

## Privacy and Security

### Data Handling
1. Local storage for unauthenticated users
2. Server storage only when authenticated
3. Clear data option in settings
4. No tracking without consent

### Secure Communication
1. HTTPS enforced
2. OAuth tokens in Authorization header
3. XSS prevention in rendering
4. Content Security Policy headers