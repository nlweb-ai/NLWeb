/**
 * Multi-Participant Chat Application
 * Main entry point and orchestrator
 */

// Import all modules (will be created in subsequent phases)
import { EventBus } from './chat/event-bus.js';
import { ApiService } from './chat/api-service.js';
import { IdentityService } from './chat/identity-service.js';
import { StateManager } from './chat/state-manager.js';
import { WebSocketService } from './chat/websocket-service.js';
import { SidebarUI } from './chat/sidebar-ui.js';
import { ChatUI } from './chat/chat-ui.js';
import { ShareUI } from './chat/share-ui.js';

class MultiChatApp {
    constructor() {
        this.eventBus = EventBus;
        this.apiService = ApiService;
        this.identityService = IdentityService;
        this.stateManager = StateManager;
        this.wsService = WebSocketService;
        
        // UI Components
        this.sidebarUI = null;
        this.chatUI = null;
        this.shareUI = null;
        
        // Current state
        this.currentConversationId = null;
        this.isInitialized = false;
    }
    
    async initialize() {
        try {
            console.log('Initializing Multi-Chat Application...');
            
            // Initialize UI components
            this.sidebarUI = new SidebarUI();
            this.chatUI = new ChatUI();
            this.shareUI = new ShareUI();
            
            // Set up event listeners
            this.setupEventListeners();
            
            // Check for conversation ID in URL
            const urlParams = new URLSearchParams(window.location.search);
            const conversationId = urlParams.get('conversation');
            
            // Initialize identity (will prompt if needed)
            const identity = await this.identityService.ensureIdentity();
            if (!identity) {
                console.error('Failed to establish identity');
                return;
            }
            
            // Load initial data
            await this.loadInitialData();
            
            // If conversation ID in URL, join it
            if (conversationId) {
                await this.joinConversation(conversationId);
            }
            
            this.isInitialized = true;
            console.log('Multi-Chat Application initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.showError('Failed to initialize chat application');
        }
    }
    
    setupEventListeners() {
        // Navigation events
        this.eventBus.on('navigate:conversation', ({ conversationId }) => {
            this.loadConversation(conversationId);
        });
        
        this.eventBus.on('create:conversation', ({ title, site }) => {
            this.createConversation(title, site);
        });
        
        // Message events
        this.eventBus.on('send:message', ({ content }) => {
            this.sendMessage(content);
        });
        
        this.eventBus.on('user:typing', () => {
            this.sendTypingIndicator();
        });
        
        // WebSocket events
        this.eventBus.on('ws:message', ({ message }) => {
            this.handleIncomingMessage(message);
        });
        
        this.eventBus.on('ws:connected', () => {
            this.handleWebSocketConnected();
        });
        
        this.eventBus.on('ws:disconnected', () => {
            this.handleWebSocketDisconnected();
        });
        
        // Share events
        this.eventBus.on('share:conversation', () => {
            this.shareCurrentConversation();
        });
    }
    
    async loadInitialData() {
        try {
            // Load sites
            const sites = await this.apiService.getSites();
            this.stateManager.setSites(sites);
            
            // Load user's conversations
            const conversations = await this.apiService.getConversations();
            conversations.forEach(conv => {
                this.stateManager.addConversation(conv);
            });
            
            // Update UI
            this.sidebarUI.render();
            
        } catch (error) {
            console.error('Failed to load initial data:', error);
        }
    }
    
    async createConversation(title, site) {
        try {
            const identity = this.identityService.getIdentity();
            const conversation = await this.apiService.createConversation({
                title: title || `Chat - ${new Date().toLocaleDateString()}`,
                site: site || 'all',
                participants: [identity]
            });
            
            this.stateManager.addConversation(conversation);
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
                this.wsService.disconnect();
            }
            
            // Load conversation details
            const conversation = await this.apiService.getConversation(conversationId);
            this.stateManager.setActiveConversation(conversation);
            
            // Update URL
            const url = new URL(window.location);
            url.searchParams.set('conversation', conversationId);
            window.history.pushState({}, '', url);
            
            // Connect WebSocket
            const identity = this.identityService.getParticipantInfo();
            await this.wsService.connect(conversationId, identity);
            
            this.currentConversationId = conversationId;
            
            // Update UI
            this.chatUI.loadConversation(conversation);
            this.sidebarUI.setActiveConversation(conversationId);
            
        } catch (error) {
            console.error('Failed to load conversation:', error);
            this.showError('Failed to load conversation');
        }
    }
    
    async joinConversation(conversationId) {
        try {
            const identity = this.identityService.getIdentity();
            await this.apiService.joinConversation(conversationId);
            await this.loadConversation(conversationId);
            
        } catch (error) {
            console.error('Failed to join conversation:', error);
            this.showError('Failed to join conversation');
        }
    }
    
    async sendMessage(content) {
        if (!content.trim() || !this.currentConversationId) return;
        
        // Create message with client-side ID
        const message = {
            id: `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            conversationId: this.currentConversationId,
            content: content,
            senderId: this.identityService.getIdentity().id,
            senderName: this.identityService.getIdentity().displayName,
            timestamp: new Date().toISOString(),
            type: 'message',
            status: 'sending'
        };
        
        // Optimistic update
        this.stateManager.addMessage(message);
        this.chatUI.renderMessage(message);
        
        // Send via WebSocket
        this.wsService.sendMessage({
            type: 'message',
            content: content
        });
    }
    
    sendTypingIndicator() {
        if (!this.currentConversationId) return;
        this.wsService.sendTyping();
    }
    
    handleIncomingMessage(wsMessage) {
        switch (wsMessage.type) {
            case 'message':
                this.handleChatMessage(wsMessage.data);
                break;
            case 'ai_response':
                this.handleAIResponse(wsMessage.data);
                break;
            case 'participant_update':
                this.handleParticipantUpdate(wsMessage.data);
                break;
            case 'typing':
                this.handleTypingIndicator(wsMessage.data);
                break;
            case 'error':
                this.handleError(wsMessage.data);
                break;
        }
    }
    
    handleChatMessage(message) {
        // Update or add message
        const existing = this.stateManager.getMessage(message.id);
        if (existing && existing.status === 'sending') {
            // Update our optimistic message with server data
            message.status = 'delivered';
        }
        
        this.stateManager.addMessage(message);
        this.chatUI.renderMessage(message);
    }
    
    handleAIResponse(response) {
        // AI responses might come in chunks or complete
        const message = {
            id: response.id,
            conversationId: this.currentConversationId,
            content: response.content,
            senderId: 'ai_assistant',
            senderName: 'AI Assistant',
            timestamp: response.timestamp,
            type: response.responseType || 'ai_response',
            metadata: response.metadata
        };
        
        this.stateManager.addMessage(message);
        this.chatUI.renderMessage(message);
    }
    
    handleParticipantUpdate(data) {
        if (data.action === 'joined') {
            this.stateManager.addParticipant(data.participant);
        } else if (data.action === 'left') {
            this.stateManager.removeParticipant(data.participantId);
        }
        
        this.chatUI.updateParticipants();
    }
    
    handleTypingIndicator(data) {
        if (data.isTyping) {
            this.stateManager.addTypingUser(data.participantId, data.participantName);
        } else {
            this.stateManager.removeTypingUser(data.participantId);
        }
        
        this.chatUI.updateTypingIndicators();
    }
    
    handleError(error) {
        console.error('WebSocket error:', error);
        this.showError(error.message || 'Connection error');
    }
    
    handleWebSocketConnected() {
        this.chatUI.setConnectionStatus('connected');
    }
    
    handleWebSocketDisconnected() {
        this.chatUI.setConnectionStatus('disconnected');
    }
    
    async shareCurrentConversation() {
        if (!this.currentConversationId) return;
        
        const shareUrl = `${window.location.origin}${window.location.pathname}?conversation=${this.currentConversationId}`;
        await this.shareUI.show(shareUrl, this.stateManager.getActiveConversation());
    }
    
    showError(message) {
        // TODO: Implement proper error UI
        console.error(message);
        alert(message);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.multiChatApp = new MultiChatApp();
    window.multiChatApp.initialize();
});