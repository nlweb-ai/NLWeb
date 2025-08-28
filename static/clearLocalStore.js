/**
 * Utility functions to clear localStorage for NLWeb application
 * 
 * Usage: Copy and paste the desired function into the browser console
 */

// Function to clear all NLWeb-related localStorage items
function clearNLWebData() {
    const nlwebKeys = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.includes('nlweb') || key.includes('conv') || key === 'authToken' || key === 'userInfo')) {
            nlwebKeys.push(key);
        }
    }

    // Remove all found keys
    nlwebKeys.forEach(key => {
        localStorage.removeItem(key);
    });

}

// Function to clear only conversation data
function clearConversationData() {
    // Get the domain-specific storage key
    const baseDomain = window.location.host;
    const conversationKeys = [
        `nlweb_messages_${baseDomain}`,  // Domain-specific messages
        'nlweb_messages',  // Legacy key for backwards compatibility
        'nlweb-remembered-items',
        'current-conversation-id'
    ];
    
    conversationKeys.forEach(key => {
        if (localStorage.getItem(key)) {
            localStorage.removeItem(key);
        }
    });
    
}

// Function to clear all localStorage (use with caution!)
function clearAllLocalStorage() {
    const itemCount = localStorage.length;
    localStorage.clear();
}

// Function to list all localStorage keys
function listLocalStorageKeys() {
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        const value = localStorage.getItem(key);
    }
}

// Auto-execute message
