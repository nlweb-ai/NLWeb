/**
 * Multi-Participant Chat Application
 * Main entry point and orchestrator
 */

// Import all services and UI components
import eventBus from './chat/event-bus.js';
import configService from './chat/config-service.js';
import identityService from './chat/identity-service.js';
// import apiService from './chat/api-service.js'; // TODO: Create this
// import stateManager from './chat/state-manager.js'; // TODO: Create this
import webSocketService from './chat/websocket-service.js';
import { SidebarUI } from './chat/sidebar-ui.js';
import { ChatUI } from './chat/chat-ui.js';
import { ShareUI } from './chat/share-ui.js';
import { SiteSelectorUI } from './chat/site-selector-ui.js';

class MultiChatApp {
    constructor() {
        // Services (singletons)
        this.eventBus = eventBus;
        this.configService = configService;
        this.identityService = identityService;
        // this.apiService = apiService; // TODO
        // this.stateManager = stateManager; // TODO
        this.webSocketService = webSocketService;
        
        // UI Components (instances)
        this.sidebarUI = null;
        this.chatUI = null;
        this.shareUI = null;
        this.siteSelectorUI = null;
        
        // Current state
        this.currentConversationId = null;
        this.currentIdentity = null;
        this.isInitialized = false;
        
        // Message tracking
        this.pendingMessages = new Map(); // Track optimistic messages
        this.lastSequenceId = 0;
        
        // Typing indicator state
        this.lastTypingTime = 0;
        this.typingThrottle = 3000; // 3 seconds
    }
    
    async initialize() {
        try {
            console.log('Initializing Multi-Chat Application...');
            
            // 1. Load configuration
            await this.configService.initialize();
            
            // 2. Initialize identity (will prompt if needed)
            this.currentIdentity = await this.identityService.ensureIdentity();
            if (!this.currentIdentity) {
                console.error('Failed to establish identity');
                this.showError('Please provide an identity to use the chat');
                return;
            }
            
            // 3. Initialize state manager (TODO)
            // await this.stateManager.initialize();
            
            // 4. Create UI components
            this.initializeUI();
            
            // 5. Check for shared conversation link
            const shareHandled = await this.checkForSharedLink();
            
            // 6. Set up event wiring
            this.wireUpEvents();
            
            // 7. Handle initial conversation
            if (!shareHandled) {
                await this.handleInitialConversation();
            }
            
            this.isInitialized = true;
            console.log('Multi-Chat Application initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.showError('Failed to initialize chat application');
        }
    }
    
    initializeUI() {
        // Get DOM containers
        const sidebarContainer = document.querySelector('.sidebar');
        const chatContainer = document.querySelector('.chat-container');
        
        // Initialize UI components
        this.sidebarUI = new SidebarUI();
        this.chatUI = new ChatUI();
        this.shareUI = new ShareUI();
        this.siteSelectorUI = new SiteSelectorUI();
        
        // Initialize with containers where needed
        if (sidebarContainer) {
            this.sidebarUI.initialize(sidebarContainer);
        }
        if (chatContainer) {
            this.chatUI.initialize(chatContainer);
        }
        
        this.shareUI.initialize();
        this.siteSelectorUI.initialize();
    }
    
    wireUpEvents() {
        // WebSocket events → State Manager → UI updates
        this.eventBus.on('websocket:connected', () => {
            console.log('WebSocket connected');
            // TODO: Update state manager
        });
        
        this.eventBus.on('websocket:disconnected', () => {
            console.log('WebSocket disconnected');
            // TODO: Update state manager
        });
        
        // Message receiving flow
        this.eventBus.on('websocket:message', (message) => {
            this.handleIncomingMessage(message);
        });
        
        // AI response handling with routing
        this.eventBus.on('websocket:ai_response', (response) => {
            this.handleAIResponse(response);
        });
        
        // Handle different AI response types
        this.eventBus.on('websocket:ai_response:result_batch', (response) => {
            this.handleAIResponse(response, 'result_batch');
        });
        
        this.eventBus.on('websocket:ai_response:chart_result', (response) => {
            this.handleAIResponse(response, 'chart_result');
        });
        
        this.eventBus.on('websocket:ai_response:ai_chunk', (response) => {
            this.handleAIStreamingResponse(response);
        });
        
        this.eventBus.on('websocket:participant_update', (update) => {
            // TODO: Update state manager
            this.eventBus.emit('state:participants', update.participants);
        });
        
        this.eventBus.on('websocket:typing', (data) => {
            // Pass through to UI without storing
            if (data.participant.participantId !== this.currentIdentity?.participantId) {
                this.chatUI?.updateTypingIndicator(data);
            }
        });
        
        // UI actions → WebSocket sends
        this.eventBus.on('ui:sendMessage', async (data) => {
            if (!this.currentConversationId) {
                console.error('No active conversation');
                return;
            }
            
            // Message sending flow
            this.sendMessage(data.content, data.sites, data.mode);
        });
        
        this.eventBus.on('ui:typing', (data) => {
            if (this.currentConversationId) {
                // Throttle typing indicators
                const now = Date.now();
                if (data.isTyping && (now - this.lastTypingTime) < this.typingThrottle) {
                    return; // Skip if within throttle period
                }
                
                if (data.isTyping) {
                    this.lastTypingTime = now;
                }
                
                this.webSocketService.sendTyping(data.isTyping);
            }
        });
        
        // Conversation management
        this.eventBus.on('ui:newConversation', async (data) => {
            await this.createConversation(data.site);
        });
        
        this.eventBus.on('ui:selectConversation', async (data) => {
            await this.loadConversation(data.conversationId);
        });
        
        this.eventBus.on('ui:joinConversation', async (data) => {
            await this.joinConversation(data.conversationId);
        });
        
        // Site and mode selection
        this.eventBus.on('ui:siteSelected', async (data) => {
            await this.createConversation(data.site, data.mode);
        });
        
        this.eventBus.on('ui:modeChanged', async (data) => {
            if (this.currentConversationId) {
                // TODO: Update conversation mode via API
                console.log('Mode changed to:', data.mode);
            }
        });
        
        // Identity changes → WebSocket reconnect
        this.eventBus.on('identity:changed', async (newIdentity) => {
            this.currentIdentity = newIdentity;
            if (this.currentConversationId) {
                // Reconnect with new identity
                await this.webSocketService.disconnect();
                await this.webSocketService.connect(
                    this.currentConversationId,
                    this.identityService.getParticipantInfo()
                );
            }
        });
        
        // Identity request from UI
        this.eventBus.on('ui:requestIdentity', () => {
            const identity = this.identityService.getCurrentIdentity();
            this.eventBus.emit('identity:current', identity);
        });
    }
    
    async checkForSharedLink() {
        const path = window.location.pathname;
        const joinMatch = path.match(/\/chat\/join\/([a-zA-Z0-9_-]+)/);
        
        if (joinMatch) {
            // Share UI will handle the join dialog
            return true;
        }
        
        return false;
    }
    
    async handleInitialConversation() {
        // Check URL for conversation ID
        const urlParams = new URLSearchParams(window.location.search);
        const conversationId = urlParams.get('conversation');
        
        if (conversationId) {
            // Load specific conversation
            await this.loadConversation(conversationId);
        } else {
            // TODO: Load conversation list from API
            // For now, just show empty state
            console.log('No initial conversation');
        }
    }
    
    async createConversation(site, mode = 'summarize') {
        try {
            // TODO: Use API service when available
            // const conversation = await this.apiService.createConversation({
            //     title: `Chat with ${site.display_name || site.name}`,
            //     sites: [site.id],
            //     mode: mode
            // });
            
            // For now, create a mock conversation
            const conversation = {
                id: `conv_${Date.now()}`,
                title: `Chat with ${site.display_name || site.name}`,
                sites: [site.id],
                mode: mode,
                participants: [this.identityService.getParticipantInfo()],
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };
            
            // TODO: Add to state manager
            // this.stateManager.addConversation(conversation);
            
            // Load the new conversation
            await this.loadConversation(conversation.id);
            
        } catch (error) {
            console.error('Failed to create conversation:', error);
            this.showError('Failed to create conversation');
        }
    }
    
    async loadConversation(conversationId) {
        try {
            // Disconnect from previous conversation
            if (this.currentConversationId) {
                await this.webSocketService.disconnect();
            }
            
            // TODO: Load conversation from API/state
            // const conversation = await this.apiService.getConversation(conversationId);
            // this.stateManager.setActiveConversation(conversation);
            
            // For now, create a mock conversation
            const conversation = {
                id: conversationId,
                title: 'Test Conversation',
                sites: [],
                mode: 'summarize',
                participants: [this.identityService.getParticipantInfo()],
                messages: []
            };
            
            // Update URL
            const url = new URL(window.location);
            url.searchParams.set('conversation', conversationId);
            window.history.pushState({}, '', url);
            
            // Connect WebSocket
            await this.webSocketService.connect(
                conversationId,
                this.identityService.getParticipantInfo()
            );
            
            this.currentConversationId = conversationId;
            
            // Update UI via state events
            this.eventBus.emit('state:currentConversation', conversation);
            
        } catch (error) {
            console.error('Failed to load conversation:', error);
            this.showError('Failed to load conversation');
        }
    }
    
    async joinConversation(conversationId) {
        try {
            // TODO: Join via API
            // await this.apiService.joinConversation(conversationId);
            
            // Load the conversation
            await this.loadConversation(conversationId);
            
        } catch (error) {
            console.error('Failed to join conversation:', error);
            this.showError('Failed to join conversation');
        }
    }
    
    // Message sending with optimistic updates
    sendMessage(content, sites = [], mode = 'summarize') {
        if (!content.trim()) return;
        
        // Create message with client ID
        const clientId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        const optimisticMessage = {
            id: clientId,
            conversation_id: this.currentConversationId,
            content: content,
            participant: this.identityService.getParticipantInfo(),
            timestamp: new Date().toISOString(),
            type: 'message',
            status: 'sending'
        };
        
        // Store pending message
        this.pendingMessages.set(clientId, optimisticMessage);
        
        // Optimistic UI update - message will be sanitized by ChatUI
        this.chatUI?.queueMessage(optimisticMessage);
        
        // Clear typing indicator
        this.lastTypingTime = 0;
        
        // Send via WebSocket
        this.webSocketService.sendMessage(content, sites, mode);
    }
    
    // Handle incoming user messages
    handleIncomingMessage(message) {
        // Update sequence ID for sync
        if (message.sequence_id) {
            this.lastSequenceId = message.sequence_id;
        }
        
        // Check if this is our optimistic message confirmed
        let isOwnMessage = false;
        for (const [clientId, pending] of this.pendingMessages) {
            if (pending.content === message.content && 
                pending.participant.participantId === message.participant?.participantId) {
                // Remove from pending
                this.pendingMessages.delete(clientId);
                isOwnMessage = true;
                break;
            }
        }
        
        // Add sender attribution
        const messageWithAttribution = {
            ...message,
            isOwnMessage,
            status: 'delivered'
        };
        
        // TODO: Store in state manager by sequence ID
        // this.stateManager.addMessage(messageWithAttribution);
        
        // Update UI (will be sanitized by ChatUI)
        if (!isOwnMessage) {
            this.chatUI?.queueMessage(messageWithAttribution);
        }
    }
    
    // Handle AI responses with proper routing
    handleAIResponse(response, specificType = null) {
        const messageType = specificType || response.message_type || 'text';
        
        // Update sequence ID
        if (response.sequence_id) {
            this.lastSequenceId = response.sequence_id;
        }
        
        // Create AI message with attribution
        const aiMessage = {
            id: response.id || `ai_${Date.now()}`,
            conversation_id: this.currentConversationId,
            content: response.content || '',
            data: response.data || response.results,
            participant: {
                participantId: 'ai_assistant',
                displayName: 'AI Assistant',
                type: 'ai'
            },
            timestamp: response.timestamp || new Date().toISOString(),
            type: 'ai_response',
            message_type: messageType,
            status: 'delivered'
        };
        
        // TODO: Store in state manager
        // this.stateManager.addMessage(aiMessage);
        
        // Update UI (will be sanitized by ChatUI)
        this.chatUI?.queueMessage(aiMessage);
    }
    
    // Handle streaming AI responses
    handleAIStreamingResponse(chunk) {
        // For streaming, we need to accumulate chunks
        const chunkId = chunk.stream_id || chunk.id;
        
        if (chunk.is_final) {
            // Final chunk - show complete message
            this.handleAIResponse(chunk, 'ai_response');
        } else {
            // Streaming update - emit to UI for real-time display
            const streamingMessage = {
                id: chunkId,
                content: chunk.content || '',
                type: 'ai_chunk',
                is_streaming: true
            };
            
            // ChatUI should handle streaming updates
            this.eventBus.emit('ui:streamingUpdate', streamingMessage);
        }
    }
    
    showError(message) {
        // TODO: Implement proper error UI
        console.error(message);
        
        // Create a simple error notification
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-notification';
        errorDiv.textContent = message;
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #e74c3c;
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 0.25rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 1002;
            animation: slideIn 0.3s ease;
        `;
        
        document.body.appendChild(errorDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }
}

// Export for testing
export function initializeChat() {
    const app = new MultiChatApp();
    return app.initialize();
}

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeChat);
} else {
    initializeChat();
}

// Make app available globally for debugging
window.MultiChatApp = MultiChatApp;