/**
 * NLWeb Chat Widget
 * A complete chat interface that can be embedded into any website
 * Includes conversation management and remembered items functionality
 */

class NLWebChatWidget {
  constructor(config = {}) {
    this.config = {
      searchInputId: config.searchInputId || 'nlweb-search-input',
      searchButtonId: config.searchButtonId || 'nlweb-search-button',
      containerId: config.containerId || 'nlweb-chat-container',
      site: config.site || 'all',
      position: config.position || 'relative', // 'relative' or 'fixed'
      ...config
    };
    
    // State management
    this.conversations = [];
    this.currentConversationId = null;
    this.eventSource = null;
    this.isStreaming = false;
    this.currentStreamingMessage = null;
    this.prevQueries = [];
    this.lastAnswers = [];
    this.rememberedItems = [];
    this.selectedSite = this.config.site;
    
    // Initialize
    this.init();
  }
  
  init() {
    this.injectStyles();
    this.createChatInterface();
    this.bindEvents();
    this.loadConversations();
    this.loadRememberedItems();
  }
  
  injectStyles() {
    const styleId = 'nlweb-chat-widget-styles';
    if (document.getElementById(styleId)) return;
    
    const styles = document.createElement('style');
    styles.id = styleId;
    styles.textContent = `
      .nlweb-chat-container {
        position: ${this.config.position === 'fixed' ? 'fixed' : 'absolute'};
        ${this.config.position === 'fixed' ? 'bottom: 20px; right: 20px;' : 'top: 100%; left: 0; right: 0;'}
        z-index: 10000;
        background: white;
        box-shadow: 0 4px 24px rgba(0,0,0,0.15);
        border-radius: 12px;
        margin-top: ${this.config.position === 'fixed' ? '0' : '8px'};
        width: ${this.config.position === 'fixed' ? '800px' : '100%'};
        height: 600px;
        display: none;
        flex-direction: row;
        overflow: hidden;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
      }
      
      .nlweb-chat-container.show {
        display: flex;
      }
      
      /* Sidebar */
      .nlweb-sidebar {
        width: 260px;
        background-color: #f9f9f9;
        border-right: 1px solid #e5e5e5;
        display: flex;
        flex-direction: column;
        transition: all 0.2s ease;
      }
      
      .nlweb-sidebar.collapsed {
        width: 0;
        overflow: hidden;
      }
      
      .nlweb-sidebar-header {
        padding: 16px;
        border-bottom: 1px solid #e5e5e5;
      }
      
      .nlweb-conversations-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      
      .nlweb-conversations-title {
        font-size: 16px;
        font-weight: 600;
        margin: 0;
      }
      
      .nlweb-new-chat-btn {
        width: 32px;
        height: 32px;
        background-color: transparent;
        border: 1px solid #e5e5e5;
        border-radius: 6px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        transition: all 0.2s;
      }
      
      .nlweb-new-chat-btn:hover {
        background-color: #f0f0f0;
        border-color: #5e5eff;
      }
      
      .nlweb-conversations-list {
        flex: 1;
        overflow-y: auto;
        padding: 8px;
      }
      
      .nlweb-conversation-item {
        padding: 12px 16px;
        margin-bottom: 2px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
        color: #666;
        display: flex;
        align-items: center;
        justify-content: space-between;
        transition: all 0.2s;
      }
      
      .nlweb-conversation-item:hover {
        background-color: #f0f0f0;
      }
      
      .nlweb-conversation-item.active {
        background-color: #f0f0f0;
        color: #0d0d0d;
      }
      
      .nlweb-conversation-title {
        flex: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      
      .nlweb-conversation-delete {
        opacity: 0;
        width: 24px;
        height: 24px;
        border: none;
        background: none;
        color: #666;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 4px;
        transition: all 0.2s;
      }
      
      .nlweb-conversation-item:hover .nlweb-conversation-delete {
        opacity: 0.7;
      }
      
      .nlweb-conversation-delete:hover {
        background-color: rgba(255, 0, 0, 0.1);
        color: #ff4444;
        opacity: 1;
      }
      
      /* Remembered items section */
      .nlweb-remembered-section {
        border-top: 1px solid #e5e5e5;
        padding: 16px;
        min-height: 150px;
        max-height: 200px;
        overflow-y: auto;
      }
      
      .nlweb-remembered-header {
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 8px;
        color: #666;
      }
      
      .nlweb-remembered-item {
        font-size: 13px;
        padding: 4px 0;
        color: #666;
      }
      
      /* Main chat area */
      .nlweb-main-content {
        flex: 1;
        display: flex;
        flex-direction: column;
      }
      
      .nlweb-chat-header {
        height: 60px;
        border-bottom: 1px solid #e5e5e5;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 24px;
        background-color: #ffffff;
      }
      
      .nlweb-chat-title {
        font-size: 16px;
        font-weight: 600;
      }
      
      .nlweb-header-controls {
        display: flex;
        gap: 12px;
        align-items: center;
      }
      
      .nlweb-site-info {
        font-size: 14px;
        color: #666;
        background-color: #f7f7f8;
        padding: 4px 12px;
        border-radius: 16px;
        font-weight: 500;
      }
      
      .nlweb-close-btn {
        width: 32px;
        height: 32px;
        border: none;
        background: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        transition: background-color 0.2s;
      }
      
      .nlweb-close-btn:hover {
        background-color: #f0f0f0;
      }
      
      /* Messages area */
      .nlweb-chat-messages {
        flex: 1;
        overflow-y: auto;
        padding: 0;
        background-color: #ffffff;
      }
      
      .nlweb-message {
        margin-bottom: 1px;
        padding: 24px 48px;
        width: 100%;
      }
      
      .nlweb-user-message {
        background-color: #f5f5f5;
      }
      
      .nlweb-assistant-message {
        background-color: #ffffff;
        border-bottom: 1px solid #e5e5e5;
      }
      
      .nlweb-message-content {
        width: 100%;
        line-height: 1.5;
      }
      
      /* Input area */
      .nlweb-chat-input-container {
        border-top: 1px solid #e5e5e5;
        background-color: #ffffff;
        padding: 16px 24px;
      }
      
      .nlweb-chat-input-box {
        background-color: #f7f7f8;
        border: 1px solid #e5e5e5;
        border-radius: 12px;
        padding: 12px 16px;
        display: flex;
        gap: 12px;
        align-items: flex-end;
      }
      
      .nlweb-chat-input {
        flex: 1;
        border: none;
        background: transparent;
        font-size: 15px;
        line-height: 1.5;
        resize: none;
        outline: none;
        max-height: 120px;
        overflow-y: auto;
        font-family: inherit;
      }
      
      .nlweb-send-button {
        background-color: #5e5eff;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        cursor: pointer;
        font-size: 14px;
        transition: background-color 0.2s;
      }
      
      .nlweb-send-button:hover {
        background-color: #4a4aff;
      }
      
      .nlweb-send-button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      
      /* Loading animation */
      .nlweb-loading-dots {
        display: inline-flex;
        gap: 4px;
      }
      
      .nlweb-loading-dot {
        width: 8px;
        height: 8px;
        background-color: #666;
        border-radius: 50%;
        animation: nlweb-loading 1.4s infinite ease-in-out both;
      }
      
      .nlweb-loading-dot:nth-child(1) {
        animation-delay: -0.32s;
      }
      
      .nlweb-loading-dot:nth-child(2) {
        animation-delay: -0.16s;
      }
      
      @keyframes nlweb-loading {
        0%, 80%, 100% {
          transform: scale(0);
        }
        40% {
          transform: scale(1);
        }
      }
      
      /* Item container styles */
      .nlweb-item-container {
        background-color: #ffffff;
        border: 1px solid #f0f0f0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        display: flex;
        gap: 16px;
        width: 100%;
      }
      
      /* Scrollbar styling */
      .nlweb-chat-container ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
      }
      
      .nlweb-chat-container ::-webkit-scrollbar-track {
        background: transparent;
      }
      
      .nlweb-chat-container ::-webkit-scrollbar-thumb {
        background: #d0d0d0;
        border-radius: 4px;
      }
      
      .nlweb-chat-container ::-webkit-scrollbar-thumb:hover {
        background: #b0b0b0;
      }
    `;
    
    document.head.appendChild(styles);
  }
  
  createChatInterface() {
    // Get search elements
    this.searchInput = document.getElementById(this.config.searchInputId);
    this.searchButton = document.getElementById(this.config.searchButtonId);
    
    if (!this.searchInput || !this.searchButton) {
      console.error('NLWebChatWidget: Search input or button not found');
      return;
    }
    
    // Create container
    this.container = document.createElement('div');
    this.container.id = this.config.containerId;
    this.container.className = 'nlweb-chat-container';
    
    this.container.innerHTML = `
      <!-- Sidebar -->
      <aside class="nlweb-sidebar" id="nlweb-sidebar">
        <div class="nlweb-sidebar-header">
          <div class="nlweb-conversations-header">
            <h2 class="nlweb-conversations-title">Conversations</h2>
            <button class="nlweb-new-chat-btn" id="nlweb-new-chat-btn" title="New chat">+</button>
          </div>
        </div>
        <div class="nlweb-conversations-list" id="nlweb-conversations-list"></div>
        <div class="nlweb-remembered-section" id="nlweb-remembered-section">
          <div class="nlweb-remembered-header">Remembered Items</div>
          <div id="nlweb-remembered-list"></div>
        </div>
      </aside>
      
      <!-- Main chat area -->
      <main class="nlweb-main-content">
        <header class="nlweb-chat-header">
          <h1 class="nlweb-chat-title" id="nlweb-chat-title">New chat</h1>
          <div class="nlweb-header-controls">
            <span class="nlweb-site-info" id="nlweb-site-info">Asking ${this.selectedSite}</span>
            <button class="nlweb-close-btn" id="nlweb-close-btn" title="Close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <path d="M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </header>
        
        <div class="nlweb-chat-messages" id="nlweb-chat-messages">
          <div id="nlweb-messages-container"></div>
        </div>
        
        <div class="nlweb-chat-input-container">
          <div class="nlweb-chat-input-box">
            <textarea 
              class="nlweb-chat-input" 
              id="nlweb-chat-input"
              placeholder="Ask a follow-up question..."
              rows="1"
            ></textarea>
            <button class="nlweb-send-button" id="nlweb-send-button">Send</button>
          </div>
        </div>
      </main>
    `;
    
    // Insert container
    if (this.config.position === 'fixed') {
      document.body.appendChild(this.container);
    } else {
      const searchWrapper = this.searchInput.closest('.search-bar__wrapper') || 
                           this.searchInput.parentElement;
      searchWrapper.style.position = 'relative';
      searchWrapper.appendChild(this.container);
    }
    
    // Get references to elements
    this.elements = {
      sidebar: this.container.querySelector('#nlweb-sidebar'),
      newChatBtn: this.container.querySelector('#nlweb-new-chat-btn'),
      conversationsList: this.container.querySelector('#nlweb-conversations-list'),
      chatTitle: this.container.querySelector('#nlweb-chat-title'),
      siteInfo: this.container.querySelector('#nlweb-site-info'),
      closeBtn: this.container.querySelector('#nlweb-close-btn'),
      chatMessages: this.container.querySelector('#nlweb-chat-messages'),
      messagesContainer: this.container.querySelector('#nlweb-messages-container'),
      chatInput: this.container.querySelector('#nlweb-chat-input'),
      sendButton: this.container.querySelector('#nlweb-send-button'),
      rememberedList: this.container.querySelector('#nlweb-remembered-list')
    };
    
    // Load JSON renderer if available
    this.loadJsonRenderer();
  }
  
  async loadJsonRenderer() {
    try {
      const baseUrl = window.location.origin;
      const modules = await Promise.all([
        import(`${baseUrl}/static/json-renderer.js`),
        import(`${baseUrl}/static/type-renderers.js`),
        import(`${baseUrl}/static/recipe-renderer.js`)
      ]);
      
      const { JsonRenderer } = modules[0];
      const { TypeRendererFactory } = modules[1];
      const { RecipeRenderer } = modules[2];
      
      this.jsonRenderer = new JsonRenderer();
      TypeRendererFactory.registerAll(this.jsonRenderer);
      TypeRendererFactory.registerRenderer(RecipeRenderer, this.jsonRenderer);
    } catch (error) {
      console.warn('NLWebChatWidget: Could not load JSON renderer, using fallback', error);
      this.jsonRenderer = null;
    }
  }
  
  bindEvents() {
    // Search input/button events
    this.searchButton.addEventListener('click', () => this.handleSearch());
    this.searchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.handleSearch();
      }
    });
    
    // Chat events
    this.elements.closeBtn.addEventListener('click', () => this.close());
    this.elements.newChatBtn.addEventListener('click', () => this.createNewChat());
    this.elements.sendButton.addEventListener('click', () => this.sendMessage());
    this.elements.chatInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
    
    // Auto-resize chat input
    this.elements.chatInput.addEventListener('input', () => {
      this.elements.chatInput.style.height = 'auto';
      this.elements.chatInput.style.height = 
        Math.min(this.elements.chatInput.scrollHeight, 120) + 'px';
    });
    
    // Close on outside click for fixed position
    if (this.config.position === 'fixed') {
      document.addEventListener('click', (e) => {
        if (!this.container.contains(e.target) && 
            !this.searchInput.contains(e.target) && 
            !this.searchButton.contains(e.target)) {
          this.close();
        }
      });
    }
  }
  
  handleSearch() {
    const query = this.searchInput.value.trim();
    if (!query) return;
    
    this.searchInput.value = '';
    this.show();
    
    if (!this.currentConversationId) {
      this.createNewChat();
    }
    
    this.sendMessage(query);
  }
  
  show() {
    this.container.classList.add('show');
  }
  
  close() {
    this.container.classList.remove('show');
    if (this.eventSource) {
      this.eventSource.close();
    }
  }
  
  createNewChat() {
    const conversation = {
      id: Date.now().toString(),
      title: 'New chat',
      messages: [],
      createdAt: new Date().toISOString()
    };
    
    this.conversations.unshift(conversation);
    this.currentConversationId = conversation.id;
    this.prevQueries = [];
    this.lastAnswers = [];
    
    this.elements.messagesContainer.innerHTML = '';
    this.elements.chatTitle.textContent = 'New chat';
    
    this.updateConversationsList();
    this.saveConversations();
  }
  
  sendMessage(text) {
    const query = text || this.elements.chatInput.value.trim();
    if (!query || this.isStreaming) return;
    
    // Add user message
    this.addMessage(query, 'user');
    
    // Clear input
    this.elements.chatInput.value = '';
    this.elements.chatInput.style.height = 'auto';
    this.elements.sendButton.disabled = true;
    this.isStreaming = true;
    
    // Create assistant message with loading
    const messageContent = this.addMessage(this.createLoadingDots(), 'assistant');
    this.currentStreamingMessage = {
      content: '',
      contentDiv: messageContent,
      items: []
    };
    
    // Update conversation title if first message
    const conversation = this.conversations.find(c => c.id === this.currentConversationId);
    if (conversation && conversation.messages.length === 1) {
      conversation.title = query.substring(0, 50) + (query.length > 50 ? '...' : '');
      this.elements.chatTitle.textContent = conversation.title;
      this.updateConversationsList();
    }
    
    // Start streaming
    this.startStreaming(query);
  }
  
  startStreaming(query) {
    if (this.eventSource) {
      this.eventSource.close();
    }
    
    const params = new URLSearchParams({
      query: query,
      generate_mode: 'list',
      display_mode: 'full',
      site: this.selectedSite
    });
    
    // Add context
    if (this.prevQueries.length > 0) {
      params.append('prev', JSON.stringify(this.prevQueries));
    }
    if (this.lastAnswers.length > 0) {
      params.append('last_ans', JSON.stringify(this.lastAnswers));
    }
    if (this.rememberedItems.length > 0) {
      params.append('item_to_remember', this.rememberedItems.join(', '));
    }
    
    const url = `/ask?${params.toString()}`;
    this.eventSource = new EventSource(url);
    
    let firstChunk = true;
    let allResults = [];
    
    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (firstChunk) {
          this.currentStreamingMessage.contentDiv.innerHTML = '';
          firstChunk = false;
        }
        
        if (data.type === 'content') {
          this.currentStreamingMessage.content += data.text || '';
          this.renderStreamingContent();
        } else if (data.type === 'items') {
          if (data.items && data.items.length > 0) {
            allResults = allResults.concat(data.items);
            this.currentStreamingMessage.items = allResults;
            this.renderStreamingContent();
          }
        } else if (data.type === 'complete') {
          this.endStreaming();
          
          // Update context
          this.prevQueries.push(query);
          if (this.prevQueries.length > 10) this.prevQueries.shift();
          
          if (this.currentStreamingMessage.content || allResults.length > 0) {
            this.lastAnswers.push({
              content: this.currentStreamingMessage.content,
              items: allResults
            });
            if (this.lastAnswers.length > 5) this.lastAnswers.shift();
          }
          
          // Save conversation
          this.saveCurrentMessage();
          this.saveConversations();
        } else if (data.type === 'remember') {
          if (data.item) {
            this.addRememberedItem(data.item);
          }
        }
        
        this.scrollToBottom();
      } catch (error) {
        console.error('Error parsing message:', error);
      }
    };
    
    this.eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      if (firstChunk) {
        this.currentStreamingMessage.contentDiv.innerHTML = 
          '<div style="color: red;">Connection error. Please try again.</div>';
      }
      this.endStreaming();
    };
  }
  
  renderStreamingContent() {
    const container = this.currentStreamingMessage.contentDiv;
    container.innerHTML = '';
    
    if (this.currentStreamingMessage.content) {
      const textDiv = document.createElement('div');
      textDiv.textContent = this.currentStreamingMessage.content;
      container.appendChild(textDiv);
    }
    
    if (this.currentStreamingMessage.items.length > 0) {
      this.renderItems(this.currentStreamingMessage.items, container);
    }
  }
  
  renderItems(items, container) {
    const sortedItems = [...items].sort((a, b) => (b.score || 0) - (a.score || 0));
    
    sortedItems.forEach(item => {
      if (this.jsonRenderer) {
        const itemElement = this.jsonRenderer.createJsonItemHtml(item);
        container.appendChild(itemElement);
      } else {
        // Fallback rendering
        const itemDiv = document.createElement('div');
        itemDiv.className = 'nlweb-item-container';
        itemDiv.innerHTML = `
          <div style="flex: 1;">
            <h3>${item.title || 'No title'}</h3>
            <p>${item.description || ''}</p>
            ${item.url ? `<a href="${item.url}" target="_blank">View more</a>` : ''}
          </div>
        `;
        container.appendChild(itemDiv);
      }
    });
  }
  
  endStreaming() {
    this.isStreaming = false;
    this.elements.sendButton.disabled = false;
    if (this.eventSource) {
      this.eventSource.close();
    }
  }
  
  addMessage(content, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `nlweb-message nlweb-${type}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'nlweb-message-content';
    
    if (typeof content === 'string') {
      contentDiv.innerHTML = content;
    } else {
      contentDiv.appendChild(content);
    }
    
    messageDiv.appendChild(contentDiv);
    this.elements.messagesContainer.appendChild(messageDiv);
    
    // Add to conversation
    const conversation = this.conversations.find(c => c.id === this.currentConversationId);
    if (conversation) {
      conversation.messages.push({
        type: type,
        content: type === 'user' ? content : '',
        timestamp: new Date().toISOString()
      });
    }
    
    this.scrollToBottom();
    return contentDiv;
  }
  
  saveCurrentMessage() {
    const conversation = this.conversations.find(c => c.id === this.currentConversationId);
    if (conversation && this.currentStreamingMessage) {
      const lastMessage = conversation.messages[conversation.messages.length - 1];
      if (lastMessage && lastMessage.type === 'assistant') {
        lastMessage.content = this.currentStreamingMessage.content;
        lastMessage.items = this.currentStreamingMessage.items;
      }
    }
  }
  
  createLoadingDots() {
    return `
      <div class="nlweb-loading-dots">
        <div class="nlweb-loading-dot"></div>
        <div class="nlweb-loading-dot"></div>
        <div class="nlweb-loading-dot"></div>
      </div>
    `;
  }
  
  scrollToBottom() {
    this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
  }
  
  updateConversationsList() {
    this.elements.conversationsList.innerHTML = '';
    
    this.conversations.forEach(conv => {
      const item = document.createElement('div');
      item.className = 'nlweb-conversation-item';
      if (conv.id === this.currentConversationId) {
        item.classList.add('active');
      }
      
      item.innerHTML = `
        <span class="nlweb-conversation-title">${conv.title}</span>
        <button class="nlweb-conversation-delete" data-id="${conv.id}">×</button>
      `;
      
      item.addEventListener('click', (e) => {
        if (!e.target.classList.contains('nlweb-conversation-delete')) {
          this.loadConversation(conv.id);
        }
      });
      
      const deleteBtn = item.querySelector('.nlweb-conversation-delete');
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.deleteConversation(conv.id);
      });
      
      this.elements.conversationsList.appendChild(item);
    });
  }
  
  loadConversation(conversationId) {
    const conversation = this.conversations.find(c => c.id === conversationId);
    if (!conversation) return;
    
    this.currentConversationId = conversationId;
    this.elements.chatTitle.textContent = conversation.title;
    this.elements.messagesContainer.innerHTML = '';
    
    // Rebuild context from conversation
    this.prevQueries = [];
    this.lastAnswers = [];
    
    conversation.messages.forEach(msg => {
      if (msg.type === 'user') {
        this.addMessage(msg.content, 'user');
        this.prevQueries.push(msg.content);
      } else if (msg.type === 'assistant') {
        const contentDiv = this.addMessage('', 'assistant');
        if (msg.content) {
          const textDiv = document.createElement('div');
          textDiv.textContent = msg.content;
          contentDiv.appendChild(textDiv);
        }
        if (msg.items && msg.items.length > 0) {
          this.renderItems(msg.items, contentDiv);
        }
        
        if (msg.content || (msg.items && msg.items.length > 0)) {
          this.lastAnswers.push({
            content: msg.content || '',
            items: msg.items || []
          });
        }
      }
    });
    
    // Keep only last 10 queries and 5 answers
    if (this.prevQueries.length > 10) {
      this.prevQueries = this.prevQueries.slice(-10);
    }
    if (this.lastAnswers.length > 5) {
      this.lastAnswers = this.lastAnswers.slice(-5);
    }
    
    this.updateConversationsList();
  }
  
  deleteConversation(conversationId) {
    this.conversations = this.conversations.filter(c => c.id !== conversationId);
    
    if (this.currentConversationId === conversationId) {
      if (this.conversations.length > 0) {
        this.loadConversation(this.conversations[0].id);
      } else {
        this.createNewChat();
      }
    }
    
    this.updateConversationsList();
    this.saveConversations();
  }
  
  addRememberedItem(item) {
    if (!this.rememberedItems.includes(item)) {
      this.rememberedItems.push(item);
      this.updateRememberedItemsList();
      this.saveRememberedItems();
    }
  }
  
  updateRememberedItemsList() {
    this.elements.rememberedList.innerHTML = '';
    
    this.rememberedItems.forEach((item, index) => {
      const itemDiv = document.createElement('div');
      itemDiv.className = 'nlweb-remembered-item';
      itemDiv.textContent = `• ${item}`;
      this.elements.rememberedList.appendChild(itemDiv);
    });
  }
  
  saveConversations() {
    try {
      localStorage.setItem('nlweb-conversations', JSON.stringify(this.conversations));
    } catch (error) {
      console.error('Failed to save conversations:', error);
    }
  }
  
  loadConversations() {
    try {
      const saved = localStorage.getItem('nlweb-conversations');
      if (saved) {
        this.conversations = JSON.parse(saved);
        this.updateConversationsList();
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  }
  
  saveRememberedItems() {
    try {
      localStorage.setItem('nlweb-remembered-items', JSON.stringify(this.rememberedItems));
    } catch (error) {
      console.error('Failed to save remembered items:', error);
    }
  }
  
  loadRememberedItems() {
    try {
      const saved = localStorage.getItem('nlweb-remembered-items');
      if (saved) {
        this.rememberedItems = JSON.parse(saved);
        this.updateRememberedItemsList();
      }
    } catch (error) {
      console.error('Failed to load remembered items:', error);
    }
  }
}

// Export for use
window.NLWebChatWidget = NLWebChatWidget;