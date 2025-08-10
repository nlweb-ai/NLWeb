import eventBus from './event-bus.js';

class ApiService {
    constructor() {
        this.baseUrl = ''; // Use relative URLs by default
    }
    
    // Helper method to build headers
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        // Get auth token from sessionStorage
        const authToken = sessionStorage.getItem('authToken');
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }
        
        return headers;
    }
    
    // Helper method for API calls
    async apiCall(method, endpoint, body = null) {
        const url = `${this.baseUrl}${endpoint}`;
        const options = {
            method,
            headers: this.getHeaders()
        };
        
        if (body) {
            options.body = JSON.stringify(body);
        }
        
        try {
            const response = await fetch(url, options);
            
            // Handle 404 specifically
            if (response.status === 404) {
                return null;
            }
            
            // Handle other non-OK responses
            if (!response.ok) {
                const error = new Error(`API Error: ${response.status} ${response.statusText}`);
                error.status = response.status;
                error.response = response;
                
                // Try to get error message from response
                try {
                    const errorData = await response.json();
                    error.message = errorData.message || error.message;
                    error.data = errorData;
                } catch (e) {
                    // Ignore JSON parse errors
                }
                
                throw error;
            }
            
            // Parse successful response
            return await response.json();
            
        } catch (error) {
            // Emit error event
            eventBus.emit('api:error', {
                method,
                endpoint,
                error: error.message,
                status: error.status
            });
            
            throw error;
        }
    }
    
    // Create a new conversation
    async createConversation(site, mode, participantIds = []) {
        const body = {
            site,
            mode,
            participantIds
        };
        
        const result = await this.apiCall('POST', '/api/chat/conversations', body);
        return result; // { conversation_id, created_at }
    }
    
    // Get all conversations
    async getConversations() {
        const conversations = await this.apiCall('GET', '/api/chat/conversations');
        return conversations || []; // Return empty array if null
    }
    
    // Get a specific conversation
    async getConversation(conversationId) {
        const conversation = await this.apiCall('GET', `/api/chat/conversations/${conversationId}`);
        return conversation; // Full conversation with messages, or null if 404
    }
    
    // Join a conversation (for already authorized users)
    async joinConversation(conversationId, participantInfo) {
        const body = {
            participant: {
                user_id: participantInfo.participantId || participantInfo.id,
                name: participantInfo.displayName || participantInfo.name
            }
        };
        
        // Check if this is a share link join (direct conversation ID)
        // Try the share link endpoint first
        try {
            const result = await this.apiCall('POST', `/chat/join/${conversationId}`, body);
            return result; // { success: true, conversation }
        } catch (error) {
            // If share link fails, try regular join
            if (error.status === 404) {
                const result = await this.apiCall('POST', `/chat/${conversationId}/join`, body);
                return result; // { success: true, conversation }
            }
            throw error;
        }
    }
    
    // Leave a conversation
    async leaveConversation(conversationId) {
        const result = await this.apiCall('DELETE', `/api/chat/conversations/${conversationId}/leave`);
        return result; // { success: true }
    }
    
    // Support optional baseUrl configuration
    setBaseUrl(baseUrl) {
        this.baseUrl = baseUrl || '';
    }
}

// Export singleton instance
export default new ApiService();
