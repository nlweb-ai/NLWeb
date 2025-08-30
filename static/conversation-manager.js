class ConversationManager {
  /**
   * Field Name Standardization for Timestamps:
   * 
   * We use 'created_at' as the standard field name on the client side for consistency.
   * However, the server may send either:
   * - 'created_at' (from Conversation model)
   * - 'time_of_creation' (from ConversationEntry model)
   * 
   * We handle both field names for backwards compatibility and to support different
   * server data models. When processing server data, we always check for both names
   * and normalize to 'created_at' in our client-side conversation objects.
   */
  constructor() {
    this.conversations = [];
    this.storage = indexedStorage; // Use IndexedDB storage
  }
  
  

  async loadConversations(selectedSite, elements) {
    // Load conversations from IndexedDB
    // Server is only contacted when joining via share link
    // Note: selectedSite parameter is kept for backward compatibility but not used
    // All conversations are shown regardless of selected site
    await this.loadLocalConversations();
  }

  async loadLocalConversations() {
    this.conversations = [];
    
    try {
      // Load all messages from IndexedDB
      const allMessages = await this.storage.getAllMessages();
        
        // Group messages by conversation_id to reconstruct conversations
        const conversationMap = {};
        
        allMessages.forEach(msg => {
          const convId = msg.conversation_id;
          if (!convId) return;
          
          if (!conversationMap[convId]) {
            conversationMap[convId] = {
              id: convId,
              messages: [],
              timestamp: msg.timestamp,
              site: msg.site || 'all',
              mode: msg.mode || 'list',
              title: 'New chat'
            };
          }
          
          // Add message to conversation and mark it as already saved
          msg.db_saved = true; // Mark as saved since it came from the database
          conversationMap[convId].messages.push(msg);
          
          // Update conversation metadata only from user messages
          // Assistant messages should not change the conversation's site or mode
          if (msg.message_type === 'user') {
            if (msg.site && conversationMap[convId].site === 'all') {
              conversationMap[convId].site = msg.site;
            }
            if (msg.mode && conversationMap[convId].mode === 'list') {
              conversationMap[convId].mode = msg.mode;
            }
          }
          
          // Set title from first user message
          if (msg.message_type === 'user' && conversationMap[convId].title === 'New chat') {
            const content = typeof msg.content === 'string' ? msg.content : msg.content?.content || 'New chat';
            conversationMap[convId].title = content.substring(0, 50);
          }
          
          // Update timestamp to be the latest message
          if (msg.timestamp > conversationMap[convId].timestamp) {
            conversationMap[convId].timestamp = msg.timestamp;
          }
        });
        
        // Convert map to array
        let conversations = Object.values(conversationMap);
        
        // Don't filter by site - show all conversations regardless of selected site
        // The selected site only affects new queries, not which conversations are shown
        
        // Sort messages within each conversation by timestamp
        conversations.forEach(conv => {
          conv.messages.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
        });
        
        // Sort conversations by timestamp (most recent first)
        conversations.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
        
        this.conversations = conversations;
    } catch (e) {
      console.error('Error loading conversations from IndexedDB:', e);
      this.conversations = [];
    }
  }



  async saveConversations() {
    try {
      // Save each conversation and its messages to IndexedDB
      for (const conv of this.conversations) {
        // Skip conversation history searches
        if (conv.site === 'conv_history') {
          continue;
        }
        
        // Save conversation metadata
        await this.storage.saveConversation({
          id: conv.id,
          title: conv.title,
          site: conv.site || 'all',
          mode: conv.mode || 'list',
          timestamp: conv.timestamp,
          created_at: conv.created_at || conv.timestamp
        });
        
        // Save messages - only save new messages that haven't been persisted yet
        if (conv.messages && conv.messages.length > 0) {
          const messagesToSave = [];
          
          for (const msg of conv.messages) {
            // Skip messages that are already saved (they have a db_saved flag)
            if (msg.db_saved) {
              continue;
            }
            
            // Ensure each message has required fields
            if (!msg.conversation_id) {
              msg.conversation_id = conv.id;
            }
            
            // Use the message_id from the server - no generation needed
            if (!msg.message_id) {
              console.warn('Message missing message_id from server:', msg);
              // Fallback to a simple ID if server didn't provide one
              msg.message_id = `${conv.id}_${msg.timestamp || Date.now()}`;
            }
            
            messagesToSave.push(msg);
            
            // Mark the original message as saved
            msg.db_saved = true;
          }
          
          // Only save if there are new messages
          if (messagesToSave.length > 0) {
            await this.storage.saveMessages(messagesToSave);
          }
        }
      }
    } catch (e) {
      console.error('Error saving conversations to IndexedDB:', e);
    }
  }

  async getConversationWithMessages(id) {
    // Guard against undefined or invalid IDs
    if (!id) {
      return null;
    }
    
    const conversation = this.conversations.find(c => c.id === id);
    if (!conversation) {
      return null;
    }
    
    // Load messages from IndexedDB if not already loaded
    if (!conversation.messages || conversation.messages.length === 0) {
      try {
        conversation.messages = await this.storage.getMessages(id);
      } catch (e) {
        console.error('Error loading messages from IndexedDB:', e);
        conversation.messages = [];
      }
    }
    
    return conversation;
  }
  
  async loadConversation(id, chatInterface) {
    const conversation = await this.getConversationWithMessages(id);
    if (!conversation) {
      return;
    }
    
    // Delegate to chat interface's own loadConversation if it has one
    if (chatInterface.loadConversation) {
      await chatInterface.loadConversation(id);
      return;
    }
    
    // Otherwise handle basic loading
    chatInterface.currentConversationId = id;
    
    // Check if this is a server conversation (starts with conv_) or local
    if (id.startsWith('conv_')) {
      // This is a server conversation, we can reconnect to it
      chatInterface.wsConversationId = id;
    } else {
      // This is a local conversation, we'll need to create it on server when sending first message
      chatInterface.wsConversationId = null;
    }
    
    // Restore the site selection for this conversation
    if (conversation.site) {
      // Check if using state object (UnifiedChatInterface) or direct property
      if (chatInterface.state) {
        chatInterface.state.selectedSite = conversation.site;
      } else {
        chatInterface.selectedSite = conversation.site;
      }
      // Update the UI to reflect the site
      const siteInfo = document.getElementById('chat-site-info');
      if (siteInfo) {
        siteInfo.textContent = `Asking ${conversation.site}`;
      }
      // Update site selector icon if it exists
      if (chatInterface.siteSelectorIcon) {
        chatInterface.siteSelectorIcon.title = `Site: ${conversation.site}`;
      }
    }
    
    // Restore the mode selection for this conversation
    if (conversation.mode) {
      // Check if using state object (UnifiedChatInterface) or direct property
      if (chatInterface.state) {
        chatInterface.state.selectedMode = conversation.mode;
      } else {
        chatInterface.selectedMode = conversation.mode;
      }
      // Update mode selector UI if it exists
      const modeSelectorIcon = document.getElementById('mode-selector-icon');
      if (modeSelectorIcon) {
        modeSelectorIcon.title = `Mode: ${conversation.mode.charAt(0).toUpperCase() + conversation.mode.slice(1)}`;
      }
      // Update selected state in dropdown
      const modeDropdown = document.getElementById('mode-dropdown');
      if (modeDropdown) {
        const modeItems = modeDropdown.querySelectorAll('.mode-dropdown-item');
        modeItems.forEach(item => {
          if (item.getAttribute('data-mode') === conversation.mode) {
            item.classList.add('selected');
          } else {
            item.classList.remove('selected');
          }
        });
      }
    }
    
    // Clear messages
    chatInterface.elements.messagesContainer.innerHTML = '';
    
    // Rebuild context arrays from conversation history
    chatInterface.prevQueries = conversation.messages
      .filter(m => m.message_type === 'user')
      .slice(-10)
      .map(m => m.content);
    
    chatInterface.lastAnswers = [];
    const assistantMessages = conversation.messages.filter(m => m.message_type === 'assistant');
    if (assistantMessages.length > 0) {
      // Extract answers from assistant messages
      assistantMessages.slice(-20).forEach(msg => {
        if (msg.parsedAnswers && msg.parsedAnswers.length > 0) {
          chatInterface.lastAnswers.push(...msg.parsedAnswers);
        }
      });
      // Keep only last 20 answers
      chatInterface.lastAnswers = chatInterface.lastAnswers.slice(-20);
    }
    
    // Clear messages container first
    chatInterface.elements.messagesContainer.innerHTML = '';
    
    // Sort messages by timestamp
    const sortedMessages = [...conversation.messages].sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
    
    // Replay all messages in timestamp order
    sortedMessages.forEach((msg) => {
      if (!msg.content) {
        return;
      }
      
      // Check if content is an object (new format) or string (legacy)
      if (typeof msg.content === 'object') {
        // This is a server-format message, replay through handler
        chatInterface.handleStreamData(msg.content);
      } else {
        // Legacy format - try to handle
        try {
          // Try to construct a message object from legacy format
          const messageObj = {
            message_type: msg.message_type,
            content: msg.content,
            timestamp: msg.timestamp
          };
          chatInterface.handleStreamData(messageObj);
        } catch {
          // Failed to handle legacy message
        }
      }
    });
    
    // Update title
    chatInterface.elements.chatTitle.textContent = conversation.title || 'Chat';
    
    // Update conversations list to show current selection
    chatInterface.updateConversationsList();
    
    // Hide centered input and show regular chat input
    chatInterface.hideCenteredInput();
    
    // Connect to WebSocket for server conversations
    if (id.startsWith('conv_') && chatInterface.connectWebSocket) {
      // This is a server conversation, connect to it
      chatInterface.connectWebSocket(id).then(() => {
      }).catch(() => {
        // Reset wsConversationId if connection fails
        chatInterface.wsConversationId = null;
      });
    }
    
    // Scroll to bottom
    setTimeout(() => {
      chatInterface.scrollToBottom();
    }, 100);
  }

  async deleteConversation(conversationId, chatInterface) {
    try {
      // Delete from IndexedDB
      await this.storage.deleteConversation(conversationId);
      
      // Remove from conversations array
      this.conversations = this.conversations.filter(conv => conv.id !== conversationId);
    } catch (e) {
      console.error('Error deleting conversation from IndexedDB:', e);
    }
    
    // If this is a server conversation (starts with conv_), also delete from server
    if (conversationId && conversationId.startsWith('conv_')) {
      try {
        // Get user ID if available
        const userInfo = localStorage.getItem('userInfo');
        let userId = null;
        if (userInfo) {
          try {
            const parsed = JSON.parse(userInfo);
            userId = parsed.id || parsed.user_id;
          } catch (e) {
            console.error('Error parsing userInfo:', e);
          }
        }
        
        // Call server API to delete conversation
        const params = new URLSearchParams({
          conversation_id: conversationId
        });
        if (userId) {
          params.append('user_id', userId);
        }
        
        const response = await fetch(`/api/conversation/delete?${params}`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json'
          }
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          console.error('Failed to delete conversation from server:', errorData);
          // Continue with local deletion even if server fails
        } else {
          console.log(`Conversation ${conversationId} deleted from server`);
        }
      } catch (error) {
        console.error('Error deleting conversation from server:', error);
        // Continue with local deletion even if server fails
      }
    }
    
    // Update UI
    chatInterface.updateConversationsList();
    
    // If we deleted the current conversation, create a new one
    if (conversationId === chatInterface.currentConversationId) {
      chatInterface.createNewChat();
    }
  }

  updateConversationsList(chatInterface, container = null) {
    // Use provided container or try to find the conversations list element
    const targetContainer = container || document.getElementById('conversations-list');
    
    if (!targetContainer) {
      return;
    }
    
    targetContainer.innerHTML = '';
    
    // Filter conversations
    const conversationsWithContent = this.conversations.filter(conv => {
      // Must have an ID
      if (!conv.id) {
        return false;
      }
      // For server conversations (conv_*), show them even without messages
      if (conv.id.startsWith('conv_')) {
        return true;
      }
      // For local conversations, must have messages
      const hasMessages = conv.messages && conv.messages.length > 0;
      if (!hasMessages) {
      }
      return hasMessages;
    });
    
    
    // Group conversations by site
    const conversationsBySite = {};
    conversationsWithContent.forEach(conv => {
      const site = conv.site || 'all';
      if (!conversationsBySite[site]) {
        conversationsBySite[site] = [];
      }
      conversationsBySite[site].push(conv);
    });
    
    // Sort sites alphabetically, but keep 'all' at the top
    const sites = Object.keys(conversationsBySite).sort((a, b) => {
      if (a === 'all') return -1;
      if (b === 'all') return 1;
      return a.toLowerCase().localeCompare(b.toLowerCase());
    });
    
    // Create UI for each site group
    sites.forEach(site => {
      const conversations = conversationsBySite[site];
      
      // Create site group wrapper
      const siteGroup = document.createElement('div');
      siteGroup.className = 'site-group';
      
      // Create site header
      const siteHeader = document.createElement('div');
      siteHeader.className = 'site-group-header';
      
      // Add site name (cleaned up for display)
      const siteName = document.createElement('span');
      siteName.textContent = this.cleanSiteName(site);
      siteHeader.appendChild(siteName);
      
      // Add chevron icon
      const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      chevron.setAttribute('class', 'chevron');
      chevron.setAttribute('viewBox', '0 0 24 24');
      chevron.setAttribute('fill', 'none');
      chevron.setAttribute('stroke', 'currentColor');
      chevron.setAttribute('stroke-width', '2');
      chevron.innerHTML = '<polyline points="6 9 12 15 18 9"></polyline>';
      siteHeader.appendChild(chevron);
      
      siteGroup.appendChild(siteHeader);
      
      // Create conversations container for this site
      const conversationsContainer = document.createElement('div');
      conversationsContainer.className = 'site-conversations';
      
      // Sort conversations by timestamp (most recent first)
      conversations.sort((a, b) => b.timestamp - a.timestamp);
      
      conversations.forEach(conv => {
        const convItem = document.createElement('div');
        convItem.className = 'conversation-item';
        convItem.dataset.conversationId = conv.id;  // Add the data attribute for the click handler
        if (conv.id === chatInterface.currentConversationId) {
          convItem.classList.add('active');
        }
        
        // Delete button (now on the left)
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'conversation-delete';
        deleteBtn.innerHTML = '×';
        deleteBtn.title = 'Delete conversation';
        deleteBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.deleteConversation(conv.id, chatInterface);
        });
        convItem.appendChild(deleteBtn);
        
        // Create conversation content container
        const convContent = document.createElement('div');
        convContent.className = 'conversation-content';
        
        // Title span
        const titleSpan = document.createElement('span');
        titleSpan.className = 'conversation-title';
        titleSpan.textContent = conv.title || 'Untitled';
        titleSpan.addEventListener('click', async () => {
          await this.loadConversation(conv.id, chatInterface);
        });
        convContent.appendChild(titleSpan);
        
        convItem.appendChild(convContent);
        
        conversationsContainer.appendChild(convItem);
      });
      
      siteGroup.appendChild(conversationsContainer);
      targetContainer.appendChild(siteGroup);
      
      // Add click handler to toggle conversations visibility
      siteHeader.addEventListener('click', () => {
        conversationsContainer.classList.toggle('collapsed');
        siteHeader.classList.toggle('collapsed');
      });
    });
  }

  // Helper method to clean up site names for display
  cleanSiteName(site) {
    if (!site) return site;
    
    // Remove common domain suffixes
    return site
      .replace(/\.myshopify\.com$/, '')
      .replace(/\.com$/, '')
      .replace(/\.org$/, '')
      .replace(/\.net$/, '')
      .replace(/\.io$/, '')
      .replace(/\.co$/, '');
  }
  
  // Helper method to get conversations
  getConversations() {
    return this.conversations;
  }

  // Helper method to find a conversation by ID
  findConversation(id) {
    return this.conversations.find(c => c.id === id);
  }

  // Helper method to add a conversation
  addConversation(conversation) {
    this.conversations.unshift(conversation);
  }

  // Helper method to update a conversation
  updateConversation(id, updates) {
    const conversation = this.findConversation(id);
    if (conversation) {
      Object.assign(conversation, updates);
    }
  }

  // Add a message to storage
  async addMessage(conversationId, message) {
    try {
      
      // Ensure message has required fields
      if (!message.conversation_id) {
        message.conversation_id = conversationId;
      }
      
      // Use the message_id from the server - no generation needed
      if (!message.message_id) {
        console.warn('Message missing message_id from server in addMessage:', message);
      }
      
      // Don't save here - messages are saved in batch by saveConversations()
      // The message is added to the conversation's messages array by the caller
      
      // Update conversation metadata only (don't push to messages array - caller handles that)
      const conversation = this.findConversation(conversationId);
      if (conversation) {
        // Update conversation timestamp
        if (message.timestamp > conversation.timestamp) {
          conversation.timestamp = message.timestamp;
        }
        
        // Update title from first user message
        if (message.message_type === 'user' && conversation.title === 'New chat') {
          const content = typeof message.content === 'string' ? message.content : message.content?.content || 'New chat';
          conversation.title = content.substring(0, 50);
          
          // Save updated conversation metadata
          await this.storage.saveConversation({
            id: conversation.id,
            title: conversation.title,
            site: conversation.site || 'all',
            mode: conversation.mode || 'list',
            timestamp: conversation.timestamp,
            created_at: conversation.created_at || conversation.timestamp
          });
        }
      }
    } catch (e) {
      console.error('Error adding message to IndexedDB:', e);
    }
  }

  // Update a message in storage
  async updateMessage(messageId, updates) {
    try {
      // Get the message from IndexedDB
      const allMessages = await this.storage.getAllMessages();
      const message = allMessages.find(m => m.message_id === messageId);
      
      if (message) {
        // Update the message
        Object.assign(message, updates);
        await this.storage.updateMessage(message);
        
        // Update in-memory if conversation is loaded
        const conversation = this.findConversation(message.conversation_id);
        if (conversation && conversation.messages) {
          const memoryMsg = conversation.messages.find(m => m.message_id === messageId);
          if (memoryMsg) {
            Object.assign(memoryMsg, updates);
          }
        }
      }
    } catch (e) {
      console.error('Error updating message in IndexedDB:', e);
    }
  }

  // Delete a message from storage
  async deleteMessage(messageId, conversationId) {
    try {
      // Delete from IndexedDB
      await this.storage.deleteMessage(messageId);
      
      // Update in-memory conversation
      const conversation = this.findConversation(conversationId);
      if (conversation && conversation.messages) {
        conversation.messages = conversation.messages.filter(m => m.message_id !== messageId);
      }
    } catch (e) {
      console.error('Error deleting message from IndexedDB:', e);
    }
  }
}

// Export the class
export { ConversationManager };
