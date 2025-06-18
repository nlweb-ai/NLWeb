/**
 * ManagedEventSource Class
 * Handles EventSource connections with retry logic and message processing
 */

import { handleCompareItems } from './show_compare.js';

export class ManagedEventSource {
  /**
   * Creates a new ManagedEventSource
   * 
   * @param {string} url - The URL to connect to
   * @param {Object} options - Options for the EventSource
   * @param {number} options.maxRetries - Maximum number of retries
   */
  constructor(url, options = {}) {
    this.url = url;
    this.options = options;
    this.maxRetries = options.maxRetries || 3;
    this.retryCount = 0;
    this.eventSource = null;
    this.isStopped = false;
    this.query_id = null;
  }

  /**
   * Connects to the EventSource
   * 
   * @param {Object} chatInterface - The chat interface instance
   */
  connect(chatInterface) {
    if (this.isStopped) {
      return;
    }
    
    this.eventSource = new EventSource(this.url);
    this.eventSource.chatInterface = chatInterface;
    
    this.eventSource.onopen = () => {
      this.retryCount = 0; // Reset retry count on successful connection
    };

    this.eventSource.onerror = (error) => {
      if (this.eventSource.readyState === EventSource.CLOSED) {
        console.log('Connection was closed');
        
        if (this.retryCount < this.maxRetries) {
          this.retryCount++;
          console.log(`Retry attempt ${this.retryCount} of ${this.maxRetries}`);
          
          // Implement exponential backoff
          const backoffTime = Math.min(1000 * Math.pow(2, this.retryCount), 10000);
          setTimeout(() => this.connect(), backoffTime);
        } else {
          console.log('Max retries reached, stopping reconnection attempts');
          this.stop();
        }
      }
    };

    this.eventSource.onmessage = this.handleMessage.bind(this);
  }

  /**
   * Handles incoming messages from the EventSource
   * 
   * @param {Event} event - The message event
   */
  handleMessage(event) {
    const chatInterface = this.eventSource.chatInterface;
    
    // Handle first message by removing loading dots
    if (chatInterface.dotsStillThere) {
      chatInterface.handleFirstMessage();
      
      // Setup new message container
      const messageDiv = document.createElement('div');
      messageDiv.className = 'message assistant-message';
      const bubble = document.createElement('div'); 
      bubble.className = 'message-bubble';
      messageDiv.appendChild(bubble);
      
      chatInterface.bubble = bubble;
      chatInterface.messagesArea.appendChild(messageDiv);
      chatInterface.currentItems = [];
      chatInterface.thisRoundRemembered = null;
    }
    
    // Parse the JSON data
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (e) {
      console.error('Error parsing event data:', e);
      return;
    }
    
    // Verify query_id matches
    if (this.query_id && data.query_id && this.query_id !== data.query_id) {
      console.log("Query ID mismatch, ignoring message");
      return;
    }
    
    // Process message based on type
    this.processMessageByType(data, chatInterface);
  }

  /**
   * Processes messages based on their type
   * 
   * @param {Object} data - The message data
   * @param {Object} chatInterface - The chat interface instance
   */
  processMessageByType(data, chatInterface) {
    // Basic validation to prevent XSS
    if (!data || typeof data !== 'object') {
      console.error('Invalid message data received');
      return;
    }
    
    const messageType = data.message_type;
    
    switch(messageType) {
      case "query_analysis":
        this.handleQueryAnalysis(data, chatInterface);
        break;
      case "remember":
        // Ensure message is a string
        if (typeof data.message === 'string') {
          chatInterface.noResponse = false;
          chatInterface.memoryMessage(data.message, chatInterface);
        }
        break;
      case "asking_sites":
        // Ensure message is a string
        if (typeof data.message === 'string') {
          chatInterface.sourcesMessage = chatInterface.createIntermediateMessageHtml(data.message);
          chatInterface.bubble.appendChild(chatInterface.sourcesMessage);
        }
        break;
      case "site_is_irrelevant_to_query":
        // Ensure message is a string
        if (typeof data.message === 'string') {
          chatInterface.noResponse = false;
          chatInterface.siteIsIrrelevantToQuery(data.message, chatInterface);
        }
        break;
      case "ask_user":
        // Ensure message is a string
        if (typeof data.message === 'string') {
          chatInterface.noResponse = false;
          chatInterface.askUserMessage(data.message, chatInterface);
        }
        break;
      case "item_details":
        chatInterface.noResponse = false;
        // Map details to description for proper rendering
        const mappedData = {
          ...data,
          description: data.details  // Map details to description
        };
        
        const items = {
          "results": [mappedData]
        }
        this.handleResultBatch(items, chatInterface);
        break;
      case "result_batch":
        chatInterface.noResponse = false;
        this.handleResultBatch(data, chatInterface);
        break;
      case "intermediate_message":
        // Ensure message is a string
        if (typeof data.message === 'string') {
          chatInterface.noResponse = false;
          chatInterface.bubble.appendChild(chatInterface.createIntermediateMessageHtml(data.message));
        }
        break;
      case "summary":
        // Ensure message is a string
        if (typeof data.message === 'string') {
          chatInterface.noResponse = false;
          chatInterface.thisRoundSummary = chatInterface.createIntermediateMessageHtml(data.message);
          chatInterface.resortResults();
        }
        break;
      case "nlws":
        chatInterface.noResponse = false;
        this.handleNLWS(data, chatInterface);
        break;
      case "compare_items":
        chatInterface.noResponse = false;
        handleCompareItems(data, chatInterface);
        break;
      case "ensemble_result":
        chatInterface.noResponse = false;
        this.handleEnsembleResult(data, chatInterface);
        break;
      case "complete":
        chatInterface.resortResults();
        // Add this check to display a message when no results found
        if (chatInterface.noResponse) {
          const noResultsMessage = chatInterface.createIntermediateMessageHtml("No results were found");
          chatInterface.bubble.appendChild(noResultsMessage);
        }
        chatInterface.scrollDiv.scrollIntoView();
        this.close();
        break;
      default:
        console.log("Unknown message type:", messageType);
        break;
    }
  }
  
  /**
   * Handles query analysis messages
   * 
   * @param {Object} data - The message data
   * @param {Object} chatInterface - The chat interface instance
   */
  handleQueryAnalysis(data, chatInterface) {
    // Validate data properties
    if (!data) return;
    
    // Safely handle item_to_remember
    if (typeof data.item_to_remember === 'string') {
      chatInterface.itemToRemember.push(data.item_to_remember);
    }
    
    // Safely handle decontextualized_query
    if (typeof data.decontextualized_query === 'string') {
      chatInterface.decontextualizedQuery = data.decontextualized_query;
      chatInterface.possiblyAnnotateUserQuery(data.decontextualized_query);
    }
    
    // Safely display item to remember if it exists
    if (chatInterface.itemToRemember && typeof data.item_to_remember === 'string') {
      chatInterface.memoryMessage(data.item_to_remember, chatInterface);
    }
  }
  
  /**
   * Handles result batch messages
   * 
   * @param {Object} data - The message data
   * @param {Object} chatInterface - The chat interface instance
   */
  handleResultBatch(data, chatInterface) {
    // Validate results array
    if (!data.results || !Array.isArray(data.results)) {
      console.error('Invalid results data');
      return;
    }
    
    for (const item of data.results) {
      // Validate each item
      if (!item || typeof item !== 'object') continue;
      const domItem = chatInterface.createJsonItemHtml(item);
      chatInterface.currentItems.push([item, domItem]);
      chatInterface.bubble.appendChild(domItem);
      chatInterface.num_results_sent++;
    }
    chatInterface.resortResults();
  }
  
  /**
   * Handles NLWS messages
   * 
   * @param {Object} data - The message data
   * @param {Object} chatInterface - The chat interface instance
   */
  handleNLWS(data, chatInterface) {
    // Basic validation
    if (!data || typeof data !== 'object') return;
    
    // Clear existing content safely
    while (chatInterface.bubble.firstChild) {
      chatInterface.bubble.removeChild(chatInterface.bubble.firstChild);
    }
    
    // Safely handle answer
    if (typeof data.answer === 'string') {
      chatInterface.itemDetailsMessage(data.answer, chatInterface);
    }
    
    // Validate items array
    if (data.items && Array.isArray(data.items)) {
      for (const item of data.items) {
        // Validate each item
        if (!item || typeof item !== 'object') continue;
        
        const domItem = chatInterface.createJsonItemHtml(item);
        chatInterface.currentItems.push([item, domItem]);
        chatInterface.bubble.appendChild(domItem);
      }
    }
  }
  
  /**
   * Handles ensemble result messages
   * 
   * @param {Object} data - The message data containing ensemble recommendations
   * @param {Object} chatInterface - The chat interface instance
   */
  handleEnsembleResult(data, chatInterface) {
    // Validate data
    if (!data || !data.result || !data.result.recommendations) {
      console.error('Invalid ensemble result data');
      return;
    }
    
    const result = data.result;
    const recommendations = result.recommendations;
    
    // Create ensemble result container
    const container = document.createElement('div');
    container.className = 'ensemble-result-container';
    container.style.cssText = 'background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 10px 0;';
    
    // Add theme header
    if (recommendations.theme) {
      const themeHeader = document.createElement('h3');
      themeHeader.textContent = recommendations.theme;
      themeHeader.style.cssText = 'color: #333; margin-bottom: 20px; font-size: 1.2em;';
      container.appendChild(themeHeader);
    }
    
    // Add items
    if (recommendations.items && Array.isArray(recommendations.items)) {
      const itemsContainer = document.createElement('div');
      itemsContainer.style.cssText = 'display: grid; gap: 15px;';
      
      recommendations.items.forEach(item => {
        const itemCard = this.createEnsembleItemCard(item);
        itemsContainer.appendChild(itemCard);
      });
      
      container.appendChild(itemsContainer);
    }
    
    // Add overall tips
    if (recommendations.overall_tips && Array.isArray(recommendations.overall_tips)) {
      const tipsSection = document.createElement('div');
      tipsSection.style.cssText = 'margin-top: 20px; padding-top: 20px; border-top: 1px solid #dee2e6;';
      
      const tipsHeader = document.createElement('h4');
      tipsHeader.textContent = 'Planning Tips';
      tipsHeader.style.cssText = 'color: #555; margin-bottom: 10px; font-size: 1.1em;';
      tipsSection.appendChild(tipsHeader);
      
      const tipsList = document.createElement('ul');
      tipsList.style.cssText = 'margin: 0; padding-left: 20px;';
      
      recommendations.overall_tips.forEach(tip => {
        const tipItem = document.createElement('li');
        tipItem.textContent = tip;
        tipItem.style.cssText = 'color: #666; margin-bottom: 5px;';
        tipsList.appendChild(tipItem);
      });
      
      tipsSection.appendChild(tipsList);
      container.appendChild(tipsSection);
    }
    
    // Add to chat interface
    chatInterface.bubble.appendChild(container);
  }
  
  /**
   * Creates a card for an ensemble item
   * 
   * @param {Object} item - The item data
   * @returns {HTMLElement} The item card element
   */
  createEnsembleItemCard(item) {
    const card = document.createElement('div');
    card.style.cssText = 'background: white; padding: 15px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);';
    
    // Category badge
    const categoryBadge = document.createElement('span');
    categoryBadge.textContent = item.category;
    categoryBadge.style.cssText = `
      display: inline-block;
      padding: 4px 12px;
      background-color: ${item.category === 'Garden' ? '#28a745' : '#007bff'};
      color: white;
      border-radius: 20px;
      font-size: 0.85em;
      margin-bottom: 10px;
    `;
    card.appendChild(categoryBadge);
    
    // Name
    const name = document.createElement('h4');
    name.textContent = item.name;
    name.style.cssText = 'margin: 10px 0; color: #333;';
    card.appendChild(name);
    
    // Description
    const description = document.createElement('p');
    description.textContent = item.description;
    description.style.cssText = 'color: #666; margin: 10px 0; line-height: 1.5;';
    card.appendChild(description);
    
    // Why recommended
    const whySection = document.createElement('div');
    whySection.style.cssText = 'background-color: #e8f4f8; padding: 10px; border-radius: 4px; margin: 10px 0;';
    
    const whyLabel = document.createElement('strong');
    whyLabel.textContent = 'Why recommended: ';
    whyLabel.style.cssText = 'color: #0066cc;';
    
    const whyText = document.createElement('span');
    whyText.textContent = item.why_recommended;
    whyText.style.cssText = 'color: #555;';
    
    whySection.appendChild(whyLabel);
    whySection.appendChild(whyText);
    card.appendChild(whySection);
    
    // Details
    if (item.details && Object.keys(item.details).length > 0) {
      const detailsSection = document.createElement('div');
      detailsSection.style.cssText = 'margin-top: 10px; font-size: 0.9em;';
      
      Object.entries(item.details).forEach(([key, value]) => {
        const detailLine = document.createElement('div');
        detailLine.style.cssText = 'color: #777; margin: 3px 0;';
        
        const detailKey = document.createElement('strong');
        detailKey.textContent = `${key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')}: `;
        detailKey.style.cssText = 'color: #555;';
        
        const detailValue = document.createElement('span');
        detailValue.textContent = value;
        
        detailLine.appendChild(detailKey);
        detailLine.appendChild(detailValue);
        detailsSection.appendChild(detailLine);
      });
      
      card.appendChild(detailsSection);
    }
    
    return card;
  }

  /**
   * Stops the EventSource connection
   */
  stop() {
    this.isStopped = true;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  /**
   * Closes the EventSource connection
   */
  close() {
    this.stop();
  }

  /**
   * Resets and reconnects the EventSource
   */
  reset() {
    this.retryCount = 0;
    this.isStopped = false;
    this.stop();
    this.connect();
  }
}