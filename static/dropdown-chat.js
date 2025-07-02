/**
 * Dropdown Chat Interface Module
 * Creates a dropdown chat interface with styles matching index.html
 */

export function initDropdownChat(searchInputId, searchButtonId, chatContainerId, site = 'all') {
  // Inject styles
  const styleSheet = document.createElement('style');
  styleSheet.textContent = `
    #${chatContainerId}.dropdown-chat-container {
      position: absolute !important;
      top: 100% !important;
      left: 0 !important;
      right: 0 !important;
      z-index: 1000 !important;
      background: white !important;
      box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
      border-radius: 8px !important;
      margin-top: 8px !important;
      height: 500px !important;
      display: flex !important;
      flex-direction: column !important;
      overflow: hidden !important;
    }
    
    #${chatContainerId} .chat-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px;
      border-bottom: 1px solid #e5e5e5;
    }
    
    #${chatContainerId} .chat-title {
      font-size: 16px;
      font-weight: 600;
    }
    
    #${chatContainerId} .close-icon {
      width: 24px;
      height: 24px;
      cursor: pointer;
      background: none;
      border: none;
      padding: 4px;
      border-radius: 4px;
      transition: background-color 0.2s;
    }
    
    #${chatContainerId} .close-icon:hover {
      background-color: #f0f0f0;
    }
    
    #${chatContainerId} .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
    }
    
    #${chatContainerId} .message {
      margin-bottom: 1px !important;
      padding: 16px !important;
      width: 100% !important;
    }
    
    #${chatContainerId} .user-message {
      background-color: #f5f5f5 !important;
    }
    
    #${chatContainerId} .assistant-message {
      background-color: #ffffff !important;
      border-bottom: 1px solid #e5e5e5 !important;
    }
    
    #${chatContainerId} .item-container {
      background-color: #ffffff !important;
      border: 1px solid #f0f0f0 !important;
      border-radius: 8px !important;
      padding: 16px !important;
      margin-bottom: 12px !important;
      width: 100% !important;
    }
    
    #${chatContainerId} .chat-input-area {
      padding: 16px;
      border-top: 1px solid #e5e5e5;
      display: flex;
      gap: 8px;
    }
    
    #${chatContainerId} .dropdown-chat-input {
      flex: 1 !important;
      border: 1px solid #e5e5e5 !important;
      border-radius: 8px !important;
      padding: 8px 12px !important;
      font-size: 14px !important;
      text-align: left !important;
      resize: none !important;
      font-family: inherit !important;
    }
    
    #${chatContainerId} .dropdown-send-button {
      padding: 8px 16px;
      background-color: #007bff;
      color: white;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      font-size: 14px;
      transition: background-color 0.2s;
    }
    
    #${chatContainerId} .dropdown-send-button:hover {
      background-color: #0056b3;
    }
    
    #${chatContainerId} .dropdown-send-button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    
    #${chatContainerId} .loading-dots {
      display: inline-flex;
      gap: 4px;
    }
    
    #${chatContainerId} .loading-dot {
      width: 6px;
      height: 6px;
      background-color: #666;
      border-radius: 50%;
      animation: loading 1.4s infinite ease-in-out both;
    }
    
    #${chatContainerId} .loading-dot:nth-child(1) {
      animation-delay: -0.32s;
    }
    
    #${chatContainerId} .loading-dot:nth-child(2) {
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
  `;
  document.head.appendChild(styleSheet);

  // Initialize chat functionality
  const searchInput = document.getElementById(searchInputId);
  const searchButton = document.getElementById(searchButtonId);
  let chatContainer = document.getElementById(chatContainerId);
  
  // Create chat container structure if it doesn't exist
  if (!chatContainer) {
    chatContainer = document.createElement('div');
    chatContainer.id = chatContainerId;
    chatContainer.className = 'dropdown-chat-container';
    chatContainer.style.display = 'none';
    
    // Add chat HTML structure
    chatContainer.innerHTML = `
      <div class="chat-header">
        <h3 class="chat-title">Chat Assistant</h3>
        <button class="close-icon" id="close-icon">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 4L4 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            <path d="M4 4L12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
      <div class="chat-messages" id="chat-messages">
        <div class="messages-container" id="messages-container"></div>
      </div>
      <div class="chat-input-area">
        <textarea 
          class="dropdown-chat-input" 
          id="dropdown-chat-input"
          placeholder="Ask a follow-up question..."
          rows="1"
        ></textarea>
        <button class="dropdown-send-button" id="dropdown-send-button">Send</button>
      </div>
    `;
    
    // Insert after the search wrapper
    const searchWrapper = searchInput.closest('.search-bar__wrapper') || searchInput.parentElement;
    searchWrapper.style.position = 'relative';
    searchWrapper.appendChild(chatContainer);
  }
  
  // Get elements from chat container
  const closeIcon = chatContainer.querySelector('#close-icon');
  const chatInput = chatContainer.querySelector('#dropdown-chat-input');
  const sendButton = chatContainer.querySelector('#dropdown-send-button');
  const messagesContainer = chatContainer.querySelector('#messages-container');
  const chatMessages = chatContainer.querySelector('#chat-messages');
  
  let eventSource = null;
  
  // Helper functions
  function createLoadingDots() {
    return `
      <div class="loading-dots">
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
        <div class="loading-dot"></div>
      </div>
    `;
  }
  
  function addMessage(content, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;
    messageDiv.textContent = content;
    messagesContainer.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageDiv;
  }
  
  function handleSendMessage() {
    const query = chatInput.value.trim();
    if (!query) return;
    
    // Add user message
    addMessage(query, true);
    
    // Clear input and disable send button
    chatInput.value = '';
    sendButton.disabled = true;
    autoResize();
    
    // Add loading message
    const loadingMessage = addMessage(createLoadingDots());
    
    // Close existing connection
    if (eventSource) {
      eventSource.close();
    }
    
    // Start streaming
    const url = `/stream?query=${encodeURIComponent(query)}&generate_mode=list&display_mode=full&site=${site}`;
    eventSource = new EventSource(url);
    
    let accumulatedContent = '';
    let isFirstChunk = true;
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.error) {
        loadingMessage.innerHTML = `<div style="color: red;">Error: ${data.error}</div>`;
        sendButton.disabled = false;
        eventSource.close();
        return;
      }
      
      if (data.content) {
        if (isFirstChunk) {
          loadingMessage.innerHTML = '';
          isFirstChunk = false;
        }
        accumulatedContent += data.content;
        loadingMessage.innerHTML = accumulatedContent;
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
      
      if (data.done) {
        sendButton.disabled = false;
        eventSource.close();
      }
    };
    
    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      if (loadingMessage.innerHTML === createLoadingDots()) {
        loadingMessage.innerHTML = '<div style="color: red;">Connection error. Please try again.</div>';
      }
      sendButton.disabled = false;
      eventSource.close();
    };
  }
  
  function autoResize() {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  }
  
  // Event handlers
  searchButton.addEventListener('click', () => {
    const query = searchInput.value.trim();
    if (query) {
      chatContainer.style.display = 'flex';
      handleSearchQuery(query);
    }
  });
  
  searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const query = searchInput.value.trim();
      if (query) {
        chatContainer.style.display = 'flex';
        handleSearchQuery(query);
      }
    }
  });
  
  function handleSearchQuery(query) {
    // Clear previous messages
    messagesContainer.innerHTML = '';
    
    // Add user message
    addMessage(query, true);
    
    // Clear search input
    searchInput.value = '';
    
    // Add loading message
    const loadingMessage = addMessage(createLoadingDots());
    
    // Start streaming
    const url = `/stream?query=${encodeURIComponent(query)}&generate_mode=list&display_mode=full&site=${site}`;
    eventSource = new EventSource(url);
    
    let accumulatedContent = '';
    let isFirstChunk = true;
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.error) {
        loadingMessage.innerHTML = `<div style="color: red;">Error: ${data.error}</div>`;
        eventSource.close();
        return;
      }
      
      if (data.content) {
        if (isFirstChunk) {
          loadingMessage.innerHTML = '';
          isFirstChunk = false;
        }
        accumulatedContent += data.content;
        loadingMessage.innerHTML = accumulatedContent;
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
      
      if (data.done) {
        eventSource.close();
      }
    };
    
    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      if (loadingMessage.innerHTML === createLoadingDots()) {
        loadingMessage.innerHTML = '<div style="color: red;">Connection error. Please try again.</div>';
      }
      eventSource.close();
    };
  }
  
  closeIcon.addEventListener('click', () => {
    chatContainer.style.display = 'none';
    if (eventSource) {
      eventSource.close();
    }
  });
  
  sendButton.addEventListener('click', handleSendMessage);
  
  chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });
  
  chatInput.addEventListener('input', autoResize);
  
  // Close on outside click
  document.addEventListener('click', (e) => {
    if (!chatContainer.contains(e.target) && 
        !searchInput.contains(e.target) && 
        !searchButton.contains(e.target)) {
      chatContainer.style.display = 'none';
    }
  });
  
  return { 
    searchInput, 
    searchButton, 
    chatContainer,
    messagesContainer,
    chatInput,
    sendButton
  };
}