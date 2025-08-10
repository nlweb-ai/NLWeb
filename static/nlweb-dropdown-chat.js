/**
 * NLWeb Dropdown Chat Component
 * A self-contained search box with dropdown chat functionality
 * 
 * Usage:
 * import { NLWebDropdownChat } from './nlweb-dropdown-chat.js';
 * const chat = new NLWebDropdownChat({
 *   containerId: 'my-search-container',
 *   site: 'seriouseats',
 *   placeholder: 'Ask a question...'
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
        this.rememberedList = this.container.querySelector(`.${this.config.cssPrefix}-remembered-list`);
        
        // Import required modules
        try {
            const [
                { JsonRenderer },
                { TypeRendererFactory },
                { RecipeRenderer },
                { ModernChatInterface }
            ] = await Promise.all([
                import(`${this.config.endpoint}/static/json-renderer.js`),
                import(`${this.config.endpoint}/static/type-renderers.js`),
                import(`${this.config.endpoint}/static/recipe-renderer.js`),
                import(`${this.config.endpoint}/static/fp-chat-interface.js`)
            ]);
            
            // Initialize JSON renderer
            this.jsonRenderer = new JsonRenderer();
            TypeRendererFactory.registerAll(this.jsonRenderer);
            TypeRendererFactory.registerRenderer(RecipeRenderer, this.jsonRenderer);
            
            // Initialize chat interface after a short delay
            setTimeout(() => {
                this.initializeChatInterface(ModernChatInterface);
                // Load remembered items after chat interface is initialized
                this.updateRememberedItems();
            }, 100);
            
        } catch (error) {
        }
    }
    
    createDOM() {
        // Get container
        this.container = document.getElementById(this.config.containerId);
        if (!this.container) {
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
                    <div class="${this.config.cssPrefix}-remembered-section">
                        <div class="${this.config.cssPrefix}-remembered-header">
                            <h3>Remembered Items</h3>
                        </div>
                        <div class="${this.config.cssPrefix}-remembered-list">
                            <!-- Remembered items will be loaded here -->
                        </div>
                    </div>
                </div>
                <div class="${this.config.cssPrefix}-messages-container">
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
                <div id="messages-container"></div>
                <div id="chat-input"></div>
                <div id="send-button"></div>
            </div>
        `;
    }
    
    initializeChatInterface(ModernChatInterface) {
        // Create chat interface instance
        this.chatInterface = new ModernChatInterface({ skipAutoInit: true });
        
        // Set the site
        this.chatInterface.selectedSite = this.config.site;
        
        // Override methods to work with our structure
        this.setupChatInterfaceOverrides();
        
        // Initialize event handlers
        this.setupEventHandlers();
        
        // Create initial chat
        this.chatInterface.createNewChat(null, this.config.site);
    }
    
    setupChatInterfaceOverrides() {
        // Override createNewChat to ensure site is set
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
        
        // Override sendMessage to show dropdown
        const originalSendMessage = this.chatInterface.sendMessage.bind(this.chatInterface);
        this.chatInterface.sendMessage = (message) => {
            this.showDropdown();
            originalSendMessage(message);
            
            const chatInputContainer = this.container.querySelector(`.${this.config.cssPrefix}-chat-input-container`);
            if (chatInputContainer) {
                chatInputContainer.style.display = 'block';
            }
            
            this.updateConversationsList();
        };
        
        // Override addMessage
        const originalAddMessage = this.chatInterface.addMessage.bind(this.chatInterface);
        this.chatInterface.addMessage = (content, type) => {
            originalAddMessage(content, type);
            
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
        };
        
        // Override endStreaming
        const originalEndStreaming = this.chatInterface.endStreaming.bind(this.chatInterface);
        this.chatInterface.endStreaming = () => {
            originalEndStreaming();
            this.dropdownResults.classList.add('loaded');
            // Update remembered items after streaming ends
            this.updateRememberedItems();
        };
        
        // Override addRememberedItem if it exists
        if (this.chatInterface.addRememberedItem) {
            const originalAddRememberedItem = this.chatInterface.addRememberedItem.bind(this.chatInterface);
            this.chatInterface.addRememberedItem = (item) => {
                originalAddRememberedItem(item);
                this.updateRememberedItems();
            };
        }
    }
    
    setupEventHandlers() {
        // Search input
        this.searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.handleSearch();
            }
        });
        
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
    
    handleSearch() {
        const query = this.searchInput.value.trim();
        if (!query) return;
        
        this.searchInput.value = '';
        this.showDropdown();
        
        if (!this.chatInterface.currentConversationId) {
            this.chatInterface.createNewChat(null, this.config.site);
        }
        
        this.chatInterface.sendMessage(query);
    }
    
    toggleConversationsPanel() {
        if (!this.dropdownResults.classList.contains('show')) {
            this.showDropdown();
        }
        
        this.dropdownConversationsPanel.classList.toggle('show');
        
        if (this.dropdownConversationsPanel.classList.contains('show')) {
            this.updateConversationsList();
            this.updateRememberedItems();
        }
    }
    
    updateConversationsList() {
        this.dropdownConversationsList.innerHTML = '';
        
        const allConversations = this.chatInterface.conversationManager.getConversations();
        const siteConversations = allConversations.filter(conv => 
            conv.site === this.config.site && conv.messages && conv.messages.length > 0
        );
        
        siteConversations.sort((a, b) => {
            const timeA = a.timestamp || 0;
            const timeB = b.timestamp || 0;
            return timeB - timeA;
        });
        
        siteConversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = `${this.config.cssPrefix}-conversation-item`;
            if (conv.id === this.chatInterface.currentConversationId) {
                item.classList.add('active');
            }
            
            const title = document.createElement('div');
            title.className = `${this.config.cssPrefix}-conversation-title`;
            title.textContent = conv.title;
            item.appendChild(title);
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = `${this.config.cssPrefix}-conversation-delete`;
            deleteBtn.innerHTML = '×';
            deleteBtn.title = 'Delete conversation';
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteConversation(conv.id);
            });
            item.appendChild(deleteBtn);
            
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                this.chatInterface.conversationManager.loadConversation(conv.id, this.chatInterface);
                
                const firstUserMessage = conv.messages.find(m => m.type === 'user');
                if (firstUserMessage) {
                    this.searchInput.value = firstUserMessage.content;
                }
                
                this.dropdownConversationsList.querySelectorAll(`.${this.config.cssPrefix}-conversation-item`).forEach(i => {
                    i.classList.remove('active');
                });
                item.classList.add('active');
            });
            
            this.dropdownConversationsList.appendChild(item);
        });
        
        if (siteConversations.length === 0) {
            const emptyMessage = document.createElement('div');
            emptyMessage.className = `${this.config.cssPrefix}-empty-conversations`;
            emptyMessage.textContent = 'No past conversations';
            this.dropdownConversationsList.appendChild(emptyMessage);
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
        this.chatInterface.elements.messagesContainer = this.messagesContainer;
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
    
    updateRememberedItems() {
        if (!this.rememberedList || !this.chatInterface) return;
        
        this.rememberedList.innerHTML = '';
        
        // Get remembered items from chat interface
        const rememberedItems = this.chatInterface.rememberedItems || [];
        
        if (rememberedItems.length === 0) {
            const emptyMessage = document.createElement('div');
            emptyMessage.className = `${this.config.cssPrefix}-empty-remembered`;
            emptyMessage.textContent = 'No remembered items';
            this.rememberedList.appendChild(emptyMessage);
            return;
        }
        
        // Display each remembered item
        rememberedItems.forEach((item, index) => {
            const itemElement = document.createElement('div');
            itemElement.className = `${this.config.cssPrefix}-remembered-item`;
            
            const itemContent = document.createElement('div');
            itemContent.className = `${this.config.cssPrefix}-remembered-content`;
            itemContent.textContent = item;
            itemElement.appendChild(itemContent);
            
            const removeBtn = document.createElement('button');
            removeBtn.className = `${this.config.cssPrefix}-remembered-remove`;
            removeBtn.innerHTML = '×';
            removeBtn.title = 'Remove from memory';
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeRememberedItem(index);
            });
            itemElement.appendChild(removeBtn);
            
            this.rememberedList.appendChild(itemElement);
        });
    }
    
    removeRememberedItem(index) {
        if (this.chatInterface && this.chatInterface.removeRememberedItem) {
            this.chatInterface.removeRememberedItem(this.chatInterface.rememberedItems[index]);
        }
    }
    
    destroy() {
        // Clean up event listeners and DOM
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}
