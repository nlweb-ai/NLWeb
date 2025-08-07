/**
 * Unified Chat Interface - Single path for both SSE and WebSocket
 */

import { ConversationManager } from './conversation-manager.js';
import { ManagedEventSource } from './managed-event-source.js';
import { ChatUICommon } from './chat-ui-common.js';

export class UnifiedChatInterface {
  constructor(options = {}) {
    this.connectionType = options.connectionType || 'sse';
    this.options = options;
    
    // Core state
    this.state = {
      conversationId: null,
      userId: this.getOrCreateUserId(),
      currentStreaming: null,
      selectedMode: 'list',
      selectedSite: 'all',
      sites: [],  // Will be loaded from API
      messageQueue: []
    };
    
    // Connection state for WebSocket
    this.ws = {
      connection: null,
      reconnectAttempts: 0,
      maxReconnects: 5,
      reconnectDelay: 1000
    };
    
    // UI delegates
    this.uiCommon = new ChatUICommon();
    this.conversationManager = new ConversationManager();
    
    // DOM references - cached once
    this.dom = {
      messages: () => document.getElementById('messages-container'),
      chatArea: () => document.getElementById('chat-messages'),
      input: () => document.getElementById('chat-input'),
      sendBtn: () => document.getElementById('send-button'),
      conversations: () => document.getElementById('conversations-list'),
      centeredInput: () => document.querySelector('.centered-input-container'),
      normalInput: () => document.querySelector('.chat-input-container')
    };
    
    this.init();
  }
  
  async init() {
    try {
      // Set up event listeners
      this.bindEvents();
      
      // Load sites from API (non-blocking - fire and forget)
      // For WebSocket, sites will be loaded when connection opens
      // For SSE, we still need to load them separately
      if (this.connectionType !== 'websocket') {
        this.loadSites().catch(err => {
          console.error('Failed to load sites:', err);
          // Continue with default sites
        });
      }
      
      // Check URL parameters BEFORE initializing connection
      const urlParams = new URLSearchParams(window.location.search);
      const joinId = urlParams.get('join');
      const convId = urlParams.get('conversation') || joinId;
      
      // Set conversation ID if provided in URL
      if (convId) {
        this.state.conversationId = convId;
      }
      
      // Initialize connection (will use the conversation ID if set)
      await this.initConnection();
      
      // If we have a join parameter, join the conversation on the server
      if (joinId && this.connectionType === 'websocket') {
        await this.joinServerConversation(joinId);
      }
      
      // Load conversation from URL or show new
      if (convId) {
        await this.loadConversation(convId);
      } else {
        this.showCenteredInput();
      }
      
      // Load conversation list
      this.conversationManager.loadConversations(this.state.selectedSite);
      this.updateConversationsList();
      
    } catch (error) {
      console.error('Initialization error:', error);
      this.showError('Failed to initialize chat interface');
    }
  }
  
  bindEvents() {
    // Single delegation pattern for all events
    document.addEventListener('click', this.handleClick.bind(this));
    document.addEventListener('keydown', this.handleKeydown.bind(this));
    
    // Close dropdowns on outside click
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.mode-dropdown, #mode-selector-icon')) {
        document.getElementById('mode-dropdown')?.classList.remove('show');
      }
    });
  }
  
  handleClick(e) {
    const target = e.target;
    
    // New chat button
    if (target.closest('#new-chat-btn')) {
      this.createNewChat();
      return;
    }
    
    // Send button (both centered and normal)
    if (target.closest('#send-button, #centered-send-button')) {
      this.sendMessage();
      return;
    }
    
    // Share button
    if (target.closest('#shareBtn')) {
      this.shareConversation();
      return;
    }
    
    // Mode selector
    if (target.closest('#mode-selector-icon')) {
      e.stopPropagation();
      document.getElementById('mode-dropdown')?.classList.toggle('show');
      return;
    }
    
    // Mode selection
    if (target.closest('.mode-dropdown-item')) {
      this.selectMode(target.dataset.mode);
      return;
    }
    
    // Conversation selection
    if (target.closest('.conversation-item')) {
      const convId = target.closest('.conversation-item').dataset.conversationId;
      this.loadConversation(convId);
      return;
    }
  }
  
  handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      const input = e.target;
      if (input.matches('#chat-input, #centered-chat-input')) {
        e.preventDefault();
        this.sendMessage();
      }
    }
  }
  
  // ========== Unified Connection Management ==========
  
  async initConnection() {
    if (this.connectionType === 'websocket') {
      return this.connectWebSocket();
    }
    // SSE doesn't need persistent connection
    return Promise.resolve();
  }
  
  async connectWebSocket() {
    // Create a general WebSocket connection (not tied to a specific conversation)
    let wsUrl = window.location.origin === 'file://' 
      ? `ws://localhost:8000/chat/ws`
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/chat/ws`;
    
    // Add authentication if available
    const authToken = localStorage.getItem('authToken');
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
    
    if (authToken && authToken !== 'anonymous') {
      // Add auth token and user info as query parameters for WebSocket
      const params = new URLSearchParams();
      params.append('auth_token', authToken);
      if (userInfo.id) params.append('user_id', userInfo.id);
      if (userInfo.name) params.append('user_name', userInfo.name);
      if (userInfo.provider) params.append('provider', userInfo.provider);
      wsUrl += '?' + params.toString();
    }
    
    return new Promise((resolve, reject) => {
      try {
        this.ws.connection = new WebSocket(wsUrl);
        
        this.ws.connection.onopen = () => {
          this.ws.reconnectAttempts = 0;
          
          // Request sites when connection opens
          this.ws.connection.send(JSON.stringify({
            type: 'sites_request'
          }));
          
          // Send any queued messages
          this.flushMessageQueue();
          
          resolve();
        };
        
        this.ws.connection.onmessage = (event) => {
          this.handleStreamData(JSON.parse(event.data));
        };
        
        this.ws.connection.onerror = (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        };
        
        this.ws.connection.onclose = () => {
          this.handleDisconnection();
        };
        
      } catch (error) {
        reject(error);
      }
    });
  }
  
  handleDisconnection() {
    if (this.ws.reconnectAttempts < this.ws.maxReconnects) {
      this.ws.reconnectAttempts++;
      const delay = this.ws.reconnectDelay * Math.pow(2, this.ws.reconnectAttempts - 1);
      
      setTimeout(() => {
        this.connectWebSocket().catch(err => {
          console.error('Reconnection failed:', err);
        });
      }, delay);
    } else {
      this.showError('Connection lost. Please refresh the page.');
    }
  }
  
  async joinServerConversation(conversationId) {
    // Send join message to WebSocket
    if (this.ws.connection?.readyState === WebSocket.OPEN) {
      // Just send the join message
      // The server will replay events which will be handled by handleStreamData
      // just like normal messages
      this.ws.connection.send(JSON.stringify({
        type: 'join',
        conversation_id: conversationId
      }));
      
      // Add the conversation to the conversation manager if not already there
      if (!this.conversationManager.findConversation(conversationId)) {
        const newConversation = {
          id: conversationId,
          title: 'Joined Conversation',
          timestamp: Date.now(),
          created_at: new Date().toISOString(),
          site: this.state.selectedSite || 'all',
          siteInfo: {
            site: this.state.selectedSite || 'all',
            mode: this.state.selectedMode || 'list'
          },
          messages: []
        };
        this.conversationManager.addConversation(newConversation);
        this.conversationManager.saveConversations();
        
        // Update the chat title immediately
        const chatTitle = document.querySelector('.chat-title');
        if (chatTitle) {
          chatTitle.textContent = 'Joined Conversation';
        }
      }
      
      // Update the conversations list in the UI
      this.updateConversationsList();
      
      // Remove the join parameter from the URL
      const url = new URL(window.location);
      url.searchParams.delete('join');
      url.searchParams.delete('conversation'); // Also remove conversation param if it was set from join
      window.history.replaceState({}, '', url.toString());
    }
  }
  
  handleConversationHistory(data) {
    console.log('Handling conversation history for:', data.conversation_id, 'with', data.messages?.length, 'messages');
    
    // Update conversation with the actual title and messages
    if (data.conversation_id && data.messages) {
      let conversation = this.conversationManager.findConversation(data.conversation_id);
      
      // If conversation doesn't exist yet (e.g., timing issue), create it
      if (!conversation) {
        console.log('Conversation not found in manager, creating new one');
        conversation = {
          id: data.conversation_id,
          title: 'Joined Conversation',
          timestamp: Date.now(),
          created_at: new Date().toISOString(),
          site: this.state.selectedSite || 'all',
          siteInfo: {
            site: this.state.selectedSite || 'all',
            mode: this.state.selectedMode || 'list'
          },
          messages: []
        };
        this.conversationManager.addConversation(conversation);
        // Re-fetch to ensure we have the reference from the manager
        conversation = this.conversationManager.findConversation(data.conversation_id);
      }
      
      if (conversation) {
        // Update title if we have messages
        if (data.messages.length > 0) {
          const firstUserMessage = data.messages.find(m => m.sender_type === 'HUMAN' || m.sender_type === 'user');
          if (firstUserMessage && firstUserMessage.content) {
            // Use first 50 chars of first user message as title
            conversation.title = firstUserMessage.content.slice(0, 50) + 
                               (firstUserMessage.content.length > 50 ? '...' : '');
          }
        }
        
        // Store the messages directly on the conversation object
        conversation.messages = data.messages.map(msg => ({
          role: msg.sender_type === 'HUMAN' || msg.sender_type === 'user' ? 'user' : 'assistant',
          content: msg.content,
          timestamp: msg.timestamp || Date.now()
        }));
        
        console.log('Conversation now has', conversation.messages.length, 'messages');
        console.log('Conversations in manager:', this.conversationManager.conversations.length);
        
        // Save and update UI
        this.conversationManager.saveConversations();
        this.updateConversationsList();
        
        // Update the chat title at the top
        const chatTitle = document.querySelector('.chat-title');
        if (chatTitle) {
          chatTitle.textContent = conversation.title || 'Chat';
        }
        
        // Display the messages in the chat area
        const container = this.dom.messages();
        if (container) {
          container.innerHTML = '';
          data.messages.forEach(msg => {
            const role = msg.sender_type === 'HUMAN' || msg.sender_type === 'user' ? 'user' : 'assistant';
            const bubble = this.addMessageBubble(msg.content, role, msg.sender_info);
            // Store timestamp for later sorting
            if (msg.timestamp) {
              bubble.dataset.timestamp = msg.timestamp;
            }
          });
        }
      }
    }
  }
  
  // ========== Unified Message Sending ==========
  
  sendMessage() {
    // Get input from either centered or normal input
    const input = document.getElementById('centered-chat-input') || 
                  document.getElementById('chat-input');
    const message = input?.value.trim();
    
    if (!message) return;
    
    // Clear input
    input.value = '';
    
    // Hide centered input if visible
    this.hideCenteredInput();
    
    // Add user message to UI with timestamp
    const bubble = this.addMessageBubble(message, 'user');
    bubble.dataset.timestamp = Date.now();
    
    // Save to conversation
    this.saveMessageToConversation(message, 'user');
    
    // Update title if it's still "New chat"
    const chatTitle = document.querySelector('.chat-title');
    if (chatTitle && chatTitle.textContent === 'New chat') {
      // Use first 50 chars of message as title
      const title = message.length > 50 ? message.substring(0, 47) + '...' : message;
      chatTitle.textContent = title;
    }
    
    // Ensure DOM is updated before sending message
    // Use setTimeout to defer sending until after the current event loop
    setTimeout(() => {
      this.sendThroughConnection(message);
    }, 0);
  }
  
  sendThroughConnection(message) {
    // Generate conversation ID if needed (for new conversations)
    if (!this.state.conversationId) {
      this.state.conversationId = 'conv_' + Math.random().toString(36).substr(2, 9);
      this.updateURL();
    }
    
    const params = {
      conversation_id: this.state.conversationId,
      user_id: this.state.userId,
      mode: this.state.selectedMode,
      site: this.state.selectedSite
    };
    
    if (this.connectionType === 'websocket') {
      const data = {
        type: 'message',
        content: message,
        ...params
      };
      
      if (this.ws.connection?.readyState === WebSocket.OPEN) {
        this.ws.connection.send(JSON.stringify(data));
      } else {
        // Queue message and try to reconnect
        this.state.messageQueue.push(data);
        this.connectWebSocket();
      }
    } else {
      // Use SSE for responses
      this.connectSSE(message, params);
    }
  }
  
  connectSSE(query, params) {
    const baseUrl = window.location.origin === 'file://' ? 'http://localhost:8000' : '';
    const urlParams = new URLSearchParams({
      q: query,
      ...params
    });
    
    const url = `${baseUrl}/stream?${urlParams}`;
    const eventSource = new ManagedEventSource(url, {
      maxRetries: 3,
      retryDelay: 1000
    });
    
    // Don't start streaming UI here - wait for actual data
    
    eventSource.handleMessage = (data) => {
      this.handleStreamData(data);
    };
    
    eventSource.onComplete = () => {
      this.endStreaming();
    };
    
    eventSource.onError = (error) => {
      console.error('SSE error:', error);
      this.showError('Failed to get response. Please try again.');
      this.endStreaming();
    };
    
    eventSource.connect();
  }
  
  flushMessageQueue() {
    while (this.state.messageQueue.length > 0) {
      const msg = this.state.messageQueue.shift();
      if (this.ws.connection?.readyState === WebSocket.OPEN) {
        this.ws.connection.send(JSON.stringify(msg));
      }
    }
  }
  
  // ========== Unified Stream Handling ==========
  
  startStreaming() {
    if (!this.state.currentStreaming) {
      const bubble = document.createElement('div');
      bubble.className = 'message assistant-message streaming-message';
      
      const textDiv = document.createElement('div');
      textDiv.className = 'message-text';
      bubble.appendChild(textDiv);
      
      this.dom.messages()?.appendChild(bubble);
      
      this.state.currentStreaming = {
        bubble,
        textDiv,
        context: {
          messageContent: '',
          allResults: []
        }
      };
    }
  }
  
  handleStreamData(data) {
    // Track messages for sorting
    if (!this.state.messageBuffer) {
      this.state.messageBuffer = [];
      this.state.nlwebBlocks = [];
      this.state.currentNlwebBlock = null;
    }
    
    // Handle different message types uniformly
    if (data.type === 'conversation_created') {
      this.state.conversationId = data.conversation_id;
      this.updateURL();
      return;
    }
    
    // Handle sites response
    if (data.type === 'sites_response' && data.sites) {
      this.processSitesData(data.sites);
      
      // Resolve the promise if waiting for sites
      if (this.sitesResponseResolver) {
        clearTimeout(this.sitesResponseTimeout);
        this.sitesResponseResolver();
        delete this.sitesResponseResolver;
        delete this.sitesResponseTimeout;
      }
      return;
    }
    
    // Handle conversation history when joining
    if (data.type === 'conversation_history') {
      // Just display messages immediately - no buffering
      this.handleConversationHistory(data);
      return;
    }
    
    // Handle end of conversation history - trigger sorting
    if (data.type === 'end-conversation-history') {
      console.log('[Conversation History End] Sorting messages by timestamp');
      this.sortAndDisplayMessages();
      return;
    }
    
    // Handle NLWeb response delimiters
    if (data.message_type === 'begin-nlweb-response') {
      console.log('[NLWeb Begin] Starting new NLWeb response block');
      this.state.currentNlwebBlock = {
        beginTimestamp: data.timestamp,
        query: data.query,
        messages: []
      };
      // Don't buffer - we'll get messages from DOM
      return;
    }
    
    if (data.message_type === 'end-nlweb-response') {
      console.log('[NLWeb End] Ending NLWeb response block');
      if (this.state.currentNlwebBlock) {
        this.state.currentNlwebBlock.endTimestamp = data.timestamp;
        this.state.nlwebBlocks.push(this.state.currentNlwebBlock);
        this.state.currentNlwebBlock = null;
        
        // For single-user chat, sort and display immediately when NLWeb response ends
        if (!data.conversation_id || data.conversation_id === this.state.conversationId) {
          console.log('[NLWeb End] Sorting messages for single-user chat');
          this.sortAndDisplayMessages();
        }
      }
      // Don't buffer - we'll get messages from DOM
      return;
    }
    
    // Track messages within NLWeb blocks
    if (this.state.currentNlwebBlock && data.message_type === 'result_batch') {
      this.state.currentNlwebBlock.messages.push(data);
      // Continue to display immediately - will re-sort at the end
    }
    
    // Ignore system messages that don't need UI updates
    if (data.type === 'connected' || 
        data.type === 'participants' || 
        data.type === 'participant_list' ||
        data.type === 'participant_update' ||
        data.type === 'message_ack') {
      return;
    }
    
    if (data.type === 'message' && data.sender_id !== this.state.userId) {
      this.addMessageBubble(data.content, 'assistant', data.sender_info);
      return;
    }
    
    // Skip other non-displayable message types
    if (data.type === 'mode_change' || data.type === 'participant_joined' || data.type === 'participant_left') {
      return;
    }
    
    // If we have a message_type field, it's likely streaming content from NLWeb
    if (!data.message_type) {
      // No message_type means it's not a streaming message
      return;
    }
    
    // Only buffer NLWeb result_batch messages for score-based sorting within blocks
    if (this.state.currentNlwebBlock && data.message_type === 'result_batch') {
      this.state.currentNlwebBlock.messages.push(data);
      // Don't buffer in general messageBuffer - we'll get them from DOM
    }
    
    // Store each streaming message to conversation
    this.storeStreamingMessage(data);
    
    // Handle streaming data - display immediately
    if (!this.state.currentStreaming) {
      this.startStreaming();
    }
    
    const { textDiv, context } = this.state.currentStreaming;
    
    // Use UI common to process the message
    const result = this.uiCommon.processMessageByType(data, textDiv, context);
    this.state.currentStreaming.context = result;
    
    // Check for completion
    if (data.type === 'complete' || data.message_type === 'complete' || data.type === 'stream_end') {
      this.endStreaming();
    }
    
    this.scrollToBottom();
  }
  
  sortAndDisplayMessages() {
    console.log('[sortAndDisplayMessages] Starting sort process');
    
    const container = this.dom.messages();
    if (!container) {
      console.log('[sortAndDisplayMessages] No container found');
      return;
    }
    
    // Get ALL existing message elements from the DOM
    const allBubbles = Array.from(container.querySelectorAll('.message'));
    
    if (allBubbles.length === 0) {
      console.log('[sortAndDisplayMessages] No messages to sort');
      return;
    }
    
    // Extract messages with their timestamps
    const messagesWithTimestamps = allBubbles.map(bubble => ({
      element: bubble,
      timestamp: parseInt(bubble.dataset.timestamp) || Date.now()
    }));
    
    // Sort by timestamp
    messagesWithTimestamps.sort((a, b) => a.timestamp - b.timestamp);
    
    console.log(`[sortAndDisplayMessages] Sorted ${messagesWithTimestamps.length} messages by timestamp`);
    
    // Clear and re-append in sorted order
    container.innerHTML = '';
    messagesWithTimestamps.forEach(item => {
      container.appendChild(item.element);
    });
    
    this.scrollToBottom();
    
    // Clear NLWeb tracking
    console.log('[sortAndDisplayMessages] Done sorting');
    this.state.nlwebBlocks = [];
    this.state.currentNlwebBlock = null;
  }
  
  extractScoreFromMessage(message) {
    // Extract score from result_batch message
    if (message.message_type === 'result_batch' && message.results) {
      // Get the highest score from results in this batch
      let maxScore = 0;
      message.results.forEach(result => {
        const score = parseFloat(result.score || result.ranking_score || 0);
        if (score > maxScore) {
          maxScore = score;
        }
      });
      return maxScore;
    }
    return 0;
  }
  
  storeStreamingMessage(data) {
    // Create conversation ID if needed
    if (!this.state.conversationId) {
      this.state.conversationId = Date.now().toString();
      this.updateURL();
    }
    
    // Find or create conversation
    let conversation = this.conversationManager.findConversation(this.state.conversationId);
    if (!conversation) {
      conversation = {
        id: this.state.conversationId,
        title: 'New chat',
        messages: [],
        streamingMessages: [],
        timestamp: Date.now(),
        site: this.state.selectedSite
      };
      this.conversationManager.conversations.push(conversation);
    }
    
    // Initialize streaming messages array if needed
    if (!conversation.streamingMessages) {
      conversation.streamingMessages = [];
    }
    
    // Store the raw streaming message
    conversation.streamingMessages.push({
      ...data,
      timestamp: Date.now()
    });
    
    // Save to localStorage
    this.conversationManager.saveConversations();
  }
  
  endStreaming() {
    if (this.state.currentStreaming) {
      // Remove streaming class
      this.state.currentStreaming.bubble.classList.remove('streaming-message');
      
      // Mark streaming as complete in conversation
      const conversation = this.conversationManager.findConversation(this.state.conversationId);
      if (conversation && conversation.streamingMessages) {
        // Add a marker that streaming is complete
        conversation.streamingMessages.push({
          message_type: 'stream_complete',
          timestamp: Date.now()
        });
        this.conversationManager.saveConversations();
      }
      
      this.state.currentStreaming = null;
    }
  }
  
  // ========== UI Methods ==========
  
  showCenteredInput() {
    // Check if already exists
    if (this.dom.centeredInput()) return;
    
    // Hide normal input
    const normalInput = this.dom.normalInput();
    if (normalInput) {
      normalInput.style.display = 'none';
    }
    
    // Create centered input
    const container = document.createElement('div');
    container.className = 'centered-input-container';
    container.innerHTML = `
      <div class="centered-input-wrapper">
        <div class="centered-input-box">
          <div class="input-box-top-row">
            <textarea 
              id="centered-chat-input"
              class="centered-chat-input" 
              placeholder="Ask anything..."
              rows="2"
            ></textarea>
            <button id="centered-send-button" class="centered-send-button">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
          <div class="input-box-bottom-row">
            <div class="input-site-selector">
              <button class="site-selector-icon" id="site-selector-icon" title="Select site">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="2" y1="12" x2="22" y2="12"></line>
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                </svg>
              </button>
              <div class="site-dropdown" id="site-dropdown">
                <div class="site-dropdown-header">Select site</div>
                <div id="site-dropdown-items">
                  <!-- Sites will be populated dynamically -->
                </div>
              </div>
            </div>
            <div class="input-mode-selector">
              <button class="mode-selector-icon" id="centered-mode-selector-icon" title="Select mode">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                  <line x1="9" y1="9" x2="15" y2="9"></line>
                  <line x1="9" y1="12" x2="15" y2="12"></line>
                  <line x1="9" y1="15" x2="11" y2="15"></line>
                </svg>
              </button>
              <div class="mode-dropdown" id="centered-mode-dropdown">
                <div class="mode-dropdown-item" data-mode="list">List</div>
                <div class="mode-dropdown-item" data-mode="summarize">Summarize</div>
                <div class="mode-dropdown-item" data-mode="generate">Generate</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    
    this.dom.messages()?.appendChild(container);
    
    // Auto-resize textarea
    const textarea = container.querySelector('textarea');
    textarea?.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    });
    
    // Bind site selector events
    const siteSelector = container.querySelector('#site-selector-icon');
    const siteDropdown = container.querySelector('#site-dropdown');
    const siteDropdownItems = container.querySelector('#site-dropdown-items');
    
    // Populate sites dropdown
    if (siteDropdownItems && this.state.sites.length > 0) {
      siteDropdownItems.innerHTML = '';
      this.state.sites.forEach(site => {
        const item = document.createElement('div');
        item.className = 'site-dropdown-item';
        item.dataset.site = site;
        if (site === this.state.selectedSite) {
          item.classList.add('selected');
        }
        item.textContent = site;
        item.addEventListener('click', () => {
          this.state.selectedSite = site;
          // Update selection visually
          siteDropdownItems.querySelectorAll('.site-dropdown-item').forEach(i => {
            i.classList.toggle('selected', i.dataset.site === site);
          });
          siteDropdown?.classList.remove('show');
          siteSelector.title = `Site: ${site}`;
          
          // Update the "Asking..." text in the header
          const siteInfo = document.getElementById('chat-site-info');
          if (siteInfo) {
            siteInfo.textContent = `Asking ${site}`;
          }
        });
        siteDropdownItems.appendChild(item);
      });
    }
    
    siteSelector?.addEventListener('click', (e) => {
      e.stopPropagation();
      siteDropdown?.classList.toggle('show');
    });
    
    // Bind mode selector events for centered input
    const modeSelector = container.querySelector('#centered-mode-selector-icon');
    const modeDropdown = container.querySelector('#centered-mode-dropdown');
    
    modeSelector?.addEventListener('click', (e) => {
      e.stopPropagation();
      modeDropdown?.classList.toggle('show');
    });
    
    // Mode selection
    const modeItems = container.querySelectorAll('.mode-dropdown-item');
    modeItems.forEach(item => {
      item.addEventListener('click', () => {
        this.state.selectedMode = item.dataset.mode;
        modeItems.forEach(i => i.classList.remove('selected'));
        item.classList.add('selected');
        modeDropdown?.classList.remove('show');
        modeSelector.title = `Mode: ${item.textContent}`;
      });
    });
    
    // Set initial mode selection (sites are already set when populated)
    const initialMode = container.querySelector(`[data-mode="${this.state.selectedMode}"]`);
    if (initialMode) {
      initialMode.classList.add('selected');
    }
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.input-site-selector')) {
        siteDropdown?.classList.remove('show');
      }
      if (!e.target.closest('.input-mode-selector')) {
        modeDropdown?.classList.remove('show');
      }
    });
    
    textarea?.focus();
  }
  
  hideCenteredInput() {
    const centered = this.dom.centeredInput();
    if (centered) {
      centered.remove();
    }
    
    const normal = this.dom.normalInput();
    if (normal) {
      normal.style.display = '';
    }
  }
  
  addMessageBubble(content, type, senderInfo = null) {
    const bubble = document.createElement('div');
    bubble.className = `message ${type}-message message-appear`;
    
    // Add sender info for multi-participant
    if (senderInfo && type === 'assistant') {
      const senderDiv = document.createElement('div');
      senderDiv.className = 'message-sender';
      senderDiv.textContent = senderInfo.name || 'Anonymous';
      bubble.appendChild(senderDiv);
    }
    
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.textContent = content;
    bubble.appendChild(textDiv);
    
    this.dom.messages()?.appendChild(bubble);
    this.scrollToBottom();
    
    return bubble;
  }
  
  showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    this.dom.messages()?.appendChild(errorDiv);
    
    setTimeout(() => errorDiv.remove(), 5000);
  }
  
  selectMode(mode) {
    this.state.selectedMode = mode;
    
    // Update UI
    const items = document.querySelectorAll('.mode-dropdown-item');
    items.forEach(item => {
      item.classList.toggle('selected', item.dataset.mode === mode);
    });
    
    document.getElementById('mode-dropdown')?.classList.remove('show');
  }
  
  // ========== Utility Methods ==========
  
  saveMessageToConversation(message, type = 'user') {
    // Create conversation ID if needed
    if (!this.state.conversationId) {
      this.state.conversationId = Date.now().toString();
      this.updateURL();
    }
    
    // Find or create conversation
    let conversation = this.conversationManager.findConversation(this.state.conversationId);
    if (!conversation) {
      conversation = {
        id: this.state.conversationId,
        title: message.substring(0, 50),
        messages: [],
        streamingMessages: [],
        timestamp: Date.now(),
        site: this.state.selectedSite,
        mode: this.state.selectedMode
      };
      this.conversationManager.conversations.push(conversation);
    }
    
    // Initialize streamingMessages if not present
    if (!conversation.streamingMessages) {
      conversation.streamingMessages = [];
    }
    
    // Add message to messages array
    conversation.messages.push({
      content: message,
      message_type: type,
      timestamp: Date.now()
    });
    
    // Also add to streaming messages for proper replay
    if (type === 'user') {
      conversation.streamingMessages.push({
        message_type: 'user_message',
        content: message,
        timestamp: Date.now()
      });
    }
    
    // Update title if it's the first user message
    if (type === 'user' && conversation.messages.filter(m => m.message_type === 'user').length === 1) {
      conversation.title = message.substring(0, 50);
    }
    
    // Save to localStorage
    this.conversationManager.saveConversations();
    
    // Update conversation list UI
    this.updateConversationsList();
  }
  
  updateSiteDropdowns() {
    // Update all site dropdown items if they exist
    const siteDropdownItems = document.getElementById('site-dropdown-items');
    if (siteDropdownItems && this.state.sites.length > 0) {
      siteDropdownItems.innerHTML = '';
      this.state.sites.forEach(site => {
        const item = document.createElement('div');
        item.className = 'site-dropdown-item';
        item.dataset.site = site;
        if (site === this.state.selectedSite) {
          item.classList.add('selected');
        }
        item.textContent = site;
        item.addEventListener('click', () => {
          this.state.selectedSite = site;
          // Update selection visually
          siteDropdownItems.querySelectorAll('.site-dropdown-item').forEach(i => {
            i.classList.toggle('selected', i.dataset.site === site);
          });
          document.getElementById('site-dropdown')?.classList.remove('show');
          document.getElementById('site-selector-icon').title = `Site: ${site}`;
          
          // Update the "Asking..." text in the header
          const siteInfo = document.getElementById('chat-site-info');
          if (siteInfo) {
            siteInfo.textContent = `Asking ${site}`;
          }
        });
        siteDropdownItems.appendChild(item);
      });
    }
  }

  async loadSites() {
    try {
      // Use WebSocket if available and open
      if (this.connectionType === 'websocket') {
        // Set up a promise to wait for sites response
        return new Promise((resolve, reject) => {
          // Store the resolver for when we receive the sites response
          this.sitesResponseResolver = resolve;
          
          // Set a timeout in case we don't get a response
          const timeout = setTimeout(() => {
            delete this.sitesResponseResolver;
            reject(new Error('Timeout waiting for sites response'));
          }, 5000);
          
          // Store timeout to clear it when we get response
          this.sitesResponseTimeout = timeout;
          
          // If WebSocket is already open, send the request
          if (this.ws.connection?.readyState === WebSocket.OPEN) {
            this.ws.connection.send(JSON.stringify({
              type: 'sites_request'
            }));
          } else {
            // WebSocket not ready, fall back to HTTP
            delete this.sitesResponseResolver;
            clearTimeout(timeout);
            this.loadSitesViaHttp();
          }
        });
      } else {
        // Use HTTP for SSE connection type
        return this.loadSitesViaHttp();
      }
    } catch (error) {
      console.error('Error loading sites:', error);
      
      // Fallback sites
      this.state.sites = ['all'];
      this.state.selectedSite = 'all';
    }
  }
  
  async loadSitesViaHttp() {
    try {
      const baseUrl = window.location.origin === 'file://' ? 'http://localhost:8000' : '';
      const response = await fetch(`${baseUrl}/sites?streaming=false`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data && data['message-type'] === 'sites' && Array.isArray(data.sites)) {
        this.processSitesData(data.sites);
      }
    } catch (error) {
      console.error('Error loading sites via HTTP:', error);
      
      // Fallback sites
      this.state.sites = ['all'];
      this.state.selectedSite = 'all';
    }
  }
  
  processSitesData(sites) {
    // Sort sites alphabetically
    sites.sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
    
    // Add 'all' to the beginning if not present
    if (!sites.includes('all')) {
      sites.unshift('all');
    } else {
      sites = sites.filter(site => site !== 'all');
      sites.unshift('all');
    }
    
    // Store sites
    this.state.sites = sites;
    this.state.selectedSite = 'all';
    
    // Update any existing site dropdowns
    this.updateSiteDropdowns();
  }
  
  getOrCreateUserId() {
    let userId = localStorage.getItem('userId');
    if (!userId) {
      userId = 'user_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('userId', userId);
    }
    return userId;
  }
  
  async loadConversation(conversationId) {
    this.state.conversationId = conversationId;
    this.updateURL();
    
    // Hide centered input
    this.hideCenteredInput();
    
    // Clear existing messages
    const container = this.dom.messages();
    if (container) {
      container.innerHTML = '';
    }
    
    // Check if we have local messages for this conversation
    const conversation = this.conversationManager.findConversation(conversationId);
    
    if (conversation && conversation.streamingMessages && conversation.streamingMessages.length > 0) {
      // Replay streaming messages to rebuild the conversation
      let currentStreamingBubble = null;
      let streamingContext = { messageContent: '', allResults: [] };
      
      conversation.streamingMessages.forEach(msg => {
        if (msg.message_type === 'user_message') {
          // Add user message bubble
          this.addMessageBubble(msg.content, 'user');
          // Reset streaming state for new response
          if (currentStreamingBubble) {
            currentStreamingBubble.classList.remove('streaming-message');
          }
          currentStreamingBubble = null;
          streamingContext = { messageContent: '', allResults: [] };
        } else if (msg.message_type === 'stream_complete') {
          // Mark streaming as complete
          if (currentStreamingBubble) {
            currentStreamingBubble.classList.remove('streaming-message');
          }
          currentStreamingBubble = null;
        } else if (msg.message_type) {
          // Only create bubble for message types that produce visible content
          const visibleTypes = ['asking_sites', 'result_batch', 'nlws', 'summary', 'ensemble_result'];
          
          if (visibleTypes.includes(msg.message_type)) {
            // Create assistant bubble if needed
            if (!currentStreamingBubble) {
              currentStreamingBubble = document.createElement('div');
              currentStreamingBubble.className = 'message assistant-message';
              
              const textDiv = document.createElement('div');
              textDiv.className = 'message-text';
              currentStreamingBubble.appendChild(textDiv);
              
              container.appendChild(currentStreamingBubble);
            }
            
            // Process the message through UI common
            const textDiv = currentStreamingBubble.querySelector('.message-text');
            streamingContext = this.uiCommon.processMessageByType(msg, textDiv, streamingContext);
          }
        }
      });
    } else if (conversation?.messages) {
      // Fallback to old message format if no streaming messages
      conversation.messages.forEach(msg => {
        this.addMessageBubble(msg.content, msg.message_type || msg.type);
      });
    }
    
    // Update the chat title
    const chatTitle = document.querySelector('.chat-title');
    if (chatTitle && conversation) {
      chatTitle.textContent = conversation.title || 'Chat';
    }
    
    // Restore site and mode settings
    if (conversation) {
      if (conversation.site) {
        this.state.selectedSite = conversation.site;
        
        // Update the "Asking..." text in the header
        const siteInfo = document.getElementById('chat-site-info');
        if (siteInfo) {
          siteInfo.textContent = `Asking ${conversation.site}`;
        }
      }
      if (conversation.mode) {
        this.state.selectedMode = conversation.mode;
      }
    }
    
    // Don't join WebSocket conversation when just viewing past conversations
    // WebSocket will auto-join when user sends a message in this conversation
  }
  
  updateConversationsList() {
    const container = this.dom.conversations();
    console.log('Updating conversations list, container:', container);
    if (!container) {
      console.warn('Conversations list container not found!');
      return;
    }
    this.conversationManager.updateConversationsList(this, container);
  }
  
  updateURL() {
    // Don't update the URL - keep it clean
    // Conversations are managed locally, no need to put them in URL
    return;
  }
  
  scrollToBottom() {
    const chatArea = this.dom.chatArea();
    if (chatArea) {
      chatArea.scrollTop = chatArea.scrollHeight;
    }
  }
  
  createNewChat() {
    // Clear current conversation state
    this.state.conversationId = null;
    this.state.currentStreaming = null;
    
    // Clear messages container
    const container = this.dom.messages();
    if (container) {
      container.innerHTML = '';
    }
    
    // Show centered input
    this.showCenteredInput();
    
    // Update chat title
    const chatTitle = document.querySelector('.chat-title');
    if (chatTitle) {
      chatTitle.textContent = 'New chat';
    }
    
    // Clear URL parameters
    this.updateURL();
    
    // Update conversation list to remove active state
    const activeConv = document.querySelector('.conversation-item.active');
    if (activeConv) {
      activeConv.classList.remove('active');
    }
  }
  
  shareConversation() {
    if (!this.state.conversationId) {
      this.showError('No conversation to share');
      return;
    }
    
    // Generate share URL
    const baseUrl = `${window.location.protocol}//${window.location.host}`;
    const shareUrl = `${baseUrl}/chat/join/${this.state.conversationId}`;
    
    // Copy to clipboard
    navigator.clipboard.writeText(shareUrl).then(() => {
      // Show success message
      const shareBtn = document.getElementById('shareBtn');
      if (shareBtn) {
        const originalTitle = shareBtn.title;
        shareBtn.title = 'Link copied!';
        shareBtn.style.color = '#27ae60';
        
        // Show a temporary success message
        const successMsg = document.createElement('div');
        successMsg.style.cssText = `
          position: fixed;
          top: 70px;
          right: 20px;
          background: #27ae60;
          color: white;
          padding: 10px 20px;
          border-radius: 4px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.2);
          z-index: 10000;
          animation: slideIn 0.3s ease;
        `;
        successMsg.textContent = 'Share link copied to clipboard!';
        document.body.appendChild(successMsg);
        
        setTimeout(() => {
          shareBtn.title = originalTitle;
          shareBtn.style.color = '';
          successMsg.remove();
        }, 3000);
      }
    }).catch(err => {
      console.error('Failed to copy:', err);
      this.showError('Failed to copy share link');
    });
  }
}

// Export for use in HTML
window.UnifiedChatInterface = UnifiedChatInterface;