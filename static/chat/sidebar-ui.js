import eventBus from './event-bus.js';
import stateManager from './state-manager.js';

export class SidebarUI {
    constructor() {
        this.container = null;
        this.sortMode = 'recency'; // 'recency' or 'alphabetical'
        this.sites = [];
        this.conversations = [];
        this.currentConversationId = null;
        this.messagesPerSite = 5; // Default, will be calculated dynamically
        this.resizeObserver = null;
        
        // Bind methods to preserve 'this' context
        this.handleSiteClick = this.handleSiteClick.bind(this);
        this.handleSortToggle = this.handleSortToggle.bind(this);
        this.handleConversationClick = this.handleConversationClick.bind(this);
        this.handleResize = this.handleResize.bind(this);
    }

    initialize(container) {
        this.container = container;
        this.setupEventListeners();
        this.setupResizeObserver();
        this.calculateMessagesPerSite();
        this.render();
    }

    setupEventListeners() {
        // Listen for state changes
        eventBus.on('state:sites', (sites) => {
            this.sites = sites;
            this.render();
        });

        eventBus.on('state:conversations', (conversations) => {
            this.conversations = conversations;
            this.render();
        });

        eventBus.on('state:currentConversation', (conversationId) => {
            this.currentConversationId = conversationId;
            this.updateCurrentHighlight();
        });

        eventBus.on('state:newMessage', () => {
            // Re-render to update last message previews and timestamps
            this.render();
        });

        // Handle window resize for dynamic message count
        window.addEventListener('resize', this.handleResize);
    }

    setupResizeObserver() {
        if ('ResizeObserver' in window) {
            this.resizeObserver = new ResizeObserver(() => {
                this.calculateMessagesPerSite();
                this.render();
            });
            this.resizeObserver.observe(this.container);
        }
    }

    calculateMessagesPerSite() {
        if (!this.container) return;

        const containerHeight = this.container.clientHeight;
        const headerHeight = 80; // Approximate height for sort controls
        const siteHeaderHeight = 40; // Height for each site header
        const conversationHeight = 60; // Height for each conversation item
        
        const availableHeight = containerHeight - headerHeight;
        const numSites = this.sites.length || 1;
        const heightPerSite = (availableHeight / numSites) - siteHeaderHeight;
        
        this.messagesPerSite = Math.max(2, Math.floor(heightPerSite / conversationHeight));
    }

    handleResize() {
        // Debounce resize events
        clearTimeout(this.resizeTimeout);
        this.resizeTimeout = setTimeout(() => {
            this.calculateMessagesPerSite();
            this.render();
        }, 150);
    }

    render() {
        if (!this.container) return;

        // Get conversations from stateManager
        this.conversations = stateManager.getAllConversations();
        this.sortMode = stateManager.getPreference('sidebarSortMode') || 'recency';

        this.container.innerHTML = `
            <div class="sidebar-header">
                <div class="sidebar-title">
                    <h2>Conversations</h2>
                    <button id="sort-toggle" class="btn btn-icon" title="Sort conversations">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 6h18M7 12h10m-4 6h4"/>
                        </svg>
                        <span class="sort-mode">${this.sortMode === 'recency' ? 'Recent' : 'A-Z'}</span>
                    </button>
                </div>
            </div>
            <div class="sidebar-content">
                ${this.renderSites()}
            </div>
        `;

        // Attach event listeners
        this.attachEventListeners();
    }

    renderSites() {
        if (!this.sites.length) {
            return '<div class="no-sites">No sites available</div>';
        }

        const sortedSites = this.getSortedSites();
        
        return sortedSites.map(site => this.renderSiteGroup(site)).join('');
    }

    getSortedSites() {
        // Get sites sorted by stateManager preference
        const sortedSiteData = stateManager.getSitesSorted(this.sortMode);
        
        const sitesWithConversations = this.sites.map(site => {
            // Use stateManager to get conversations for site
            const siteConversations = stateManager.getConversationsForSite(site.id);
            
            return {
                ...site,
                conversations: this.getSortedConversations(siteConversations)
            };
        });

        if (this.sortMode === 'alphabetical') {
            return sitesWithConversations.sort((a, b) => 
                (a.display_name || a.name || '').localeCompare(b.display_name || b.name || '')
            );
        } else {
            // Sort by most recent activity
            return sitesWithConversations.sort((a, b) => {
                const aLatest = a.conversations[0]?.updated_at || a.conversations[0]?.created_at || 0;
                const bLatest = b.conversations[0]?.updated_at || b.conversations[0]?.created_at || 0;
                return new Date(bLatest) - new Date(aLatest);
            });
        }
    }

    getSortedConversations(conversations) {
        return conversations.sort((a, b) => {
            const aTime = a.updated_at || a.created_at || 0;
            const bTime = b.updated_at || b.created_at || 0;
            return new Date(bTime) - new Date(aTime);
        });
    }

    renderSiteGroup(site) {
        const conversations = site.conversations.slice(0, this.messagesPerSite);
        const displayName = site.display_name || site.name || site.id;
        const hasMoreConversations = site.conversations.length > this.messagesPerSite;

        return `
            <div class="site-group" data-site-id="${site.id}">
                <div class="site-header" data-site-id="${site.id}">
                    <div class="site-info">
                        <div class="site-name">${this.escapeHtml(displayName)}</div>
                        <div class="site-description">${this.escapeHtml(site.description || '')}</div>
                    </div>
                    <button class="btn btn-sm btn-primary new-conversation" data-site-id="${site.id}">
                        +
                    </button>
                </div>
                <div class="conversations-list">
                    ${conversations.map(conv => this.renderConversation(conv)).join('')}
                    ${hasMoreConversations ? `<div class="more-conversations">+${site.conversations.length - this.messagesPerSite} more...</div>` : ''}
                </div>
            </div>
        `;
    }

    renderConversation(conversation) {
        const isActive = conversation.id === this.currentConversationId;
        const lastMessage = this.getLastMessagePreview(conversation);
        const timestamp = this.formatTimestamp(conversation.updated_at || conversation.created_at);
        
        return `
            <div class="conversation-item ${isActive ? 'active' : ''}" 
                 data-conversation-id="${conversation.id}">
                <div class="conversation-content">
                    <div class="conversation-title">
                        ${this.escapeHtml(conversation.title || 'New Conversation')}
                    </div>
                    <div class="conversation-preview">
                        ${this.escapeHtml(lastMessage)}
                    </div>
                </div>
                <div class="conversation-meta">
                    <div class="conversation-timestamp">${timestamp}</div>
                    ${conversation.message_count ? `<div class="message-count">${conversation.message_count}</div>` : ''}
                </div>
            </div>
        `;
    }

    getLastMessagePreview(conversation) {
        if (conversation.last_message) {
            const content = conversation.last_message.content || '';
            return content.length > 60 ? content.substring(0, 60) + '...' : content;
        }
        return 'No messages yet';
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return '';
        
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'now';
        if (diffMins < 60) return `${diffMins}m`;
        if (diffHours < 24) return `${diffHours}h`;
        if (diffDays < 7) return `${diffDays}d`;
        
        return date.toLocaleDateString();
    }

    attachEventListeners() {
        // Sort toggle
        const sortToggle = this.container.querySelector('#sort-toggle');
        if (sortToggle) {
            sortToggle.addEventListener('click', this.handleSortToggle);
        }

        // Site clicks (new conversation)
        const newConversationButtons = this.container.querySelectorAll('.new-conversation');
        newConversationButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const siteId = button.dataset.siteId;
                this.handleSiteClick(siteId);
            });
        });

        // Conversation clicks
        const conversationItems = this.container.querySelectorAll('.conversation-item');
        conversationItems.forEach(item => {
            item.addEventListener('click', (e) => {
                const conversationId = item.dataset.conversationId;
                this.handleConversationClick(conversationId);
            });
        });
    }

    handleSiteClick(siteId) {
        const site = this.sites.find(s => s.id === siteId);
        if (site) {
            eventBus.emit('ui:newConversation', { site });
        }
    }

    handleConversationClick(conversationId) {
        eventBus.emit('ui:selectConversation', { conversationId });
    }

    handleSortToggle() {
        // Toggle sort mode and update state manager preference
        eventBus.emit('ui:sortToggle');
        this.render();
    }

    updateCurrentHighlight() {
        if (!this.container) return;

        // Remove existing active class
        const activeItems = this.container.querySelectorAll('.conversation-item.active');
        activeItems.forEach(item => item.classList.remove('active'));

        // Add active class to current conversation
        if (this.currentConversationId) {
            const currentItem = this.container.querySelector(
                `.conversation-item[data-conversation-id="${this.currentConversationId}"]`
            );
            if (currentItem) {
                currentItem.classList.add('active');
            }
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        
        window.removeEventListener('resize', this.handleResize);
        
        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
    }
}
