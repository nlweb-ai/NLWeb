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
      titleLink.href = item.url || '#';
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
      
      // Add user name (extract from conversation_id which contains user email)
      if (schema.conversation_id) {
        // For now, we'll need to get the user from the search context
        // In the future, we might want to include user_id in the schema
        const userSpan = document.createElement('span');
        userSpan.className = 'user-info';
        userSpan.style.cssText = 'color: #888; font-size: 13px;';
        // Extract user from handler context if available
        const userId = item.user_id || 'User';
        userSpan.textContent = userId.split('@')[0]; // Get username part before @
        metaDiv.appendChild(userSpan);
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
      
      // Add score indicator if available
      if (item.score) {
        const scoreDiv = document.createElement('div');
        scoreDiv.className = 'relevance-score';
        scoreDiv.style.cssText = 'margin-top: 8px; padding-top: 8px; border-top: 1px solid #e0e0e0; color: #666; font-size: 12px;';
        
        // Create visual score indicator
        const scoreBar = document.createElement('div');
        scoreBar.style.cssText = 'display: inline-block; width: 100px; height: 6px; background: #e0e0e0; border-radius: 3px; margin-right: 8px;';
        const scoreFill = document.createElement('div');
        scoreFill.style.cssText = `width: ${item.score}%; height: 100%; background: #4caf50; border-radius: 3px;`;
        scoreBar.appendChild(scoreFill);
        
        scoreDiv.appendChild(scoreBar);
        scoreDiv.appendChild(document.createTextNode(`Relevance: ${item.score}%`));
        container.appendChild(scoreDiv);
      }
      
      // Add timestamp if available
      if (schema.timestamp || schema.time_of_creation) {
        const timeDiv = document.createElement('div');
        timeDiv.className = 'conversation-time';
        timeDiv.style.cssText = 'margin-top: 8px; color: #999; font-size: 12px;';
        const timestamp = schema.timestamp || schema.time_of_creation;
        const date = new Date(timestamp);
        timeDiv.textContent = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        container.appendChild(timeDiv);
      }
      
      return container;
    }
}