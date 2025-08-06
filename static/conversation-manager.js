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
  }

  async loadConversations(selectedSite, elements) {
    // Always load conversations from localStorage
    // Server is only contacted when joining via share link
    this.loadLocalConversations(selectedSite);
  }

  loadLocalConversations(selectedSite) {
    const saved = localStorage.getItem('nlweb_conversations');
    if (saved) {
      try {
        const allConversations = JSON.parse(saved);
        
        // Filter out empty conversations
        let filteredConversations = allConversations.filter(conv => conv.messages && conv.messages.length > 0);
        
        // If a specific site is selected, filter by site
        if (selectedSite && selectedSite !== 'all') {
          filteredConversations = filteredConversations.filter(conv => 
            conv.site === selectedSite || 
            (conv.siteInfo && conv.siteInfo.site === selectedSite)
          );
        }
        
        this.conversations = filteredConversations;
        // Save the cleaned list back
        this.saveConversations();
      } catch (e) {
        console.error('Error loading conversations:', e);
        this.conversations = [];
      }
    } else {
      this.conversations = [];
    }
  }

  convertServerConversations(serverConversations) {
    // Convert server format to local format
    // Server returns array of conversation objects with conversation_id
    const convertedConversations = [];
    
    serverConversations.forEach(conv => {
      // Skip if no conversation_id
      if (!conv.conversation_id) {
        return;
      }
      
      const converted = {
        id: conv.conversation_id,
        title: conv.title || 'Untitled Chat',
        timestamp: new Date(conv.last_message_at || conv.created_at).getTime(),
        created_at: conv.created_at,
        site: 'all', // Default site
        siteInfo: {
          site: 'all',
          mode: 'list'
        },
        messages: [], // Messages will be loaded separately
        participant_count: conv.participant_count || 0
      };
      
      convertedConversations.push(converted);
    });
    
    // Sort by timestamp (most recent first)
    return convertedConversations.sort((a, b) => b.timestamp - a.timestamp);
  }

  mergeLocalConversations(selectedSite) {
    // Check if there are any conversations in localStorage that aren't on the server
    const saved = localStorage.getItem('nlweb_conversations');
    if (saved) {
      try {
        const localConversations = JSON.parse(saved);
        const serverIds = new Set(this.conversations.map(c => c.id));
        
        // Add any local conversations that aren't on the server
        localConversations.forEach(localConv => {
          if (!serverIds.has(localConv.id) && localConv.messages && localConv.messages.length > 0) {
            // Check site filter
            const convSite = localConv.site || (localConv.siteInfo && localConv.siteInfo.site) || 'all';
            if (selectedSite === 'all' || convSite === selectedSite) {
              this.conversations.push(localConv);
            }
          }
        });
        
        // Sort by timestamp
        this.conversations.sort((a, b) => b.timestamp - a.timestamp);
      } catch (e) {
        console.error('Error merging local conversations:', e);
      }
    }
  }

  async migrateLocalConversations() {
    // Migrate local conversations to server when user logs in
    const saved = localStorage.getItem('nlweb_conversations');
    if (!saved) return;
    
    try {
      const localConversations = JSON.parse(saved);
      if (!localConversations || localConversations.length === 0) return;
      
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
      const authToken = localStorage.getItem('authToken');
      const userId = userInfo.id || userInfo.email;
      
      if (!userId || !authToken) return;
      
      // Convert local conversations to server format
      const conversationsToMigrate = [];
      
      localConversations.forEach(conv => {
        if (!conv.messages || conv.messages.length === 0) return;
        
        // Convert to server format - extract user/assistant message pairs
        for (let i = 0; i < conv.messages.length - 1; i += 2) {
          const userMsg = conv.messages[i];
          const assistantMsg = conv.messages[i + 1];
          
          if (userMsg.message_type === 'user' && assistantMsg && assistantMsg.message_type === 'assistant') {
            conversationsToMigrate.push({
              thread_id: conv.id,
              user_id: userId,
              user_prompt: userMsg.content,
              response: assistantMsg.content,
              timestamp: new Date(userMsg.timestamp || Date.now()).toISOString(),
              time_of_creation: conv.created_at || new Date(userMsg.timestamp || Date.now()).toISOString(),
              site: conv.site || 'all'
            });
          }
        }
      });
      
      if (conversationsToMigrate.length === 0) return;
      
      
      // Send to server
      const baseUrl = window.location.origin === 'file://' ? 'http://localhost:8000' : '';
      const response = await fetch(`${baseUrl}/api/conversations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          conversations: conversationsToMigrate
        })
      });
      
      if (response.ok) {
        // Don't clear local storage - we want to keep local copies
        // localStorage.removeItem('nlweb_conversations');
      } else {
        console.error('Failed to migrate conversations:', response.status);
      }
    } catch (error) {
      console.error('Error migrating conversations:', error);
    }
  }

  saveConversations() {
    // Always save conversations locally, regardless of login status
    // Only save conversations that have messages
    const conversationsToSave = this.conversations.filter(conv => conv.messages && conv.messages.length > 0);
    localStorage.setItem('nlweb_conversations', JSON.stringify(conversationsToSave));
  }

  loadConversation(id, chatInterface) {
    // Guard against undefined or invalid IDs
    if (!id) {
      console.error('loadConversation called with undefined ID');
      return;
    }
    
    const conversation = this.conversations.find(c => c.id === id);
    if (!conversation) return;
    
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
      chatInterface.selectedSite = conversation.site;
      // Update the UI to reflect the site
      if (chatInterface.elements.chatSiteInfo) {
        chatInterface.elements.chatSiteInfo.textContent = `Asking ${conversation.site}`;
      }
      // Update site selector icon if it exists
      if (chatInterface.siteSelectorIcon) {
        chatInterface.siteSelectorIcon.title = `Site: ${conversation.site}`;
      }
    }
    
    // Restore the mode selection for this conversation
    if (conversation.mode) {
      chatInterface.selectedMode = conversation.mode;
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
    
    // Restore messages to UI
    conversation.messages.forEach(msg => {
      // Create sender info based on message type and any stored metadata
      let senderInfo = null;
      if (msg.senderInfo) {
        // Use stored sender info if available
        senderInfo = msg.senderInfo;
      } else if (msg.message_type === 'user') {
        // For user messages, try to get from current user info or use default
        const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
        senderInfo = {
          id: userInfo.id || 'user',
          name: userInfo.name || userInfo.email || 'User'
        };
      } else if (msg.message_type === 'assistant') {
        // For assistant messages, include site if available
        const site = msg.site || conversation.site || chatInterface.selectedSite || 'all';
        senderInfo = {
          id: 'nlweb_assistant',
          name: `NLWeb ${site}`
        };
      }
      
      // For assistant messages, check if content contains HTML
      if (msg.message_type === 'assistant' && msg.content && 
          (msg.content.includes('<') || msg.content.includes('class='))) {
        // Content has HTML, pass it as an object with html property
        chatInterface.addMessageToUI({ html: msg.content }, msg.message_type, false, senderInfo);
      } else {
        // Plain text content
        chatInterface.addMessageToUI(msg.content, msg.message_type, false, senderInfo);
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
      }).catch(error => {
        console.error('Failed to connect WebSocket:', error);
        // Reset wsConversationId if connection fails
        chatInterface.wsConversationId = null;
      });
    }
    
    // Scroll to bottom
    setTimeout(() => {
      chatInterface.scrollToBottom();
    }, 100);
  }

  deleteConversation(conversationId, chatInterface) {
    // Remove from conversations array
    this.conversations = this.conversations.filter(conv => conv.id !== conversationId);
    
    // Save updated list
    this.saveConversations();
    
    // Update UI
    chatInterface.updateConversationsList();
    
    // If we deleted the current conversation, create a new one
    if (conversationId === chatInterface.currentConversationId) {
      chatInterface.createNewChat();
    }
  }

  updateConversationsList(chatInterface, container = null) {
    // Use provided container or default to the sidebar conversations list
    const targetContainer = container || chatInterface.elements.conversationsList;
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
      
      // Create site header
      const siteHeader = document.createElement('div');
      siteHeader.className = 'site-group-header';
      
      // Add site name
      const siteName = document.createElement('span');
      siteName.textContent = site;
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
      
      targetContainer.appendChild(siteHeader);
      
      // Create conversations container for this site
      const conversationsContainer = document.createElement('div');
      conversationsContainer.className = 'conversations-container';
      
      // Sort conversations by timestamp (most recent first)
      conversations.sort((a, b) => b.timestamp - a.timestamp);
      
      conversations.forEach(conv => {
        const convItem = document.createElement('div');
        convItem.className = 'conversation-item';
        convItem.dataset.conversationId = conv.id;  // Add the data attribute for the click handler
        if (conv.id === chatInterface.currentConversationId) {
          convItem.classList.add('active');
        }
        
        // Create conversation content container
        const convContent = document.createElement('div');
        convContent.className = 'conversation-content';
        
        // Title span
        const titleSpan = document.createElement('span');
        titleSpan.className = 'conversation-title';
        titleSpan.textContent = conv.title || 'Untitled';
        titleSpan.addEventListener('click', () => chatInterface.loadConversation(conv.id));
        convContent.appendChild(titleSpan);
        
        convItem.appendChild(convContent);
        
        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'conversation-delete';
        deleteBtn.innerHTML = '×';
        deleteBtn.title = 'Delete conversation';
        deleteBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.deleteConversation(conv.id, chatInterface);
        });
        convItem.appendChild(deleteBtn);
        
        conversationsContainer.appendChild(convItem);
      });
      
      targetContainer.appendChild(conversationsContainer);
      
      // Add click handler to toggle conversations visibility
      siteHeader.addEventListener('click', () => {
        conversationsContainer.style.display = 
          conversationsContainer.style.display === 'none' ? 'block' : 'none';
        chevron.style.transform = 
          conversationsContainer.style.display === 'none' ? 'rotate(-90deg)' : '';
      });
    });
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
}

// Export the class
export { ConversationManager };