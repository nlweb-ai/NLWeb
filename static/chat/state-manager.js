import eventBus from './event-bus.js';
import ParticipantTracker from './participant-tracker.js';

class StateManager {
    constructor() {
        // Core data structures
        this.conversations = new Map(); // id -> conversation object
        this.currentConversationId = null;
        this.siteMetadata = new Map(); // site -> {lastUsed, conversationCount}
        this.participantTrackers = new Map(); // conversationId -> ParticipantTracker
        
        // User preferences
        this.preferences = {
            sidebarSortMode: 'recency', // 'recency' or 'alphabetical'
            defaultMode: 'summarize',
            defaultSite: null
        };
        
        // Configuration
        this.MAX_MESSAGES_PER_CONVERSATION = 50;
        this.STORAGE_KEY = 'nlweb_chat_state';
        this.CONVERSATION_EXPIRY_DAYS = 30;
        
        // Load persisted state on initialization
        this.loadFromStorage();
    }
    
    // Current conversation management
    setCurrentConversation(conversationId) {
        const oldId = this.currentConversationId;
        this.currentConversationId = conversationId;
        
        if (oldId !== conversationId) {
            eventBus.emit('conversation:changed', {
                previousId: oldId,
                currentId: conversationId,
                conversation: this.getCurrentConversation()
            });
        }
        
        this.saveToStorage();
    }
    
    getCurrentConversation() {
        if (!this.currentConversationId) return null;
        return this.conversations.get(this.currentConversationId);
    }
    
    // Conversation management
    addConversation(conversation) {
        if (!conversation.id) {
            return;
        }
        
        // Normalize sites field - handle both 'site' (singular) and 'sites' (plural)
        let sites = conversation.sites;
        if (!sites && conversation.site) {
            sites = [conversation.site];
        }
        
        // Initialize conversation structure
        const conversationData = {
            ...conversation,
            sites: sites || [],  // Ensure sites is always an array
            messages: conversation.messages || [],
            participants: conversation.participants || [],
            created_at: conversation.created_at || new Date().toISOString(),
            updated_at: new Date().toISOString()
        };
        
        this.conversations.set(conversation.id, conversationData);
        
        // Create participant tracker for this conversation
        const tracker = new ParticipantTracker(conversationData);
        this.participantTrackers.set(conversation.id, tracker);
        
        // Update site metadata
        if (conversationData.sites && conversationData.sites.length > 0) {
            conversationData.sites.forEach(site => {
                this.updateSiteUsage(site);
            });
        }
        
        eventBus.emit('conversation:added', conversationData);
        this.saveToStorage();
    }
    
    updateConversation(conversationId, updates) {
        const conversation = this.conversations.get(conversationId);
        if (!conversation) {
            return;
        }
        
        // Apply updates
        Object.assign(conversation, updates, {
            updated_at: new Date().toISOString()
        });
        
        eventBus.emit('conversation:updated', {
            conversationId,
            updates,
            conversation
        });
        
        this.saveToStorage();
    }
    
    // Message management
    addMessage(conversationId, message) {
        const conversation = this.conversations.get(conversationId);
        if (!conversation) {
            return;
        }
        
        // Initialize messages array if needed
        if (!conversation.messages) {
            conversation.messages = [];
        }
        
        // Clear typing state for the message sender
        const tracker = this.participantTrackers.get(conversationId);
        if (tracker && message.participant && message.participant.participantId) {
            tracker.handleMessageSent(message.participant.participantId);
        }
        
        // Add sequence_id if not present
        if (!message.sequence_id) {
            const lastMessage = conversation.messages[conversation.messages.length - 1];
            message.sequence_id = lastMessage ? lastMessage.sequence_id + 1 : 1;
        }
        
        // Check if message already exists (by ID or sequence_id)
        const existingIndex = conversation.messages.findIndex(m => 
            (m.id && m.id === message.id) || 
            (m.sequence_id && m.sequence_id === message.sequence_id)
        );
        
        if (existingIndex >= 0) {
            // Update existing message
            conversation.messages[existingIndex] = {
                ...conversation.messages[existingIndex],
                ...message
            };
        } else {
            // Add new message
            conversation.messages.push(message);
            
            // Sort by sequence_id
            conversation.messages.sort((a, b) => 
                (a.sequence_id || 0) - (b.sequence_id || 0)
            );
            
            // Enforce message limit
            if (conversation.messages.length > this.MAX_MESSAGES_PER_CONVERSATION) {
                const removed = conversation.messages.shift();
            }
        }
        
        // Update conversation timestamp
        conversation.updated_at = new Date().toISOString();
        
        // Update last message for preview
        conversation.last_message = message;
        conversation.message_count = conversation.messages.length;
        
        eventBus.emit('message:added', {
            conversationId,
            message,
            conversation
        });
        
        this.saveToStorage();
    }
    
    getMessages(conversationId, startSeq = 0, endSeq = Infinity) {
        const conversation = this.conversations.get(conversationId);
        if (!conversation || !conversation.messages) {
            return [];
        }
        
        return conversation.messages.filter(msg => {
            const seq = msg.sequence_id || 0;
            return seq >= startSeq && seq <= endSeq;
        });
    }
    
    // Participant management
    updateParticipants(conversationId, participants) {
        const conversation = this.conversations.get(conversationId);
        if (!conversation) {
            return;
        }
        
        // Update via participant tracker
        const tracker = this.participantTrackers.get(conversationId);
        if (tracker) {
            tracker.updateParticipants(participants);
        } else {
            // Create tracker if it doesn't exist
            const newTracker = new ParticipantTracker(conversation);
            newTracker.updateParticipants(participants);
            this.participantTrackers.set(conversationId, newTracker);
        }
        
        conversation.updated_at = new Date().toISOString();
        
        eventBus.emit('participants:updated', {
            conversationId,
            participants,
            conversation
        });
        
        this.saveToStorage();
    }
    
    // Typing state management
    updateTypingState(conversationId, participantId, isTyping) {
        const tracker = this.participantTrackers.get(conversationId);
        if (tracker) {
            tracker.setTyping(participantId, isTyping);
            
            // Emit typing update event
            eventBus.emit('typing:updated', {
                conversationId,
                participantId,
                isTyping,
                typingParticipants: tracker.getTypingParticipants()
            });
        }
    }
    
    getTypingParticipants(conversationId) {
        const tracker = this.participantTrackers.get(conversationId);
        return tracker ? tracker.getTypingParticipants() : [];
    }
    
    getActiveParticipants(conversationId) {
        const tracker = this.participantTrackers.get(conversationId);
        return tracker ? tracker.getActiveParticipants() : [];
    }
    
    isMultiParticipantConversation(conversationId) {
        const tracker = this.participantTrackers.get(conversationId);
        return tracker ? tracker.isMultiParticipant() : false;
    }
    
    // Site management
    updateSiteUsage(site) {
        const metadata = this.siteMetadata.get(site) || {
            conversationCount: 0,
            lastUsed: null
        };
        
        metadata.lastUsed = new Date().toISOString();
        metadata.conversationCount = this.getConversationsForSite(site).length;
        
        this.siteMetadata.set(site, metadata);
        this.saveToStorage();
    }
    
    getSitesSorted(mode = 'recency') {
        const sites = Array.from(this.siteMetadata.entries());
        
        if (mode === 'alphabetical') {
            return sites.sort((a, b) => a[0].localeCompare(b[0]));
        } else {
            // Sort by recency
            return sites.sort((a, b) => {
                const aTime = new Date(a[1].lastUsed || 0);
                const bTime = new Date(b[1].lastUsed || 0);
                return bTime - aTime;
            });
        }
    }
    
    getConversationsForSite(site) {
        return Array.from(this.conversations.values()).filter(conv => 
            conv.sites && conv.sites.includes(site)
        );
    }
    
    // Get all conversations sorted
    getAllConversations(sortBy = 'updated') {
        const conversations = Array.from(this.conversations.values());
        
        if (sortBy === 'updated') {
            return conversations.sort((a, b) => 
                new Date(b.updated_at || 0) - new Date(a.updated_at || 0)
            );
        } else if (sortBy === 'created') {
            return conversations.sort((a, b) => 
                new Date(b.created_at || 0) - new Date(a.created_at || 0)
            );
        }
        
        return conversations;
    }
    
    // Preferences
    setPreference(key, value) {
        if (key in this.preferences) {
            this.preferences[key] = value;
            this.saveToStorage();
            
            eventBus.emit('preference:changed', { key, value });
        }
    }
    
    getPreference(key) {
        return this.preferences[key];
    }
    
    // Storage management
    saveToStorage() {
        try {
            const state = {
                conversations: Array.from(this.conversations.entries()),
                currentConversationId: this.currentConversationId,
                siteMetadata: Array.from(this.siteMetadata.entries()),
                preferences: this.preferences,
                version: '1.0',
                lastSaved: new Date().toISOString()
            };
            
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(state));
        } catch (error) {
            
            // Handle quota exceeded error
            if (error.name === 'QuotaExceededError') {
                this.cleanupOldData();
                // Try again
                try {
                    this.saveToStorage();
                } catch (retryError) {
                }
            }
        }
    }
    
    loadFromStorage() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            if (!stored) return;
            
            const state = JSON.parse(stored);
            
            // Restore conversations
            if (state.conversations) {
                this.conversations = new Map(state.conversations);
                
                // Recreate participant trackers for each conversation
                for (const [conversationId, conversation] of this.conversations.entries()) {
                    const tracker = new ParticipantTracker(conversation);
                    this.participantTrackers.set(conversationId, tracker);
                }
                
                // Clean up old conversations
                this.cleanupOldConversations();
            }
            
            // Restore current conversation
            if (state.currentConversationId) {
                this.currentConversationId = state.currentConversationId;
            }
            
            // Restore site metadata
            if (state.siteMetadata) {
                this.siteMetadata = new Map(state.siteMetadata);
            }
            
            // Restore preferences
            if (state.preferences) {
                Object.assign(this.preferences, state.preferences);
            }
            
            
        } catch (error) {
            // Continue with empty state
        }
    }
    
    cleanupOldConversations() {
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - this.CONVERSATION_EXPIRY_DAYS);
        
        let removedCount = 0;
        
        for (const [id, conversation] of this.conversations.entries()) {
            const lastUpdate = new Date(conversation.updated_at || conversation.created_at || 0);
            
            if (lastUpdate < cutoffDate) {
                // Clean up tracker
                const tracker = this.participantTrackers.get(id);
                if (tracker) {
                    tracker.destroy();
                    this.participantTrackers.delete(id);
                }
                
                this.conversations.delete(id);
                removedCount++;
            }
        }
        
        if (removedCount > 0) {
        }
    }
    
    cleanupOldData() {
        // Remove oldest conversations to free up space
        const conversations = this.getAllConversations('updated');
        const toKeep = Math.floor(conversations.length / 2);
        
        // Keep only the most recent half
        const keepIds = new Set(conversations.slice(0, toKeep).map(c => c.id));
        
        for (const [id] of this.conversations.entries()) {
            if (!keepIds.has(id)) {
                this.conversations.delete(id);
            }
        }
        
    }
    
    // Clear all data
    clearAll() {
        // Clean up all participant trackers
        for (const [id, tracker] of this.participantTrackers.entries()) {
            tracker.destroy();
        }
        this.participantTrackers.clear();
        
        this.conversations.clear();
        this.siteMetadata.clear();
        this.currentConversationId = null;
        this.preferences = {
            sidebarSortMode: 'recency',
            defaultMode: 'summarize',
            defaultSite: null
        };
        
        localStorage.removeItem(this.STORAGE_KEY);
        
        eventBus.emit('state:cleared');
    }
    
    // Get state summary for debugging
    getStateSummary() {
        return {
            conversationCount: this.conversations.size,
            currentConversationId: this.currentConversationId,
            siteCount: this.siteMetadata.size,
            preferences: this.preferences,
            storageSize: this.getStorageSize()
        };
    }
    
    getStorageSize() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            return stored ? new Blob([stored]).size : 0;
        } catch {
            return 0;
        }
    }
}

// Export singleton instance
export default new StateManager();
