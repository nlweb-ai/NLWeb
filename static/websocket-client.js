/**
 * WebSocket client with exponential backoff reconnection.
 * Example implementation for chat system.
 */

class ChatWebSocketClient {
  constructor(options = {}) {
    // Configuration
    this.url = options.url || null;
    this.conversationId = options.conversationId;
    this.token = options.token;
    this.maxRetries = options.maxRetries || 10;
    this.onMessage = options.onMessage || (() => {});
    this.onConnect = options.onConnect || (() => {});
    this.onDisconnect = options.onDisconnect || (() => {});
    this.onError = options.onError || (() => {});
    
    // State
    this.ws = null;
    this.reconnectAttempt = 0;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.isIntentionallyClosed = false;
    this.messageQueue = [];
    
    // Ping/pong tracking
    this.lastPingTime = null;
    this.lastPongTime = null;
    this.pingInterval = 30000; // 30 seconds
    this.pongTimeout = 600000; // 10 minutes
  }
  
  /**
   * Connect to WebSocket server
   */
  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return;
    }
    
    this.isIntentionallyClosed = false;
    
    try {
      // Build WebSocket URL with auth token
      const wsUrl = new URL(this.url);
      wsUrl.searchParams.set('token', this.token);
      wsUrl.searchParams.set('conversation_id', this.conversationId);
      
      this.ws = new WebSocket(wsUrl.toString());
      
      // Set up event handlers
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      
    } catch (error) {
      this.scheduleReconnect();
    }
  }
  
  /**
   * Handle WebSocket open event
   */
  handleOpen(event) {
    
    // Reset reconnection state
    this.reconnectAttempt = 0;
    
    // Start heartbeat
    this.startHeartbeat();
    
    // Send any queued messages
    this.flushMessageQueue();
    
    // Notify callback
    this.onConnect(event);
  }
  
  /**
   * Handle incoming WebSocket message
   */
  handleMessage(event) {
    try {
      const data = JSON.parse(event.data);
      
      // Handle pong response
      if (data.type === 'pong') {
        this.lastPongTime = Date.now();
        return;
      }
      
      // Handle other messages
      this.onMessage(data);
      
    } catch (error) {
    }
  }
  
  /**
   * Handle WebSocket close event
   */
  handleClose(event) {
    
    // Stop heartbeat
    this.stopHeartbeat();
    
    // Clear WebSocket reference
    this.ws = null;
    
    // Notify callback
    this.onDisconnect(event);
    
    // Attempt reconnection if not intentionally closed
    if (!this.isIntentionallyClosed) {
      this.scheduleReconnect();
    }
  }
  
  /**
   * Handle WebSocket error event
   */
  handleError(event) {
    this.onError(event);
  }
  
  /**
   * Schedule reconnection with exponential backoff
   */
  scheduleReconnect() {
    if (this.reconnectAttempt >= this.maxRetries) {
      this.onError(new Error('Max reconnection attempts reached. Please refresh the page.'));
      return;
    }
    
    // Calculate backoff delay: 1s, 2s, 4s, 8s, 16s, max 30s
    const delay = Math.min(Math.pow(2, this.reconnectAttempt) * 1000, 30000);
    
    
    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempt++;
      this.connect();
    }, delay);
  }
  
  /**
   * Cancel pending reconnection
   */
  cancelReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
  
  /**
   * Start heartbeat mechanism
   */
  startHeartbeat() {
    this.stopHeartbeat();
    
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        // Check for pong timeout
        if (this.lastPingTime && !this.lastPongTime) {
          const timeSinceLastPing = Date.now() - this.lastPingTime;
          if (timeSinceLastPing > this.pongTimeout) {
            this.ws.close(4000, 'Pong timeout');
            return;
          }
        }
        
        // Send ping
        this.sendMessage({ type: 'ping' });
        this.lastPingTime = Date.now();
        this.lastPongTime = null;
      }
    }, this.pingInterval);
  }
  
  /**
   * Stop heartbeat mechanism
   */
  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    this.lastPingTime = null;
    this.lastPongTime = null;
  }
  
  /**
   * Send a message through WebSocket
   */
  sendMessage(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
        return true;
      } catch (error) {
        this.messageQueue.push(message);
        return false;
      }
    } else {
      // Queue message for later
      this.messageQueue.push(message);
      return false;
    }
  }
  
  /**
   * Send all queued messages
   */
  flushMessageQueue() {
    while (this.messageQueue.length > 0 && this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = this.messageQueue.shift();
      try {
        this.ws.send(JSON.stringify(message));
      } catch (error) {
        // Put it back
        this.messageQueue.unshift(message);
        break;
      }
    }
  }
  
  /**
   * Close the WebSocket connection
   */
  close() {
    this.isIntentionallyClosed = true;
    this.cancelReconnect();
    this.stopHeartbeat();
    
    if (this.ws) {
      this.ws.close(1000, 'Client closing connection');
      this.ws = null;
    }
    
    this.messageQueue = [];
  }
  
  /**
   * Get current connection state
   */
  getState() {
    if (!this.ws) {
      return 'disconnected';
    }
    
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      case WebSocket.CLOSING:
        return 'closing';
      case WebSocket.CLOSED:
        return 'disconnected';
      default:
        return 'unknown';
    }
  }
}

/**
 * Example usage in a chat application
 */
class ChatApplication {
  constructor() {
    this.wsClient = null;
    this.conversationId = null;
    this.authToken = null;
  }
  
  /**
   * Initialize WebSocket connection for a conversation
   */
  initializeWebSocket(conversationId, authToken) {
    this.conversationId = conversationId;
    this.authToken = authToken;
    
    // Create WebSocket client
    this.wsClient = new ChatWebSocketClient({
      url: `wss://${window.location.host}/chat/ws/${conversationId}`,
      conversationId: conversationId,
      token: authToken,
      maxRetries: 10,
      
      // Handle incoming messages
      onMessage: (data) => {
        
        switch (data.type) {
          case 'message':
            this.handleChatMessage(data);
            break;
          case 'participant_update':
            this.handleParticipantUpdate(data);
            break;
          case 'error':
            this.handleServerError(data);
            break;
          default:
        }
      },
      
      // Handle connection events
      onConnect: () => {
        this.updateConnectionStatus('connected');
        this.hideReconnectionNotice();
      },
      
      onDisconnect: (event) => {
        this.updateConnectionStatus('disconnected');
        
        if (!event.wasClean) {
          this.showReconnectionNotice();
        }
      },
      
      onError: (error) => {
        
        // Check if max retries reached
        if (error.message && error.message.includes('Max reconnection attempts')) {
          this.showErrorModal(
            'Connection Failed',
            'Unable to establish connection to the chat server. Please refresh the page to try again.',
            () => window.location.reload()
          );
        }
      }
    });
    
    // Connect
    this.wsClient.connect();
  }
  
  /**
   * Send a chat message
   */
  sendMessage(content) {
    if (!this.wsClient) {
      return;
    }
    
    const message = {
      type: 'message',
      content: content,
      message_id: this.generateMessageId(),
      timestamp: new Date().toISOString()
    };
    
    const sent = this.wsClient.sendMessage(message);
    if (!sent) {
      this.showMessageQueuedNotice();
    }
  }
  
  /**
   * Handle incoming chat message
   */
  handleChatMessage(data) {
    // Add message to UI
    this.addMessageToChat(data);
  }
  
  /**
   * Handle participant update
   */
  handleParticipantUpdate(data) {
    // Update participant list
    this.updateParticipantList(data.participants);
  }
  
  /**
   * Handle server error
   */
  handleServerError(data) {
    if (data.code === 'QUEUE_FULL') {
      this.showNotice('Message queue full. Please wait before sending more messages.');
    } else {
      this.showNotice(`Server error: ${data.content || data.message}`);
    }
  }
  
  /**
   * Update connection status in UI
   */
  updateConnectionStatus(status) {
    const statusElement = document.getElementById('connection-status');
    if (statusElement) {
      statusElement.textContent = status;
      statusElement.className = `status-${status}`;
    }
  }
  
  /**
   * Show reconnection notice
   */
  showReconnectionNotice() {
    const notice = document.getElementById('reconnection-notice');
    if (notice) {
      notice.style.display = 'block';
      notice.textContent = 'Reconnecting to chat...';
    }
  }
  
  /**
   * Hide reconnection notice
   */
  hideReconnectionNotice() {
    const notice = document.getElementById('reconnection-notice');
    if (notice) {
      notice.style.display = 'none';
    }
  }
  
  /**
   * Show error modal
   */
  showErrorModal(title, message, onClose) {
    // Implementation depends on your UI framework
    alert(`${title}\n\n${message}`);
    if (onClose) onClose();
  }
  
  /**
   * Generate unique message ID
   */
  generateMessageId() {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  // Placeholder methods for UI updates
  addMessageToChat(data) { /* ... */ }
  updateParticipantList(participants) { /* ... */ }
  showNotice(message) { /* ... */ }
  showMessageQueuedNotice() { /* ... */ }
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { ChatWebSocketClient, ChatApplication };
}
