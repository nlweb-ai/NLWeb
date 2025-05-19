/**
 * ManagedEventSource Class
 * Handles EventSource connections with retry logic and message processing
 */

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
        if (typeof data.message === 'string') {
          chatInterface.itemDetailsMessage(data.message, chatInterface);
        }
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