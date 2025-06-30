/**
 * NLWeb Chat Web Component
 * A custom HTML element that provides a complete chat interface
 * 
 * Usage:
 * <nlweb-chat 
 *   search-input-id="my-search-input"
 *   search-button-id="my-search-button"
 *   site="seriouseats"
 *   position="relative">
 * </nlweb-chat>
 */

class NLWebChatElement extends HTMLElement {
  constructor() {
    super();
    
    // Create shadow DOM for style encapsulation
    this.attachShadow({ mode: 'open' });
    
    // State management
    this.conversations = [];
    this.currentConversationId = null;
    this.eventSource = null;
    this.isStreaming = false;
    this.currentStreamingMessage = null;
    this.prevQueries = [];
    this.lastAnswers = [];
    this.rememberedItems = [];
    
    // Default config
    this.config = {
      searchInputId: this.getAttribute('search-input-id') || 'search-input',
      searchButtonId: this.getAttribute('search-button-id') || 'search-button',
      site: this.getAttribute('site') || 'all',
      position: this.getAttribute('position') || 'relative'
    };
  }
  
  static get observedAttributes() {
    return ['search-input-id', 'search-button-id', 'site', 'position'];
  }
  
  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue) return;
    
    switch(name) {
      case 'search-input-id':
        this.config.searchInputId = newValue;
        break;
      case 'search-button-id':
        this.config.searchButtonId = newValue;
        break;
      case 'site':
        this.config.site = newValue;
        this.selectedSite = newValue;
        if (this.elements?.siteInfo) {
          this.elements.siteInfo.textContent = `Asking ${newValue}`;
        }
        break;
      case 'position':
        this.config.position = newValue;
        this.updatePosition();
        break;
    }
  }
  
  async connectedCallback() {
    this.selectedSite = this.config.site;
    this.render();
    this.bindExternalEvents();
    this.bindInternalEvents();
    this.loadConversations();
    this.loadRememberedItems();
    
    // Load JSON renderer before we might need it
    await this.loadJsonRenderer();
  }
  
  disconnectedCallback() {
    if (this.eventSource) {
      this.eventSource.close();
    }
  }
  
  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --primary-color: #5e5eff;
          --text-primary: #0d0d0d;
          --text-secondary: #666;
          --bg-primary: #ffffff;
          --bg-secondary: #f7f7f8;
          --bg-sidebar: #f9f9f9;
          --border-color: #e5e5e5;
          --hover-bg: #f0f0f0;
          --message-user-bg: #f5f5f5;
          --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
          --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
          --shadow-lg: 0 4px 24px rgba(0,0,0,0.15);
        }
        
        * {
          box-sizing: border-box;
        }
        
        .chat-container {
          position: ${this.config.position === 'fixed' ? 'fixed' : 'absolute'};
          ${this.config.position === 'fixed' ? 'bottom: 20px; right: 20px;' : 'top: calc(100% + 8px); left: 0;'}
          z-index: 10000;
          background: var(--bg-primary);
          box-shadow: var(--shadow-lg);
          border-radius: 12px;
          width: ${this.config.position === 'fixed' ? '800px' : 'min(800px, 100vw - 40px)'};
          max-width: 100%;
          height: 500px;
          display: none;
          flex-direction: row;
          overflow: hidden;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
          font-size: 14px;
          line-height: 1.5;
          color: var(--text-primary);
        }
        
        .chat-container.show {
          display: flex;
        }
        
        /* Sidebar */
        .sidebar {
          width: 260px;
          background-color: var(--bg-sidebar);
          border-right: 1px solid var(--border-color);
          display: flex;
          flex-direction: column;
          transition: all 0.2s ease;
        }
        
        .sidebar.collapsed {
          width: 0;
          overflow: hidden;
        }
        
        .sidebar-header {
          padding: 16px;
          border-bottom: 1px solid var(--border-color);
        }
        
        .conversations-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        
        .conversations-title {
          font-size: 16px;
          font-weight: 600;
          margin: 0;
        }
        
        .new-chat-btn {
          width: 32px;
          height: 32px;
          background-color: transparent;
          border: 1px solid var(--border-color);
          border-radius: 6px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
          transition: all 0.2s;
          color: var(--text-secondary);
        }
        
        .new-chat-btn:hover {
          background-color: var(--hover-bg);
          border-color: var(--primary-color);
          color: var(--primary-color);
        }
        
        .conversations-list {
          flex: 1;
          overflow-y: auto;
          padding: 8px;
        }
        
        .conversation-item {
          padding: 12px 16px;
          margin-bottom: 2px;
          border-radius: 6px;
          cursor: pointer;
          font-size: 14px;
          color: var(--text-secondary);
          display: flex;
          align-items: center;
          justify-content: space-between;
          transition: all 0.2s;
        }
        
        .conversation-item:hover {
          background-color: var(--hover-bg);
        }
        
        .conversation-item.active {
          background-color: var(--hover-bg);
          color: var(--text-primary);
        }
        
        .conversation-title {
          flex: 1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        
        .conversation-delete {
          opacity: 0;
          width: 24px;
          height: 24px;
          border: none;
          background: none;
          color: var(--text-secondary);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 4px;
          transition: all 0.2s;
          font-size: 20px;
          line-height: 1;
        }
        
        .conversation-item:hover .conversation-delete {
          opacity: 0.7;
        }
        
        .conversation-delete:hover {
          background-color: rgba(255, 0, 0, 0.1);
          color: #ff4444;
          opacity: 1;
        }
        
        /* Remembered items section */
        .remembered-section {
          border-top: 1px solid var(--border-color);
          padding: 16px;
          min-height: 150px;
          max-height: 200px;
          overflow-y: auto;
        }
        
        .remembered-header {
          font-size: 14px;
          font-weight: 600;
          margin-bottom: 8px;
          color: var(--text-secondary);
        }
        
        .remembered-item {
          font-size: 13px;
          padding: 4px 0;
          color: var(--text-secondary);
        }
        
        /* Main chat area */
        .main-content {
          flex: 1;
          display: flex;
          flex-direction: column;
        }
        
        .chat-header {
          height: 60px;
          border-bottom: 1px solid var(--border-color);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 24px;
          background-color: var(--bg-primary);
        }
        
        .chat-title {
          font-size: 16px;
          font-weight: 600;
        }
        
        .header-controls {
          display: flex;
          gap: 12px;
          align-items: center;
        }
        
        .site-info {
          font-size: 14px;
          color: var(--text-secondary);
          background-color: var(--bg-secondary);
          padding: 4px 12px;
          border-radius: 16px;
          font-weight: 500;
        }
        
        .close-btn {
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
          color: var(--text-secondary);
        }
        
        .close-btn:hover {
          background-color: var(--hover-bg);
        }
        
        /* Messages area */
        .chat-messages {
          flex: 1;
          overflow-y: auto;
          padding: 0;
          background-color: var(--bg-primary);
        }
        
        .message {
          margin-bottom: 1px;
          padding: 24px 48px;
          width: 100%;
        }
        
        .user-message {
          background-color: var(--message-user-bg);
        }
        
        .assistant-message {
          background-color: var(--bg-primary);
          border-bottom: 1px solid var(--border-color);
        }
        
        .message-content {
          width: 100%;
          line-height: 1.5;
        }
        
        /* Input area */
        .chat-input-container {
          border-top: 1px solid var(--border-color);
          background-color: var(--bg-primary);
          padding: 16px 24px;
        }
        
        .chat-input-box {
          background-color: var(--bg-secondary);
          border: 1px solid var(--border-color);
          border-radius: 12px;
          padding: 12px 16px;
          display: flex;
          gap: 12px;
          align-items: flex-end;
        }
        
        .chat-input {
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
          color: var(--text-primary);
        }
        
        .chat-input::placeholder {
          color: var(--text-secondary);
        }
        
        .send-button {
          background-color: var(--primary-color);
          color: white;
          border: none;
          border-radius: 6px;
          padding: 8px 16px;
          cursor: pointer;
          font-size: 14px;
          transition: background-color 0.2s;
          font-weight: 500;
        }
        
        .send-button:hover {
          background-color: #4a4aff;
        }
        
        .send-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        /* Loading animation */
        .loading-dots {
          display: inline-flex;
          gap: 4px;
        }
        
        .loading-dot {
          width: 8px;
          height: 8px;
          background-color: var(--text-secondary);
          border-radius: 50%;
          animation: loading 1.4s infinite ease-in-out both;
        }
        
        .loading-dot:nth-child(1) {
          animation-delay: -0.32s;
        }
        
        .loading-dot:nth-child(2) {
          animation-delay: -0.16s;
        }
        
        @keyframes loading {
          0%, 80%, 100% {
            transform: scale(0);
          }
          40% {
            transform: scale(1);
          }
        }
        
        /* Item container styles */
        .item-container {
          background-color: var(--bg-primary);
          border: 1px solid #f0f0f0;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 12px;
          display: flex;
          gap: 16px;
          width: 100%;
          align-items: flex-start;
        }
        
        .item-container:hover {
          border-color: #e0e0e0;
          box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        .item-content {
          flex: 1;
        }
        
        .item-title {
          font-size: 16px;
          font-weight: 500;
          color: var(--primary-color);
          text-decoration: none;
          display: block;
          margin-bottom: 8px;
        }
        
        .item-title:hover {
          text-decoration: underline;
        }
        
        .item-description {
          color: var(--text-secondary);
          font-size: 14px;
          line-height: 1.5;
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        
        ::-webkit-scrollbar-track {
          background: transparent;
        }
        
        ::-webkit-scrollbar-thumb {
          background: #d0d0d0;
          border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
          background: #b0b0b0;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
          .chat-container {
            width: 100% !important;
            height: 100% !important;
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
            border-radius: 0 !important;
            margin: 0 !important;
          }
          
          .message {
            padding: 16px 20px;
          }
          
          .sidebar {
            width: 200px;
          }
        }
      </style>
      
      <div class="chat-container" id="chat-container">
        <!-- Sidebar -->
        <aside class="sidebar" id="sidebar">
          <div class="sidebar-header">
            <div class="conversations-header">
              <h2 class="conversations-title">Conversations</h2>
              <button class="new-chat-btn" id="new-chat-btn" title="New chat">+</button>
            </div>
          </div>
          <div class="conversations-list" id="conversations-list"></div>
          <div class="remembered-section" id="remembered-section">
            <div class="remembered-header">Remembered Items</div>
            <div id="remembered-list"></div>
          </div>
        </aside>
        
        <!-- Main chat area -->
        <main class="main-content">
          <header class="chat-header">
            <h1 class="chat-title" id="chat-title">New chat</h1>
            <div class="header-controls">
              <span class="site-info" id="site-info">Asking ${this.selectedSite}</span>
              <button class="close-btn" id="close-btn" title="Close">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M15 5L5 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                  <path d="M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
          </header>
          
          <div class="chat-messages" id="chat-messages">
            <div id="messages-container"></div>
          </div>
          
          <div class="chat-input-container">
            <div class="chat-input-box">
              <textarea 
                class="chat-input" 
                id="chat-input"
                placeholder="Ask a follow-up question..."
                rows="1"
              ></textarea>
              <button class="send-button" id="send-button">Send</button>
            </div>
          </div>
        </main>
      </div>
    `;
    
    // Get references to shadow DOM elements
    this.elements = {
      container: this.shadowRoot.getElementById('chat-container'),
      sidebar: this.shadowRoot.getElementById('sidebar'),
      newChatBtn: this.shadowRoot.getElementById('new-chat-btn'),
      conversationsList: this.shadowRoot.getElementById('conversations-list'),
      chatTitle: this.shadowRoot.getElementById('chat-title'),
      siteInfo: this.shadowRoot.getElementById('site-info'),
      closeBtn: this.shadowRoot.getElementById('close-btn'),
      chatMessages: this.shadowRoot.getElementById('chat-messages'),
      messagesContainer: this.shadowRoot.getElementById('messages-container'),
      chatInput: this.shadowRoot.getElementById('chat-input'),
      sendButton: this.shadowRoot.getElementById('send-button'),
      rememberedList: this.shadowRoot.getElementById('remembered-list')
    };
  }
  
  bindExternalEvents() {
    // Get external search elements
    this.searchInput = document.getElementById(this.config.searchInputId);
    this.searchButton = document.getElementById(this.config.searchButtonId);
    
    if (!this.searchInput || !this.searchButton) {
      console.error('NLWebChatElement: Search input or button not found', {
        searchInputId: this.config.searchInputId,
        searchButtonId: this.config.searchButtonId
      });
      return;
    }
    
    // Bind search events
    this.searchButton.addEventListener('click', () => this.handleSearch());
    this.searchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.handleSearch();
      }
    });
    
    // Position the component relative to search input if needed
    if (this.config.position === 'relative') {
      const searchWrapper = this.searchInput.closest('.search-wrapper') || 
                           this.searchInput.parentElement;
      searchWrapper.style.position = 'relative';
    }
  }
  
  bindInternalEvents() {
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
        // Check if click is outside shadow DOM
        const path = e.composedPath();
        if (!path.includes(this) && 
            !path.includes(this.searchInput) && 
            !path.includes(this.searchButton)) {
          this.close();
        }
      });
    }
  }
  
  // API Methods that can be called from outside
  show() {
    console.log('NLWebChat: show() called');
    if (!this.elements.container) {
      console.error('NLWebChat: Container element not found!');
      return;
    }
    this.elements.container.classList.add('show');
    console.log('NLWebChat: Container classes:', this.elements.container.className);
    this.dispatchEvent(new CustomEvent('nlweb-chat-opened'));
  }
  
  close() {
    this.elements.container.classList.remove('show');
    if (this.eventSource) {
      this.eventSource.close();
    }
    this.dispatchEvent(new CustomEvent('nlweb-chat-closed'));
  }
  
  toggle() {
    if (this.elements.container.classList.contains('show')) {
      this.close();
    } else {
      this.show();
    }
  }
  
  setQuery(query) {
    if (this.searchInput) {
      this.searchInput.value = query;
    }
  }
  
  search(query) {
    this.show();
    if (!this.currentConversationId) {
      this.createNewChat();
    }
    this.sendMessage(query);
  }
  
  // All other methods remain the same as the original widget
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
  
  updatePosition() {
    if (!this.elements?.container) return;
    
    const styles = this.shadowRoot.querySelector('style');
    if (styles) {
      // Update the position-related CSS
      const css = styles.textContent;
      const updatedCss = css.replace(
        /position: (fixed|absolute)/,
        `position: ${this.config.position === 'fixed' ? 'fixed' : 'absolute'}`
      );
      styles.textContent = updatedCss;
    }
  }
  
  async loadJsonRenderer() {
    try {
      console.log('NLWebChat: Loading JSON renderer modules...');
      const baseUrl = window.location.origin;
      
      // Try to load the modules
      const [jsonRendererModule, typeRenderersModule, recipeRendererModule] = await Promise.all([
        import(`${baseUrl}/static/json-renderer.js`),
        import(`${baseUrl}/static/type-renderers.js`),
        import(`${baseUrl}/static/recipe-renderer.js`)
      ]);
      
      console.log('NLWebChat: Modules loaded successfully');
      
      const { JsonRenderer } = jsonRendererModule;
      const { TypeRendererFactory } = typeRenderersModule;
      const { RecipeRenderer } = recipeRendererModule;
      
      this.jsonRenderer = new JsonRenderer();
      TypeRendererFactory.registerAll(this.jsonRenderer);
      TypeRendererFactory.registerRenderer(RecipeRenderer, this.jsonRenderer);
      
      console.log('NLWebChat: JSON renderer initialized successfully');
    } catch (error) {
      console.error('NLWebChat: Failed to load JSON renderer modules:', error);
      console.error('NLWebChat: Will use fallback rendering');
      this.jsonRenderer = null;
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
    
    // Dispatch event
    this.dispatchEvent(new CustomEvent('nlweb-message-sent', { 
      detail: { query, conversationId: this.currentConversationId } 
    }));
    
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
    
    // Construct full URL - handle both relative and absolute paths
    const baseUrl = window.location.origin;
    const url = `${baseUrl}/ask?${params.toString()}`;
    console.log('NLWebChat: Connecting to:', url);
    
    try {
      this.eventSource = new EventSource(url);
    } catch (error) {
      console.error('NLWebChat: Failed to create EventSource:', error);
      this.currentStreamingMessage.contentDiv.innerHTML = 
        '<div style="color: red;">Failed to connect to server. Please ensure the server is running on ' + baseUrl + '</div>';
      this.endStreaming();
      return;
    }
    
    let firstChunk = true;
    let allResults = [];
    
    // Set a timeout to detect connection issues
    let connectionTimeout = setTimeout(() => {
      if (firstChunk) {
        console.error('NLWebChat: Connection timeout - no data received within 10 seconds');
        this.currentStreamingMessage.contentDiv.innerHTML = 
          '<div style="color: red;">Connection timeout. The server may be slow or unavailable.</div>';
        this.endStreaming();
      }
    }, 10000);
    
    this.eventSource.onopen = (event) => {
      console.log('NLWebChat: EventSource connection opened');
    };
    
    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (firstChunk) {
          this.currentStreamingMessage.contentDiv.innerHTML = '';
          firstChunk = false;
          // Clear the timeout since we received data
          clearTimeout(connectionTimeout);
        }
        
        // Handle different message types from the server
        if (data.message_type === 'content' || data.type === 'content') {
          this.currentStreamingMessage.content += data.content || data.text || '';
          this.renderStreamingContent();
        } else if (data.message_type === 'result_batch') {
          // Handle result batches
          if (data.results && data.results.length > 0) {
            allResults = allResults.concat(data.results);
            this.currentStreamingMessage.items = allResults;
            this.renderStreamingContent();
          }
        } else if (data.message_type === 'items' || data.type === 'items') {
          if (data.items && data.items.length > 0) {
            allResults = allResults.concat(data.items);
            this.currentStreamingMessage.items = allResults;
            this.renderStreamingContent();
          }
        } else if (data.message_type === 'complete' || data.type === 'complete') {
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
          
          // Dispatch event
          this.dispatchEvent(new CustomEvent('nlweb-message-received', { 
            detail: { 
              content: this.currentStreamingMessage.content,
              items: allResults,
              conversationId: this.currentConversationId 
            } 
          }));
        } else if (data.message_type === 'remember' || data.type === 'remember') {
          if (data.item) {
            this.addRememberedItem(data.item);
          }
        } else {
          // Log other message types for debugging
          console.log('NLWebChat: Received message type:', data.message_type || data.type, data);
        }
        
        this.scrollToBottom();
      } catch (error) {
        console.error('Error parsing message:', error);
      }
    };
    
    this.eventSource.onerror = (error) => {
      // Check if this is a normal closure after receiving complete message
      if (this.eventSource.readyState === EventSource.CLOSED && !firstChunk) {
        console.log('NLWebChat: Connection closed normally after receiving data');
        this.endStreaming();
        return;
      }
      
      // This is a real error
      console.error('NLWebChat: EventSource error:', error);
      console.error('NLWebChat: ReadyState:', this.eventSource.readyState);
      console.error('NLWebChat: URL was:', url);
      
      if (firstChunk) {
        this.currentStreamingMessage.contentDiv.innerHTML = 
          '<div style="color: red;">Connection error. Please check if the server is running and the /ask endpoint is available.</div>';
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
        itemDiv.className = 'item-container';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'item-content';
        
        // Handle both 'title' and 'name' fields
        const title = item.title || item.name;
        if (item.url && title) {
          const titleLink = document.createElement('a');
          titleLink.className = 'item-title';
          titleLink.href = item.url;
          titleLink.target = '_blank';
          titleLink.textContent = title;
          contentDiv.appendChild(titleLink);
        } else if (title) {
          const titleDiv = document.createElement('div');
          titleDiv.className = 'item-title';
          titleDiv.textContent = title;
          contentDiv.appendChild(titleDiv);
        }
        
        if (item.description) {
          const descDiv = document.createElement('div');
          descDiv.className = 'item-description';
          descDiv.textContent = item.description;
          contentDiv.appendChild(descDiv);
        }
        
        // Add score if available
        if (item.score) {
          const scoreDiv = document.createElement('div');
          scoreDiv.className = 'item-score';
          scoreDiv.style.fontSize = '12px';
          scoreDiv.style.color = '#666';
          scoreDiv.style.marginTop = '4px';
          scoreDiv.textContent = `Score: ${item.score}`;
          contentDiv.appendChild(scoreDiv);
        }
        
        itemDiv.appendChild(contentDiv);
        
        // Add image if available
        if (item.image) {
          const imgDiv = document.createElement('div');
          const img = document.createElement('img');
          img.src = item.image;
          img.alt = 'Item image';
          img.className = 'item-image';
          img.style.maxWidth = '120px';
          img.style.height = 'auto';
          img.style.objectFit = 'cover';
          imgDiv.appendChild(img);
          itemDiv.appendChild(imgDiv);
        }
        
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
    messageDiv.className = `message ${type}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
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
      <div class="loading-dots">
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
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
      item.className = 'conversation-item';
      if (conv.id === this.currentConversationId) {
        item.classList.add('active');
      }
      
      const title = document.createElement('span');
      title.className = 'conversation-title';
      title.textContent = conv.title;
      
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'conversation-delete';
      deleteBtn.textContent = '×';
      deleteBtn.dataset.id = conv.id;
      
      item.appendChild(title);
      item.appendChild(deleteBtn);
      
      item.addEventListener('click', (e) => {
        if (!e.target.classList.contains('conversation-delete')) {
          this.loadConversation(conv.id);
        }
      });
      
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
      itemDiv.className = 'remembered-item';
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

// Register the custom element
customElements.define('nlweb-chat', NLWebChatElement);