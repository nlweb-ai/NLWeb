import eventBus from './event-bus.js';

export class ChatUI {
    constructor() {
        this.container = null;
        this.messagesContainer = null;
        this.inputElement = null;
        this.currentConversation = null;
        this.lastTypingEventTime = 0;
        this.typingThrottle = 3000; // 3 seconds
        this.messageQueue = [];
        this.renderScheduled = false;
        this.typingUsers = new Map();
        this.typingTimeout = null;
        
        // Bind methods to preserve context
        this.handleInputKeydown = this.handleInputKeydown.bind(this);
        this.handleInputChange = this.handleInputChange.bind(this);
        this.handleSendClick = this.handleSendClick.bind(this);
        this.renderQueuedMessages = this.renderQueuedMessages.bind(this);
    }

    initialize(container) {
        this.container = container;
        this.setupDOM();
        this.setupEventListeners();
    }

    setupDOM() {
        this.container.innerHTML = `
            <div class="chat-header">
                <div class="chat-info">
                    <h2 class="chat-title">Select a conversation</h2>
                    <div class="chat-meta">
                        <span class="chat-site"></span>
                        <span class="chat-mode"></span>
                        <span class="chat-participants"></span>
                    </div>
                </div>
                <div class="chat-actions">
                    <button id="share-button" class="btn btn-icon" title="Share conversation" style="display: none;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8"></path>
                            <polyline points="16 6 12 2 8 6"></polyline>
                            <line x1="12" y1="2" x2="12" y2="15"></line>
                        </svg>
                    </button>
                </div>
            </div>
            <div class="chat-messages" id="messages-container">
                <div class="welcome-message">
                    <h3>Welcome to Multi-Participant Chat</h3>
                    <p>Select a conversation from the sidebar or start a new one.</p>
                </div>
            </div>
            <div id="typing-indicators" class="typing-indicators" style="display: none;">
                <div class="typing-users"></div>
            </div>
            <div class="chat-input-container">
                <div class="chat-input-wrapper">
                    <textarea 
                        id="chat-input" 
                        class="chat-input" 
                        placeholder="Type your message..."
                        rows="1"
                        disabled
                    ></textarea>
                    <button id="send-button" class="btn btn-primary" disabled>
                        Send
                    </button>
                </div>
            </div>
        `;

        this.messagesContainer = this.container.querySelector('#messages-container');
        this.inputElement = this.container.querySelector('#chat-input');
        this.sendButton = this.container.querySelector('#send-button');
        this.shareButton = this.container.querySelector('#share-button');
        this.typingIndicators = this.container.querySelector('#typing-indicators');
        this.typingUsersContainer = this.container.querySelector('.typing-users');
    }

    setupEventListeners() {
        // Input events
        this.inputElement.addEventListener('keydown', this.handleInputKeydown);
        this.inputElement.addEventListener('input', this.handleInputChange);
        this.sendButton.addEventListener('click', this.handleSendClick);

        // Listen for state changes
        eventBus.on('state:currentConversation', (conversation) => {
            this.setCurrentConversation(conversation);
        });

        eventBus.on('websocket:message', (message) => {
            this.queueMessage(message);
        });

        eventBus.on('websocket:ai_response', (message) => {
            this.queueMessage(message);
        });

        eventBus.on('websocket:typing', (data) => {
            this.updateTypingIndicator(data);
        });

        eventBus.on('websocket:participant_update', (data) => {
            this.updateParticipants(data);
        });

        // Share button
        this.shareButton.addEventListener('click', () => {
            eventBus.emit('ui:shareConversation', { conversationId: this.currentConversation?.id });
        });
    }

    setCurrentConversation(conversation) {
        this.currentConversation = conversation;
        this.clearMessages();
        this.updateChatHeader(conversation);
        this.setInputMode(conversation?.mode || 'multi');
        
        if (conversation) {
            this.enableInput();
            this.shareButton.style.display = 'block';
            
            // Load existing messages
            if (conversation.messages && conversation.messages.length > 0) {
                conversation.messages.forEach(message => this.queueMessage(message));
            }
        } else {
            this.disableInput();
            this.shareButton.style.display = 'none';
            this.showWelcomeMessage();
        }
    }

    updateChatHeader(conversation) {
        const titleElement = this.container.querySelector('.chat-title');
        const siteElement = this.container.querySelector('.chat-site');
        const modeElement = this.container.querySelector('.chat-mode');
        const participantsElement = this.container.querySelector('.chat-participants');

        if (conversation) {
            titleElement.textContent = conversation.title || 'New Conversation';
            
            // Site info
            if (conversation.sites && conversation.sites.length > 0) {
                siteElement.textContent = conversation.sites.join(', ');
                siteElement.style.display = 'inline';
            } else {
                siteElement.style.display = 'none';
            }

            // Mode
            modeElement.textContent = conversation.mode || 'multi';
            
            // Participants
            const participantCount = conversation.participants ? conversation.participants.length : 1;
            participantsElement.textContent = `${participantCount} participant${participantCount !== 1 ? 's' : ''}`;
        } else {
            titleElement.textContent = 'Select a conversation';
            siteElement.style.display = 'none';
            modeElement.textContent = '';
            participantsElement.textContent = '';
        }
    }

    clearMessages() {
        this.messagesContainer.innerHTML = '';
        this.messageQueue = [];
        this.typingUsers.clear();
        this.updateTypingDisplay();
    }

    showWelcomeMessage() {
        this.messagesContainer.innerHTML = `
            <div class="welcome-message">
                <h3>Welcome to Multi-Participant Chat</h3>
                <p>Select a conversation from the sidebar or start a new one.</p>
            </div>
        `;
    }

    queueMessage(message) {
        this.messageQueue.push(message);
        
        if (!this.renderScheduled) {
            this.renderScheduled = true;
            requestAnimationFrame(this.renderQueuedMessages);
        }
    }

    renderQueuedMessages() {
        const fragment = document.createDocumentFragment();
        
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            const messageElement = this.renderMessage(message);
            if (messageElement) {
                fragment.appendChild(messageElement);
            }
        }
        
        this.messagesContainer.appendChild(fragment);
        this.scrollToBottom();
        this.renderScheduled = false;
    }

    renderMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message';
        messageDiv.dataset.messageId = message.id || message.message_id;
        
        // Determine message type and sender
        const isAI = message.type === 'ai_response' || message.sender === 'ai';
        const isSystem = message.type === 'system' || message.sender === 'system';
        
        if (isAI) {
            messageDiv.classList.add('ai-message');
        } else if (isSystem) {
            messageDiv.classList.add('system-message');
        } else {
            messageDiv.classList.add('user-message');
        }

        // Build message content
        const senderInfo = this.renderSenderInfo(message);
        const content = this.renderMessageContent(message);
        const timestamp = this.renderTimestamp(message.timestamp || message.created_at);

        messageDiv.innerHTML = `
            <div class="message-header">
                ${senderInfo}
                ${timestamp}
            </div>
            <div class="message-content">
                ${content}
            </div>
        `;

        return messageDiv;
    }

    renderSenderInfo(message) {
        const sender = message.participant || message.sender || {};
        const displayName = this.sanitizeContent(sender.displayName || sender.display_name || 'Unknown');
        
        if (message.type === 'ai_response' || message.sender === 'ai') {
            return '<span class="sender-name">AI Assistant</span>';
        } else if (message.type === 'system') {
            return '<span class="sender-name">System</span>';
        }
        
        return `<span class="sender-name">${displayName}</span>`;
    }

    renderMessageContent(message) {
        // Always sanitize content first
        const sanitized = this.sanitizeContent(message.content || '');
        
        // For AI responses with special types, use existing renderers
        if (message.type === 'ai_response' && message.message_type) {
            return this.renderAIResponse(message, sanitized);
        }
        
        // Regular text message
        return `<div class="message-text">${sanitized}</div>`;
    }

    renderAIResponse(message, sanitizedContent) {
        // Check if we have JSON content to render
        if (message.data || message.results) {
            try {
                // Use existing json-renderer if available
                if (window.JsonRenderer) {
                    const renderer = new window.JsonRenderer();
                    const rendered = renderer.render(message.data || message.results);
                    // Sanitize the rendered HTML as well
                    return this.sanitizeContent(rendered);
                }
            } catch (error) {
                console.error('Failed to render AI response:', error);
            }
        }
        
        // Fallback to text content
        return `<div class="message-text">${sanitizedContent}</div>`;
    }

    renderTimestamp(timestamp) {
        if (!timestamp) return '';
        
        const date = new Date(timestamp);
        const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        return `<span class="message-timestamp">${time}</span>`;
    }

    sanitizeContent(content) {
        if (typeof content !== 'string') {
            content = String(content);
        }
        
        // Use DOMPurify if available, otherwise basic escaping
        if (window.DOMPurify) {
            return window.DOMPurify.sanitize(content, {
                ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 'code', 'pre'],
                ALLOWED_ATTR: ['href', 'target', 'rel']
            });
        }
        
        // Fallback to basic HTML escaping
        const div = document.createElement('div');
        div.textContent = content;
        return div.innerHTML;
    }

    handleInputKeydown(event) {
        const now = Date.now();
        
        // Handle Enter key for sending
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage();
            return;
        }
        
        // Typing indicator throttling
        if (!this.lastTypingEventTime || (now - this.lastTypingEventTime) > this.typingThrottle) {
            this.lastTypingEventTime = now;
            eventBus.emit('ui:typing', { isTyping: true });
        }
    }

    handleInputChange() {
        // Auto-resize textarea
        this.inputElement.style.height = 'auto';
        this.inputElement.style.height = Math.min(this.inputElement.scrollHeight, 120) + 'px';
        
        // Enable/disable send button
        this.sendButton.disabled = !this.inputElement.value.trim();
    }

    handleSendClick() {
        this.sendMessage();
    }

    sendMessage() {
        const content = this.inputElement.value.trim();
        if (!content || !this.currentConversation) return;
        
        // Clear typing indicator
        this.lastTypingEventTime = 0;
        eventBus.emit('ui:typing', { isTyping: false });
        
        // Emit send event
        eventBus.emit('ui:sendMessage', {
            conversationId: this.currentConversation.id,
            content: content,
            sites: this.currentConversation.sites || [],
            mode: this.currentConversation.mode || 'summarize'
        });
        
        // Clear input
        this.inputElement.value = '';
        this.inputElement.style.height = 'auto';
        this.sendButton.disabled = true;
    }

    updateTypingIndicator(data) {
        if (!data.participant) return;
        
        const participantId = data.participant.participantId || data.participant.participant_id;
        
        if (data.is_typing) {
            this.typingUsers.set(participantId, {
                displayName: data.participant.displayName || data.participant.display_name || 'Someone',
                timestamp: Date.now()
            });
        } else {
            this.typingUsers.delete(participantId);
        }
        
        this.updateTypingDisplay();
        
        // Clear old typing indicators after 5 seconds
        this.scheduleTypingCleanup();
    }

    updateTypingDisplay() {
        if (this.typingUsers.size === 0) {
            this.typingIndicators.style.display = 'none';
            return;
        }
        
        const typingNames = Array.from(this.typingUsers.values())
            .map(user => this.sanitizeContent(user.displayName));
        
        let text = '';
        if (typingNames.length === 1) {
            text = `${typingNames[0]} is typing...`;
        } else if (typingNames.length === 2) {
            text = `${typingNames[0]} and ${typingNames[1]} are typing...`;
        } else {
            text = `${typingNames.length} people are typing...`;
        }
        
        this.typingUsersContainer.innerHTML = text;
        this.typingIndicators.style.display = 'block';
    }

    scheduleTypingCleanup() {
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
        }
        
        this.typingTimeout = setTimeout(() => {
            const now = Date.now();
            let changed = false;
            
            // Remove typing indicators older than 5 seconds
            for (const [id, user] of this.typingUsers.entries()) {
                if (now - user.timestamp > 5000) {
                    this.typingUsers.delete(id);
                    changed = true;
                }
            }
            
            if (changed) {
                this.updateTypingDisplay();
            }
        }, 1000);
    }

    updateParticipants(data) {
        if (this.currentConversation) {
            this.currentConversation.participants = data.participants;
            this.updateChatHeader(this.currentConversation);
        }
    }

    setInputMode(mode) {
        if (mode === 'single') {
            this.inputElement.placeholder = 'Type your message (100ms delay for single mode)...';
        } else {
            this.inputElement.placeholder = 'Type your message (2s delay for multi mode)...';
        }
    }

    enableInput() {
        this.inputElement.disabled = false;
        this.sendButton.disabled = !this.inputElement.value.trim();
        this.inputElement.focus();
    }

    disableInput() {
        this.inputElement.disabled = true;
        this.sendButton.disabled = true;
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    showTypingIndicators(typingUsers) {
        // Public method for external updates
        this.typingUsers.clear();
        typingUsers.forEach(user => {
            this.typingUsers.set(user.participantId || user.participant_id, {
                displayName: user.displayName || user.display_name || 'Someone',
                timestamp: Date.now()
            });
        });
        this.updateTypingDisplay();
    }

    destroy() {
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
        }
    }
}