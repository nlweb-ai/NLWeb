/**
 * WebSocket-based chat interface for multi-participant chat
 * Handles WebSocket communication and delegates UI rendering to ChatUICommon
 */

import { ConversationManager } from './conversation-manager.js';
import { ManagedEventSource } from './managed-event-source.js';
import { ChatUICommon } from './chat-ui-common.js';

export class ModernChatInterface {
  constructor(options = {}) {
    this.options = options;
    this.currentStreamingMessage = null;
    this.conversationId = null;
    this.userId = null;
    this.ws = null;
    this.wsReconnectAttempts = 0;
    this.wsMaxReconnectAttempts = 5;
    this.wsReconnectDelay = 1000;
    this.messageQueue = [];
    this.selectedMode = 'list';
    this.selectedSite = 'all';
    
    // UI rendering delegate
    this.uiCommon = new ChatUICommon();
    
    // Conversation management
    this.conversationManager = new ConversationManager();
    
    // DOM element references
    this.elements = {
      messagesContainer: document.getElementById('messages-container'),
      chatMessages: document.getElementById('chat-messages'),
      chatInput: document.getElementById('chat-input'),
      sendButton: document.getElementById('send-button'),
      conversationsList: document.getElementById('conversations-list')
    };
    
    // Initialize
    this.init();
  }
  
  init() {
    this.bindEvents();
    this.initializeWebSocket();
    
    // Load conversation from URL if present
    const urlParams = new URLSearchParams(window.location.search);
    const conversationId = urlParams.get('conversation');
    if (conversationId) {
      this.loadConversation(conversationId);
    }
  }
  
  bindEvents() {
    // Send button
    if (this.elements.sendButton) {
      this.elements.sendButton.addEventListener('click', () => {
        const message = this.elements.chatInput.value.trim();
        if (message) {
          this.sendMessage(message);
        }
      });
    }
    
    // Enter key to send
    if (this.elements.chatInput) {
      this.elements.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          const message = this.elements.chatInput.value.trim();
          if (message) {
            this.sendMessage(message);
          }
        }
      });
    }
  }
  
  initializeWebSocket() {
    // Generate a conversation ID if we don't have one
    if (!this.conversationId) {
      this.conversationId = 'conv_' + Math.random().toString(36).substr(2, 9);
    }
    
    const wsUrl = window.location.origin === 'file://' 
      ? `ws://localhost:8000/chat/ws/${this.conversationId}`
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/chat/ws/${this.conversationId}`;
    
    try {
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => {
        this.wsReconnectAttempts = 0;
        
        // Send queued messages
        while (this.messageQueue.length > 0) {
          const message = this.messageQueue.shift();
          this.ws.send(JSON.stringify(message));
        }
        
        // Join conversation if we have one
        if (this.conversationId) {
          this.joinConversation(this.conversationId);
        }
      };
      
      this.ws.onmessage = (event) => {
        this.handleWebSocketMessage(event);
      };
      
      this.ws.onerror = (error) => {
      };
      
      this.ws.onclose = () => {
        this.reconnectWebSocket();
      };
      
    } catch (error) {
    }
  }
  
  reconnectWebSocket() {
    if (this.wsReconnectAttempts < this.wsMaxReconnectAttempts) {
      this.wsReconnectAttempts++;
      const delay = this.wsReconnectDelay * Math.pow(2, this.wsReconnectAttempts - 1);
      
      setTimeout(() => {
        this.initializeWebSocket();
      }, delay);
    } else {
    }
  }
  
  handleWebSocketMessage(event) {
    try {
      const data = JSON.parse(event.data);
      
      // Handle different message types
      switch (data.type) {
        case 'conversation_created':
          this.conversationId = data.conversation_id;
          this.updateURL();
          break;
          
        case 'message':
          // Handle chat messages from other participants
          if (data.sender_id !== this.userId) {
            this.addMessageToUI(data.content, 'assistant', false, data.sender_info);
          }
          break;
          
        case 'stream_start':
          this.handleStreamStart(data);
          break;
          
        case 'stream_data':
          this.handleStreamingData(data);
          break;
          
        case 'stream_end':
          this.handleStreamEnd(data);
          break;
          
        case 'participant_joined':
          break;
          
        case 'participant_left':
          break;
          
        default:
          // For SSE-style events, process them directly
          if (data.answer || data.items || data.message_type) {
            this.handleStreamingData(data);
          }
      }
    } catch (error) {
    }
  }
  
  handleStreamStart(data) {
    // Create a new streaming message bubble
    const bubble = document.createElement('div');
    bubble.className = 'message assistant-message streaming-message';
    
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    bubble.appendChild(textDiv);
    
    this.elements.messagesContainer.appendChild(bubble);
    
    this.currentStreamingMessage = {
      bubble,
      textDiv,
      messageContent: '',
      allResults: []
    };
  }
  
  handleStreamingData(data) {
    if (!this.currentStreamingMessage) {
      // If no streaming message exists, create one
      this.handleStreamStart(data);
    }
    
    const { textDiv, messageContent, allResults } = this.currentStreamingMessage;
    
    // Use the common UI library to process the message
    const result = this.uiCommon.processMessageByType(data, textDiv, {
      messageContent,
      allResults
    });
    
    // Update the streaming context
    this.currentStreamingMessage.messageContent = result.messageContent;
    this.currentStreamingMessage.allResults = result.allResults;
  }
  
  handleStreamEnd(data) {
    if (this.currentStreamingMessage) {
      this.currentStreamingMessage.bubble.classList.remove('streaming-message');
      this.currentStreamingMessage = null;
    }
  }
  
  sendMessage(message) {
    if (!message.trim()) return;
    
    // Add user message to UI
    this.addMessageToUI(message, 'user');
    
    // Clear input
    if (this.elements.chatInput) {
      this.elements.chatInput.value = '';
    }
    
    // Prepare message data
    const messageData = {
      type: 'message',
      content: message,
      conversation_id: this.conversationId,
      user_id: this.userId || this.getOrCreateAnonymousUserId(),
      mode: this.selectedMode,
      site: this.selectedSite
    };
    
    // Send via WebSocket or queue if not connected
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(messageData));
    } else {
      this.messageQueue.push(messageData);
      this.initializeWebSocket();
    }
    
    // Also trigger SSE query for backward compatibility
    this.getStreamingResponse(message);
  }
  
  getStreamingResponse(query) {
    const baseUrl = window.location.origin === 'file://' ? 'http://localhost:8000' : '';
    const params = new URLSearchParams({
      q: query,
      mode: this.selectedMode,
      site: this.selectedSite,
      conversation_id: this.conversationId || '',
      user_id: this.userId || this.getOrCreateAnonymousUserId()
    });
    
    const url = `${baseUrl}/stream?${params}`;
    
    // Use ManagedEventSource for SSE
    const eventSource = new ManagedEventSource(url, {
      maxRetries: 3,
      retryDelay: 1000
    });
    
    // Create streaming message UI
    this.handleStreamStart({});
    
    eventSource.handleMessage = (data) => {
      this.handleStreamingData(data);
    };
    
    eventSource.onComplete = () => {
      this.handleStreamEnd({});
    };
    
    eventSource.connect();
  }
  
  addMessageToUI(content, type, animate = true, senderInfo = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    if (animate) {
      messageDiv.classList.add('message-appear');
    }
    
    // Add sender info for multi-participant chat
    if (senderInfo && type === 'assistant') {
      const senderDiv = document.createElement('div');
      senderDiv.className = 'message-sender';
      senderDiv.textContent = senderInfo.name || 'Anonymous';
      messageDiv.appendChild(senderDiv);
    }
    
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.textContent = content;
    messageDiv.appendChild(textDiv);
    
    this.elements.messagesContainer.appendChild(messageDiv);
    this.scrollToBottom();
  }
  
  getOrCreateAnonymousUserId() {
    let userId = localStorage.getItem('anonymousUserId');
    if (!userId) {
      userId = 'anon_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('anonymousUserId', userId);
    }
    this.userId = userId;
    return userId;
  }
  
  joinConversation(conversationId) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'join',
        conversation_id: conversationId,
        user_id: this.userId || this.getOrCreateAnonymousUserId()
      }));
    }
  }
  
  loadConversation(conversationId) {
    this.conversationId = conversationId;
    this.joinConversation(conversationId);
    // Load conversation history if needed
  }
  
  updateURL() {
    if (this.conversationId) {
      const url = new URL(window.location);
      url.searchParams.set('conversation', this.conversationId);
      window.history.replaceState({}, '', url);
    }
  }
  
  scrollToBottom() {
    if (this.elements.chatMessages) {
      this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    new ModernChatInterface();
  });
} else {
  new ModernChatInterface();
}
