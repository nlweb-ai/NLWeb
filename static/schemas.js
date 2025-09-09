/**
 * Core message and conversation schemas for NLWeb system.
 * Provides standardized data structures and utilities.
 */

// Enums
export const SenderType = {
    USER: "user",
    ASSISTANT: "assistant",
    SYSTEM: "system"
};

export const MessageStatus = {
    PENDING: "pending",
    DELIVERED: "delivered",
    FAILED: "failed",
    PROCESSING: "processing"
};

export const MessageType = {
    // User interactions
    QUERY: "query",
    
    // Results and responses
    RESULT: "result",
    NLWS: "nlws",
    
    // Status and progress
    STATUS: "status",
    INTERMEDIATE: "intermediate_message",
    
    // Errors
    ERROR: "error",
    
    // Specific content types
    ITEM_DETAILS: "item_details",
    STATISTICS: "statistics_result",
    CHART: "chart_result",
    COMPARISON: "compare_items",
    SUBSTITUTION: "substitution_suggestions",
    ENSEMBLE: "ensemble_result",
    
    // Multi-site operations
    SITE_QUERYING: "site_querying",
    SITE_COMPLETE: "site_complete",
    SITE_ERROR: "site_error",
    MULTI_SITE_COMPLETE: "multi_site_complete",
    
    // System messages
    NO_RESULTS: "no_results",
    COMPLETE: "complete",
    TOOL_SELECTION: "tool_selection",
    
    // Chat-specific events
    CONVERSATION_START: "conversation_start",
    USER_JOINING: "user_joining",
    USER_LEAVING: "user_leaving",
    JOIN: "join",
    LEAVE: "leave"
};

/**
 * User query content structure
 */
export class UserQuery {
    constructor(query, site = null, mode = null, prevQueries = null) {
        this.query = query;
        this.site = site;
        this.mode = mode;
        this.prev_queries = prevQueries;
    }
    
    toDict() {
        const result = { query: this.query };
        if (this.site !== null) result.site = this.site;
        if (this.mode !== null) result.mode = this.mode;
        if (this.prev_queries !== null) result.prev_queries = this.prev_queries;
        return result;
    }
    
    static fromDict(data) {
        return new UserQuery(
            data.query || "",
            data.site || null,
            data.mode || null,
            data.prev_queries || null
        );
    }
}

/**
 * Core message structure for all communication
 */
export class Message {
    constructor({
        message_id = null,
        sender_type = SenderType.USER,
        message_type = MessageType.QUERY,
        conversation_id = null,
        timestamp = null,
        content = "",
        sender_info = null,
        metadata = null
    } = {}) {
        this.message_id = message_id || `msg_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
        this.sender_type = sender_type;
        this.message_type = message_type;
        this.conversation_id = conversation_id;
        this.timestamp = timestamp || new Date().toISOString();
        this.content = content;
        this.sender_info = sender_info;
        this.metadata = metadata;
    }
    
    toDict() {
        const result = {
            message_id: this.message_id,
            sender_type: this.sender_type,
            message_type: this.message_type,
            timestamp: this.timestamp
        };
        
        // Handle content serialization
        if (this.content instanceof UserQuery) {
            result.content = this.content.toDict();
        } else {
            result.content = this.content;
        }
        
        // Add optional fields
        if (this.conversation_id !== null) {
            result.conversation_id = this.conversation_id;
        }
        if (this.sender_info !== null) {
            result.sender_info = this.sender_info;
        }
        if (this.metadata !== null) {
            result.metadata = this.metadata;
        }
        
        return result;
    }
    
    toJSON() {
        return JSON.stringify(this.toDict());
    }
    
    static fromDict(data) {
        let content = data.content || "";
        const senderType = data.sender_type || "user";
        
        // If content is a dict with 'query' field and sender is user, treat as UserQuery
        if (typeof content === 'object' && content !== null && 'query' in content && senderType === "user") {
            content = UserQuery.fromDict(content);
        }
        
        return new Message({
            message_id: data.message_id,
            sender_type: senderType,
            message_type: data.message_type || MessageType.QUERY,
            conversation_id: data.conversation_id,
            timestamp: data.timestamp,
            content: content,
            sender_info: data.sender_info,
            metadata: data.metadata
        });
    }
    
    static fromJSON(jsonStr) {
        return Message.fromDict(JSON.parse(jsonStr));
    }
}

/**
 * Represents a conversation with multiple entries
 */
export class Conversation {
    constructor(entries = []) {
        this.entries = entries;
    }
    
    addEntry(entry) {
        this.entries.push(entry);
    }
    
    getEntries() {
        return this.entries;
    }
    
    toDict() {
        return {
            entries: this.entries.map(entry => 
                entry instanceof ConversationEntry ? entry.toDict() : entry
            )
        };
    }
    
    toJSON() {
        return JSON.stringify(this.toDict());
    }
    
    static fromDict(data) {
        const entries = (data.entries || []).map(entryData => {
            if (entryData instanceof ConversationEntry) {
                return entryData;
            }
            return ConversationEntry.fromDict(entryData);
        });
        return new Conversation(entries);
    }
    
    static fromJSON(jsonStr) {
        return Conversation.fromDict(JSON.parse(jsonStr));
    }
}

/**
 * Represents a single conversation entry
 */
export class ConversationEntry {
    constructor({
        user_id,
        site,
        message_id,
        user_prompt,
        response,
        time_of_creation,
        conversation_id,
        embedding = null,
        summary = null,
        main_topics = null,
        participants = null
    }) {
        this.user_id = user_id;
        this.site = site;
        this.message_id = message_id;
        this.user_prompt = user_prompt;
        this.response = response;
        this.time_of_creation = time_of_creation;
        this.conversation_id = conversation_id;
        this.embedding = embedding;
        this.summary = summary;
        this.main_topics = main_topics;
        this.participants = participants;
    }
    
    toDict() {
        // Handle response field - convert Message objects to dicts if needed
        let responseData = this.response;
        if (Array.isArray(this.response) && this.response.length > 0 && this.response[0] instanceof Message) {
            responseData = this.response.map(msg => msg.toDict());
        }
        
        return {
            user_id: this.user_id,
            site: this.site,
            message_id: this.message_id,
            user_prompt: this.user_prompt,
            response: responseData,
            time_of_creation: this.time_of_creation,
            conversation_id: this.conversation_id,
            embedding: this.embedding,
            summary: this.summary,
            main_topics: this.main_topics,
            participants: this.participants
        };
    }
    
    toJSON() {
        // Handle response field - convert Message objects to dicts if needed
        let responseData = this.response;
        if (Array.isArray(this.response) && this.response.length > 0 && this.response[0] instanceof Message) {
            responseData = this.response.map(msg => msg.toDict());
        }
        
        return {
            id: this.conversation_id,
            user_prompt: this.user_prompt,
            response: responseData,
            time: this.time_of_creation
        };
    }
    
    static fromDict(data) {
        // Handle response field - convert dicts to Message objects if it's a list
        let response = data.response;
        if (Array.isArray(response) && response.length > 0 && typeof response[0] === 'object') {
            try {
                response = response.map(msg => Message.fromDict(msg));
            } catch (e) {
                // If conversion fails, keep as is
            }
        }
        
        return new ConversationEntry({
            user_id: data.user_id,
            site: data.site,
            message_id: data.message_id,
            user_prompt: data.user_prompt,
            response: response,
            time_of_creation: data.time_of_creation,
            conversation_id: data.conversation_id,
            embedding: data.embedding,
            summary: data.summary,
            main_topics: data.main_topics,
            participants: data.participants
        });
    }
}

// Convenience functions for creating common message types

/**
 * Create a user message with UserQuery content
 */
export function createUserMessage(query, site = null, mode = null, senderInfo = null, conversationId = null) {
    const userQuery = new UserQuery(query, site, mode);
    return new Message({
        sender_type: SenderType.USER,
        message_type: MessageType.QUERY,
        content: userQuery,
        conversation_id: conversationId,
        sender_info: senderInfo
    });
}

/**
 * Create an assistant message with search results
 */
export function createAssistantResult(results, conversationId = null, metadata = null) {
    return new Message({
        sender_type: SenderType.ASSISTANT,
        message_type: MessageType.RESULT,
        content: results,
        conversation_id: conversationId,
        metadata: metadata
    });
}

/**
 * Create an assistant message with generated answer
 */
export function createAssistantAnswer(answer, items = null, conversationId = null) {
    const content = { answer: answer, "@type": "GeneratedAnswer" };
    if (items) {
        content.items = items;
    }
    
    return new Message({
        sender_type: SenderType.ASSISTANT,
        message_type: MessageType.NLWS,
        content: content,
        conversation_id: conversationId
    });
}

/**
 * Create a status/intermediate message
 */
export function createStatusMessage(statusText, senderType = SenderType.SYSTEM, conversationId = null) {
    return new Message({
        sender_type: senderType,
        message_type: MessageType.INTERMEDIATE,
        content: statusText,
        conversation_id: conversationId
    });
}

/**
 * Create an error message
 */
export function createErrorMessage(errorText, metadata = null, conversationId = null) {
    return new Message({
        sender_type: SenderType.SYSTEM,
        message_type: MessageType.ERROR,
        content: errorText,
        conversation_id: conversationId,
        metadata: metadata
    });
}

/**
 * Create a completion message
 */
export function createCompleteMessage(conversationId = null, senderInfo = null) {
    return new Message({
        sender_type: SenderType.SYSTEM,
        message_type: MessageType.COMPLETE,
        content: "",
        conversation_id: conversationId,
        sender_info: senderInfo || { id: "system", name: "NLWeb" }
    });
}

/**
 * Create a message in the legacy format for backward compatibility
 */
export function createLegacyMessage(messageType, content, conversationId = null, senderInfo = null) {
    const message = {
        message_type: messageType,
        content: content
    };
    
    if (conversationId) {
        message.conversation_id = conversationId;
    }
    if (senderInfo) {
        message.sender_info = senderInfo;
    }
    
    return message;
}