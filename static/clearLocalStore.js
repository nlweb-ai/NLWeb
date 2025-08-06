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
        console.log('Removing:', key);
        localStorage.removeItem(key);
    });

    console.log('Cleared', nlwebKeys.length, 'NLWeb-related items from localStorage');
}

// Function to clear only conversation data
function clearConversationData() {
    const conversationKeys = [
        'nlweb_conversations',
        'nlweb-remembered-items',
        'current-conversation-id'
    ];
    
    conversationKeys.forEach(key => {
        if (localStorage.getItem(key)) {
            console.log('Removing:', key);
            localStorage.removeItem(key);
        }
    });
    
    console.log('Cleared conversation data from localStorage');
}

// Function to clear all localStorage (use with caution!)
function clearAllLocalStorage() {
    const itemCount = localStorage.length;
    localStorage.clear();
    console.log('Cleared all localStorage (' + itemCount + ' items)');
}

// Function to list all localStorage keys
function listLocalStorageKeys() {
    console.log('Current localStorage keys:');
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        const value = localStorage.getItem(key);
        console.log(`  ${key}: ${value ? value.substring(0, 50) + '...' : 'null'}`);
    }
}

// Auto-execute message
console.log('localStorage clearing functions loaded. Available functions:');
console.log('  clearNLWebData() - Clear all NLWeb-related data');
console.log('  clearConversationData() - Clear only conversation data');
console.log('  clearAllLocalStorage() - Clear ALL localStorage (use with caution!)');
console.log('  listLocalStorageKeys() - List all current localStorage keys');