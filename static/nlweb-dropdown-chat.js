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
            
            // Set the site for the chat interface
            this.chatInterface.state.selectedSite = this.config.site;
            
            // Initialize event handlers
            this.setupEventHandlers();

            // Set up the overrides for chat interface methods
            this.setupChatInterfaceOverrides();

            // Point UnifiedChatInterface to our visible messages container
            const existingChatMessages = document.getElementById('chat-messages');
            if (!existingChatMessages) {
                // Create a wrapper div with the ID that UnifiedChatInterface expects
                // But make it point to our visible container
                const wrapper = document.createElement('div');
                wrapper.id = 'chat-messages';
                this.messagesContainer.appendChild(wrapper);
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
                
                // Let UnifiedChatInterface handle all conversation management
            };
        }
        
        // Override sendMessage to show dropdown when called
        if (this.chatInterface.sendMessage) {
            const originalSendMessage = this.chatInterface.sendMessage.bind(this.chatInterface);
            this.chatInterface.sendMessage = (message) => {
                this.showDropdown();

                // Call the original sendMessage - pass the message parameter through
                originalSendMessage(message);

                // UnifiedChatInterface handles saving

                const chatInputContainer = this.container.querySelector(`.${this.config.cssPrefix}-chat-input-container`);
                if (chatInputContainer) {
                    chatInputContainer.style.display = 'block';
                }

                // Don't update conversation list after sending - not needed
            };
        }
        

        // Override handleStreamData to add progressive scrolling
        if (this.chatInterface.handleStreamData) {
            const originalHandleStreamData = this.chatInterface.handleStreamData.bind(this.chatInterface);
            this.chatInterface.handleStreamData = (data, shouldStore) => {
                const result = originalHandleStreamData(data, shouldStore);

                // After each message is processed, check if we need to scroll
                if (this.messagesContainer) {
                    // Use setTimeout to let DOM update
                    setTimeout(() => {
                        const userMessages = this.messagesContainer.querySelectorAll('.user-message');
                        if (userMessages.length > 0) {
                            const lastUserMessage = userMessages[userMessages.length - 1];
                            const rect = lastUserMessage.getBoundingClientRect();
                            const containerRect = this.messagesContainer.getBoundingClientRect();

                            // If user message is below the viewport, scroll to make it visible
                            if (rect.bottom > containerRect.bottom) {
                                // Scroll just enough to show the user message
                                lastUserMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                            }
                            // If user message is visible but below the top 30%, scroll up progressively
                            else if (rect.top > containerRect.top + (containerRect.height * 0.3)) {
                                // Scroll a bit to move user message up
                                this.messagesContainer.scrollBy({
                                    top: 50,
                                    behavior: 'smooth'
                                });
                            }
                        }
                    }, 100);
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
            this.searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.handleSearch();
                }
            });
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

            sendButton.addEventListener('click', () => {
                const message = chatInput.value.trim();
                if (message) {
                    // UnifiedChatInterface will handle conversation creation
                    // Just set up the input element for it to read
                    // Create or update that element with our message
                    let hiddenInput = document.getElementById('chat-input');
                    if (!hiddenInput) {
                        hiddenInput = document.createElement('textarea');
                        hiddenInput.id = 'chat-input';
                        hiddenInput.style.display = 'none';
                        document.body.appendChild(hiddenInput);
                    }
                    hiddenInput.value = message;
                    this.chatInterface.sendMessage();
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

        // Don't clear messages if we have an existing conversation
        // Only clear if starting a new conversation
        if (!this.chatInterface?.state?.conversationId) {
            if (this.messagesContainer) {
                this.messagesContainer.innerHTML = '';
            }
        }

        this.showDropdown();

        if (!this.chatInterface) {
            return;
        }

        // Chat interface is already initialized in initializeChatInterface()
        // Don't call init() again as it resets the conversations array!

        // Set the site for the search
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

        // Call sendMessage without parameters - it will read from the DOM and construct the proper message
        this.chatInterface.sendMessage();

        // Show the chat input container for follow-up questions
        const chatInputContainer = this.container.querySelector(`.${this.config.cssPrefix}-chat-input-container`);
        if (chatInputContainer) {
            chatInputContainer.style.display = 'block';
        }

        // After sending message, scroll to show the user message
        setTimeout(() => {
            const messages = this.messagesContainer.querySelectorAll('.user-message');
            const lastUserMessage = messages[messages.length - 1];
            if (lastUserMessage) {
                lastUserMessage.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }
        }, 100);
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
        // Just update the UI - don't manipulate conversation data
        // Let the conversation manager handle its own data
        this.chatInterface.conversationManager.updateConversationsList(
            this.chatInterface,
            this.dropdownConversationsList
        );

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

        // Don't create a new chat when closing - preserve the conversation
        // The user might want to continue the conversation later
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
