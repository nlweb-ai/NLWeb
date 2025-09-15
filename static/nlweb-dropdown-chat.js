/**
 * NLWeb Dropdown Chat Component
 * A self-contained search box with dropdown chat functionality
 * 
 * Usage:
 * import { NLWebDropdownChat } from './nlweb-dropdown-chat.js';
 * const chat = new NLWebDropdownChat({
 *   containerId: 'my-search-container',
 *   site: 'seriouseats',
 *   placeholder: 'Ask a question...',
 *   inputId: 'custom-chat-input'  // Optional: custom input element ID
 * });
 */

export class NLWebDropdownChat {
    constructor(config = {}) {
        this.config = {
            containerId: config.containerId || 'nlweb-search-container',
            site: config.site || 'all',
            placeholder: config.placeholder || 'Ask a question...',
            endpoint: config.endpoint || window.location.origin,
            cssPrefix: config.cssPrefix || 'nlweb-dropdown',
            inputId: config.inputId || 'chat-input',  // Allow custom input ID
            ...config
        };
        
        this.init();
    }
    
    async init() {
        // Create the HTML structure
        this.createDOM();
        
        // Get references to elements
        this.searchInput = this.container.querySelector(`.${this.config.cssPrefix}-search-input`);
        this.dropdownResults = this.container.querySelector(`.${this.config.cssPrefix}-results`);
        this.messagesContainer = this.container.querySelector(`.${this.config.cssPrefix}-messages-container`);
        this.dropdownConversationsList = this.container.querySelector(`.${this.config.cssPrefix}-conversations-list`);
        this.dropdownConversationsPanel = this.container.querySelector(`.${this.config.cssPrefix}-conversations-panel`);
        this.historyIcon = this.container.querySelector(`.${this.config.cssPrefix}-history-icon`);
        
        // Import required modules
        try {
            const [
                { JsonRenderer },
                { TypeRendererFactory },
                { RecipeRenderer },
                { UnifiedChatInterface }
            ] = await Promise.all([
                import(`${this.config.endpoint}/static/json-renderer.js`),
                import(`${this.config.endpoint}/static/type-renderers.js`),
                import(`${this.config.endpoint}/static/recipe-renderer.js`),
                import(`${this.config.endpoint}/static/chat-interface-unified.js`)
            ]);
            
            // Initialize JSON renderer
            this.jsonRenderer = new JsonRenderer();
            TypeRendererFactory.registerAll(this.jsonRenderer);
            TypeRendererFactory.registerRenderer(RecipeRenderer, this.jsonRenderer);
            
            // Initialize chat interface after a short delay
            setTimeout(() => {
                this.initializeChatInterface(UnifiedChatInterface);
            }, 100);
            
        } catch (error) {
            console.error('[NLWebDropdown] Error importing modules:', error);
            console.error('[NLWebDropdown] Stack trace:', error.stack);
        }
    }
    
    createDOM() {
        // Get container
        this.container = document.getElementById(this.config.containerId);
        if (!this.container) {
            console.error('[NLWebDropdown] Container not found with ID:', this.config.containerId);
            return;
        }
        
        // Add container class
        this.container.classList.add(`${this.config.cssPrefix}-container`);
        
        // Create HTML structure
        this.container.innerHTML = `
            <div class="${this.config.cssPrefix}-search-wrapper">
                <svg class="${this.config.cssPrefix}-history-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
                <input type="text" 
                       class="${this.config.cssPrefix}-search-input" 
                       placeholder="${this.config.placeholder}">
            </div>
            
            <div class="${this.config.cssPrefix}-results">
                <div class="${this.config.cssPrefix}-conversations-panel">
                    <div class="${this.config.cssPrefix}-conversations-header">
                        <h3>Past Conversations</h3>
                    </div>
                    <div class="${this.config.cssPrefix}-conversations-list">
                        <!-- Conversations will be loaded here -->
                    </div>
                </div>
                <div class="${this.config.cssPrefix}-messages-container" id="messages-container">
                    <button class="${this.config.cssPrefix}-close" onclick="this.closest('.${this.config.cssPrefix}-results').classList.remove('show')">×</button>
                </div>
                
                <!-- Chat input for follow-up questions -->
                <div class="${this.config.cssPrefix}-chat-input-container" style="display: none;">
                    <div class="${this.config.cssPrefix}-chat-input-wrapper">
                        <div class="${this.config.cssPrefix}-chat-input-box">
                            <textarea 
                                class="${this.config.cssPrefix}-chat-input" 
                                placeholder="Ask a follow-up question..."
                                rows="1"
                            ></textarea>
                            <button class="${this.config.cssPrefix}-send-button">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="22" y1="2" x2="11" y2="13"></line>
                                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Hidden elements that fp-chat-interface.js expects -->
            <div style="display: none;">
                <div id="sidebar"></div>
                <div id="sidebar-toggle"></div>
                <div id="mobile-menu-toggle"></div>
                <div id="new-chat-btn"></div>
                <div id="conversations-list"></div>
                <div class="chat-title"></div>
                <div id="chat-site-info"></div>
                <div id="chat-messages"></div>
                <div id="chat-input"></div>
                <div id="send-button"></div>
            </div>
        `;
    }
    
    initializeChatInterface(UnifiedChatInterface) {
        try {
            // Create chat interface instance with skipAutoInit
            this.chatInterface = new UnifiedChatInterface({
                skipAutoInit: true,
                connectionType: 'websocket',  // Use WebSocket for dropdown
                additionalParams: {
                    site: this.config.site
                }
            });
            
            // Store the initialized flag
            this.chatInitialized = false;
            
            // Override methods to work with our structure
            this.setupChatInterfaceOverrides();
            
            // Initialize event handlers
            this.setupEventHandlers();
            
            // Set up the messages container
            const messagesContainer = document.getElementById('chat-messages');
            if (!messagesContainer) {
                // Create a hidden messages container that UnifiedChatInterface expects
                const hiddenMessages = document.createElement('div');
                hiddenMessages.id = 'chat-messages';
                hiddenMessages.style.display = 'none';
                document.body.appendChild(hiddenMessages);
            }
        } catch (error) {
            console.error('[NLWebDropdown] Error in initializeChatInterface:', error);
        }
    }
    
    setupChatInterfaceOverrides() {
        // Override createNewChat to ensure site is set
        if (this.chatInterface.createNewChat) {
            const originalCreateNewChat = this.chatInterface.createNewChat.bind(this.chatInterface);
            this.chatInterface.createNewChat = (searchInputId, site) => {
                originalCreateNewChat(searchInputId, site || this.config.site);
                
                const conversation = this.chatInterface.conversationManager.findConversation(
                    this.chatInterface.currentConversationId
                );
                if (conversation) {
                    if (!conversation.site) {
                        conversation.site = this.config.site;
                    }
                    if (!conversation.timestamp) {
                        conversation.timestamp = Date.now();
                    }
                    this.chatInterface.conversationManager.saveConversations();
                }
            };
        }
        
        // Override sendMessage to show dropdown when called
        if (this.chatInterface.sendMessage) {
            const originalSendMessage = this.chatInterface.sendMessage.bind(this.chatInterface);
            this.chatInterface.sendMessage = () => {
                this.showDropdown();

                // Call the original sendMessage which will construct the proper message
                originalSendMessage();

                // Force save after sending
                if (this.chatInterface.conversationManager) {
                    this.chatInterface.conversationManager.saveConversations();
                }

                const chatInputContainer = this.container.querySelector(`.${this.config.cssPrefix}-chat-input-container`);
                if (chatInputContainer) {
                    chatInputContainer.style.display = 'block';
                }

                this.updateConversationsList();
            };
        }
        
        // Override addMessageBubble (UnifiedChatInterface uses this instead of addMessage)
        if (this.chatInterface.addMessageBubble) {
            const originalAddMessageBubble = this.chatInterface.addMessageBubble.bind(this.chatInterface);
            this.chatInterface.addMessageBubble = (content, type, sender_info) => {
                const result = originalAddMessageBubble(content, type, sender_info);
                
                // Access conversations through conversationManager
                const conversation = this.chatInterface.conversationManager.findConversation(
                    this.chatInterface.currentConversationId
                );
                if (conversation) {
                    if (conversation.site !== this.config.site) {
                        conversation.site = this.config.site;
                    }
                    if (!conversation.timestamp) {
                        conversation.timestamp = Date.now();
                    }
                    this.chatInterface.conversationManager.saveConversations();
                }
                
                return result;
            };
        }
        
        // Override endStreaming if it exists
        if (this.chatInterface.endStreaming) {
            const originalEndStreaming = this.chatInterface.endStreaming.bind(this.chatInterface);
            this.chatInterface.endStreaming = () => {
                originalEndStreaming();
                this.dropdownResults.classList.add('loaded');
            };
        }
        
    }
    
    setupEventHandlers() {
        // Search input
        if (this.searchInput) {
            console.log('[NLWebDropdown] Adding keypress listener to searchInput');
            this.searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    console.log('[NLWebDropdown] Enter pressed, calling handleSearch');
                    e.preventDefault();
                    this.handleSearch();
                }
            });
        } else {
            console.error('[NLWebDropdown] searchInput is null - cannot add event handler');
        }
        
        // History icon
        if (this.historyIcon) {
            this.historyIcon.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.toggleConversationsPanel();
            });
        }
        
        // Chat input and send button
        const chatInput = this.container.querySelector(`.${this.config.cssPrefix}-chat-input`);
        const sendButton = this.container.querySelector(`.${this.config.cssPrefix}-send-button`);
        
        if (chatInput && sendButton) {
            // Ensure elements object exists
            if (!this.chatInterface.elements) {
                this.chatInterface.elements = {};
            }
            // Override the chat interface elements
            this.chatInterface.elements.chatInput = chatInput;
            this.chatInterface.elements.sendButton = sendButton;
            
            sendButton.addEventListener('click', () => {
                const message = chatInput.value.trim();
                if (message) {
                    this.chatInterface.sendMessage(message);
                    chatInput.value = '';
                    chatInput.style.height = 'auto';
                }
            });
            
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendButton.click();
                }
            });
            
            // Auto-resize
            chatInput.addEventListener('input', () => {
                chatInput.style.height = 'auto';
                chatInput.style.height = Math.min(chatInput.scrollHeight, 100) + 'px';
            });
        }
        
        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this.closeDropdown();
            }
        });
        
        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeDropdown();
            }
        });
    }
    
    async handleSearch() {
        if (!this.searchInput) {
            return;
        }

        const query = this.searchInput.value.trim();
        if (!query) {
            return;
        }

        this.searchInput.value = '';

        // Clear existing results before starting new search
        if (this.messagesContainer) {
            this.messagesContainer.innerHTML = '';
        }

        this.showDropdown();

        if (!this.chatInterface) {
            console.error('[NLWebDropdown] chatInterface is null');
            return;
        }

        // Initialize the chat interface on first use
        if (!this.chatInitialized) {
            console.log('[NLWebDropdown] Initializing chat interface on first query');
            console.log('[NLWebDropdown] Pre-init state:', {
                state: this.chatInterface.state,
                ws: !!this.chatInterface.ws,
                wsConnection: !!this.chatInterface.ws?.connection
            });

            // Ensure the site is set before initialization
            this.chatInterface.state.selectedSite = this.config.site;

            // Call the init method that UnifiedChatInterface expects
            await this.chatInterface.init();

            this.chatInitialized = true;
            console.log('[NLWebDropdown] Chat interface initialized');
            console.log('[NLWebDropdown] Post-init state:', {
                state: this.chatInterface.state,
                ws: !!this.chatInterface.ws,
                wsConnection: !!this.chatInterface.ws?.connection,
                conversationManager: !!this.chatInterface.conversationManager
            });
        }

        // Always create a new conversation for top search bar queries
        const conversationId = `${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
        this.chatInterface.state.conversationId = conversationId;
        this.chatInterface.state.selectedSite = this.config.site;

        // End any existing streaming
        if (this.chatInterface.state.currentStreaming) {
            this.chatInterface.endStreaming();
        }
        
        // Set the input value that UnifiedChatInterface.sendMessage() will read
        let input = document.getElementById('centered-chat-input') || document.getElementById('chat-input');
        if (!input) {
            input = document.createElement('textarea');
            input.id = 'chat-input';
            input.style.display = 'none';
            document.body.appendChild(input);
        }
        input.value = query;
        
        console.log('[NLWebDropdown] Sending query:', query);
        console.log('[NLWebDropdown] Input value set to:', input.value);
        
        // Call sendMessage without parameters - it will read from the DOM and construct the proper message
        this.chatInterface.sendMessage();
    }
    
    toggleConversationsPanel() {
        if (!this.dropdownResults.classList.contains('show')) {
            this.showDropdown();
        }
        
        this.dropdownConversationsPanel.classList.toggle('show');
        
        if (this.dropdownConversationsPanel.classList.contains('show')) {
            this.updateConversationsList();
        }
    }
    
    updateConversationsList() {
        // First, temporarily filter conversations to only show this site's conversations
        const originalConversations = this.chatInterface.conversationManager.conversations;
        const siteFilteredConversations = originalConversations.filter(conv =>
            conv.site === this.config.site && conv.messages && conv.messages.length > 0
        );

        // Temporarily replace the conversations array with filtered version
        this.chatInterface.conversationManager.conversations = siteFilteredConversations;

        // Use the shared conversation list rendering from conversation-manager.js
        // This ensures consistent UI and behavior across both interfaces
        this.chatInterface.conversationManager.updateConversationsList(
            this.chatInterface,
            this.dropdownConversationsList
        );

        // Restore the original conversations array
        this.chatInterface.conversationManager.conversations = originalConversations;

        // Override click handlers for dropdown-specific behavior
        const convItems = this.dropdownConversationsList.querySelectorAll('.conversation-item');
        convItems.forEach(item => {
            // Store the conversation ID from data attribute
            const convId = item.dataset.conversationId;
            if (!convId) return;

            // Override the main click handler for dropdown behavior
            const clickHandler = (e) => {
                // Don't interfere with delete button
                if (e.target.classList.contains('conversation-delete')) {
                    return;
                }

                e.stopPropagation();
                this.chatInterface.conversationManager.loadConversation(convId, this.chatInterface);

                // Update search input with first user message
                const conv = this.chatInterface.conversationManager.findConversation(convId);
                if (conv && conv.messages) {
                    const firstUserMessage = conv.messages.find(m =>
                        m.type === 'user' || m.message_type === 'user'
                    );
                    if (firstUserMessage && this.searchInput) {
                        const content = firstUserMessage.content;
                        this.searchInput.value = typeof content === 'string'
                            ? content
                            : content?.query || content?.content || '';
                    }
                }

                // Update active state
                this.dropdownConversationsList.querySelectorAll('.conversation-item').forEach(i => {
                    i.classList.remove('active');
                });
                item.classList.add('active');
            };

            // Remove existing click handlers and add our custom one
            const newItem = item.cloneNode(true);
            item.parentNode.replaceChild(newItem, item);
            newItem.addEventListener('click', clickHandler);

            // Re-attach delete button handler since we cloned
            const deleteBtn = newItem.querySelector('.conversation-delete');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.deleteConversation(convId);
                });
            }
        });

        // Add active class to current conversation
        if (this.chatInterface.currentConversationId) {
            const activeItem = this.dropdownConversationsList.querySelector(
                `[data-conversation-id="${this.chatInterface.currentConversationId}"]`
            );
            if (activeItem) {
                activeItem.classList.add('active');
            }
        }
    }
    
    deleteConversation(conversationId) {
        // Use conversationManager's deleteConversation method
        this.chatInterface.conversationManager.deleteConversation(conversationId, this.chatInterface);
        
        if (this.chatInterface.currentConversationId === conversationId) {
            this.chatInterface.createNewChat(null, this.config.site);
        }
        
        this.updateConversationsList();
    }
    
    showDropdown() {
        this.dropdownResults.classList.add('show');
        this.dropdownResults.classList.remove('loaded');
        
        // Update messages container reference
        if (this.chatInterface) {
            if (!this.chatInterface.elements) {
                this.chatInterface.elements = {};
            }
            this.chatInterface.elements.messagesContainer = this.messagesContainer;
        }
    }
    
    closeDropdown() {
        this.dropdownResults.classList.remove('show');
        this.dropdownConversationsPanel.classList.remove('show');
        
        const chatInputContainer = this.container.querySelector(`.${this.config.cssPrefix}-chat-input-container`);
        if (chatInputContainer) {
            chatInputContainer.style.display = 'none';
        }
        
        if (this.messagesContainer) {
            const closeButton = this.messagesContainer.querySelector(`.${this.config.cssPrefix}-close`);
            this.messagesContainer.innerHTML = '';
            if (closeButton) {
                this.messagesContainer.appendChild(closeButton);
            }
        }
        
        if (this.chatInterface) {
            this.chatInterface.createNewChat(null, this.config.site);
        }
    }
    
    // Public API methods
    search(query) {
        this.searchInput.value = query;
        this.handleSearch();
    }
    
    setQuery(query) {
        this.searchInput.value = query;
    }
    
    setSite(site) {
        this.config.site = site;
        if (this.chatInterface) {
            this.chatInterface.selectedSite = site;
        }
    }
    
    
    destroy() {
        // Clean up event listeners and DOM
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}
