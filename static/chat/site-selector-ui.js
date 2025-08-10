import eventBus from './event-bus.js';
import configService from './config-service.js';

export class SiteSelectorUI {
    constructor() {
        this.modal = null;
        this.modeSelector = null;
        this.sites = [];
        this.filteredSites = [];
        this.currentSiteId = null;
        this.currentMode = this.getStoredMode() || 'summarize';
        
        // Bind methods
        this.showSiteSelector = this.showSiteSelector.bind(this);
        this.hideSiteSelector = this.hideSiteSelector.bind(this);
        this.handleSiteSearch = this.handleSiteSearch.bind(this);
        this.handleModeChange = this.handleModeChange.bind(this);
    }

    initialize() {
        this.setupModeSelector();
        this.setupEventListeners();
        this.loadSites();
    }

    setupEventListeners() {
        eventBus.on('ui:selectSite', () => {
            this.showSiteSelector();
        });

        eventBus.on('state:currentConversation', (conversation) => {
            if (conversation) {
                this.currentSiteId = conversation.sites?.[0] || null;
                this.currentMode = conversation.mode || 'summarize';
                this.updateModeSelector();
            }
        });

        eventBus.on('config:loaded', () => {
            this.loadSites();
        });
    }

    loadSites() {
        this.sites = configService.getSites();
        this.filteredSites = [...this.sites];
    }

    setupModeSelector() {
        // Find or create mode selector container
        let modeSelectorContainer = document.querySelector('.mode-selector-container');
        if (!modeSelectorContainer) {
            // Add to chat header if it exists
            const chatHeader = document.querySelector('.chat-header');
            if (chatHeader) {
                modeSelectorContainer = document.createElement('div');
                modeSelectorContainer.className = 'mode-selector-container';
                chatHeader.appendChild(modeSelectorContainer);
            }
        }

        if (modeSelectorContainer) {
            modeSelectorContainer.innerHTML = `
                <label for="mode-selector" class="mode-label">Mode:</label>
                <select id="mode-selector" class="mode-selector">
                    <option value="list">List</option>
                    <option value="summarize">Summarize</option>
                    <option value="generate">Generate</option>
                </select>
            `;

            this.modeSelector = modeSelectorContainer.querySelector('#mode-selector');
            this.modeSelector.value = this.currentMode;
            this.modeSelector.addEventListener('change', this.handleModeChange);

            // Add styles
            this.addModeSelectorStyles();
        }
    }

    addModeSelectorStyles() {
        if (document.querySelector('#site-selector-styles')) return;

        const style = document.createElement('style');
        style.id = 'site-selector-styles';
        style.textContent = `
            .mode-selector-container {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-left: auto;
                margin-right: 1rem;
            }
            .mode-label {
                font-size: 0.875rem;
                color: #586069;
                font-weight: 500;
            }
            .mode-selector {
                padding: 0.5rem 0.75rem;
                border: 1px solid #dfe4ea;
                border-radius: 0.25rem;
                background-color: white;
                font-size: 0.875rem;
                cursor: pointer;
                transition: border-color 0.2s;
            }
            .mode-selector:hover {
                border-color: #3498db;
            }
            .mode-selector:focus {
                outline: none;
                border-color: #3498db;
                box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
            }
        `;
        document.head.appendChild(style);
    }

    showSiteSelector() {
        if (this.modal) {
            this.modal.remove();
        }

        this.modal = document.createElement('div');
        this.modal.className = 'site-selector-modal';
        this.modal.innerHTML = `
            <div class="site-selector-overlay"></div>
            <div class="site-selector-content">
                <div class="site-selector-header">
                    <h2>Select a Site</h2>
                    <button class="btn-close" aria-label="Close">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>
                <div class="site-search-container">
                    <input 
                        type="text" 
                        class="site-search-input" 
                        placeholder="Search sites..."
                        aria-label="Search sites"
                    >
                    <svg class="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="11" cy="11" r="8"></circle>
                        <path d="m21 21-4.35-4.35"></path>
                    </svg>
                </div>
                <div class="site-grid" role="list">
                    ${this.renderSiteGrid()}
                </div>
            </div>
        `;

        // Add styles
        this.addSiteSelectorStyles();

        document.body.appendChild(this.modal);

        // Setup event handlers
        this.setupModalEventHandlers();

        // Focus search input
        const searchInput = this.modal.querySelector('.site-search-input');
        searchInput.focus();
    }

    renderSiteGrid() {
        if (this.filteredSites.length === 0) {
            return '<div class="no-sites">No sites found</div>';
        }

        return this.filteredSites.map(site => {
            const isSelected = site.id === this.currentSiteId;
            const displayName = site.display_name || site.name || site.id;
            const description = site.description || '';
            
            return `
                <div class="site-card ${isSelected ? 'selected' : ''}" 
                     data-site-id="${site.id}"
                     role="listitem"
                     tabindex="0"
                     aria-label="${this.escapeHtml(displayName)}">
                    <div class="site-card-header">
                        <div class="site-icon">
                            ${this.getSiteIcon(site)}
                        </div>
                        ${isSelected ? '<div class="selected-badge">Current</div>' : ''}
                    </div>
                    <div class="site-card-body">
                        <h3 class="site-name">${this.escapeHtml(displayName)}</h3>
                        ${description ? `<p class="site-description">${this.escapeHtml(description)}</p>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }

    getSiteIcon(site) {
        // Use first letter of site name as icon
        const name = site.display_name || site.name || site.id || '?';
        return name.charAt(0).toUpperCase();
    }

    setupModalEventHandlers() {
        const overlay = this.modal.querySelector('.site-selector-overlay');
        const closeBtn = this.modal.querySelector('.btn-close');
        const searchInput = this.modal.querySelector('.site-search-input');
        const siteCards = this.modal.querySelectorAll('.site-card');

        // Close handlers
        overlay.addEventListener('click', this.hideSiteSelector);
        closeBtn.addEventListener('click', this.hideSiteSelector);

        // Search handler
        searchInput.addEventListener('input', this.handleSiteSearch);

        // Site selection handlers
        siteCards.forEach(card => {
            card.addEventListener('click', () => {
                const siteId = card.dataset.siteId;
                this.selectSite(siteId);
            });

            card.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    const siteId = card.dataset.siteId;
                    this.selectSite(siteId);
                }
            });
        });

        // Escape key handler
        this.modal.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideSiteSelector();
            }
        });
    }

    handleSiteSearch(event) {
        const searchTerm = event.target.value.toLowerCase().trim();
        
        if (!searchTerm) {
            this.filteredSites = [...this.sites];
        } else {
            this.filteredSites = this.sites.filter(site => {
                const name = (site.display_name || site.name || site.id || '').toLowerCase();
                const description = (site.description || '').toLowerCase();
                return name.includes(searchTerm) || description.includes(searchTerm);
            });
        }

        // Update grid
        const gridContainer = this.modal.querySelector('.site-grid');
        gridContainer.innerHTML = this.renderSiteGrid();
        
        // Re-attach event handlers to new cards
        const siteCards = gridContainer.querySelectorAll('.site-card');
        siteCards.forEach(card => {
            card.addEventListener('click', () => {
                const siteId = card.dataset.siteId;
                this.selectSite(siteId);
            });

            card.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    const siteId = card.dataset.siteId;
                    this.selectSite(siteId);
                }
            });
        });
    }

    selectSite(siteId) {
        const site = this.sites.find(s => s.id === siteId);
        if (site) {
            this.currentSiteId = siteId;
            eventBus.emit('ui:siteSelected', { 
                site,
                mode: this.currentMode 
            });
            this.hideSiteSelector();
        }
    }

    hideSiteSelector() {
        if (this.modal) {
            this.modal.remove();
            this.modal = null;
        }
    }

    handleModeChange(event) {
        const newMode = event.target.value;
        this.currentMode = newMode;
        this.storeModePreference(newMode);
        
        eventBus.emit('ui:modeChanged', { mode: newMode });
    }

    updateModeSelector() {
        if (this.modeSelector) {
            this.modeSelector.value = this.currentMode;
        }
    }

    getStoredMode() {
        return localStorage.getItem('nlweb_chat_mode');
    }

    storeModePreference(mode) {
        localStorage.setItem('nlweb_chat_mode', mode);
    }

    addSiteSelectorStyles() {
        if (document.querySelector('#site-selector-modal-styles')) return;

        const style = document.createElement('style');
        style.id = 'site-selector-modal-styles';
        style.textContent = `
            .site-selector-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                z-index: 1000;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .site-selector-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: rgba(0, 0, 0, 0.5);
                animation: fadeIn 0.2s ease;
            }
            .site-selector-content {
                position: relative;
                background: white;
                border-radius: 0.5rem;
                width: 90%;
                max-width: 800px;
                max-height: 80vh;
                display: flex;
                flex-direction: column;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                animation: slideUp 0.3s ease;
            }
            .site-selector-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 1.5rem;
                border-bottom: 1px solid #e1e4e8;
            }
            .site-selector-header h2 {
                margin: 0;
                font-size: 1.5rem;
            }
            .btn-close {
                background: none;
                border: none;
                padding: 0.5rem;
                cursor: pointer;
                color: #586069;
                transition: color 0.2s;
            }
            .btn-close:hover {
                color: #24292e;
            }
            .site-search-container {
                position: relative;
                padding: 1rem 1.5rem;
            }
            .site-search-input {
                width: 100%;
                padding: 0.75rem 1rem 0.75rem 2.5rem;
                border: 1px solid #dfe4ea;
                border-radius: 0.25rem;
                font-size: 1rem;
                transition: border-color 0.2s;
            }
            .site-search-input:focus {
                outline: none;
                border-color: #3498db;
                box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
            }
            .search-icon {
                position: absolute;
                left: 2rem;
                top: 50%;
                transform: translateY(-50%);
                color: #586069;
                pointer-events: none;
            }
            .site-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 1rem;
                padding: 1.5rem;
                overflow-y: auto;
                flex: 1;
            }
            .site-card {
                border: 1px solid #e1e4e8;
                border-radius: 0.5rem;
                padding: 1rem;
                cursor: pointer;
                transition: all 0.2s;
                background: white;
            }
            .site-card:hover {
                border-color: #3498db;
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
            .site-card:focus {
                outline: none;
                border-color: #3498db;
                box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.2);
            }
            .site-card.selected {
                border-color: #3498db;
                background-color: #f0f8ff;
            }
            .site-card-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 0.75rem;
            }
            .site-icon {
                width: 40px;
                height: 40px;
                border-radius: 0.25rem;
                background: #3498db;
                color: white;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.25rem;
                font-weight: 600;
            }
            .selected-badge {
                font-size: 0.75rem;
                padding: 0.25rem 0.5rem;
                background: #3498db;
                color: white;
                border-radius: 0.25rem;
                font-weight: 500;
            }
            .site-name {
                margin: 0 0 0.5rem 0;
                font-size: 1rem;
                font-weight: 600;
                color: #24292e;
            }
            .site-description {
                margin: 0;
                font-size: 0.875rem;
                color: #586069;
                overflow: hidden;
                text-overflow: ellipsis;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
            }
            .no-sites {
                text-align: center;
                padding: 2rem;
                color: #586069;
                grid-column: 1 / -1;
            }
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            @keyframes slideUp {
                from {
                    transform: translateY(20px);
                    opacity: 0;
                }
                to {
                    transform: translateY(0);
                    opacity: 1;
                }
            }
            @media (max-width: 768px) {
                .site-grid {
                    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                }
            }
        `;
        document.head.appendChild(style);
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        this.hideSiteSelector();
        if (this.modeSelector) {
            this.modeSelector.removeEventListener('change', this.handleModeChange);
        }
    }
}
