/**
 * Modern Chat Interface
 * A full-screen chat interface similar to Claude.ai and ChatGPT
 */

import { JsonRenderer } from './json-renderer.js';
import { TypeRendererFactory } from './type-renderers.js';
import { RecipeRenderer } from './recipe-renderer.js';
import { MapDisplay } from './display_map.js';
import { ConversationManager } from './conversation-manager.js';
import { ManagedEventSource } from './managed-event-source.js';
import { ChatUICommon } from './chat-ui-common.js';

class ModernChatInterface {
  constructor(options = {}) {
    
    // Initialize properties
    this.conversationManager = new ConversationManager();
    this.currentConversationId = null;
    this.websocket = null;
    this.wsConversationId = null;
    this.isStreaming = false;
    this.currentStreamingMessage = null;
    this.prevQueries = [];  // Track previous queries
    this.lastAnswers = [];  // Track last answers
    this.rememberedItems = [];  // Track remembered items
    
    // Store options
    this.options = options;
    
    // Initialize UI common library
    this.uiCommon = new ChatUICommon();
    
    // Initialize JSON renderer
    this.jsonRenderer = new JsonRenderer();
    TypeRendererFactory.registerAll(this.jsonRenderer);
    TypeRendererFactory.registerRenderer(RecipeRenderer, this.jsonRenderer);
    
    // Get DOM elements
    this.elements = {
      sidebar: document.getElementById('sidebar'),
      sidebarToggle: document.getElementById('sidebar-toggle'),
      mobileMenuToggle: document.getElementById('mobile-menu-toggle'),
      newChatBtn: document.getElementById('new-chat-btn'),
      conversationsList: document.getElementById('conversations-list'),
      chatTitle: document.querySelector('.chat-title'),
      chatSiteInfo: document.getElementById('chat-site-info'),
      messagesContainer: document.getElementById('messages-container'),
      chatMessages: document.getElementById('chat-messages'),
      chatInput: document.getElementById('chat-input'),
      sendButton: document.getElementById('send-button'),
      shareButton: document.getElementById('shareBtn')
    };
    
    // Debug mode state
    this.debugMode = false;
    this.debugMessages = [];
    
    // Initialize the interface
    this.init();
  }
  
  init() {
    // Initialize default values
    this.selectedSite = this.options.site || 'all';
    this.selectedMode = this.options.mode || 'list'; // Default generate_mode
    
    // Check for join parameter in URL
    const urlParams = new URLSearchParams(window.location.search);
    const joinConvId = urlParams.get('join');
    
    // Load saved conversations from localStorage only
    this.conversationManager.loadLocalConversations(this.selectedSite);
    this.updateConversationsList();
    
    // After loading conversations, decide what to show
    if (!this.options.skipAutoInit) {
      if (joinConvId) {
        // Handle join link
        this.handleJoinLink(joinConvId);
      } else {
        const conversations = this.conversationManager.getConversations();
        
        // Always show centered input for new page loads to match user expectation
        this.showCenteredInput();
      }
    }
    
    // Load remembered items
    this.loadRememberedItems();
    this.updateRememberedItemsList();
    
    // Restore sidebar state
    const isCollapsed = localStorage.getItem('nlweb-sidebar-collapsed') === 'true';
    if (isCollapsed) {
      this.elements.sidebar.classList.add('collapsed');
      this.elements.sidebarToggle.classList.add('sidebar-collapsed');
    }
    
    // Bind events
    this.bindEvents();
    
    // Listen for auth state changes
    window.addEventListener('authStateChanged', async (event) => {
      // When auth state changes, just update UI - no server sync
      // All conversations remain local-only
      
      if (event.detail.isAuthenticated) {
        // User just logged in - keep using local conversations
        this.conversationManager.loadLocalConversations(this.selectedSite);
        this.updateConversationsList();
      } else {
        // User logged out - continue using local conversations
        this.conversationManager.loadLocalConversations(this.selectedSite);
        this.updateConversationsList();
      }
    });
  }
  
  bindEvents() {
    // Sidebar toggle
    this.elements.sidebarToggle.addEventListener('click', () => {
      this.elements.sidebar.classList.toggle('collapsed');
      this.elements.sidebarToggle.classList.toggle('sidebar-collapsed');
      
      // Save state to localStorage
      const isCollapsed = this.elements.sidebar.classList.contains('collapsed');
      localStorage.setItem('nlweb-sidebar-collapsed', isCollapsed);
    });
    
    // Mobile menu toggle
    this.elements.mobileMenuToggle.addEventListener('click', () => {
      this.elements.sidebar.classList.toggle('open');
    });
    
    // New chat button
    this.elements.newChatBtn.addEventListener('click', () => this.createNewChat());
    
    
    // Send button
    this.elements.sendButton.addEventListener('click', () => this.sendMessage());
    
    // Enter key to send
    this.elements.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
    
    // Share button
    const shareBtn = document.getElementById('shareBtn');
    if (shareBtn) {
      shareBtn.addEventListener('click', () => this.shareConversation());
    }
    
    // Auto-resize textarea
    this.elements.chatInput.addEventListener('input', () => {
      this.elements.chatInput.style.height = 'auto';
      this.elements.chatInput.style.height = Math.min(this.elements.chatInput.scrollHeight, 200) + 'px';
    });
    
    // Mode selector
    const modeSelectorIcon = document.getElementById('mode-selector-icon');
    const modeDropdown = document.getElementById('mode-dropdown');
    
    if (modeSelectorIcon && modeDropdown) {
      modeSelectorIcon.addEventListener('click', (e) => {
        e.stopPropagation();
        modeDropdown.classList.toggle('show');
      });
      
      // Mode selection
      const modeItems = modeDropdown.querySelectorAll('.mode-dropdown-item');
      modeItems.forEach(item => {
        item.addEventListener('click', () => {
          const mode = item.getAttribute('data-mode');
          this.selectedMode = mode;
          
          // Update UI
          modeItems.forEach(i => i.classList.remove('selected'));
          item.classList.add('selected');
          modeDropdown.classList.remove('show');
          
          // Update icon title
          modeSelectorIcon.title = `Mode: ${mode.charAt(0).toUpperCase() + mode.slice(1)}`;
        });
      });
      
      // Set initial selection
      const initialItem = modeDropdown.querySelector(`[data-mode="${this.selectedMode}"]`);
      if (initialItem) {
        initialItem.classList.add('selected');
      }
      modeSelectorIcon.title = `Mode: ${this.selectedMode.charAt(0).toUpperCase() + this.selectedMode.slice(1)}`;
    }
    
    // Click outside to close mode dropdown
    document.addEventListener('click', (e) => {
      if (modeDropdown && !e.target.closest('.input-mode-selector')) {
        modeDropdown.classList.remove('show');
      }
    });
  }
  
  shareConversation() {
    if (!this.currentConversationId) return;
    
    const shareUrl = `${window.location.origin}/chat/join/${this.currentConversationId}`;
    
    // Show the share link container
    const shareLinkContainer = document.getElementById('shareLinkContainer');
    const shareLinkInput = document.getElementById('shareLinkInput');
    const copyShareLink = document.getElementById('copyShareLink');
    
    if (shareLinkContainer && shareLinkInput) {
      shareLinkInput.value = shareUrl;
      shareLinkContainer.style.display = 'block';
      
      // Add copy button functionality
      if (copyShareLink) {
        copyShareLink.onclick = () => {
          navigator.clipboard.writeText(shareUrl).then(() => {
            const originalText = copyShareLink.textContent;
            copyShareLink.textContent = 'Copied!';
            setTimeout(() => {
              copyShareLink.textContent = originalText;
            }, 2000);
          });
        };
      }
      
      // Also copy immediately on share button click
      navigator.clipboard.writeText(shareUrl).then(() => {
        // Show success feedback
        const shareBtn = document.getElementById('shareBtn');
        if (shareBtn) {
          const originalHTML = shareBtn.innerHTML;
          shareBtn.innerHTML = '✓ Copied!';
          shareBtn.style.color = 'var(--success-color)';
          
          setTimeout(() => {
            shareBtn.innerHTML = originalHTML;
            shareBtn.style.color = '';
          }, 2000);
        }
      }).catch(err => {
      });
    } else {
      // Fallback if container not found
      navigator.clipboard.writeText(shareUrl).then(() => {
        alert(`Share link copied: ${shareUrl}`);
      }).catch(err => {
        alert(`Share link: ${shareUrl}`);
      });
    }
  }
  
  async createNewChat(existingInputElementId = null, site = null) {
    // Clear current conversation IDs to force creation of new one
    this.currentConversationId = null;
    this.wsConversationId = null;
    
    // Clear UI
    this.elements.messagesContainer.innerHTML = '';
    this.elements.chatTitle.textContent = 'New chat';
    this.elements.chatInput.value = '';
    this.elements.chatInput.style.height = 'auto';
    
    // Hide share link container
    const shareLinkContainer = document.getElementById('shareLinkContainer');
    if (shareLinkContainer) {
      shareLinkContainer.style.display = 'none';
    }
    
    // Clear context arrays for new chat
    this.prevQueries = [];
    this.lastAnswers = [];
    
    // Update UI without saving
    this.updateConversationsList();
    
    // Show centered input for new chat or use existing element
    if (existingInputElementId) {
      // Use existing DOM element as input
      const existingInput = document.getElementById(existingInputElementId);
      if (existingInput) {
        // Store reference to the external input
        this.externalInput = existingInput;
        
        // Add event listener for sending message
        const sendHandler = (e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const message = existingInput.value.trim();
            if (message) {
              this.sendMessage(message);
              existingInput.value = '';
            }
          }
        };
        
        // Remove any existing listeners and add new one
        existingInput.removeEventListener('keydown', sendHandler);
        existingInput.addEventListener('keydown', sendHandler);
        
        // Focus the external input
        existingInput.focus();
      } else {
        this.showCenteredInput();
      }
    } else {
      // Show the default centered input
      this.showCenteredInput();
    }
    
    // If site is specified, use it; otherwise load sites
    if (site) {
      this.selectedSite = site;
      // Update UI elements
      if (this.siteSelectorIcon) {
        this.siteSelectorIcon.title = `Site: ${site}`;
      }
      if (this.elements.chatSiteInfo) {
        this.elements.chatSiteInfo.textContent = `Asking ${site}`;
      }
    } else {
      // Load sites for the dropdown
      this.loadSites();
    }
  }
  
  
  async sendMessage(messageText = null) {
    const message = messageText || this.elements.chatInput.value.trim();
    if (!message || this.isStreaming) return;
    
    // Get user info for sender attribution
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
    const userId = userInfo.id || userInfo.email || this.getOrCreateAnonymousUserId();
    const senderInfo = {
      id: userId,
      name: userInfo.name || userInfo.email || `Anonymous ${userId.slice(-4)}`
    };
    
    // Store the pending message to add to conversation once created
    this.pendingUserMessage = {
      content: message,
      message_type: 'user',
      timestamp: Date.now(),
      senderInfo: senderInfo
    };
    
    // Add user message with sender info
    this.addMessage(message, 'user', senderInfo);
    
    // Clear input
    this.elements.chatInput.value = '';
    this.elements.chatInput.style.height = 'auto';
    
    
    // Get response via WebSocket
    await this.sendViaWebSocket(message);
  }
  
  addMessage(content, type, senderInfo = null) {
    // Add to UI
    this.addMessageToUI(content, type, true, senderInfo);
    
    // Find conversation - don't create here, should be created by server
    let conversation = this.conversationManager.findConversation(this.currentConversationId);
    
    // Only add to conversation if it exists
    if (conversation) {
      // Add message to conversation with sender info
      conversation.messages.push({ 
        message_id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        conversation_id: this.currentConversationId,
        content, 
        message_type: type, 
        timestamp: Date.now(),
        senderInfo: senderInfo 
      });
      
      // Update conversation title from first user message
      if (type === 'user' && (conversation.messages.length === 1 || conversation.title === 'New chat')) {
        conversation.title = content.substring(0, 50) + (content.length > 50 ? '...' : '');
        
        // Update UI element if it exists
        if (this.elements.chatTitle) {
          this.elements.chatTitle.textContent = conversation.title;
        }
        
      }
      
      // Update timestamp
      conversation.timestamp = Date.now();
      
      // Save updated conversations
      this.conversationManager.saveConversations();
      
      // Update UI to show the new conversation
      this.updateConversationsList();
    }
    
    // When user sends a message, we'll add debug icon to the next assistant message
    if (type === 'user') {
      this.pendingDebugIcon = true;
    }
  }
  
  addMessageToUI(content, type, animate = true, senderInfo = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    if (animate) {
      messageDiv.style.opacity = '0';
      messageDiv.style.transform = 'translateY(10px)';
    }
    
    // Create message layout container
    const messageLayout = document.createElement('div');
    messageLayout.className = 'message-layout';
    
    // Only create header row if there's a debug icon to show
    if (type === 'assistant' && this.pendingDebugIcon) {
      const headerRow = document.createElement('div');
      headerRow.className = 'message-layout-header';
      
      const debugIcon = document.createElement('span');
      debugIcon.className = 'message-debug-icon';
      debugIcon.textContent = '{}';
      debugIcon.title = 'Show debug info';
      debugIcon.addEventListener('click', () => this.toggleDebugInfo());
      headerRow.appendChild(debugIcon);
      this.pendingDebugIcon = false;
      
      messageLayout.appendChild(headerRow);
    }
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Add sender name if provided (but not for current user)
    if (senderInfo && senderInfo.name) {
      // Check if this is the current user
      const currentUserInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
      const currentUserId = currentUserInfo.id || currentUserInfo.email || this.getOrCreateAnonymousUserId();
      
      // Only show sender name for other users, not the current user
      if (senderInfo.id !== currentUserId || type !== 'user') {
        const senderDiv = document.createElement('div');
        senderDiv.className = 'message-sender';
        senderDiv.textContent = senderInfo.name;
        contentDiv.appendChild(senderDiv);
      }
    }
    
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    
    // Handle different content types
    if (typeof content === 'string') {
      // For assistant messages with HTML content, use innerHTML
      if (type === 'assistant' && content.includes('<') && content.includes('>')) {
        textDiv.innerHTML = content;
      } else {
        textDiv.textContent = content;
      }
    } else if (content && content.html) {
      textDiv.innerHTML = content.html;
    } else {
      textDiv.textContent = JSON.stringify(content);
    }
    
    contentDiv.appendChild(textDiv);
    
    // Build the message structure
    messageLayout.appendChild(contentDiv);
    messageDiv.appendChild(messageLayout);
    
    this.elements.messagesContainer.appendChild(messageDiv);
    
    if (animate) {
      // Trigger animation
      setTimeout(() => {
        messageDiv.style.transition = 'all 0.3s ease';
        messageDiv.style.opacity = '1';
        messageDiv.style.transform = 'translateY(0)';
      }, 10);
    }
    
    // For user messages, scroll to top of viewport
    if (type === 'user') {
      // Wait a bit for the message to be fully rendered
      setTimeout(() => {
        this.scrollToUserMessage();
      }, 50);
    }
    // For assistant messages, scrolling is handled when first result appears
    
    return { messageDiv, textDiv };
  }
  
  getOrCreateAnonymousUserId() {
    // Check if user is authenticated
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
    const authToken = localStorage.getItem('authToken');
    
    if (authToken && userInfo.id) {
      // User is authenticated, return their ID
      return null;
    }
    
    // Check for existing anonymous user ID
    let anonUserId = sessionStorage.getItem('anonymousUserId');
    if (!anonUserId) {
      // Create new anonymous user ID
      const randomId = Math.floor(Math.random() * 9000) + 1000;
      anonUserId = `anon_${randomId}`;
      sessionStorage.setItem('anonymousUserId', anonUserId);
    }
    
    return anonUserId;
  }
  
  async connectWebSocket(conversationId) {
    
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      if (this.wsConversationId === conversationId) {
        return; // Already connected to this conversation
      }
      this.websocket.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    
    // Build WebSocket URL with auth token or anonymous user ID
    let wsUrl = `${protocol}//${host}/chat/ws/${conversationId}`;
    const authToken = localStorage.getItem('authToken');
    
    if (authToken) {
      // User is authenticated, pass auth token and user info
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
      wsUrl += `?auth_token=${encodeURIComponent(authToken)}`;
      
      // Also pass user info for OAuth tokens that can't be decoded
      if (userInfo.id) {
        wsUrl += `&user_id=${encodeURIComponent(userInfo.id)}`;
        wsUrl += `&user_name=${encodeURIComponent(userInfo.name || userInfo.email || 'User')}`;
        wsUrl += `&provider=${encodeURIComponent(userInfo.provider || 'oauth')}`;
      }
    } else {
      // Add anonymous user ID if not authenticated
      const anonUserId = this.getOrCreateAnonymousUserId();
      if (anonUserId) {
        wsUrl += `?anon_user_id=${encodeURIComponent(anonUserId)}`;
      }
    }
    
    
    this.websocket = new WebSocket(wsUrl);
    this.wsConversationId = conversationId;
    
    return new Promise((resolve, reject) => {
      this.websocket.onopen = () => {
        resolve();
      };
      
      this.websocket.onerror = (error) => {
        reject(error);
      };
      
      this.websocket.onmessage = (event) => {
        // Only log message type, not full data
        try {
          const msgData = JSON.parse(event.data);
        } catch (e) {
        }
        this.handleWebSocketMessage(event);
      };
      
      this.websocket.onclose = () => {
        this.websocket = null;
        this.wsConversationId = null;
      };
    });
  }

  async sendViaWebSocket(query) {
    // Show loading state
    this.isStreaming = true;
    this.elements.sendButton.disabled = true;
    
    // Create conversation locally if we don't have one
    if (!this.currentConversationId) {
      // Get user info for conversation ID
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
      const userId = userInfo.id || userInfo.email || this.getOrCreateAnonymousUserId();
      const userName = userInfo.name || userInfo.email || `Anonymous${userId.slice(-4)}`;
      
      // Create conversation ID with username and timestamp
      const timestamp = Date.now();
      const randomStr = Math.random().toString(36).substr(2, 4);
      this.currentConversationId = `conv_${userName.replace(/[^a-zA-Z0-9]/g, '')}_${timestamp}_${randomStr}`;
      this.wsConversationId = this.currentConversationId;
        
      // Create the conversation locally
      const conversation = {
        id: this.currentConversationId,
        title: 'New chat',
        messages: [],
        timestamp: Date.now(),
        created_at: new Date().toISOString(),
        site: this.selectedSite || 'all',
        mode: this.selectedMode || 'list'
      };
        
      // Add the pending user message if exists
      if (this.pendingUserMessage) {
        // Add conversation_id to the message
        this.pendingUserMessage.conversation_id = this.currentConversationId;
        conversation.messages.push(this.pendingUserMessage);
        // Update title from the user's message
        conversation.title = this.pendingUserMessage.content.substring(0, 50) + 
                           (this.pendingUserMessage.content.length > 50 ? '...' : '');
        
        // Update UI title
        if (this.elements.chatTitle) {
          this.elements.chatTitle.textContent = conversation.title;
        }
        
        // Clear pending message
        this.pendingUserMessage = null;
      }
      
      // Add to conversation manager
      this.conversationManager.addConversation(conversation);
      this.conversationManager.saveConversations();
      
      // Update UI
      this.updateConversationsList();
    }
    
    // Connect to WebSocket if not connected
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN || this.wsConversationId !== this.currentConversationId) {
      try {
        await this.connectWebSocket(this.currentConversationId);
      } catch (error) {
        // Fallback to HTTP streaming
        this.getStreamingResponse(query);
        return;
      }
    }
    
    // Add assistant message with loading dots
    const loadingHtml = `
      <div class="loading-dots">
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
      </div>
    `;
    
    // AI sender info with site
    const site = this.selectedSite || 'all';
    const aiSenderInfo = {
      id: 'nlweb_assistant',
      name: `NLWeb ${site}`
    };
    
    const { messageDiv, textDiv } = this.addMessageToUI({ html: loadingHtml }, 'assistant', true, aiSenderInfo);
    
    // Find the actual message-text div (not the loading dots container)
    const actualTextDiv = messageDiv.querySelector('.message-text');
    
    this.currentStreamingMessage = { 
      messageDiv, 
      textDiv: actualTextDiv || textDiv, 
      content: '', 
      allResults: [],
      resultElements: new Map()
    };
    
    // Build message object
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
    const userId = userInfo.id || userInfo.email || 'anonymous';
    
    const message = {
      type: 'message',
      content: query,
      participant: {
        participant_id: userId,
        display_name: userInfo.name || userInfo.email || 'Anonymous',
        type: 'human'
      },
      sites: [this.selectedSite || 'all'],
      mode: this.selectedMode || 'list',
      metadata: {
        generate_mode: this.selectedMode || 'list',
        display_mode: 'full',
        prev_queries: this.prevQueries.slice(0, 10),
        last_answers: this.lastAnswers.slice(0, 20)
      }
    };
    
    // Add current query to prevQueries for next request
    this.prevQueries.push(query);
    if (this.prevQueries.length > 10) {
      this.prevQueries = this.prevQueries.slice(-10);
    }
    
    // Clear debug messages for new request
    this.debugMessages = [];
    
    // Send message via WebSocket
    this.websocket.send(JSON.stringify(message));
  }
  
  getStreamingResponse(query) {
    // Show loading state
    this.isStreaming = true;
    this.elements.sendButton.disabled = true;
    
    // Add assistant message with loading dots
    const loadingHtml = `
      <div class="loading-dots">
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
      </div>
    `;
    
    // AI sender info with site
    const site = this.selectedSite || 'all';
    const aiSenderInfo = {
      id: 'nlweb_assistant',
      name: `NLWeb ${site}`
    };
    
    const { messageDiv, textDiv } = this.addMessageToUI({ html: loadingHtml }, 'assistant', true, aiSenderInfo);
    
    // Find the actual message-text div (not the loading dots container)
    const actualTextDiv = messageDiv.querySelector('.message-text');
    
    this.currentStreamingMessage = { 
      messageDiv, 
      textDiv: actualTextDiv || textDiv, 
      content: '', 
      allResults: [],
      resultElements: new Map()
    };
    
    // Build URL with parameters
    const params = new URLSearchParams({
      query: query,
      generate_mode: this.selectedMode || 'list',
      display_mode: 'full',
      site: this.selectedSite || 'all'
    });
    
    // Context is tracked server-side in conversation history
    
    if (this.rememberedItems.length > 0) {
      params.append('item_to_remember', this.rememberedItems.join(', '));
    }
    
    // Add auth info if available
    const authToken = localStorage.getItem('authToken');
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
    if (authToken) {
      params.append('auth_token', authToken);
    }
    if (userInfo && userInfo.id) {
      params.append('oauth_id', userInfo.id);
      params.append('user_id', userInfo.id);
    } else if (userInfo && userInfo.email) {
      params.append('oauth_id', userInfo.email);
      params.append('user_id', userInfo.email);
    }
    
    if (this.currentConversationId) {
      params.append('thread_id', this.currentConversationId);
    }
    
    // Create event source using ManagedEventSource
    const baseUrl = window.location.origin === 'file://' ? 'http://localhost:8000' : '';
    const url = `${baseUrl}/ask?${params.toString()}`;
    
    // Use ManagedEventSource for proper message handling
    this.eventSource = new ManagedEventSource(url);
    
    // Set up the chat interface context for ManagedEventSource
    // ManagedEventSource expects certain properties and methods
    this.dotsStillThere = true;
    this.bubble = textDiv;
    this.messagesArea = this.elements.messagesContainer;
    this.currentItems = [];
    this.thisRoundRemembered = null;
    this.thisRoundDecontextQuery = null;
    this.debugMessages = [];
    this.pendingResultBatches = [];
    this.noResponse = true;
    this.scrollDiv = messageDiv;
    this.lastAnswers = this.lastAnswers || [];
    this.num_results_sent = 0;
    this.itemToRemember = [];
    this.decontextualizedQuery = null;
    
    // Methods required by ManagedEventSource
    this.handleFirstMessage = () => {
      textDiv.innerHTML = '';
      this.dotsStillThere = false;
      this.currentStreamingMessage.started = true;
    };
    
    this.createIntermediateMessageHtml = (message) => {
      const div = document.createElement('div');
      div.className = 'intermediate-message';
      div.textContent = message;
      return div;
    };
    
    this.memoryMessage = (message, chatInterface) => {
      const memDiv = this.createIntermediateMessageHtml(`Remembering: ${message}`);
      memDiv.style.fontStyle = 'italic';
      memDiv.style.color = '#666';
      this.bubble.appendChild(memDiv);
    };
    
    this.siteIsIrrelevantToQuery = (message, chatInterface) => {
      const div = this.createIntermediateMessageHtml(message);
      div.style.color = '#888';
      this.bubble.appendChild(div);
    };
    
    this.askUserMessage = (message, chatInterface) => {
      const div = this.createIntermediateMessageHtml(message);
      div.style.fontWeight = 'bold';
      this.bubble.appendChild(div);
    };
    
    this.itemDetailsMessage = (message, chatInterface) => {
      const div = document.createElement('div');
      div.className = 'item-details';
      div.innerHTML = message;
      this.bubble.appendChild(div);
    };
    
    this.possiblyAnnotateUserQuery = (decontextQuery) => {
      // Optional - can be implemented if needed
    };
    
    this.createJsonItemHtml = (item) => {
      return this.renderSingleResult(item);
    };
    
    this.renderItems = (results) => {
      const html = results.map(item => {
        const elem = this.renderSingleResult(item);
        return elem.outerHTML;
      }).join('');
      return html;
    };
    
    this.resortResults = () => {
      // Optional - can be implemented if needed for result sorting
    };
    
    // Connect ManagedEventSource with this as the chat interface
    this.eventSource.connect(this);
  }
  
  handleWebSocketMessage(event) {
    try {
      const data = JSON.parse(event.data);
      
      // Handle different message types
      if (data.type === 'connected') {
        return;
      }
      
      if (data.type === 'error') {
        this.endStreaming();
        return;
      }
      
      // Handle replay messages for new users
      if (data.type === 'replay_start') {
        // Find the AI message div that was just created
        const messages = this.elements.chatMessages.querySelectorAll('.assistant-message');
        const lastMessage = messages[messages.length - 1];
        if (lastMessage) {
          const textDiv = lastMessage.querySelector('.message-bubble');
          if (textDiv) {
            // Store original content and prepare for replay
            const originalContent = textDiv.innerHTML;
            textDiv.innerHTML = '';
            
            // Create a replay context similar to streaming
            this.replayContext = {
              messageDiv: lastMessage,
              textDiv: textDiv,
              content: '',
              allResults: [],
              resultElements: new Map(),
              originalContent: originalContent,
              messageId: data.message_id
            };
          }
        }
        return;
      }
      
      if (data.type === 'replay_end') {
        // Clean up replay context
        if (this.replayContext && this.replayContext.messageId === data.message_id) {
          this.replayContext = null;
        }
        return;
      }
      
      // Handle participant updates (both formats)
      if (data.type === 'participant_update' || data.type === 'participant_joined' || data.type === 'participant_left') {
        const action = data.action || (data.type === 'participant_joined' ? 'join' : 'leave');
        let participantName = null;
        
        // Extract participant info from the nested participant object
        if (data.participant) {
          // Handle different field names
          participantName = data.participant.displayName || data.participant.name;
          const participantType = data.participant.type;
          const participantId = data.participant.participantId || data.participant.id;
          
          // For AI participants, format the name appropriately
          if (participantType === 'ai' || participantId?.startsWith('nlweb')) {
            // Extract site information if available
            const site = data.metadata?.site || data.site || 'Assistant';
            participantName = `NLWeb ${site}`;
          }
        }
        
        // Fallback if no name provided
        if (!participantName) {
          // Use the participant ID to create a more specific name
          const participantId = data.participant?.participantId || data.participant?.id || data.participant_id;
          if (participantId && participantId.startsWith('anon_')) {
            participantName = `Anonymous ${participantId.slice(-4)}`;
          } else {
            participantName = participantId || 'User';
          }
        }
        
        // Check if this is the current user
        const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
        const currentUserId = userInfo.id || userInfo.email || this.getOrCreateAnonymousUserId();
        const participantId = data.participant?.participantId || data.participant?.id || data.participant_id;
        
        // Skip join/leave messages for the current user
        if (participantId === currentUserId) {
          return;
        }
        
        if (action === 'join') {
          this.addSystemMessage(`${participantName} has joined the conversation`);
        } else if (action === 'leave') {
          this.addSystemMessage(`${participantName} has left the conversation`);
        }
        return;
      }
      
      // Handle conversation history (new format for joining users)
      if (data.type === 'conversation_history' && data.messages) {
        
        // Clear existing messages first
        this.elements.chatMessages.innerHTML = '';
        
        // Process each message in order
        data.messages.forEach((msg, index) => {
          const senderInfo = msg.senderInfo || {
            id: msg.type === 'user' ? 'user' : 'nlweb_1',
            name: msg.type === 'user' ? 'User' : 'NLWeb Assistant'
          };
          
          // Add message to UI without animation
          if (msg.type === 'assistant' && msg.content && 
              (msg.content.includes('<') || msg.content.includes('class='))) {
            this.addMessageToUI({ html: msg.content }, msg.type, false, senderInfo);
          } else {
            this.addMessageToUI(msg.content, msg.type, false, senderInfo);
          }
          
          // Update context for assistant messages
          if (msg.type === 'assistant' && msg.parsedAnswers) {
            this.lastAnswers.push(...msg.parsedAnswers);
            // Keep only last 20 answers
            if (this.lastAnswers.length > 20) {
              this.lastAnswers = this.lastAnswers.slice(-20);
            }
          }
        });
        
        // Scroll to bottom after loading history
        setTimeout(() => this.scrollToBottom(), 100);
        
        return;
      }
      
      // Handle messages (both historical and real-time from other participants)
      if (data.type === 'message' && data.message) {
        const msg = data.message;
        
        // Skip if this is our own message (should already be displayed)
        const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
        const currentUserId = userInfo.id || userInfo.email || this.getOrCreateAnonymousUserId();
        if (msg.sender_id === currentUserId) {
          return;
        }
        
        // Check if we're loading a conversation and this is a historical message we already have
        const conversation = this.conversationManager.findConversation(this.currentConversationId);
        if (conversation && conversation.messages) {
          // Check if this message already exists (by checking content and timestamp)
          const messageExists = conversation.messages.some(m => {
            // Convert timestamps for comparison
            const msgTimestamp = new Date(msg.timestamp).getTime();
            const existingTimestamp = m.timestamp;
            // Check if timestamps are within 1 second of each other and content matches
            return Math.abs(msgTimestamp - existingTimestamp) < 1000 && 
                   m.content === msg.content;
          });
          
          if (messageExists) {
            return;
          }
        }
        
        // Extract site for AI messages - handle both old and new message formats
        const msgSenderId = msg.senderInfo?.id || msg.sender_id;
        const msgSenderName = msg.senderInfo?.name || msg.sender_name;
        
        let displayName = msgSenderName;
        if (msgSenderId && msgSenderId.startsWith('nlweb')) {
          const site = msg.metadata?.site || this.selectedSite || 'all';
          displayName = `NLWeb ${site}`;
        } else if (!displayName) {
          displayName = 'User';
        }
        
        const senderInfo = {
          id: msgSenderId || 'unknown',
          name: displayName
        };
        const messageType = msg.message_type || (msgSenderId && msgSenderId.startsWith('nlweb') ? 'assistant' : 'user');
        
        // Check if this is a real-time message (has higher sequence_id than our last known)
        const isRealTime = true; // For now, treat all incoming messages as real-time
        
        // For assistant messages with HTML content, pass as object
        if (messageType === 'assistant' && msg.content && 
            (msg.content.includes('<') || msg.content.includes('class='))) {
          this.addMessageToUI({ html: msg.content }, messageType, isRealTime, senderInfo);
        } else {
          // Animate real-time messages, don't animate historical
          this.addMessageToUI(msg.content, messageType, isRealTime, senderInfo);
        }
        
        // Update conversation in memory (reuse the conversation variable from above)
        if (conversation) {
          conversation.messages.push({
            message_id: msg.message_id || `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            conversation_id: this.currentConversationId,
            content: msg.content,
            message_type: messageType,
            timestamp: new Date(msg.timestamp).getTime(),
            senderInfo: senderInfo
          });
          this.conversationManager.saveConversations();
        }
        
        return;
      }
      
      // Handle streaming data (from both EventSource and WebSocket)
      if (data.message_type) {
        // Check if this is a replay message
        if (data.is_replay && this.replayContext) {
          // Use replay context instead of current streaming context
          const savedContext = this.currentStreamingMessage;
          this.currentStreamingMessage = this.replayContext;
          
          // Process the streaming data
          this.handleStreamingData(data);
          
          // Restore original context
          this.currentStreamingMessage = savedContext;
        } else if (!data.is_replay) {
          // Regular live streaming
          
          // If no currentStreamingMessage exists, this is an AI response from another participant
          // Create the UI elements for it
          if (!this.currentStreamingMessage && data.message_type !== 'complete') {
            
            // Create AI message UI
            const loadingHtml = '<div class="loading-dots"><span></span><span></span><span></span></div>';
            const aiSenderInfo = {
              id: 'nlweb_assistant',
              name: 'NLWeb Assistant'
            };
            
            const { messageDiv, textDiv } = this.addMessageToUI({ html: loadingHtml }, 'assistant', true, aiSenderInfo);
            
            // Find the actual message-text div (not the loading dots container)
            const actualTextDiv = messageDiv.querySelector('.message-text');
            
            this.currentStreamingMessage = { 
              messageDiv, 
              textDiv: actualTextDiv || textDiv, 
              content: '', 
              allResults: [],
              resultElements: new Map(),
              fromWebSocket: true  // Mark as WebSocket origin
            };
          }
          
          if (data.message_type === 'result_batch' || data.message_type === 'item_details') {
          }
          
          // Only process if we have a streaming context
          if (this.currentStreamingMessage) {
            this.handleStreamingData(data);
          }
        }
      }
    } catch (error) {
    }
  }
  
  handleStreamingData(data) {
    // Shared handler for both EventSource and WebSocket streaming data
    if (!this.currentStreamingMessage) {
      // Special case: handle 'complete' message even without context
      if (data.message_type === 'complete') {
        this.endStreaming();
      }
      return;
    }
    
    const { textDiv } = this.currentStreamingMessage;
    
    // Clear loading dots on first real content
    if (!this.currentStreamingMessage.started) {
      textDiv.innerHTML = '';
      this.currentStreamingMessage.started = true;
    }
    
    // Store debug messages
    this.debugMessages.push({
      type: data.message_type || 'unknown',
      data: data,
      timestamp: new Date().toISOString()
    });
    
    // Use the common UI library to process the message
    const context = {
      messageContent: this.currentStreamingMessage.content || '',
      allResults: this.currentStreamingMessage.allResults || []
    };
    
    const result = this.uiCommon.processMessageByType(data, textDiv, context);
    
    // Update current streaming message
    if (this.currentStreamingMessage) {
      this.currentStreamingMessage.content = result.messageContent;
      this.currentStreamingMessage.allResults = result.allResults;
    }
    
    // Check if this is a completion message
    if (data.message_type === 'complete') {
      this.endStreaming();
    }
  }

  
  handleStreamingMessageWithResult(data, textDiv, messageContent, allResults) {
    // Create a context object to pass by reference
    const context = {
      messageContent: messageContent,
      allResults: allResults
    };
    
    this.handleStreamingMessage(data, textDiv, context);
    
    return {
      messageContent: context.messageContent,
      allResults: context.allResults
    };
  }
  
  handleStreamingMessage(data, textDiv, context) {
    let { messageContent, allResults } = context;
    // Handle different message types
        
    // Scroll to user message when first actual result appears
    if (data.message_type === 'fast_track' || 
        (data.message_type === 'content' && data.content) || 
        (data.items && data.items.length > 0)) {
      this.scrollToUserMessage();
    }
        
        // Always clear temp_intermediate divs when ANY new message arrives
        if (textDiv) {
          const tempDivs = textDiv.querySelectorAll('.temp_intermediate');
          tempDivs.forEach(div => div.remove());
        }
        
        // Handle different message types
        if (data.message_type === 'summary' && data.message) {
          messageContent += data.message + '\n\n';
          context.messageContent = messageContent;
          textDiv.innerHTML = messageContent + this.renderItems(allResults);
        } else if (data.message_type === 'result_batch' && data.results) {
          // Accumulate all results instead of replacing
          allResults = allResults.concat(data.results);
          context.allResults = allResults;
          const renderedHtml = this.renderItems(allResults);
          textDiv.innerHTML = messageContent + renderedHtml;
          // Force display the element
          textDiv.style.display = 'block';
          textDiv.style.visibility = 'visible';
          textDiv.style.opacity = '1';
          // Check parent elements
          const messageBubble = textDiv.closest('.message-bubble');
          if (messageBubble) {
            messageBubble.style.display = 'block';
          }
          const messageDiv = textDiv.closest('.message');
          if (messageDiv) {
          }
        } else if (data.message_type === 'intermediate_message') {
          // Handle intermediate messages with temp_intermediate class
          const tempContainer = document.createElement('div');
          tempContainer.className = 'temp_intermediate';
          
          if (data.results) {
            // Use the same rendering as result_batch
            tempContainer.innerHTML = this.renderItems(data.results);
          } else if (data.message) {
            // Handle text-only intermediate messages in italics
            const textSpan = document.createElement('span');
            textSpan.style.fontStyle = 'italic';
            textSpan.textContent = data.message;
            tempContainer.appendChild(textSpan);
          }
          
          // Update textDiv to include existing content plus the temp container
          textDiv.innerHTML = messageContent + this.renderItems(allResults);
          textDiv.appendChild(tempContainer);
        } else if (data.message_type === 'ask_user' && data.message) {
          messageContent += data.message + '\n';
          context.messageContent = messageContent;
          textDiv.innerHTML = messageContent + this.renderItems(allResults);
        } else if (data.message_type === 'asking_sites' && data.message) {
          messageContent += `Searching: ${data.message}\n\n`;
          context.messageContent = messageContent;
          textDiv.innerHTML = messageContent + this.renderItems(allResults);
        } else if (data.message_type === 'decontextualized_query') {
          // Display the decontextualized query if different from original
          if (data.decontextualized_query && data.original_query && 
              data.decontextualized_query !== data.original_query) {
            const decontextMsg = `<div style="font-style: italic; color: #666; margin-bottom: 10px;">Query interpreted as: "${data.decontextualized_query}"</div>`;
            messageContent = decontextMsg + messageContent;
            context.messageContent = messageContent;
            textDiv.innerHTML = messageContent + this.renderItems(allResults);
          }
        } else if (data.message_type === 'item_details') {
          // Handle item_details message type
          // Map details to description for proper rendering
          let description = data.details;
          
          // If details is an object (like nutrition info), format it as a string
          if (typeof data.details === 'object' && data.details !== null) {
            description = Object.entries(data.details)
              .map(([key, value]) => `${key}: ${value}`)
              .join(', ');
          }
          
          const mappedData = {
            ...data,
            description: description
          };
          
          // Add to results array
          allResults.push(mappedData);
          context.allResults = allResults;
          textDiv.innerHTML = messageContent + this.renderItems(allResults);
        } else if (data.message_type === 'ensemble_result') {
          // Handle ensemble result message type
          if (data.result && data.result.recommendations) {
            const ensembleHtml = this.renderEnsembleResult(data.result);
            textDiv.innerHTML = messageContent + ensembleHtml + this.renderItems(allResults);
          }
        } else if (data.message_type === 'remember' && data.item_to_remember) {
          // Handle remember message
          const rememberMsg = `<div style="background-color: #e8f4f8; padding: 10px; border-radius: 6px; margin-bottom: 10px; color: #0066cc;">I will remember that</div>`;
          messageContent = rememberMsg + messageContent;
          context.messageContent = messageContent;
          textDiv.innerHTML = messageContent + this.renderItems(allResults);
          
          // Add to remembered items
          this.addRememberedItem(data.item_to_remember);
        } else if (data.message_type === 'query_analysis') {
          // Handle query analysis which may include decontextualized query
          if (data.decontextualized_query && query && 
              data.decontextualized_query !== query) {
            const decontextMsg = `<div style="font-style: italic; color: #666; margin-bottom: 10px;">Query interpreted as: "${data.decontextualized_query}"</div>`;
            messageContent = decontextMsg + messageContent;
            context.messageContent = messageContent;
            textDiv.innerHTML = messageContent + this.renderItems(allResults);
          }
          
          // Also check for item_to_remember in query_analysis
          if (data.item_to_remember) {
            const rememberMsg = `<div style="background-color: #e8f4f8; padding: 10px; border-radius: 6px; margin-bottom: 10px; color: #0066cc;">I will remember that: "${data.item_to_remember}"</div>`;
            messageContent = rememberMsg + messageContent;
            context.messageContent = messageContent;
            textDiv.innerHTML = messageContent + this.renderItems(allResults);
            
            // Add to remembered items
            this.addRememberedItem(data.item_to_remember);
          }

        } else if (data.message_type === 'api_key') {
          // Handle API key configuration EARLY to ensure it's available for maps
          if (data.key_name === 'google_maps' && data.key_value) {
            // Store the Google Maps API key globally
            window.GOOGLE_MAPS_API_KEY = data.key_value;
            // Verify it's actually set
          } else {
          }
          
        } else if (data.message_type === 'nlws') {
          // Handle NLWS message type (Natural Language Web Search synthesized response)
          
          // Update the answer if provided
          if (data.answer && typeof data.answer === 'string') {
            messageContent = data.answer + '\n\n';
            context.messageContent = messageContent;
          }
          
          // Update the items if provided
          if (data.items && Array.isArray(data.items)) {
            allResults = data.items;
            context.allResults = allResults;
          }
          
          // Always update the display with current answer and items
          textDiv.innerHTML = messageContent + this.renderItems(allResults);
          
        } else if (data.message_type === 'chart_result') {
          // Handle chart result (web components)
          
          if (data.html) {
            // Create container for the chart
            const chartContainer = document.createElement('div');
            chartContainer.className = 'chart-result-container';
            chartContainer.style.cssText = 'margin: 15px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px; min-height: 400px;';
            
            // Parse the HTML to extract just the web component (remove script tags)
            const parser = new DOMParser();
            const doc = parser.parseFromString(data.html, 'text/html');
            
            // Find all datacommons elements
            const datacommonsElements = doc.querySelectorAll('[datacommons-scatter], [datacommons-bar], [datacommons-line], [datacommons-pie], [datacommons-map], datacommons-scatter, datacommons-bar, datacommons-line, datacommons-pie, datacommons-map');
            
            // Append each web component directly
            datacommonsElements.forEach(element => {
              // Clone the element to ensure we get all attributes
              const clonedElement = element.cloneNode(true);
              chartContainer.appendChild(clonedElement);
            });
            
            // If no datacommons elements found, try to add the raw HTML (excluding scripts)
            if (datacommonsElements.length === 0) {
              const allElements = doc.body.querySelectorAll('*:not(script)');
              allElements.forEach(element => {
                chartContainer.appendChild(element.cloneNode(true));
              });
            }
            
            // Append the chart to the message content
            textDiv.innerHTML = messageContent + this.renderItems(allResults);
            textDiv.appendChild(chartContainer);
            
            
            // Force re-initialization of Data Commons components if available
            if (window.datacommons && window.datacommons.init) {
              setTimeout(() => {
                window.datacommons.init();
              }, 100);
            }
          }

        } else if (data.message_type === 'results_map') {
          // Handle results map
          
          if (data.locations && Array.isArray(data.locations) && data.locations.length > 0) {
            
            // Create container for the map
            const mapContainer = document.createElement('div');
            mapContainer.className = 'results-map-container';
            mapContainer.style.cssText = 'margin: 15px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px;';
            
            // Create the map div
            const mapDiv = document.createElement('div');
            mapDiv.id = 'results-map-' + Date.now();
            mapDiv.style.cssText = 'width: 100%; height: 250px; border-radius: 6px;';
            
            // Add a title
            const mapTitle = document.createElement('h3');
            mapTitle.textContent = 'Result Locations';
            mapTitle.style.cssText = 'margin: 0 0 10px 0; color: #333; font-size: 1.1em;';
            
            mapContainer.appendChild(mapTitle);
            mapContainer.appendChild(mapDiv);
            
            // Prepend map BEFORE the results
            textDiv.innerHTML = ''; // Clear existing content
            textDiv.appendChild(mapContainer); // Add map first
            
            // Then add the message content and results
            const contentDiv = document.createElement('div');
            contentDiv.innerHTML = messageContent + this.renderItems(allResults);
            textDiv.appendChild(contentDiv);
            
            
            // Initialize the map using the imported MapDisplay class
            MapDisplay.initializeResultsMap(mapDiv, data.locations);
          } else {
          }

        } else if (data.message_type === 'complete') {
          this.endStreaming();
          return; // Exit early to avoid setting content on null
        }
        
        // Only update content if streaming message still exists
        if (this.currentStreamingMessage) {
          this.currentStreamingMessage.content = messageContent;
          this.currentStreamingMessage.allResults = allResults;
        }
  }
  
  handleNLWSMessage(nlwsData, textDiv, messageContent, allResults) {
    // Handle NLWS formatted messages
    if (nlwsData.answer && typeof nlwsData.answer === 'string') {
      messageContent = nlwsData.answer + '\n\n';
    }
    
    if (nlwsData.items && Array.isArray(nlwsData.items)) {
      allResults = nlwsData.items;
    }
    
    textDiv.innerHTML = messageContent + this.renderItems(allResults);
    
    // Update streaming message state
    this.currentStreamingMessage.content = messageContent;
    this.currentStreamingMessage.allResults = allResults;
  }
  
  renderItems(items) {
    // Delegate to the common UI library
    return this.uiCommon.renderItems(items);
  }
  
  renderEnsembleResult(result) {
    // Delegate to the common UI library
    return this.uiCommon.renderEnsembleResult(result);
  }
  
  endStreaming() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    
    this.isStreaming = false;
    this.elements.sendButton.disabled = false;
    
    // Save the final message
    if (this.currentStreamingMessage) {
      const finalContent = this.currentStreamingMessage.textDiv.innerHTML || this.currentStreamingMessage.content;
      const conversation = this.conversationManager.findConversation(this.currentConversationId);
      if (conversation) {
        // Extract answers (title and URL) from the accumulated results
        const parsedAnswers = [];
        if (this.currentStreamingMessage.allResults && Array.isArray(this.currentStreamingMessage.allResults)) {
          for (const item of this.currentStreamingMessage.allResults) {
            if ((item.title || item.name) && item.url) {
              parsedAnswers.push({
                title: item.title || item.name,
                url: item.url
              });
            }
          }
        }
        
        // Update global lastAnswers array (keep last 20)
        if (parsedAnswers.length > 0) {
          this.lastAnswers = [...parsedAnswers, ...this.lastAnswers].slice(0, 20);
        }
        
        // Update the last assistant message
        const lastMessage = conversation.messages[conversation.messages.length - 1];
        if (lastMessage && lastMessage.type === 'assistant') {
          lastMessage.content = finalContent;
          lastMessage.parsedAnswers = parsedAnswers;
        } else {
          // AI sender info with site
          const site = this.selectedSite || 'all';
          const aiSenderInfo = {
            id: 'nlweb_assistant',
            name: `NLWeb ${site}`
          };
          conversation.messages.push({ 
            message_id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            conversation_id: this.currentConversationId,
            content: finalContent, 
            message_type: 'assistant', 
            timestamp: Date.now(),
            parsedAnswers: parsedAnswers,
            senderInfo: aiSenderInfo
          });
        }
        this.conversationManager.saveConversations();
        // Update UI to reflect the AI response
        this.updateConversationsList();
      }
    }
    
    this.currentStreamingMessage = null;
  }

  /**
   * Updates the list of conversations displayed in the UI.
   * 
   * @param {HTMLElement|null} container - The container element where the conversations list will be rendered.
   *                                       If null, defaults to `this.elements.conversationsList`.
   */
  updateConversationsList(container = null) {
    this.conversationManager.updateConversationsList(this, container);
  }

  deleteConversation(conversationId) {
    this.conversationManager.deleteConversation(conversationId, this);
  }
  
  scrollToBottom() {
    this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
  }

  scrollToUserMessage() {
    // Find the last user message
    const userMessages = this.elements.messagesContainer.querySelectorAll('.user-message');
    if (userMessages.length > 0) {
      const lastUserMessage = userMessages[userMessages.length - 1];
      
      // Always scroll to put the user message at the top of the viewport
      // This ensures consistent positioning for follow-up queries
      lastUserMessage.scrollIntoView({ behavior: 'smooth', block: 'start' });
      
      // Add a small offset from the top (e.g., 20px padding)
      setTimeout(() => {
        this.elements.chatMessages.scrollTop -= 20;
      }, 100);
    }
  }
  
  showCenteredInput() {
    // This method should delegate to UI common library
    // TODO: Move DOM manipulation to chat-ui-common.js
  }
  
  hideCenteredInput() {
    // This method should delegate to UI common library
    // TODO: Move DOM manipulation to chat-ui-common.js
  }
  
  sendFromCenteredInput() {
    // This method should delegate to UI common library  
    // TODO: Move DOM manipulation to chat-ui-common.js
  }
  
  async handleJoinLink(conversationId) {
    try {
      // Get user info
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
      const authToken = localStorage.getItem('authToken');
    
    if (itemUrl) {
      const nameLink = document.createElement('a');
      nameLink.href = itemUrl;
      nameLink.textContent = item.name;
      nameLink.target = '_blank';
      nameLink.style.cssText = 'color: #0066cc; text-decoration: none; font-weight: bold;';
      nameLink.onmouseover = function() { this.style.textDecoration = 'underline'; };
      nameLink.onmouseout = function() { this.style.textDecoration = 'none'; };
      nameContainer.appendChild(nameLink);
    } else {
      nameContainer.textContent = item.name;
      nameContainer.style.color = '#333';
    }
    
    contentContainer.appendChild(nameContainer);
    
    // Description
    if (item.description) {
      const description = document.createElement('p');
      description.textContent = item.description;
      description.style.cssText = 'color: #666; margin: 10px 0; line-height: 1.5;';
      contentContainer.appendChild(description);
    }
    
    // Why recommended
    if (item.why_recommended) {
      const whySection = document.createElement('div');
      whySection.style.cssText = 'background-color: #e8f4f8; padding: 10px; border-radius: 4px; margin: 10px 0;';
      
      const whyLabel = document.createElement('strong');
      whyLabel.textContent = 'Why recommended: ';
      whyLabel.style.cssText = 'color: #0066cc;';
      
      const whyText = document.createElement('span');
      whyText.textContent = item.why_recommended;
      whyText.style.cssText = 'color: #555;';
      
      whySection.appendChild(whyLabel);
      whySection.appendChild(whyText);
      contentContainer.appendChild(whySection);
    }
    
    // Details
    if (item.details && Object.keys(item.details).length > 0) {
      const detailsSection = document.createElement('div');
      detailsSection.style.cssText = 'margin-top: 10px; font-size: 0.9em;';
      
      Object.entries(item.details).forEach(([key, value]) => {
        const detailLine = document.createElement('div');
        detailLine.style.cssText = 'color: #777; margin: 3px 0;';
        
        const detailKey = document.createElement('strong');
        detailKey.textContent = `${key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')}: `;
        detailKey.style.cssText = 'color: #555;';
        
        const detailValue = document.createElement('span');
        detailValue.textContent = value;
        
        detailLine.appendChild(detailKey);
        detailLine.appendChild(detailValue);
        detailsSection.appendChild(detailLine);
      });
      
      contentContainer.appendChild(detailsSection);
    }
    
    // Additional info from schema_object
    if (item.schema_object) {
      // Price
      if (item.schema_object.price || (item.schema_object.offers && item.schema_object.offers.price)) {
        const priceDiv = document.createElement('div');
        priceDiv.style.cssText = 'margin-top: 10px; font-weight: bold; color: #28a745;';
        const price = item.schema_object.price || item.schema_object.offers.price;
        priceDiv.textContent = `Price: ${typeof price === 'object' ? price.value : price}`;
        contentContainer.appendChild(priceDiv);
      }
      
      // Rating
      if (item.schema_object.aggregateRating) {
        const rating = item.schema_object.aggregateRating;
        const ratingValue = rating.ratingValue || rating.value;
        const reviewCount = rating.reviewCount || rating.ratingCount || rating.count;
        
        if (ratingValue) {
          const ratingDiv = document.createElement('div');
          ratingDiv.style.cssText = 'margin-top: 5px; color: #f39c12;';
          const stars = '★'.repeat(Math.round(ratingValue));
          const reviewText = reviewCount ? ` (${reviewCount} reviews)` : '';
          ratingDiv.innerHTML = `Rating: ${stars} ${ratingValue}/5${reviewText}`;
          contentContainer.appendChild(ratingDiv);
        }
      }
    }
    
    // Append content container to flex container
    flexContainer.appendChild(contentContainer);
    
    // Add image from schema_object if available (on the right side)
    if (item.schema_object) {
      const imageUrl = this.extractImageUrl(item.schema_object);
      
      if (imageUrl) {
        const imageContainer = document.createElement('div');
        imageContainer.style.cssText = 'flex-shrink: 0; display: flex; align-items: center;';
        
        const image = document.createElement('img');
        image.src = imageUrl;
        image.alt = item.name;
        image.style.cssText = 'width: 120px; height: 120px; object-fit: cover; border-radius: 6px;';
        imageContainer.appendChild(image);
        flexContainer.appendChild(imageContainer);
      }
    }
    
    // Append flex container to card
    card.appendChild(flexContainer);
    
    return card;
  }
  
    
    // Check various possible image fields
    if (schema_object.image) {
      return this.extractImageUrlFromField(schema_object.image);
    } else if (schema_object.images && Array.isArray(schema_object.images) && schema_object.images.length > 0) {
      return this.extractImageUrlFromField(schema_object.images[0]);
    } else if (schema_object.thumbnailUrl) {
      return this.extractImageUrlFromField(schema_object.thumbnailUrl);
    } else if (schema_object.thumbnail) {
      return this.extractImageUrlFromField(schema_object.thumbnail);
    }
    
    return null;
  }
  
    
    // Handle object with url property
    if (typeof imageField === 'object' && imageField !== null) {
      if (imageField.url) {
        return imageField.url;
      }
      if (imageField.contentUrl) {
        return imageField.contentUrl;
      }
      if (imageField['@id']) {
        return imageField['@id'];
      }
    }
    
    // Handle array of images
    if (Array.isArray(imageField) && imageField.length > 0) {
      return this.extractImageUrlFromField(imageField[0]);
    }
    
    return null;
  }
    this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
  }
  
  scrollToUserMessage() {
    // Find the last user message
    const userMessages = this.elements.messagesContainer.querySelectorAll('.user-message');
    if (userMessages.length > 0) {
      const lastUserMessage = userMessages[userMessages.length - 1];
      
      // Always scroll to put the user message at the top of the viewport
      // This ensures consistent positioning for follow-up queries
      lastUserMessage.scrollIntoView({ behavior: 'smooth', block: 'start' });
      
      // Add a small offset from the top (e.g., 20px padding)
      setTimeout(() => {
        this.elements.chatMessages.scrollTop -= 20;
      }, 100);
    }
  }
  
  showCenteredInput() {
    // Remove any existing centered input first
    const existingCentered = document.querySelector('.centered-input-container');
    if (existingCentered) {
      existingCentered.remove();
    }
    
    // Hide the normal chat input area
    const chatInputContainer = document.querySelector('.chat-input-container');
    if (chatInputContainer) {
      chatInputContainer.style.display = 'none';
    }
    
    // Create centered input container
    const centeredContainer = document.createElement('div');
    centeredContainer.className = 'centered-input-container';
    centeredContainer.innerHTML = `
      <div class="centered-input-wrapper">
        <div class="centered-input-box">
          <div class="input-box-top-row">
            <textarea 
              class="centered-chat-input" 
              id="centered-chat-input"
              placeholder="Ask"
              rows="2"
            ></textarea>
            <button class="centered-send-button" id="centered-send-button">
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
                  <!-- Sites will be added here -->
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
    
    // Add to messages area
    this.elements.messagesContainer.appendChild(centeredContainer);
    
    // Store references
    this.centeredInput = document.getElementById('centered-chat-input');
    this.centeredSendButton = document.getElementById('centered-send-button');
    this.siteSelectorIcon = document.getElementById('site-selector-icon');
    this.siteDropdown = document.getElementById('site-dropdown');
    this.siteDropdownItems = document.getElementById('site-dropdown-items');
    
    // Bind events for centered input
    this.centeredSendButton.addEventListener('click', () => this.sendFromCenteredInput());
    
    // Site selector events
    this.siteSelectorIcon.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleSiteDropdown();
    });
    
    // Mode selector events for centered input
    const centeredModeSelectorIcon = document.getElementById('centered-mode-selector-icon');
    const centeredModeDropdown = document.getElementById('centered-mode-dropdown');
    
    if (centeredModeSelectorIcon && centeredModeDropdown) {
      centeredModeSelectorIcon.addEventListener('click', (e) => {
        e.stopPropagation();
        centeredModeDropdown.classList.toggle('show');
      });
      
      // Mode selection
      const modeItems = centeredModeDropdown.querySelectorAll('.mode-dropdown-item');
      modeItems.forEach(item => {
        item.addEventListener('click', () => {
          const mode = item.getAttribute('data-mode');
          this.selectedMode = mode;
          
          // Update UI
          modeItems.forEach(i => i.classList.remove('selected'));
          item.classList.add('selected');
          centeredModeDropdown.classList.remove('show');
          
          // Update icon title
          centeredModeSelectorIcon.title = `Mode: ${mode.charAt(0).toUpperCase() + mode.slice(1)}`;
        });
      });
      
      // Set initial selection
      const initialItem = centeredModeDropdown.querySelector(`[data-mode="${this.selectedMode}"]`);
      if (initialItem) {
        initialItem.classList.add('selected');
      }
      centeredModeSelectorIcon.title = `Mode: ${this.selectedMode.charAt(0).toUpperCase() + this.selectedMode.slice(1)}`;
    }
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!this.siteDropdown.contains(e.target) && !this.siteSelectorIcon.contains(e.target)) {
        this.siteDropdown.classList.remove('show');
      }
      if (centeredModeDropdown && !e.target.closest('.input-mode-selector')) {
        centeredModeDropdown.classList.remove('show');
      }
    });
    
    this.centeredInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendFromCenteredInput();
      }
    });
    
    // Auto-resize centered textarea
    this.centeredInput.addEventListener('input', () => {
      this.centeredInput.style.height = 'auto';
      this.centeredInput.style.height = Math.min(this.centeredInput.scrollHeight, 150) + 'px';
    });
    
    // Focus the input
    this.centeredInput.focus();
    
    // Load sites if not already loaded AND no specific site is selected
    if ((!this.sites || this.sites.length === 0) && (!this.selectedSite || this.selectedSite === 'all')) {
      this.loadSites();
    } else {
      // If sites are already loaded, populate the dropdown
      this.populateSiteDropdown();
    }
  }
  
  hideCenteredInput() {
    const centeredContainer = document.querySelector('.centered-input-container');
    if (centeredContainer) {
      centeredContainer.remove();
    }
    
    // Show the normal chat input area
    const chatInputContainer = document.querySelector('.chat-input-container');
    if (chatInputContainer) {
      chatInputContainer.style.display = '';
    }
  }
  
  sendFromCenteredInput() {
    const message = this.centeredInput.value.trim();
    if (!message) return;
    
    // Hide centered input
    this.hideCenteredInput();
    
    // Send the message using the normal flow
    this.sendMessage(message);
  }
  
  async handleJoinLink(conversationId) {
    try {
      // Get user info
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
      const authToken = localStorage.getItem('authToken');
      
      // Check if user is authenticated
      if (!authToken || !userInfo.id) {
        // Store the conversation ID for retry after login
        window.pendingJoinConversationId = conversationId;
        
        // Show login popup
        if (window.oauthManager) {
          window.oauthManager.showLoginPopup();
        }
        
        // Listen for successful login to retry join
        const retryJoinHandler = (event) => {
          if (event.detail.conversationId === conversationId) {
            window.removeEventListener('retryJoin', retryJoinHandler);
            this.handleJoinLink(conversationId);
          }
        };
        window.addEventListener('retryJoin', retryJoinHandler);
        
        return;
      }
      
      // Prepare participant info
      const participant = {
        user_id: userInfo.id || userInfo.email,
        name: userInfo.name || userInfo.email || 'User'
      };
      
      // Call the join API
      const baseUrl = window.location.origin === 'file://' ? 'http://localhost:8000' : '';
      const response = await fetch(`${baseUrl}/chat/join/${conversationId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {})
        },
        body: JSON.stringify({ participant })
      });
      
      if (response.ok) {
        const data = await response.json();
        
        // Add conversation to local storage
        const conversation = {
          id: data.conversation.id,
          title: data.conversation.title || 'Shared Chat',
          messages: [],
          timestamp: Date.now(),
          created_at: new Date().toISOString(),
          site: 'all',
          shared: true
        };
        
        // Add messages if any
        if (data.messages && data.messages.length > 0) {
          data.messages.forEach(msg => {
            // Extract site for AI messages
            let displayName = msg.sender_name;
            if (msg.sender_id.startsWith('nlweb')) {
              const site = conversation.site || this.selectedSite || 'all';
              displayName = `NLWeb ${site}`;
            } else if (!displayName) {
              displayName = 'User';
            }
            
            const senderInfo = {
              id: msg.sender_id,
              name: displayName
            };
            conversation.messages.push({
              message_id: msg.message_id || `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              conversation_id: conversation.id,
              content: msg.content,
              message_type: msg.sender_id.startsWith('nlweb') ? 'assistant' : 'user',
              timestamp: new Date(msg.timestamp).getTime(),
              senderInfo: senderInfo
            });
          });
        }
        
        this.conversationManager.addConversation(conversation);
        this.conversationManager.saveConversations();
        
        // Load the conversation
        this.conversationManager.loadConversation(conversationId, this);
        
        // Connect to WebSocket
        await this.connectWebSocket(conversationId);
        
        // Show success message
        this.addSystemMessage(`Successfully joined conversation: ${data.conversation.title || 'Shared Chat'}`);
      } else {
        const error = await response.json();
        throw new Error(error.error || 'Failed to join conversation');
      }
    } catch (error) {
      this.addSystemMessage(`Error joining conversation: ${error.message}`);
      // Show centered input as fallback
      this.showCenteredInput();
    }
  }
  
  addSystemMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system-message';
    messageDiv.innerHTML = `
      <div class="message-content">
        <div class="message-text">${message}</div>
      </div>
    `;
    this.elements.messagesContainer.appendChild(messageDiv);
    this.scrollToBottom();
  }
  
  toggleDebugInfo() {
    // Find the last assistant message
    const assistantMessages = this.elements.messagesContainer.querySelectorAll('.assistant-message');
    if (assistantMessages.length === 0) return;
    
    const lastAssistantMessage = assistantMessages[assistantMessages.length - 1];
    const messageContent = lastAssistantMessage.querySelector('.message-content');
    const messageText = lastAssistantMessage.querySelector('.message-text');
    
    if (!messageContent || !messageText) return;
    
    // Check if we're currently showing debug info
    const isShowingDebug = messageText.classList.contains('showing-debug');
    
    if (isShowingDebug) {
      // Restore original HTML content
      const originalContent = messageText.getAttribute('data-original-content');
      if (originalContent) {
        messageText.textContent = originalContent;
        messageText.classList.remove('showing-debug');
        messageText.style.cssText = ''; // Reset inline styles
      }
    } else {
      // Store original content and show debug info
      messageText.setAttribute('data-original-content', messageText.innerHTML);
      messageText.classList.add('showing-debug');
      
      // Create pretty formatted debug content
      const debugHtml = this.createDebugString();
      
      // Replace content with debug info
      messageText.innerHTML = debugHtml;
    }
  }
  
  createDebugString() {
    let debugHtml = '<div style="font-family: ui-monospace, SFMono-Regular, \'SF Mono\', Consolas, \'Liberation Mono\', Menlo, monospace; font-size: 13px; line-height: 1.5;">';
    
    // MCP-style header
    debugHtml += '<div style="background: #f6f8fa; border: 1px solid #d1d9e0; border-radius: 6px; padding: 12px; margin-bottom: 16px;">';
    debugHtml += '<div style="color: #57606a; font-weight: 600; margin-bottom: 4px;">Debug Information</div>';
    debugHtml += `<div style="color: #6e7781; font-size: 12px;">Messages: ${this.debugMessages ? this.debugMessages.length : 0}</div>`;
    debugHtml += '</div>';
    
    // Add debug messages in MCP style
    if (this.debugMessages && this.debugMessages.length > 0) {
      for (const msg of this.debugMessages) {
        // Message type header
        debugHtml += '<div style="margin-bottom: 12px;">';
        debugHtml += '<div style="background: #ddf4ff; border: 1px solid #54aeff; border-radius: 6px 6px 0 0; padding: 8px 12px; font-weight: 600; color: #0969da;">';
        debugHtml += `${this.escapeHtml(msg.type || 'unknown')}`;
        if (msg.timestamp) {
          debugHtml += `<span style="float: right; font-weight: normal; font-size: 11px; color: #57606a;">${new Date(msg.timestamp).toLocaleTimeString()}</span>`;
        }
        debugHtml += '</div>';
        
        // Message content
        debugHtml += '<div style="background: #ffffff; border: 1px solid #d1d9e0; border-top: none; border-radius: 0 0 6px 6px; padding: 12px;">';
        debugHtml += '<pre style="margin: 0; white-space: pre-wrap; word-wrap: break-word; color: #1f2328; font-size: 12px;">';
        debugHtml += this.formatDebugData(msg.data);
        debugHtml += '</pre>';
        debugHtml += '</div>';
        debugHtml += '</div>';
      }
    }
    
    // Add current results if available
    if (this.currentStreamingMessage && this.currentStreamingMessage.allResults && this.currentStreamingMessage.allResults.length > 0) {
      debugHtml += '<div style="margin-top: 24px;">';
      debugHtml += '<div style="background: #fff8c5; border: 1px solid #d4a72c; border-radius: 6px 6px 0 0; padding: 8px 12px; font-weight: 600; color: #7d4e00;">';
      debugHtml += `Result Items (${this.currentStreamingMessage.allResults.length})`;
      debugHtml += '</div>';
      debugHtml += '<div style="background: #ffffff; border: 1px solid #d1d9e0; border-top: none; border-radius: 0 0 6px 6px; padding: 12px;">';
      debugHtml += '<pre style="margin: 0; white-space: pre-wrap; word-wrap: break-word; color: #1f2328; font-size: 12px;">';
      debugHtml += this.formatDebugData(this.currentStreamingMessage.allResults);
      debugHtml += '</pre>';
      debugHtml += '</div>';
      debugHtml += '</div>';
    }
    
    debugHtml += '</div>';
    return debugHtml;
  }
  
  formatDebugData(data) {
    // Handle collapsible schema_objects
    const createCollapsibleHtml = (obj, depth = 0) => {
      if (typeof obj !== 'object' || obj === null) {
        return this.escapeHtml(JSON.stringify(obj));
      }
      
      if (Array.isArray(obj)) {
        let html = '[\n';
        obj.forEach((item, index) => {
          const indent = '  '.repeat(depth + 1);
          html += indent + createCollapsibleHtml(item, depth + 1);
          if (index < obj.length - 1) html += ',';
          html += '\n';
        });
        html += '  '.repeat(depth) + ']';
        return html;
      }
      
      let html = '{\n';
      const entries = Object.entries(obj);
      entries.forEach(([key, value], index) => {
        const indent = '  '.repeat(depth + 1);
        html += indent + '"' + this.escapeHtml(key) + '": ';
        
        if (key === 'schema_object' && value) {
          // Create collapsible section for schema_object
          const buttonId = `schema-toggle-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
          const contentId = `schema-content-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
          
          html += `<span style="color: #0969da; cursor: pointer;" onclick="
            var btn = document.getElementById('${buttonId}');
            var content = document.getElementById('${contentId}');
            if (content.style.display === 'none') {
              content.style.display = 'inline';
              btn.textContent = '[-]';
            } else {
              content.style.display = 'none';
              btn.textContent = '[+]';
            }
          "><span id="${buttonId}" style="font-weight: bold;">[+]</span></span><span id="${contentId}" style="display: none;">`;
          
          // Pretty print the schema object
          html += '\n' + indent + JSON.stringify(value, null, 2).split('\n').join('\n' + indent);
          html += '</span>';
        } else {
          html += createCollapsibleHtml(value, depth + 1);
        }
        
        if (index < entries.length - 1) html += ',';
        html += '\n';
      });
      html += '  '.repeat(depth) + '}';
      return html;
    };
    
    return createCollapsibleHtml(data);
  }
  
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  toggleSiteDropdown() {
    this.siteDropdown.classList.toggle('show');
    if (this.siteDropdown.classList.contains('show')) {
      this.populateSiteDropdown();
    }
  }
  
  populateSiteDropdown() {
    if (!this.sites || this.sites.length === 0) return;
    
    this.siteDropdownItems.innerHTML = '';
    this.sites.forEach(site => {
      const item = document.createElement('div');
      item.className = 'site-dropdown-item';
      if (site === this.selectedSite) {
        item.classList.add('selected');
      }
      item.textContent = site;
      item.addEventListener('click', () => {
        // Only create new conversation if site actually changed
        if (this.selectedSite !== site) {
          this.selectedSite = site;
          this.siteDropdown.classList.remove('show');
          this.populateSiteDropdown(); // Update selection
          
          // Update icon title to show selected site
          this.siteSelectorIcon.title = `Site: ${site}`;
          
          // Update the header site info
          if (this.elements.chatSiteInfo) {
            this.elements.chatSiteInfo.textContent = `Asking ${site}`;
          }
          
          // Create a new conversation for the new site
          // This ensures each site has its own conversation
          this.createNewChat(null, site);
        } else {
          // Just close the dropdown if same site selected
          this.siteDropdown.classList.remove('show');
        }
      });
      this.siteDropdownItems.appendChild(item);
    });
  }
  
  
  addRememberedItem(item) {
    if (!item || this.rememberedItems.includes(item)) return;
    
    this.rememberedItems.push(item);
    this.saveRememberedItems();
    this.updateRememberedItemsList();
  }
  
  deleteRememberedItem(item) {
    this.rememberedItems = this.rememberedItems.filter(i => i !== item);
    this.saveRememberedItems();
    this.updateRememberedItemsList();
  }
  
  saveRememberedItems() {
    localStorage.setItem('nlweb-remembered-items', JSON.stringify(this.rememberedItems));
  }
  
  loadRememberedItems() {
    const saved = localStorage.getItem('nlweb-remembered-items');
    if (saved) {
      try {
        this.rememberedItems = JSON.parse(saved);
      } catch (e) {
        this.rememberedItems = [];
      }
    }
  }
  
  updateRememberedItemsList() {
    // Find or create remembered section
    let rememberedSection = document.getElementById('remembered-section');
    
    // Update sidebar class based on remembered items
    if (this.rememberedItems.length > 0) {
      this.elements.sidebar.classList.add('has-remembered');
    } else {
      this.elements.sidebar.classList.remove('has-remembered');
    }
    
    if (!rememberedSection && this.rememberedItems.length > 0) {
      // Create remembered section
      rememberedSection = document.createElement('div');
      rememberedSection.id = 'remembered-section';
      // CSS is now handled in the stylesheet
      
      const header = document.createElement('h3');
      header.textContent = 'Remembered';
      header.style.cssText = 'font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 12px;';
      rememberedSection.appendChild(header);
      
      const itemsList = document.createElement('div');
      itemsList.id = 'remembered-items-list';
      rememberedSection.appendChild(itemsList);
      
      // Insert after conversations list in the sidebar
      const sidebar = this.elements.sidebar;
      const conversationsList = this.elements.conversationsList;
      // Insert after conversations list, not inside it
      conversationsList.parentNode.insertBefore(rememberedSection, conversationsList.nextSibling);
    } else if (rememberedSection && this.rememberedItems.length === 0) {
      // Remove section if no items
      rememberedSection.remove();
      return;
    }
    
    // Update items list
    const itemsList = document.getElementById('remembered-items-list');
    if (itemsList) {
      itemsList.innerHTML = '';
      
      this.rememberedItems.forEach(item => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'remembered-item';
        itemDiv.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; margin-bottom: 4px; background-color: var(--bg-secondary); border-radius: 6px; font-size: 13px; color: var(--text-primary); transition: background-color 0.2s ease;';
        
        const itemText = document.createElement('span');
        itemText.textContent = item;
        itemText.style.cssText = 'flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;';
        itemText.title = item; // Add full text as tooltip
        
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'remembered-item-delete';
        deleteBtn.innerHTML = '&times;';
        deleteBtn.style.cssText = 'border: none; background: none; color: var(--text-secondary); font-size: 18px; cursor: pointer; padding: 0; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.2s ease;';
        deleteBtn.title = 'Delete remembered item';
        deleteBtn.addEventListener('click', () => this.deleteRememberedItem(item));
        
        // Add hover effect
        itemDiv.addEventListener('mouseenter', () => {
          itemDiv.style.backgroundColor = 'var(--hover-bg)';
          deleteBtn.style.opacity = '0.7';
        });
        
        itemDiv.addEventListener('mouseleave', () => {
          itemDiv.style.backgroundColor = 'var(--bg-secondary)';
          deleteBtn.style.opacity = '0';
        });
        
        // Make delete button fully visible on hover
        deleteBtn.addEventListener('mouseenter', () => {
          deleteBtn.style.opacity = '1';
        });
        
        itemDiv.appendChild(itemText);
        itemDiv.appendChild(deleteBtn);
        itemsList.appendChild(itemDiv);
      });
    }
  }
  
  async loadSites() {
    try {
      const baseUrl = window.location.origin === 'file://' ? 'http://localhost:8000' : '';
      const response = await fetch(`${baseUrl}/sites?streaming=false`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data && data['message-type'] === 'sites' && Array.isArray(data.sites)) {
        let sites = data.sites;
        
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
        this.sites = sites;
        this.selectedSite = 'all';
        
        // Update site selector icon if it exists
        if (this.siteSelectorIcon) {
          this.siteSelectorIcon.title = `Site: ${this.selectedSite}`;
        }
        
        // Update the header site info
        if (this.elements.chatSiteInfo) {
          this.elements.chatSiteInfo.textContent = `Asking ${this.selectedSite}`;
        }
        
        // Populate the site dropdown if it exists
        if (this.siteDropdownItems) {
          this.populateSiteDropdown();
        }
      }
    } catch (error) {
      
      // Fallback sites
      const fallbackSites = ['all', 'eventbrite', 'oreilly', 'scifi_movies', 'verge'];
      this.sites = fallbackSites;
      this.selectedSite = 'all';
      
      // Update site selector icon if it exists
      if (this.siteSelectorIcon) {
        this.siteSelectorIcon.title = `Site: ${this.selectedSite}`;
      }
      
      // Update the header site info
      if (this.elements.chatSiteInfo) {
        this.elements.chatSiteInfo.textContent = `Site: ${this.selectedSite}`;
      }
      
      // Populate the site dropdown if it exists
      if (this.siteDropdownItems) {
        this.populateSiteDropdown();
      }
    }
  }
}

// Export the class for use in other modules
export { ModernChatInterface };

// Initialize when DOM is ready (only if not imported as module)
if (typeof window !== 'undefined' && !window.ModernChatInterfaceExported) {
  document.addEventListener('DOMContentLoaded', () => {
    try {
      new ModernChatInterface();
    } catch (error) {
    }
  });
  window.ModernChatInterfaceExported = true;
}
