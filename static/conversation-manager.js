class ConversationManager {
  constructor() {
    this.conversations = [];
  }

  async loadConversations(selectedSite, elements) {
    console.log('ConversationManager: Loading conversations for site:', selectedSite);
    
    // Check if user is logged in
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
    const authToken = localStorage.getItem('authToken');
    
    if (authToken && userInfo && (userInfo.id || userInfo.email)) {
      // User is logged in, load conversations from server
      try {
        const userId = userInfo.id || userInfo.email;
        const site = selectedSite;
        const baseUrl = window.location.origin === 'file://' ? 'http://localhost:8000' : '';
        const url = `${baseUrl}/api/conversations?user_id=${encodeURIComponent(userId)}&site=${encodeURIComponent(site)}&limit=50`;
        
        const response = await fetch(url, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });
        
        if (response.ok) {
          const data = await response.json();
          
          // Convert server conversations to our format
          this.conversations = this.convertServerConversations(data.conversations);
          
          // Also check localStorage for any unsaved conversations
          this.mergeLocalConversations(selectedSite);
          
          console.log('Loaded', this.conversations.length, 'conversations from server');
        } else {
          console.error('Failed to load conversations from server:', response.status);
          // Fall back to localStorage
          this.loadLocalConversations(selectedSite);
        }
      } catch (error) {
        console.error('Error loading conversations from server:', error);
        // Fall back to localStorage
        this.loadLocalConversations(selectedSite);
      }
    } else {
      // User not logged in, use localStorage only
      this.loadLocalConversations(selectedSite);
    }
  }

  loadLocalConversations(selectedSite) {
    const saved = localStorage.getItem('nlweb-modern-conversations');
    if (saved) {
      try {
        const allConversations = JSON.parse(saved);
        console.log('ConversationManager: Found', allConversations.length, 'stored conversations');
        
        // Filter out empty conversations
        let filteredConversations = allConversations.filter(conv => conv.messages && conv.messages.length > 0);
        console.log('ConversationManager: After filtering empty conversations:', filteredConversations.length);
        
        // If a specific site is selected, filter by site
        if (selectedSite && selectedSite !== 'all') {
          filteredConversations = filteredConversations.filter(conv => 
            conv.site === selectedSite || 
            (conv.siteInfo && conv.siteInfo.site === selectedSite)
          );
          console.log('ConversationManager: After filtering by site', selectedSite, ':', filteredConversations.length);
        }
        
        this.conversations = filteredConversations;
        // Save the cleaned list back
        this.saveConversations();
      } catch (e) {
        console.error('Error loading conversations:', e);
        this.conversations = [];
      }
    } else {
      console.log('ConversationManager: No stored conversations found');
      this.conversations = [];
    }
  }

  convertServerConversations(serverConversations) {
    // Convert server format to local format
    // Server returns flat array of ConversationEntry objects
    const conversationMap = new Map();
    
    // Group conversations by thread_id
    serverConversations.forEach(entry => {
      const threadId = entry.thread_id;
      if (!conversationMap.has(threadId)) {
        conversationMap.set(threadId, {
          id: threadId,
          title: '',
          timestamp: 0,
          site: entry.site,
          siteInfo: {
            site: entry.site,
            mode: 'list'
          },
          messages: []
        });
      }
      
      const conversation = conversationMap.get(threadId);
      const timestamp = new Date(entry.timestamp).getTime();
      
      // Add user message
      conversation.messages.push({
        content: entry.user_prompt,
        type: 'user',
        timestamp: timestamp
      });
      
      // Add assistant message
      conversation.messages.push({
        content: entry.response,
        type: 'assistant',
        timestamp: timestamp + 1
      });
      
      // Update conversation timestamp to latest message
      if (timestamp > conversation.timestamp) {
        conversation.timestamp = timestamp;
      }
      
      // Set title from first user prompt if not set
      if (!conversation.title && entry.user_prompt) {
        conversation.title = entry.user_prompt.substring(0, 50) + 
                           (entry.user_prompt.length > 50 ? '...' : '');
      }
    });
    
    // Convert map to array and sort by timestamp
    const convertedConversations = Array.from(conversationMap.values());
    return convertedConversations.sort((a, b) => b.timestamp - a.timestamp);
  }

  mergeLocalConversations(selectedSite) {
    // Check if there are any conversations in localStorage that aren't on the server
    const saved = localStorage.getItem('nlweb-modern-conversations');
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
    const saved = localStorage.getItem('nlweb-modern-conversations');
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
          
          if (userMsg.type === 'user' && assistantMsg && assistantMsg.type === 'assistant') {
            conversationsToMigrate.push({
              thread_id: conv.id,
              user_id: userId,
              user_prompt: userMsg.content,
              response: assistantMsg.content,
              timestamp: new Date(userMsg.timestamp || Date.now()).toISOString(),
              site: conv.site || 'all'
            });
          }
        }
      });
      
      if (conversationsToMigrate.length === 0) return;
      
      console.log('Migrating', conversationsToMigrate.length, 'conversation entries to server');
      
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
        console.log('Successfully migrated conversations to server');
        // Clear local storage after successful migration
        localStorage.removeItem('nlweb-modern-conversations');
      } else {
        console.error('Failed to migrate conversations:', response.status);
      }
    } catch (error) {
      console.error('Error migrating conversations:', error);
    }
  }

  saveConversations() {
    // Only save conversations that have messages
    const conversationsToSave = this.conversations.filter(conv => conv.messages && conv.messages.length > 0);
    localStorage.setItem('nlweb-modern-conversations', JSON.stringify(conversationsToSave));
  }

  loadConversation(id, chatInterface) {
    const conversation = this.conversations.find(c => c.id === id);
    if (!conversation) return;
    
    chatInterface.currentConversationId = id;
    
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
    
    // Clear messages
    chatInterface.elements.messagesContainer.innerHTML = '';
    
    // Rebuild context arrays from conversation history
    chatInterface.prevQueries = conversation.messages
      .filter(m => m.type === 'user')
      .slice(-10)
      .map(m => m.content);
    
    chatInterface.lastAnswers = [];
    const assistantMessages = conversation.messages.filter(m => m.type === 'assistant');
    if (assistantMessages.length > 0) {
      // Get the last assistant message
      const lastAssistant = assistantMessages[assistantMessages.length - 1];
      if (lastAssistant.content) {
        chatInterface.lastAnswers.push(lastAssistant.content);
      }
    }
    
    // Restore messages to UI
    conversation.messages.forEach(msg => {
      chatInterface.addMessageToUI(msg.content, msg.type, false);
    });
    
    // Update title
    chatInterface.elements.chatTitle.textContent = conversation.title || 'Chat';
    
    // Update conversations list to show current selection
    chatInterface.updateConversationsList();
    
    // Hide centered input and show regular chat input
    chatInterface.hideCenteredInput();
    
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
      console.warn('No target container found for conversations list');
      return;
    }
    
    targetContainer.innerHTML = '';
    
    // Only show conversations that have messages
    const conversationsWithContent = this.conversations.filter(conv => conv.messages && conv.messages.length > 0);
    console.log('Updating conversations list with', conversationsWithContent.length, 'conversations');
    
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
        titleSpan.addEventListener('click', () => this.loadConversation(conv.id, chatInterface));
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