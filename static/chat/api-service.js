import eventBus from './event-bus.js';
import identityService from './identity-service.js';

class ApiService {
    constructor() {
        this.baseUrl = window.location.origin;
        this.retryAttempts = 3;
        this.retryDelay = 1000; // Start with 1 second
    }
    
    // Helper method to build headers
    getHeaders(additionalHeaders = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...additionalHeaders
        };
        
        // Add authentication token if available
        const authToken = sessionStorage.getItem('authToken');
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }
        
        // Add participant info for non-OAuth users
        const identity = identityService.getCurrentIdentity();
        if (identity && !authToken) {
            headers['X-Participant-Id'] = identity.participantId;
            headers['X-Participant-Email'] = identity.email;
        }
        
        return headers;
    }
    
    // Helper method for fetch with retry logic
    async fetchWithRetry(url, options = {}, attempt = 1) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: this.getHeaders(options.headers)
            });
            
            if (!response.ok) {
                // Handle specific error codes
                if (response.status === 401) {
                    eventBus.emit('auth:unauthorized');
                    throw new Error('Unauthorized');
                }
                
                if (response.status >= 500 && attempt < this.retryAttempts) {
                    // Server error - retry
                    const delay = this.retryDelay * attempt;
                    console.warn(`Server error ${response.status}, retrying in ${delay}ms...`);
                    await new Promise(resolve => setTimeout(resolve, delay));
                    return this.fetchWithRetry(url, options, attempt + 1);
                }
                
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return response;
            
        } catch (error) {
            // Network error - retry if attempts remaining
            if (attempt < this.retryAttempts && error.name === 'TypeError') {
                const delay = this.retryDelay * attempt;
                console.warn(`Network error, retrying in ${delay}ms...`, error);
                await new Promise(resolve => setTimeout(resolve, delay));
                return this.fetchWithRetry(url, options, attempt + 1);
            }
            
            throw error;
        }
    }
    
    // Create a new conversation
    async createConversation(params = {}) {
        const url = `${this.baseUrl}/chat/create`;
        
        const body = {
            title: params.title || `Chat - ${new Date().toLocaleDateString()}`,
            sites: params.sites || [],
            mode: params.mode || 'summarize',
            participant: params.participant || identityService.getParticipantInfo()
        };
        
        try {
            const response = await this.fetchWithRetry(url, {
                method: 'POST',
                body: JSON.stringify(body)
            });
            
            const conversation = await response.json();
            
            eventBus.emit('api:conversationCreated', conversation);
            return conversation;
            
        } catch (error) {
            console.error('Failed to create conversation:', error);
            eventBus.emit('api:error', {
                operation: 'createConversation',
                error: error.message
            });
            throw error;
        }
    }
    
    // Get user's conversations
    async getConversations(params = {}) {
        const url = new URL(`${this.baseUrl}/chat/my-conversations`);
        
        // Add query parameters
        if (params.site) {
            url.searchParams.append('site', params.site);
        }
        if (params.limit) {
            url.searchParams.append('limit', params.limit);
        }
        if (params.offset) {
            url.searchParams.append('offset', params.offset);
        }
        
        try {
            const response = await this.fetchWithRetry(url.toString());
            const conversations = await response.json();
            
            eventBus.emit('api:conversationsLoaded', conversations);
            return conversations;
            
        } catch (error) {
            console.error('Failed to get conversations:', error);
            eventBus.emit('api:error', {
                operation: 'getConversations',
                error: error.message
            });
            throw error;
        }
    }
    
    // Get a specific conversation
    async getConversation(conversationId) {
        const url = `${this.baseUrl}/chat/conversations/${conversationId}`;
        
        try {
            const response = await this.fetchWithRetry(url);
            const conversation = await response.json();
            
            eventBus.emit('api:conversationLoaded', conversation);
            return conversation;
            
        } catch (error) {
            console.error(`Failed to get conversation ${conversationId}:`, error);
            eventBus.emit('api:error', {
                operation: 'getConversation',
                error: error.message,
                conversationId
            });
            throw error;
        }
    }
    
    // Send a message to a conversation
    async sendMessage(conversationId, content, params = {}) {
        const url = `${this.baseUrl}/chat/${conversationId}/messages`;
        
        const body = {
            content: content,
            sites: params.sites || [],
            mode: params.mode || 'summarize',
            participant: params.participant || identityService.getParticipantInfo()
        };
        
        try {
            const response = await this.fetchWithRetry(url, {
                method: 'POST',
                body: JSON.stringify(body)
            });
            
            const result = await response.json();
            
            eventBus.emit('api:messageSent', {
                conversationId,
                message: result.message,
                response: result
            });
            
            return result;
            
        } catch (error) {
            console.error('Failed to send message:', error);
            eventBus.emit('api:error', {
                operation: 'sendMessage',
                error: error.message,
                conversationId
            });
            throw error;
        }
    }
    
    // Join a conversation
    async joinConversation(conversationId) {
        const url = `${this.baseUrl}/chat/${conversationId}/join`;
        
        const body = {
            participant: identityService.getParticipantInfo()
        };
        
        try {
            const response = await this.fetchWithRetry(url, {
                method: 'POST',
                body: JSON.stringify(body)
            });
            
            const result = await response.json();
            
            eventBus.emit('api:conversationJoined', {
                conversationId,
                result
            });
            
            return result;
            
        } catch (error) {
            console.error(`Failed to join conversation ${conversationId}:`, error);
            eventBus.emit('api:error', {
                operation: 'joinConversation',
                error: error.message,
                conversationId
            });
            throw error;
        }
    }
    
    // Update conversation (title, mode, etc.)
    async updateConversation(conversationId, updates) {
        const url = `${this.baseUrl}/chat/conversations/${conversationId}`;
        
        try {
            const response = await this.fetchWithRetry(url, {
                method: 'PATCH',
                body: JSON.stringify(updates)
            });
            
            const conversation = await response.json();
            
            eventBus.emit('api:conversationUpdated', {
                conversationId,
                updates,
                conversation
            });
            
            return conversation;
            
        } catch (error) {
            console.error(`Failed to update conversation ${conversationId}:`, error);
            eventBus.emit('api:error', {
                operation: 'updateConversation',
                error: error.message,
                conversationId
            });
            throw error;
        }
    }
    
    // Health check
    async checkHealth() {
        const url = `${this.baseUrl}/health/chat`;
        
        try {
            const response = await this.fetchWithRetry(url, {}, 1); // Only 1 attempt for health
            const health = await response.json();
            
            eventBus.emit('api:healthChecked', health);
            return health;
            
        } catch (error) {
            console.error('Health check failed:', error);
            eventBus.emit('api:error', {
                operation: 'checkHealth',
                error: error.message
            });
            return { status: 'error', error: error.message };
        }
    }
    
    // Get sites list
    async getSites() {
        const url = `${this.baseUrl}/sites?streaming=false`;
        
        try {
            const response = await this.fetchWithRetry(url);
            const data = await response.json();
            const sites = Array.isArray(data) ? data : (data.sites || []);
            
            eventBus.emit('api:sitesLoaded', sites);
            return sites;
            
        } catch (error) {
            console.error('Failed to get sites:', error);
            eventBus.emit('api:error', {
                operation: 'getSites',
                error: error.message
            });
            throw error;
        }
    }
    
    // Get configuration
    async getConfig() {
        const url = `${this.baseUrl}/api/chat/config`;
        
        try {
            const response = await this.fetchWithRetry(url);
            const config = await response.json();
            
            eventBus.emit('api:configLoaded', config);
            return config;
            
        } catch (error) {
            console.error('Failed to get config:', error);
            // Non-critical error - just log
            return {};
        }
    }
}

// Export singleton instance
export default new ApiService();