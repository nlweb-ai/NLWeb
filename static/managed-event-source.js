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
        // Ensure message is a string
        console.log('item_details: data:', data);
        chatInterface.noResponse = false;
        if (typeof data.details === 'object') {
          data.details = JSON.stringify(data.details);
        }
        console.log('item_details: data:', data);
        const items = {
          "results": [data]
        }
        this.handleResultBatch(items, chatInterface);
          //chatInterface.itemDetailsMessage(data.message, chatInterface);
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
      case "substitution_suggestions":
        chatInterface.noResponse = false;
        this.handleSubstitutionSuggestions(data, chatInterface);
        break;
      case "no_results":
        chatInterface.noResponse = false;
        if (typeof data.message === 'string') {
          const noResultsMessage = chatInterface.createIntermediateMessageHtml(data.message);
          chatInterface.bubble.appendChild(noResultsMessage);
        }
        break;
      case "error":
        chatInterface.noResponse = false;
        if (typeof data.message === 'string') {
          const errorMessage = chatInterface.createIntermediateMessageHtml(`Error: ${data.message}`);
          errorMessage.style.color = '#d32f2f';
          chatInterface.bubble.appendChild(errorMessage);
        }
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
   * Handles substitution suggestions messages
   * 
   * @param {Object} data - The message data
   * @param {Object} chatInterface - The chat interface instance
   */
  handleSubstitutionSuggestions(data, chatInterface) {
    // Basic validation
    if (!data || typeof data !== 'object') return;
    
    // Clear any loading indicators
    while (chatInterface.bubble.firstChild) {
      chatInterface.bubble.removeChild(chatInterface.bubble.firstChild);
    }
    
    // Create container for substitution content
    const containerDiv = document.createElement('div');
    containerDiv.className = 'substitution-suggestions-container';
    
    // Add the HTML content if available
    if (typeof data.content === 'string') {
      const contentDiv = document.createElement('div');
      contentDiv.className = 'substitution-content';
      // Add styling to reduce text size
      contentDiv.style.cssText = 'font-size: 0.9em; line-height: 1.5;';
      // Content is already HTML from the backend
      contentDiv.innerHTML = data.content;
      
      // Apply additional styling to specific elements
      const h2Elements = contentDiv.querySelectorAll('h2');
      h2Elements.forEach(h2 => {
        h2.style.cssText = 'font-size: 1.3em; margin-top: 15px; margin-bottom: 10px;';
      });
      
      const h3Elements = contentDiv.querySelectorAll('h3');
      h3Elements.forEach(h3 => {
        h3.style.cssText = 'font-size: 1.1em; margin-top: 12px; margin-bottom: 8px; color: #333;';
      });
      
      const paragraphs = contentDiv.querySelectorAll('p');
      paragraphs.forEach(p => {
        p.style.cssText = 'margin: 8px 0; color: #555;';
      });
      
      const lists = contentDiv.querySelectorAll('ul');
      lists.forEach(ul => {
        ul.style.cssText = 'margin: 8px 0; padding-left: 25px;';
      });
      
      const listItems = contentDiv.querySelectorAll('li');
      listItems.forEach(li => {
        li.style.cssText = 'margin: 5px 0; line-height: 1.4;';
      });
      
      containerDiv.appendChild(contentDiv);
    }
    
    // Add reference recipes if available using the recipe renderer
    if (data.reference_recipes && Array.isArray(data.reference_recipes)) {
      // Add a heading for reference recipes
      const recipesHeading = document.createElement('h3');
      recipesHeading.textContent = 'Recipes Used for Reference';
      recipesHeading.style.marginTop = '20px';
      containerDiv.appendChild(recipesHeading);
      
      // Create recipe items using the JSON item renderer
      for (const recipe of data.reference_recipes) {
        if (!recipe || typeof recipe !== 'object') continue;
        
        // Create a recipe item in the format expected by createJsonItemHtml
        const recipeItem = {
          name: recipe.name,
          url: recipe.url,
          schema_object: recipe.schema_object,
          score: 100, // High score to indicate relevance
          description: "Reference recipe for substitution suggestions"
        };
        
        // Use the chat interface's existing recipe rendering
        const domItem = chatInterface.createJsonItemHtml(recipeItem);
        containerDiv.appendChild(domItem);
      }
    }
    
    chatInterface.bubble.appendChild(containerDiv);
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