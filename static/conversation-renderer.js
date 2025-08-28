export class ConversationRenderer {
    /**
     * Creates a new ConversationRenderer
     * 
     * @param {JsonRenderer} jsonRenderer - The parent JSON renderer
     */
    constructor(jsonRenderer) {
      this.jsonRenderer = jsonRenderer;
    }
  
    /**
     * Types that this renderer can handle
     * 
     * @returns {Array<string>} - The types this renderer can handle
     */
    static get supportedTypes() {
      return ["Conversation"];
    }
    
    /**
     * Renders a conversation history item
     * 
     * @param {Object} item - The item to render
     * @returns {HTMLElement} - The rendered HTML
     */
    render(item) {
      // Create custom container for conversation
      const container = document.createElement('div');
      container.className = 'conversation-result-container';
      container.style.cssText = 'margin: 12px 0; padding: 16px; border: 1px solid #e0e0e0; border-radius: 8px; background: #f9f9f9;';
      
      // Get the conversation data
      const schema = item.schema_object || {};
      
      // Create header row with user prompt and site
      const headerDiv = document.createElement('div');
      headerDiv.className = 'conversation-header';
      headerDiv.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;';
      
      // Title (user prompt)
      const titleLink = document.createElement('a');
      // Convert conversation:// URL to join link
      if (item.url && item.url.startsWith('conversation://')) {
        const conversationId = item.url.replace('conversation://', '');
        titleLink.href = `/static/join.html?conv_id=${conversationId}`;
        titleLink.target = '_blank';
      } else {
        titleLink.href = item.url || '#';
      }
      titleLink.textContent = item.name || schema.user_prompt || 'Conversation';
      titleLink.className = 'conversation-title-link';
      titleLink.style.cssText = 'font-weight: 600; color: #0066cc; text-decoration: none; font-size: 16px;';
      titleLink.onmouseover = function() { this.style.textDecoration = 'underline'; };
      titleLink.onmouseout = function() { this.style.textDecoration = 'none'; };
      headerDiv.appendChild(titleLink);
      
      // Site and user info
      const metaDiv = document.createElement('div');
      metaDiv.className = 'conversation-meta';
      metaDiv.style.cssText = 'display: flex; gap: 12px; align-items: center; color: #666; font-size: 14px;';
      
      // Add site badge
      if (item.site) {
        const siteBadge = document.createElement('span');
        siteBadge.className = 'site-badge';
        siteBadge.style.cssText = 'background: #e3f2fd; color: #1976d2; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 500;';
        siteBadge.textContent = item.site;
        metaDiv.appendChild(siteBadge);
      }
      
      // Add user info - show who performed this search
      if (item.user_id) {
        const userSpan = document.createElement('span');
        userSpan.className = 'user-info';
        userSpan.style.cssText = 'color: #888; font-size: 13px;';
        
        // Check if it's the current user
        const currentUserInfo = localStorage.getItem('userInfo');
        let isCurrentUser = false;
        if (currentUserInfo) {
          try {
            const userInfo = JSON.parse(currentUserInfo);
            const currentUserId = userInfo.id || userInfo.user_id;
            isCurrentUser = (currentUserId === item.user_id);
          } catch (e) {
            // Ignore parsing errors
          }
        }
        
        // Display user ID or "You" if it's the current user
        if (isCurrentUser) {
          userSpan.textContent = 'You';
        } else {
          // Extract readable part from user ID if it's an email
          let displayName = item.user_id;
          if (item.user_id.includes('@')) {
            displayName = item.user_id.split('@')[0];
          }
          userSpan.textContent = `by ${displayName}`;
        }
        
        metaDiv.appendChild(userSpan);
      }
      
      // Add timestamp next to site
      if (schema.time_of_creation) {
        const timeSpan = document.createElement('span');
        timeSpan.className = 'conversation-time';
        timeSpan.style.cssText = 'color: #999; font-size: 12px;';
        const date = new Date(schema.time_of_creation);
        timeSpan.textContent = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        metaDiv.appendChild(timeSpan);
      }
      
      headerDiv.appendChild(metaDiv);
      container.appendChild(headerDiv);
      
      // Add summary (use the summary field from schema, not the ranking description)
      if (schema.description || item.summary) {
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'conversation-summary';
        summaryDiv.style.cssText = 'margin: 12px 0; color: #333; line-height: 1.5;';
        // Use the summary from the conversation schema, not the ranking description
        summaryDiv.textContent = schema.description || item.summary || '';
        container.appendChild(summaryDiv);
      }
      
      
      return container;
    }
}