/**
 * IndexedDB Storage Manager for NLWeb Conversations
 * Provides async storage with no size limits
 */

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

        // Create conversations store
        if (!db.objectStoreNames.contains('conversations')) {
          const convStore = db.createObjectStore('conversations', { keyPath: 'id' });
          convStore.createIndex('timestamp', 'timestamp', { unique: false });
          convStore.createIndex('site', 'site', { unique: false });
        }

        // Create messages store
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
   * Save a conversation
   */
  async saveConversation(conversation) {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['conversations'], 'readwrite');
      const store = transaction.objectStore('conversations');
      const request = store.put(conversation);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Get all conversations
   */
  async getAllConversations() {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['conversations'], 'readonly');
      const store = transaction.objectStore('conversations');
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Get a specific conversation
   */
  async getConversation(conversationId) {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['conversations'], 'readonly');
      const store = transaction.objectStore('conversations');
      const request = store.get(conversationId);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Delete a conversation
   */
  async deleteConversation(conversationId) {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['conversations', 'messages'], 'readwrite');
      
      // Delete conversation
      const convStore = transaction.objectStore('conversations');
      convStore.delete(conversationId);

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
      const request = store.put(message);

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
        store.put(message);
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
        const messages = request.result || [];
        // Sort by timestamp
        messages.sort((a, b) => a.timestamp - b.timestamp);
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
        const messages = request.result || [];
        // Sort by timestamp
        messages.sort((a, b) => a.timestamp - b.timestamp);
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
    return this.saveMessage(message); // put() will update if exists
  }

  /**
   * Clear all data
   */
  async clearAll() {
    const db = await this.ensureDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['conversations', 'messages'], 'readwrite');
      
      transaction.objectStore('conversations').clear();
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

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = indexedStorage;
}