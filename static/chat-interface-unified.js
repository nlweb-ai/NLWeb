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
    this.additionalParams = options.additionalParams || {};  // Store additional URL params
    
    // Core state
    this.state = {
      conversationId: null,
      userId: this.getOrCreateUserId(),
      currentStreaming: null,
      selectedMode: this.additionalParams.mode || 'list',
      selectedSite: this.additionalParams.site || 'all',
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
      // Update user ID from auth info if available (before any connections)
      // This ensures we use the OAuth user ID if logged in
      this.state.userId = this.getOrCreateUserId();
      
      // Set up event listeners
      this.bindEvents();
      
      // Listen for auth state changes to update user ID
      window.addEventListener('authStateChanged', () => {
        const previousUserId = this.state.userId;
        this.state.userId = this.getOrCreateUserId();
        
        // If WebSocket is connected and user ID changed, might need to reconnect
        if (this.ws.connection && previousUserId !== this.state.userId) {
          this.ws.connection.close();
          this.connectWebSocket();
        }
      });
      
      // Load sites from API (non-blocking - fire and forget)
      // Always load sites asynchronously without blocking
      // Commented out to reduce unnecessary sites requests
      // this.loadSitesNonBlocking();
      
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
      
      // Handle auto-query from URL parameters after DOM is fully loaded
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
          this.handleUrlAutoQuery();
        });
      } else {
        // DOM is already loaded
        this.handleUrlAutoQuery();
      }
      
      // Check for pending join from join.html redirect
      const pendingJoin = localStorage.getItem('pendingJoin');
      if (pendingJoin) {
        // Check if user is logged in
        const authToken = localStorage.getItem('authToken');
        if (!authToken || authToken === 'anonymous') {
          // User is not logged in, keep pendingJoin in localStorage
          // The login flow will handle it after authentication
          const overlay = document.getElementById('oauthPopupOverlay');
          if (overlay) {
            overlay.style.display = 'flex';
          }
        } else {
          // User is logged in
          localStorage.removeItem('pendingJoin');
          
          // Check if conversation messages are already in localStorage
          const allMessages = JSON.parse(localStorage.getItem('nlweb_messages') || '[]');
          const convMessages = allMessages.filter(m => m.conversation_id === pendingJoin);
          
          if (convMessages.length > 0) {
            // Conversation exists locally, just display it
            this.state.conversationId = pendingJoin;
            // Clear current messages
            const messagesContainer = this.dom.messages();
            if (messagesContainer) {
              messagesContainer.innerHTML = '';
            }
            // Display each message
            convMessages.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
            convMessages.forEach(msg => {
              this.handleStreamData(msg, false);
            });
          } else {
            // Request conversation history from server via WebSocket
            if (this.connectionType === 'websocket') {
              const ws = await this.getWebSocketConnection(true);
              if (ws && ws.readyState === WebSocket.OPEN) {
                // Send request for conversation history
                ws.send(JSON.stringify({
                  type: 'get_conversation_history',
                  conversation_id: pendingJoin
                }));
                // Set the conversation ID so incoming messages are associated correctly
                this.state.conversationId = pendingJoin;
              }
            }
          }
          
          // Update URL to show the conversation
          const newUrl = new URL(window.location);
          newUrl.searchParams.set('conversation', pendingJoin);
          window.history.replaceState({}, '', newUrl);
        }
      }
      
      // Load conversation from URL or show new
      if (convId && !pendingJoin) {
        // Load messages from localStorage if we have a conversation ID (and it's not from pendingJoin)
        const allMessages = JSON.parse(localStorage.getItem('nlweb_messages') || '[]');
        const convMessages = allMessages.filter(m => m.conversation_id === convId);
        
        if (convMessages.length > 0) {
          // Clear current messages
          const messagesContainer = this.dom.messages();
          if (messagesContainer) {
            messagesContainer.innerHTML = '';
          }
          // Display each message
          convMessages.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
          convMessages.forEach(msg => {
            this.handleStreamData(msg, false);
          });
        } else {
          // No messages in localStorage - this might be a shared conversation
          // Send join_conversation message to get the messages from server
          if (this.ws.connection && this.ws.connection.readyState === WebSocket.OPEN) {
            this.ws.connection.send(JSON.stringify({
              type: 'join',
              conversation_id: convId
            }));
          }
        }
      } else if (!pendingJoin) {
        this.showCenteredInput();
      }
      
      // Update the UI to show the selected site from URL params
      const siteInfo = document.getElementById('chat-site-info');
      if (siteInfo) {
        siteInfo.textContent = `Asking ${this.state.selectedSite}`;
      }
      
      // Load conversation list
      this.conversationManager.loadConversations(this.state.selectedSite);
      this.updateConversationsList();
      
      // Note: Auto-query from URL params is now handled in handleUrlAutoQuery()
      // which is called during initialization
      
    } catch (error) {
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
    
    // Sidebar toggle
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    
    if (sidebarToggle && sidebar) {
      // Restore sidebar state from localStorage
      const isCollapsed = localStorage.getItem('nlweb-sidebar-collapsed') === 'true';
      if (isCollapsed) {
        sidebar.classList.add('collapsed');
        sidebarToggle.classList.add('sidebar-collapsed');
      }
      
      // Handle sidebar toggle click
      sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        sidebarToggle.classList.toggle('sidebar-collapsed');
        
        // Save state to localStorage
        const isCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('nlweb-sidebar-collapsed', isCollapsed);
      });
    }
    
    // Mobile menu toggle
    if (mobileMenuToggle && sidebar) {
      mobileMenuToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
      });
    }
  }
  
  handleUrlAutoQuery() {
    // Check if there's both a site and query parameter to auto-send
    if (this.additionalParams.site && this.additionalParams.query) {
      // First ensure the site is selected in the UI
      const siteInfo = document.getElementById('chat-site-info');
      if (siteInfo) {
        siteInfo.textContent = `Asking ${this.state.selectedSite}`;
      }
      
      // Create a new conversation
      this.createNewChat(this.state.selectedSite);
      
      // Wait for the new chat UI to be created, then set the input and send
      // createNewChat() calls showCenteredInput() which creates a NEW input element
      // So we need to wait for that to complete before setting the value
      setTimeout(() => {
        // Find the input element - use the same priority as sendMessage()
        // sendMessage checks centered-chat-input first, so we should set it there if it exists
        const centeredInput = document.getElementById('centered-chat-input');
        const regularInput = document.getElementById('chat-input');
        const input = centeredInput || regularInput;
        
        if (input) {
          // Set the query value
          const decodedQuery = decodeURIComponent(this.additionalParams.query);
          input.value = decodedQuery;
          
          // Also set it on both inputs to be sure
          if (centeredInput) centeredInput.value = decodedQuery;
          if (regularInput) regularInput.value = decodedQuery;
          
          // Trigger the send after another short delay to ensure value is set
          setTimeout(() => {
            this.sendMessage();
          }, 200);
        }
      }, 100); // Wait for createNewChat to complete
    }
  }
  
  handleClick(e) {
    const target = e.target;
    
    // New chat button
    if (target.closest('#new-chat-btn')) {
      this.createNewChat();
      return;
    }
    
    // Search history button
    if (target.closest('#search-history-btn')) {
      this.createNewChat('conv_history');
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
    
    // Debug button
    if (target.closest('#debugBtn')) {
      this.toggleDebugInfo();
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
  
  async getWebSocketConnection(createIfNeeded = true) {
    // Check if already connected
    if (this.ws.connection && this.ws.connection.readyState === WebSocket.OPEN) {
      return this.ws.connection;
    }
    
    // Check if connecting
    if (this.ws.connection && this.ws.connection.readyState === WebSocket.CONNECTING) {
      // Wait for connection to complete
      await new Promise((resolve, reject) => {
        const checkInterval = setInterval(() => {
          if (this.ws.connection.readyState === WebSocket.OPEN) {
            clearInterval(checkInterval);
            resolve();
          } else if (this.ws.connection.readyState === WebSocket.CLOSED) {
            clearInterval(checkInterval);
            reject(new Error('Connection closed while waiting'));
          }
        }, 100);
      });
      return this.ws.connection;
    }
    
    // If not connected and should create
    if (createIfNeeded) {
      await this.connectWebSocket();
      return this.ws.connection;
    }
    
    return null;
  }
  
  async connectWebSocket() {
    // Prevent multiple connection attempts
    if (this.ws.connectingPromise) {
      return this.ws.connectingPromise;
    }
    
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
    
    this.ws.connectingPromise = new Promise((resolve, reject) => {
      try {
        this.ws.connection = new WebSocket(wsUrl);
        
        this.ws.connection.onopen = () => {
          this.ws.reconnectAttempts = 0;
          delete this.ws.connectingPromise; // Clear the connecting promise
          
          // Request sites when connection opens
          // Commented out to reduce unnecessary sites requests
          // this.ws.connection.send(JSON.stringify({
          //   type: 'sites_request'
          // }));
          
          // Send any queued messages
          this.flushMessageQueue();
          
          resolve();
        };
        
        this.ws.connection.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.message_type === 'multi_site_complete') {
          }
          this.handleStreamData(data);
        };
        
        this.ws.connection.onerror = (error) => {
          delete this.ws.connectingPromise; // Clear the connecting promise
          reject(error);
        };
        
        this.ws.connection.onclose = () => {
          delete this.ws.connectingPromise; // Clear the connecting promise
          this.handleDisconnection();
        };
        
      } catch (error) {
        delete this.ws.connectingPromise; // Clear the connecting promise
        reject(error);
      }
    });
    
    return this.ws.connectingPromise;
  }
  
  handleDisconnection() {
    if (this.ws.reconnectAttempts < this.ws.maxReconnects) {
      this.ws.reconnectAttempts++;
      const delay = this.ws.reconnectDelay * Math.pow(2, this.ws.reconnectAttempts - 1);
      
      setTimeout(() => {
        this.connectWebSocket().catch(() => {});
      }, delay);
    } else {
      this.showError('Connection lost. Please refresh the page.');
    }
  }
  
  showLoginForJoin(conversationId) {
    // Show the OAuth login popup
    const overlay = document.getElementById('oauthPopupOverlay');
    if (overlay) {
      overlay.style.display = 'flex';
      
      // Store the conversation ID to join after login
      sessionStorage.setItem('pendingJoinConversation', conversationId);
      
      // Add a message explaining why login is required
      const popupContent = overlay.querySelector('.oauth-popup-content');
      if (popupContent && !popupContent.querySelector('.join-login-message')) {
        const message = document.createElement('div');
        message.className = 'join-login-message';
        message.style.padding = '10px';
        message.style.background = '#f0f0f0';
        message.style.borderRadius = '4px';
        message.style.marginBottom = '15px';
        message.innerHTML = '<strong>Login required to join conversation</strong><br>Please login to participate in this conversation.';
        popupContent.insertBefore(message, popupContent.firstChild);
      }
    }
  }
  
  async joinServerConversation(conversationId) {
    
    // Get or create WebSocket connection
    const ws = await this.getWebSocketConnection(true);
    
    if (!ws) {
      return;
    }
    
    // Get user details to send with join message
    const userId = this.getOrCreateUserId();
    const userName = userId.split('@')[0] || 'User';
    
    // Send join message to WebSocket with user details
    ws.send(JSON.stringify({
      type: 'join',
      conversation_id: conversationId,
      user_id: userId,
      user_name: userName,
      user_info: {
        id: userId,
        name: userName
      }
    }));
    
    // Don't create conversation here - wait for conversation_history message
    // The conversation_history handler will create the conversation with proper metadata
    
    // Update the conversations list in the UI
    this.updateConversationsList();
    
    // Remove the join parameter from the URL
    const url = new URL(window.location);
    url.searchParams.delete('join');
    url.searchParams.delete('conversation'); // Also remove conversation param if it was set from join
    window.history.replaceState({}, '', url.toString());
    
    // Clear any pending join from session storage
    sessionStorage.removeItem('pendingJoinConversation');
  }
  
  // Removed handleConversationHistory - messages now go through normal flow
  
  // ========== Unified Message Sending ==========
  
  createUserMessage(content, conversation = null) {
    // ONLY place where message IDs and conversation IDs are created
    
    // Generate conversation ID if needed
    if (!this.state.conversationId) {
      this.state.conversationId = Date.now().toString();
      this.updateURL();
    }
    
    // Get user info
    const userId = this.getOrCreateUserId();
    const userName = userId.split('@')[0] || 'User';
    
    // Build prev_queries from conversation's existing messages
    const prevQueries = [];
    if (conversation && conversation.messages) {
      // Extract previous user queries from conversation history
      const userMessages = conversation.messages
        .filter(m => m.message_type === 'user')
        .slice(-5);  // Keep last 5 user messages for context
      
      userMessages.forEach(msg => {
        prevQueries.push({
          query: msg.content,
          user_id: msg.sender_info?.id || userId,
          timestamp: new Date(msg.timestamp).toISOString()
        });
      });
    }
    
    // Create complete message object
    const message = {
      message_id: `msg_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`,
      conversation_id: this.state.conversationId,
      type: 'message',
      message_type: 'user',
      content: content,
      timestamp: Date.now(),
      sender_info: {
        id: userId,
        name: userName
      },
      site: this.state.selectedSite,
      mode: this.state.selectedMode,
      prev_queries: prevQueries  // Include previous queries for NLWeb context
    };
    
    // Add search_all_users parameter if we're searching conversation history
    if (this.state.selectedSite === 'conv_history') {
      const searchAllUsersCheckbox = document.getElementById('search-all-users');
      if (searchAllUsersCheckbox) {
        message.search_all_users = searchAllUsersCheckbox.checked;
      }
    }
    
    // Add any additional URL parameters
    Object.assign(message, this.additionalParams);
    
    return message;
  }
  
  sendMessage() {
    // Get input from either centered or normal input
    const input = document.getElementById('centered-chat-input') || 
                  document.getElementById('chat-input');
    const messageText = input?.value.trim();
    
    if (!messageText) return;
    
    // Clear input
    input.value = '';
    
    // Hide centered input if visible
    this.hideCenteredInput();
    
    // Get current conversation for context
    const conversation = this.conversationManager?.findConversation(this.state.conversationId);
    
    // Create the message with conversation context
    const message = this.createUserMessage(messageText, conversation);
    
    // Display and store locally
    this.handleStreamData(message, true);
    
    // Update title if it's still "New chat"
    const chatTitle = document.querySelector('.chat-title');
    if (chatTitle && chatTitle.textContent === 'New chat') {
      const title = messageText.length > 50 ? messageText.substring(0, 47) + '...' : messageText;
      chatTitle.textContent = title;
    }
    
    // Send to server
    setTimeout(() => {
      this.sendThroughConnection(message);
    }, 0);
  }
  
  async sendThroughConnection(message) {
    // Just send the message as-is - no modification
    
    if (this.connectionType === 'websocket') {
      // Get or create WebSocket connection
      const ws = await this.getWebSocketConnection(true);
      
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
      } else {
        // Queue message for later
        this.state.messageQueue.push(message);
      }
    } else {
      // For SSE, pass all message properties except some internal ones
      const { content, message_id, timestamp, message_type, type, sender_info, prev_queries, ...sseParams } = message;
      
      this.connectSSE(content, {
        ...sseParams,  // Include all additional parameters
        user_id: this.state.userId,
        streaming: 'true'
      });
    }
  }
  
  connectSSE(query, params) {
    const baseUrl = window.location.origin === 'file://' ? 'http://localhost:8000' : '';
    const urlParams = new URLSearchParams({
      q: query,
      ...params
    });
    
    const url = `${baseUrl}/ask?${urlParams}`;
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
          allResults: [],
          selectedSite: this.state.selectedSite || 'all'  // Ensure we always have a selectedSite
        }
      };
    }
  }
  
  handleStreamData(data, shouldStore = true) {
    // No deduplication - multiple events can share the same message_id
    // (e.g., multiple NLWeb results belong to the same logical message)
    
    
    // Debug logging for multi_site_complete
    if (data.message_type === 'multi_site_complete') {
    }
    
    // Track messages for sorting
    if (!this.state.messageBuffer) {
      this.state.messageBuffer = [];
      this.state.nlwebBlocks = [];
      this.state.currentNlwebBlock = null;
    }
    
    // Handle user messages (from replay)
    if (data.message_type === 'user') {
      // End any current streaming before showing user message
      if (this.state.currentStreaming) {
        this.endStreaming();
      }
      
      // Update selectedSite from the user message if it's present
      if (data.site) {
        this.state.selectedSite = data.site;
      }
      
      // Extract actual message text from nested structure if needed
      let messageText = data.content;
      let sender_info = data.sender_info;
      if (typeof data.content === 'object' && data.content !== null && data.content.content) {
        // Content is nested - extract the actual text
        messageText = data.content.content;
        // Also extract sender_info from nested structure if present
        if (data.content.sender_info) {
          sender_info = data.content.sender_info;
        }
      }
      
      // Display user message with sender info
      const bubble = this.addMessageBubble(messageText, 'user', sender_info);
      bubble.dataset.timestamp = data.timestamp || Date.now();
      
      // Store the message in conversation if shouldStore is true
      if (shouldStore) {
        this.storeStreamingMessage(data);
      }
      return;
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
      
      // Sites loaded successfully
      return;
    }
    
    // Handle conversation history when joining
    if (data.type === 'conversation_history') {
      
      // Create or update conversation with messages
      if (data.conversation_id) {
        let conversation = this.conversationManager.findConversation(data.conversation_id);
        if (!conversation) {
          // Create conversation with basic info - metadata will be extracted in loadConversation
          conversation = {
            id: data.conversation_id,
            title: 'Joined Conversation',
            timestamp: Date.now(),
            created_at: new Date().toISOString(),
            site: 'all',  // Will be extracted from message metadata in loadConversation
            mode: 'list',  // Will be extracted from message metadata in loadConversation
            messages: []
          };
          
          // Store all messages in the conversation - no wrapping!
          if (data.messages && data.messages.length > 0) {
            conversation.messages = data.messages;
            
            // Try to get a better title from the first user message
            const firstUserMsg = data.messages.find(m => m.message_type === 'user');
            if (firstUserMsg && firstUserMsg.content) {
              conversation.title = firstUserMsg.content.substring(0, 50);
            }
          }
          
          this.conversationManager.addConversation(conversation);
          this.conversationManager.saveConversations();
        }
        
        // Load the conversation - this will replay messages and extract metadata
        this.loadConversation(data.conversation_id);
      }
      return;
    }
    
    // Handle end of conversation history
    if (data.type === 'end-conversation-history') {
      // Don't sort - keep messages in order they were received
      
      // Save the conversation with all messages
      this.conversationManager.saveConversations();
      this.updateConversationsList();
      return;
    }
    
    // Handle NLWeb response delimiters
    if (data.message_type === 'begin-nlweb-response') {
      // End any current streaming before starting new NLWeb response
      if (this.state.currentStreaming) {
        this.endStreaming();
      }
      
      this.state.currentNlwebBlock = {
        beginTimestamp: data.timestamp,
        query: data.query,
        messages: []
      };
      // Don't buffer - we'll get messages from DOM
      return;
    }
    
    if (data.message_type === 'end-nlweb-response') {
      if (this.state.currentNlwebBlock) {
        this.state.currentNlwebBlock.endTimestamp = data.timestamp;
        this.state.nlwebBlocks.push(this.state.currentNlwebBlock);
        this.state.currentNlwebBlock = null;
        
        // Don't sort - keep messages in order they were received
      }
      
      // Scroll to the user message after NLWeb response completes
      setTimeout(() => {
        this.scrollToUserMessage();
      }, 100);
      
      // Don't buffer - we'll get messages from DOM
      return;
    }
    
    // Track messages within NLWeb blocks
    if (this.state.currentNlwebBlock && data.message_type === 'result') {
      this.state.currentNlwebBlock.messages.push(data);
      // Continue to display immediately - will re-sort at the end
    }
    
    // Handle participant updates (join/leave notifications) as messages
    if (data.type === 'participant_update') {
      const action = data.action; // 'join' or 'leave'
      const participant = data.participant;
      
      // Don't show join/leave messages for the current user
      if (participant.participantId === this.state.userId) {
        return;
      }
      
      // Create a system message for join/leave
      const message = action === 'join' 
        ? `${participant.displayName} has joined the conversation`
        : `${participant.displayName} has left the conversation`;
      
      // Add message bubble through the standard flow
      const bubble = this.addMessageBubble(message, 'system');
      bubble.dataset.timestamp = data.timestamp || Date.now();
      
      // Store the participant update message
      if (shouldStore) {
        this.storeStreamingMessage({
          message_type: 'system',
          content: message,
          timestamp: data.timestamp || Date.now(),
          sender_info: {
            id: 'system',
            name: 'System'
          },
          metadata: {
            action: action,
            participant_id: participant.participantId,
            participant_name: participant.displayName
          }
        });
      }
      
      return;
    }
    
    // Ignore other system messages that don't need UI updates
    if (data.type === 'connected' || 
        data.type === 'participants' || 
        data.type === 'participant_list' ||
        data.type === 'message_ack') {
      return;
    }
    
    if (data.type === 'message' && data.sender_id !== this.state.userId) {
      // Determine if sender is human or AI based on sender_info
      const role = data.sender_info?.type === 'ai' ? 'assistant' : 'user';
      this.addMessageBubble(data.content, role, data.sender_info);
      
      // Messages from other users should be stored using storeStreamingMessage
      if (shouldStore) {
        this.storeStreamingMessage(data);
      }
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
    
    // Log that we passed the message_type check
    if (data.message_type === 'multi_site_complete') {
    }
    
    // Only buffer NLWeb result messages for score-based sorting within blocks
    if (this.state.currentNlwebBlock && data.message_type === 'result') {
      this.state.currentNlwebBlock.messages.push(data);
      // Don't buffer in general messageBuffer - we'll get them from DOM
    }
    
    // Store each streaming message to conversation if shouldStore is true
    if (shouldStore) {
      this.storeStreamingMessage(data);
    }
    
    // Handle streaming data - display immediately
    if (!this.state.currentStreaming) {
      this.startStreaming();
    }
    
    const { textDiv, context } = this.state.currentStreaming;
    
    
    // Use UI common to process the message
    const result = this.uiCommon.processMessageByType(data, textDiv, context);
    this.state.currentStreaming.context = result;
    
    // Check for completion - but don't end streaming yet if we're expecting multi_site_complete
    if (data.type === 'complete' || data.message_type === 'complete' || data.type === 'stream_end') {
      // If we're in a multi-site query (site=all), don't end streaming yet
      // The multi_site_complete message will come after this
      if (this.state.selectedSite !== 'all') {
        this.endStreaming();
      }
    }
    
    // End streaming after multi_site_complete for multi-site queries
    if (data.message_type === 'multi_site_complete') {
      // Process is complete, now we can end streaming
      setTimeout(() => this.endStreaming(), 100);
    }
    
    this.scrollToBottom();
  }
  
  sortAndDisplayMessages() {
    
    const container = this.dom.messages();
    if (!container) {
      return;
    }
    
    // Get ALL existing message elements from the DOM
    const allBubbles = Array.from(container.querySelectorAll('.message'));
    
    if (allBubbles.length === 0) {
      return;
    }
    
    // Extract messages with their timestamps
    const messagesWithTimestamps = allBubbles.map(bubble => ({
      element: bubble,
      timestamp: parseInt(bubble.dataset.timestamp) || Date.now()
    }));
    
    // Sort by timestamp
    messagesWithTimestamps.sort((a, b) => a.timestamp - b.timestamp);
    
    
    // Clear and re-append in sorted order
    container.innerHTML = '';
    messagesWithTimestamps.forEach(item => {
      container.appendChild(item.element);
    });
    
    this.scrollToBottom();
    
    // Clear NLWeb tracking
    this.state.nlwebBlocks = [];
    this.state.currentNlwebBlock = null;
  }
  
  extractScoreFromMessage(message) {
    // Extract score from result message
    if (message.message_type === 'result' && message.content) {
      // Get the highest score from results in this batch
      let maxScore = 0;
      message.content.forEach(result => {
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
    // Just store the message as-is - no wrapping, no ID generation
    const conversationId = data.conversation_id || this.state.conversationId;
    if (!conversationId) {
      return;
    }
    
    // Find or create conversation
    let conversation = this.conversationManager.findConversation(conversationId);
    if (!conversation) {
      conversation = {
        id: conversationId,
        title: 'New chat',
        messages: [],
        timestamp: Date.now(),
        // Always use the selected site from state, not from individual messages
        // This ensures multi-site queries show as 'all' correctly
        site: this.state.selectedSite,
        mode: this.state.selectedMode
      };
      this.conversationManager.conversations.push(conversation);
    }
    
    // Don't check for duplicates - multiple events can share the same message_id
    // (e.g., multiple NLWeb results for the same query)
    
    // Store the message exactly as received - no wrapping!
    conversation.messages.push(data);
    
    // Update title if it's the first user message and title is still generic
    if (data.message_type === 'user' && 
        (conversation.title === 'New chat' || conversation.title === 'Joined Conversation')) {
      // Extract the actual message text for the title
      let messageText = data.content;
      if (typeof data.content === 'object' && data.content !== null && data.content.content) {
        messageText = data.content.content;
      }
      if (typeof messageText === 'string') {
        conversation.title = messageText.substring(0, 50);
        // Update the UI title as well
        const chatTitle = document.querySelector('.chat-title');
        if (chatTitle) {
          chatTitle.textContent = conversation.title;
        }
      }
      
      // Update conversation list UI for user messages
      this.updateConversationsList();
    }
    
    // Save to localStorage - for now still using the batch approach
    // TODO: Consider IndexedDB for more efficient per-message storage
    this.conversationManager.saveConversations();
  }
  
  endStreaming() {
    if (this.state.currentStreaming) {
      // Remove streaming class
      this.state.currentStreaming.bubble.classList.remove('streaming-message');
      
      // Just clean up the UI state
      // Messages are already stored by storeStreamingMessage()
      
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
    
    // Populate sites dropdown immediately if we have cached sites
    if (this.state.sites && this.state.sites.length > 0 && siteDropdownItems) {
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
          
          // Handle search all users checkbox visibility
          const bottomRow = container.querySelector('.input-box-bottom-row');
          const existingCheckbox = container.querySelector('.search-all-users-container');
          
          if (site === 'conv_history' && !existingCheckbox && bottomRow) {
            // Add checkbox if switching to conv_history
            const checkboxContainer = document.createElement('div');
            checkboxContainer.className = 'search-all-users-container';
            checkboxContainer.style.cssText = 'display: flex; align-items: center; margin-right: 10px;';
            checkboxContainer.innerHTML = `
              <input type="checkbox" id="search-all-users" style="margin-right: 5px;">
              <label for="search-all-users" style="font-size: 12px; color: #666; cursor: pointer;">Search all users</label>
            `;
            bottomRow.insertBefore(checkboxContainer, bottomRow.firstChild);
          } else if (site !== 'conv_history' && existingCheckbox) {
            // Remove checkbox if switching away from conv_history
            existingCheckbox.remove();
          }
        });
        siteDropdownItems.appendChild(item);
      });
    }
    
    siteSelector?.addEventListener('click', async (e) => {
      e.stopPropagation();
      
      // Load sites if not already loaded
      if (!this.state.sites || this.state.sites.length === 0) {
        await this.loadSitesViaHttp();
        
        // Populate the dropdown after loading
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
      }
      
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
    
    // Add search all users checkbox if we're in conversation history mode
    if (this.state.selectedSite === 'conv_history') {
      const bottomRow = container.querySelector('.input-box-bottom-row');
      if (bottomRow) {
        const checkboxContainer = document.createElement('div');
        checkboxContainer.className = 'search-all-users-container';
        checkboxContainer.style.cssText = 'display: flex; align-items: center; margin-right: 10px;';
        checkboxContainer.innerHTML = `
          <input type="checkbox" id="search-all-users" style="margin-right: 5px;">
          <label for="search-all-users" style="font-size: 12px; color: #666; cursor: pointer;">Search all users</label>
        `;
        bottomRow.insertBefore(checkboxContainer, bottomRow.firstChild);
      }
    }
    
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
  
  addMessageBubble(content, type, sender_info = null) {
    const bubble = document.createElement('div');
    bubble.className = `message ${type}-message message-appear`;
    
    // Add sender info for both user and assistant messages
    if (type === 'user' || type === 'assistant') {
      const senderDiv = document.createElement('div');
      senderDiv.className = 'message-sender';
      
      if (type === 'user') {
        // For user messages, check if it's the current user
        if (sender_info && sender_info.id === this.state.userId) {
          senderDiv.textContent = 'You';
        } else if (sender_info && sender_info.id) {
          senderDiv.textContent = sender_info.id;
        } else {
          // If no sender info, assume it's the current user (for messages they just sent)
          senderDiv.textContent = 'You';
        }
      } else {
        // Assistant messages
        senderDiv.textContent = sender_info?.name || 'Assistant';
      }
      
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

  loadSitesNonBlocking() {
    // Always use HTTP for sites loading to avoid blocking
    // This runs completely asynchronously without any waiting
    this.loadSitesViaHttp().catch(error => {
      // Continue with default sites
      this.state.sites = ['all'];
      // Only set to 'all' if not already set from URL params
      if (!this.state.selectedSite) {
        this.state.selectedSite = 'all';
      }
    });
  }
  
  
  async loadSitesViaHttp() {
    // Check if we already have sites in memory
    if (this.state.sites && this.state.sites.length > 0) {
      return;
    }
    
    // Fetch fresh sites data from server
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
      
      // Fallback sites
      this.state.sites = ['all'];
      // Only set to 'all' if not already set from URL params
      if (!this.state.selectedSite) {
        this.state.selectedSite = 'all';
      }
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
    // Don't override selectedSite if it was set from URL parameters
    // Only set to 'all' if it wasn't already set
    if (!this.state.selectedSite) {
      this.state.selectedSite = 'all';
    }
    
    // Don't automatically update dropdowns - they will be populated on-demand when clicked
    // this.updateSiteDropdowns();
  }
  
  clearCachedSites() {
    // This method is kept for backwards compatibility but no longer needed
    this.state.sites = [];
  }
  
  getOrCreateUserId() {
    // First check if user is logged in via OAuth
    const userInfo = localStorage.getItem('userInfo');
    if (userInfo) {
      try {
        const user = JSON.parse(userInfo);
        
        // For GitHub users, prefer the login/username over numeric ID
        if (user.provider === 'github') {
          // Try these fields in order of preference for GitHub
          if (user.login) return user.login;  // GitHub username
          if (user.username) return user.username;  // Alternative field name
          if (user.name) return user.name;  // Display name
        }
        
        // For other providers or if GitHub fields not found
        // Prefer human-readable identifiers over numeric IDs
        if (user.email) return user.email;
        if (user.name) return user.name;
        if (user.username) return user.username;
        if (user.login) return user.login;
        
        // Last resort - use the ID (might be numeric for GitHub)
        if (user.id) return user.id;
        
      } catch (e) {
      }
    }
    
    // If not logged in, use or create anonymous user ID
    let userId = localStorage.getItem('userId');
    if (!userId) {
      userId = 'user_' + Math.random().toString(36).substring(2, 11);
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
    
    // Get all messages from localStorage
    const allMessages = JSON.parse(localStorage.getItem('nlweb_messages') || '[]');
    
    // Filter messages for this conversation
    const conversationMessages = allMessages.filter(msg => msg.conversation_id === conversationId);
    
    // Replay each message through handleStreamData
    conversationMessages.forEach(msg => {
      this.handleStreamData(msg, false); // false = don't store again
    });
    
    // Update the chat title from first user message if available
    const chatTitle = document.querySelector('.chat-title');
    if (chatTitle) {
      const firstUserMessage = conversationMessages.find(msg => msg.message_type === 'user');
      if (firstUserMessage && firstUserMessage.content) {
        const content = typeof firstUserMessage.content === 'string' ? 
          firstUserMessage.content : 'Chat';
        chatTitle.textContent = content.substring(0, 50);
      } else {
        chatTitle.textContent = 'Chat';
      }
    }
    
    // Restore site and mode settings from first user message
    const firstUserMsg = conversationMessages.find(msg => msg.message_type === 'user');
    if (firstUserMsg) {
      if (firstUserMsg.site) {
        this.state.selectedSite = firstUserMsg.site;
        
        // Update the "Asking..." text in the header
        const siteInfo = document.getElementById('chat-site-info');
        if (siteInfo) {
          siteInfo.textContent = `Asking ${firstUserMsg.site}`;
        }
      }
      if (firstUserMsg.mode) {
        this.state.selectedMode = firstUserMsg.mode;
      }
    }
    
    // Don't join WebSocket conversation when just viewing past conversations
    // WebSocket will auto-join when user sends a message in this conversation
  }
  
  updateConversationsList() {
    const container = this.dom.conversations();
    if (!container) {
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
  
  scrollToUserMessage() {
    const chatArea = this.dom.chatArea();
    const messagesContainer = this.dom.messages();
    
    if (!chatArea || !messagesContainer) return;
    
    // Find the last user message
    const userMessages = messagesContainer.querySelectorAll('.user-message');
    if (userMessages.length > 0) {
      const lastUserMessage = userMessages[userMessages.length - 1];
      
      // Get the position of the user message relative to the chat container
      const messageRect = lastUserMessage.getBoundingClientRect();
      const containerRect = chatArea.getBoundingClientRect();
      
      // Calculate the optimal scroll position
      // Position the user message about 1/3 down from the top of the viewport
      // This ensures it's clearly visible with context above and space for results below
      const targetOffset = containerRect.height * 0.3;
      const scrollTarget = chatArea.scrollTop + 
                          (messageRect.top - containerRect.top) - targetOffset;
      
      // Smooth scroll to the calculated position
      chatArea.scrollTo({
        top: Math.max(0, scrollTarget),
        behavior: 'smooth'
      });
    }
  }
  
  createNewChat(site = null) {
    // Clear current conversation state
    this.state.conversationId = null;
    this.state.currentStreaming = null;
    
    // Set site if provided (for conversation history search)
    if (site) {
      this.state.selectedSite = site;
      // Update site info display
      const siteInfo = document.getElementById('chat-site-info');
      if (siteInfo) {
        if (site === 'conv_history') {
          siteInfo.textContent = 'Searching conversation history';
        } else {
          siteInfo.textContent = `Asking ${site}`;
        }
      }
    }
    
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
  
  async shareConversation() {
    
    if (!this.state.conversationId) {
      this.showError('No conversation to share');
      return;
    }
    
    // Get the current conversation to verify it exists
    const conversation = this.conversationManager.findConversation(this.state.conversationId);
    
    if (!conversation) {
      this.showError('No conversation found');
      return;
    }
    
    // Don't upload messages to server - conversations are stored locally
    // The share URL will contain the conversation ID, and when someone joins,
    // they'll retrieve the conversation from the WebSocket connection
    
    // Generate share URL directly to join.html
    const baseUrl = `${window.location.protocol}//${window.location.host}`;
    const shareUrl = `${baseUrl}/static/join.html?conv_id=${this.state.conversationId}`;
    
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
      this.showError('Failed to copy share link');
    });
  }
  
  toggleDebugInfo() {
    // Get all messages from localStorage for current conversation
    const allMessages = JSON.parse(localStorage.getItem('nlweb_messages') || '[]');
    
    // Filter messages for current conversation
    const conversationMessages = this.state.conversationId 
      ? allMessages.filter(msg => msg.conversation_id === this.state.conversationId)
      : allMessages;
    
    // Create modal or overlay to show debug info
    const existingModal = document.getElementById('debug-modal');
    if (existingModal) {
      existingModal.remove();
      document.getElementById('debug-backdrop')?.remove();
      return;
    }
    
    const modal = document.createElement('div');
    modal.id = 'debug-modal';
    modal.style.cssText = `
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 80%;
      max-width: 800px;
      height: 70vh;
      background: white;
      border: 1px solid #ccc;
      border-radius: 8px;
      padding: 20px;
      z-index: 10000;
      box-shadow: 0 4px 20px rgba(0,0,0,0.2);
      display: flex;
      flex-direction: column;
    `;
    
    // Header
    const header = document.createElement('div');
    header.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;';
    header.innerHTML = `
      <h3 style="margin: 0; font-size: 16px;">Debug: Raw Messages (${conversationMessages.length} messages)</h3>
      <button id="close-debug" style="background: transparent; border: none; font-size: 24px; cursor: pointer; padding: 0; width: 30px; height: 30px;">&times;</button>
    `;
    modal.appendChild(header);
    
    // Content area
    const content = document.createElement('pre');
    content.style.cssText = `
      flex: 1;
      overflow: auto;
      background: #f6f8fa;
      padding: 15px;
      border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: 12px;
      line-height: 1.5;
      margin: 0;
    `;
    
    // Format and display messages
    try {
      content.textContent = JSON.stringify(conversationMessages, null, 2);
    } catch (e) {
      content.textContent = 'Error formatting messages: ' + e.message;
    }
    
    modal.appendChild(content);
    
    // Copy button
    const copyBtn = document.createElement('button');
    copyBtn.textContent = 'Copy to Clipboard';
    copyBtn.style.cssText = 'margin-top: 10px; padding: 8px 16px; background: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer;';
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(JSON.stringify(conversationMessages, null, 2));
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = 'Copy to Clipboard'; }, 2000);
    };
    modal.appendChild(copyBtn);
    
    // Add backdrop
    const backdrop = document.createElement('div');
    backdrop.id = 'debug-backdrop';
    backdrop.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0,0,0,0.5);
      z-index: 9999;
    `;
    
    // Close handlers
    const closeModal = () => {
      modal.remove();
      backdrop.remove();
    };
    
    backdrop.onclick = closeModal;
    header.querySelector('#close-debug').onclick = closeModal;
    
    document.body.appendChild(backdrop);
    document.body.appendChild(modal);
  }
}

// Export for use in HTML
window.UnifiedChatInterface = UnifiedChatInterface;
