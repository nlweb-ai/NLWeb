/**
 * IndexedDB Storage Manager for NLWeb Conversations
 * Provides async storage with no size limits
 */

import { Message } from './schemas.js';

class IndexedStorage {
  constructor() {
    this.dbName = 'NLWebDB_v1';
    this.dbVersion = 2; // Increment version to force schema update
    this.db = null;
  }

  /**
   * Initialize and open the IndexedDB database
   */
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion);

      request.onerror = () => {
        console.error('Failed to open IndexedDB:', request.error);
        reject(request.error);
      };

      request.onsuccess = () => {
        this.db = request.result;
        console.log('IndexedDB initialized successfully');
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;

        // Create messages store only - conversations are reconstructed from messages
        if (!db.objectStoreNames.contains('messages')) {
          const msgStore = db.createObjectStore('messages', { keyPath: 'message_id' });
          msgStore.createIndex('conversation_id', 'conversation_id', { unique: false });
          msgStore.createIndex('timestamp', 'timestamp', { unique: false });
          msgStore.createIndex('message_type', 'message_type', { unique: false });
        }
      };
    });
  }

  /**
   * Ensure database is initialized
   */
  async ensureDB() {
    if (!this.db) {
      await this.init();
    }
    return this.db;
  }

  /**
   * Delete a conversation (removes all messages for this conversation)
   */
  async deleteConversation(conversationId) {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['messages'], 'readwrite');
      
      // Delete all messages for this conversation
      const msgStore = transaction.objectStore('messages');
      const index = msgStore.index('conversation_id');
      const request = index.openCursor(IDBKeyRange.only(conversationId));

      request.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor) {
          msgStore.delete(cursor.primaryKey);
          cursor.continue();
        }
      };

      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
  }

  /**
   * Save a message
   */
  async saveMessage(message) {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['messages'], 'readwrite');
      const store = transaction.objectStore('messages');
      
      // Convert Message object to plain object if needed
      const messageData = message instanceof Message ? message.toDict() : message;
      const request = store.put(messageData);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Save multiple messages
   */
  async saveMessages(messages) {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['messages'], 'readwrite');
      const store = transaction.objectStore('messages');
      
      messages.forEach(message => {
        // Convert Message object to plain object if needed
        const messageData = message instanceof Message ? message.toDict() : message;
        store.put(messageData);
      });

      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
  }

  /**
   * Get all messages for a conversation
   */
  async getMessages(conversationId) {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['messages'], 'readonly');
      const store = transaction.objectStore('messages');
      const index = store.index('conversation_id');
      const request = index.getAll(conversationId);

      request.onsuccess = () => {
        const rawMessages = request.result || [];
        // Convert to Message objects and sort by timestamp
        const messages = rawMessages.map(data => Message.fromDict(data));
        messages.sort((a, b) => {
          const timeA = new Date(a.timestamp).getTime();
          const timeB = new Date(b.timestamp).getTime();
          return timeA - timeB;
        });
        resolve(messages);
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Get all messages (for building conversation list)
   */
  async getAllMessages() {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['messages'], 'readonly');
      const store = transaction.objectStore('messages');
      const request = store.getAll();

      request.onsuccess = () => {
        const rawMessages = request.result || [];
        // Convert to Message objects and sort by timestamp
        const messages = rawMessages.map(data => Message.fromDict(data));
        messages.sort((a, b) => {
          const timeA = new Date(a.timestamp).getTime();
          const timeB = new Date(b.timestamp).getTime();
          return timeA - timeB;
        });
        resolve(messages);
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Delete a specific message
   */
  async deleteMessage(messageId) {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['messages'], 'readwrite');
      const store = transaction.objectStore('messages');
      const request = store.delete(messageId);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Update a message
   */
  async updateMessage(message) {
    // Accepts either Message object or plain object
    return this.saveMessage(message); // put() will update if exists
  }

  /**
   * Clear all data
   */
  async clearAll() {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['messages'], 'readwrite');
      
      transaction.objectStore('messages').clear();

      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
  }

  /**
   * Get database size info
   */
  async getStorageInfo() {
    if (navigator.storage && navigator.storage.estimate) {
      const estimate = await navigator.storage.estimate();
      return {
        usage: estimate.usage,
        quota: estimate.quota,
        percentage: (estimate.usage / estimate.quota) * 100
      };
    }
    return null;
  }
}

// Create singleton instance
const indexedStorage = new IndexedStorage();

// Export for use in modules
export { indexedStorage, IndexedStorage };

// Also expose globally for backward compatibility
window.indexedStorage = indexedStorage;
window.IndexedStorage = IndexedStorage;

// Debug function for console - dump all data
window.dumpIndexedDB = async function() {
  try {
    const messages = await indexedStorage.getAllMessages();
    
    console.log('=== INDEXEDDB DUMP ===');
    console.log(`Total: ${messages.length} messages\n`);
    
    console.log('\n=== MESSAGES BY CONVERSATION ===');
    const messagesByConv = {};
    messages.forEach(msg => {
      if (!messagesByConv[msg.conversation_id]) {
        messagesByConv[msg.conversation_id] = [];
      }
      messagesByConv[msg.conversation_id].push(msg);
    });
    
    Object.keys(messagesByConv).forEach(convId => {
      const convMessages = messagesByConv[convId];
      console.log(`\nConversation ${convId}: ${convMessages.length} messages`);
      convMessages.sort((a, b) => a.timestamp - b.timestamp);
      convMessages.forEach((msg, i) => {
        if (msg.message_type === 'user') {
          console.log(`  [${i}] USER: ${msg.content}`);
        } else if (msg.message_type === 'result') {
          const items = msg.content ? msg.content.length : 0;
          console.log(`  [${i}] RESULT: ${items} items`);
          if (msg.content) {
            msg.content.forEach((item, j) => {
              console.log(`      ${j}: ${item.url || item.name || 'NO URL/NAME'}`);
            });
          }
        } else {
          console.log(`  [${i}] ${msg.message_type.toUpperCase()}: ${msg.content || ''}`);
        }
      });
    });
    
    return { conversations, messages };
  } catch (e) {
    console.error('Error dumping IndexedDB:', e);
  }
};

// Shorthand version - just show counts
window.dbStats = async function() {
  const messages = await indexedStorage.getAllMessages();
  console.log(`IndexedDB: ${messages.length} messages`);
  
  // Group messages by type
  const messageTypes = {};
  messages.forEach(m => {
    messageTypes[m.message_type] = (messageTypes[m.message_type] || 0) + 1;
  });
  console.log('Message types:', messageTypes);
};

// Export default for ES6 modules
export default indexedStorage;