/**
 * ParticipantTracker - Utility class for tracking participant state
 * Used by StateManager to manage participants per conversation
 */

class ParticipantTracker {
    constructor(conversation) {
        this.conversation = conversation;
        this.participants = new Map(); // participantId -> participant object
        this.typingStates = new Map(); // participantId -> timeoutId
        
        // Initialize with existing participants
        if (conversation.participants) {
            this.updateParticipants(conversation.participants);
        }
    }
    
    /**
     * Sync participants with server list
     */
    updateParticipants(participantList) {
        // Clear existing participants
        this.participants.clear();
        
        // Add new participants
        if (Array.isArray(participantList)) {
            participantList.forEach(participant => {
                if (participant.participantId) {
                    this.participants.set(participant.participantId, {
                        ...participant,
                        joinedAt: participant.joinedAt || new Date().toISOString(),
                        lastSeen: participant.lastSeen || new Date().toISOString(),
                        isOnline: participant.isOnline !== false // Default to online
                    });
                }
            });
        }
        
        // Update conversation reference
        this.conversation.participants = Array.from(this.participants.values());
    }
    
    /**
     * Update typing state for a participant
     */
    setTyping(participantId, isTyping) {
        if (!participantId) return;
        
        // Clear any existing timeout
        this.clearTyping(participantId);
        
        if (isTyping) {
            // Set typing state with auto-clear after 5 seconds
            const timeoutId = setTimeout(() => {
                this.clearTyping(participantId);
            }, 5000);
            
            this.typingStates.set(participantId, timeoutId);
        }
    }
    
    /**
     * Clear typing state for a participant
     */
    clearTyping(participantId) {
        if (!participantId) return;
        
        const timeoutId = this.typingStates.get(participantId);
        if (timeoutId) {
            clearTimeout(timeoutId);
            this.typingStates.delete(participantId);
        }
    }
    
    /**
     * Clear all typing states
     */
    clearAllTyping() {
        // Clear all timeouts
        for (const [participantId, timeoutId] of this.typingStates.entries()) {
            clearTimeout(timeoutId);
        }
        
        // Clear the map
        this.typingStates.clear();
    }
    
    /**
     * Get array of participant IDs currently typing
     */
    getTypingParticipants() {
        return Array.from(this.typingStates.keys());
    }
    
    /**
     * Get participants filtered by online status
     */
    getActiveParticipants() {
        return Array.from(this.participants.values()).filter(p => p.isOnline);
    }
    
    /**
     * Check if this is a multi-participant conversation
     */
    isMultiParticipant() {
        return this.participants.size > 2;
    }
    
    /**
     * Get participant by ID
     */
    getParticipant(participantId) {
        return this.participants.get(participantId);
    }
    
    /**
     * Get all participants
     */
    getAllParticipants() {
        return Array.from(this.participants.values());
    }
    
    /**
     * Update participant online status
     */
    setOnlineStatus(participantId, isOnline) {
        const participant = this.participants.get(participantId);
        if (participant) {
            participant.isOnline = isOnline;
            participant.lastSeen = new Date().toISOString();
            
            // Update conversation reference
            this.conversation.participants = Array.from(this.participants.values());
        }
    }
    
    /**
     * Clear typing state when participant sends a message
     * Called by StateManager when processing messages
     */
    handleMessageSent(participantId) {
        this.clearTyping(participantId);
    }
    
    /**
     * Clean up resources (clear all timeouts)
     */
    destroy() {
        this.clearAllTyping();
        this.participants.clear();
    }
}

export default ParticipantTracker;
