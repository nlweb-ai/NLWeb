import eventBus from './event-bus.js';

class WebSocketService {
    constructor() {
        this.ws = null;
        this.conversationId = null;
        this.participantInfo = null;
        this.reconnectDelay = 1000; // Start at 1 second
        this.maxReconnectDelay = 30000; // Max 30 seconds
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.heartbeatInterval = 30000; // 30 seconds
        this.messageQueue = [];
        this.lastSequenceId = 0;
        this.lastTypingSent = 0;
        this.typingThrottle = 3000; // 3 seconds
        this.isConnecting = false;
        this.isConnected = false;
    }

    async connect(conversationId, participantInfo) {
        if (this.isConnecting || (this.isConnected && this.conversationId === conversationId)) {
            return;
        }

        this.conversationId = conversationId;
        this.participantInfo = participantInfo;
        this.isConnecting = true;

        try {
            await this._establishConnection();
        } catch (error) {
            this.isConnecting = false;
            this._scheduleReconnection();
        }
    }

    async _establishConnection() {
        const wsUrl = this._buildWebSocketUrl();
        
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                this.isConnected = true;
                this.isConnecting = false;
                this.reconnectDelay = 1000; // Reset delay on successful connection
                
                this._startHeartbeat();
                this._sendJoinMessage();
                this._sendSyncRequest();
                this._flushMessageQueue();
                
                eventBus.emit('websocket:connected', { conversationId: this.conversationId });
                resolve();
            };

            this.ws.onmessage = (event) => {
                this._handleMessage(event.data);
            };

            this.ws.onclose = (event) => {
                this.isConnected = false;
                this.isConnecting = false;
                this._stopHeartbeat();
                
                if (event.code !== 1000) { // Not a normal closure
                    this._scheduleReconnection();
                }
                
                eventBus.emit('websocket:disconnected', { 
                    conversationId: this.conversationId,
                    code: event.code 
                });
            };

            this.ws.onerror = (error) => {
                this.isConnected = false;
                this.isConnecting = false;
                reject(error);
            };
        });
    }

    _buildWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        let url = `${protocol}//${host}/chat/ws?conversation_id=${this.conversationId}`;
        
        // Add auth token if available
        const authToken = sessionStorage.getItem('authToken');
        if (authToken) {
            url += `&token=${encodeURIComponent(authToken)}`;
        }
        
        return url;
    }

    _sendJoinMessage() {
        const joinMessage = {
            type: 'join',
            conversation_id: this.conversationId,
            participant: this.participantInfo
        };
        this._send(joinMessage);
    }

    _sendSyncRequest() {
        if (this.lastSequenceId > 0) {
            const syncMessage = {
                type: 'sync',
                conversation_id: this.conversationId,
                last_sequence_id: this.lastSequenceId
            };
            this._send(syncMessage);
        }
    }

    _handleMessage(data) {
        try {
            const message = JSON.parse(data);
            
            // Update sequence ID for sync
            if (message.sequence_id) {
                this.lastSequenceId = Math.max(this.lastSequenceId, message.sequence_id);
            }

            // Route message by type
            switch (message.type) {
                case 'message':
                    eventBus.emit('websocket:message', message);
                    break;
                    
                case 'ai_response':
                    // Further route by message_type
                    const responseType = message.message_type || 'unknown';
                    eventBus.emit('websocket:ai_response', message);
                    eventBus.emit(`websocket:ai_response:${responseType}`, message);
                    break;
                    
                case 'participant_update':
                    eventBus.emit('websocket:participant_update', message);
                    break;
                    
                case 'typing':
                    eventBus.emit('websocket:typing', message);
                    break;
                    
                case 'sync':
                    eventBus.emit('websocket:sync', message);
                    break;
                    
                case 'error':
                    eventBus.emit('websocket:error', message);
                    break;
                    
                case 'pong':
                    // Heartbeat response
                    break;
                    
                default:
                    eventBus.emit('websocket:unknown', message);
            }
            
        } catch (error) {
        }
    }

    sendMessage(content, sites = [], mode = 'summarize') {
        const message = {
            type: 'message',
            conversation_id: this.conversationId,
            content: {
                query: content,
                site: sites.length > 0 ? sites[0] : 'all',  // Use 'all' for multi-site queries
                mode: mode
            },
            participant: this.participantInfo
        };
        
        this._send(message);
        this._clearTyping();
    }

    sendTyping(isTyping) {
        const now = Date.now();
        
        if (isTyping) {
            // Throttle typing events
            if (now - this.lastTypingSent < this.typingThrottle) {
                return;
            }
            this.lastTypingSent = now;
        }
        
        const typingMessage = {
            type: 'typing',
            conversation_id: this.conversationId,
            participant: this.participantInfo,
            is_typing: isTyping
        };
        
        this._send(typingMessage);
    }

    _clearTyping() {
        this.sendTyping(false);
    }

    _send(message) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            // Queue message for when connection is restored
            this.messageQueue.push(message);
        }
    }

    _flushMessageQueue() {
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            this._send(message);
        }
    }

    _startHeartbeat() {
        this._stopHeartbeat();
        this.heartbeatTimer = setInterval(() => {
            if (this.isConnected) {
                this._send({ type: 'ping' });
            }
        }, this.heartbeatInterval);
    }

    _stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    _scheduleReconnection() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        
        
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            
            if (!this.isConnected && this.conversationId) {
                this.connect(this.conversationId, this.participantInfo);
            }
        }, this.reconnectDelay);
        
        // Exponential backoff with max delay
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    }

    disconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        this._stopHeartbeat();
        
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
            this.ws = null;
        }
        
        this.isConnected = false;
        this.isConnecting = false;
        this.conversationId = null;
        this.participantInfo = null;
        this.messageQueue = [];
        this.lastSequenceId = 0;
        
        eventBus.emit('websocket:disconnected', { manual: true });
    }

    getConnectionState() {
        return {
            isConnected: this.isConnected,
            isConnecting: this.isConnecting,
            conversationId: this.conversationId,
            queuedMessages: this.messageQueue.length,
            lastSequenceId: this.lastSequenceId
        };
    }
}

// Export singleton instance
export default new WebSocketService();
