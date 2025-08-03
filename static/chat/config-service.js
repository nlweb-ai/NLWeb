import eventBus from './event-bus.js';

class ConfigService {
    constructor() {
        this.config = {};
        this.sites = [];
        this.modes = ['list', 'summarize', 'generate'];
        this.loaded = false;
        this.loading = false;
    }

    async initialize() {
        if (this.loaded || this.loading) {
            return;
        }

        this.loading = true;
        
        try {
            // Load config and sites in parallel
            const [configResult, sitesResult] = await Promise.allSettled([
                this.loadConfig(),
                this.loadSites()
            ]);

            if (configResult.status === 'rejected') {
                console.warn('Failed to load config:', configResult.reason);
            }

            if (sitesResult.status === 'rejected') {
                console.warn('Failed to load sites:', sitesResult.reason);
            }

            this.loaded = true;
            eventBus.emit('config:loaded', {
                config: this.config,
                sites: this.sites,
                modes: this.modes
            });

        } catch (error) {
            console.error('ConfigService initialization failed:', error);
            this.loaded = true; // Mark as loaded even on error to prevent retry loops
            eventBus.emit('config:loaded', {
                config: this.config,
                sites: this.sites,
                modes: this.modes
            });
        } finally {
            this.loading = false;
        }
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/chat/config');
            if (response.ok) {
                this.config = await response.json();
            } else {
                console.warn('Config endpoint returned:', response.status);
            }
        } catch (error) {
            console.warn('Failed to fetch config:', error);
        }
    }

    async loadSites() {
        try {
            const response = await fetch('/sites?streaming=false');
            if (response.ok) {
                const data = await response.json();
                this.sites = Array.isArray(data) ? data : (data.sites || []);
            } else {
                console.warn('Sites endpoint returned:', response.status);
            }
        } catch (error) {
            console.warn('Failed to fetch sites:', error);
        }
    }

    getSites() {
        return this.sites;
    }

    getModes() {
        return this.modes;
    }

    getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        return `${protocol}//${host}/chat/ws`;
    }

    getConfig() {
        return this.config;
    }

    isLoaded() {
        return this.loaded;
    }
}

// Export singleton instance
export default new ConfigService();