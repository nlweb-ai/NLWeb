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
    console.log('=== ManagedEventSource.connect called ===');
    console.log('URL:', this.url);
    
    if (this.isStopped) {
      console.log('Connection stopped, not connecting');
      return;
    }
    
    this.eventSource = new EventSource(this.url);
    this.eventSource.chatInterface = chatInterface;
    
    console.log('EventSource created:', this.eventSource);
    
    this.eventSource.onopen = () => {
      console.log('EventSource connection opened');
      this.retryCount = 0; // Reset retry count on successful connection
    };

    this.eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
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
    console.log('=== handleMessage called ===');
    console.log('Raw event data:', event.data);
    
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
      chatInterface.thisRoundDecontextQuery = null;
      chatInterface.debugMessages = [];  // Reset debug messages for new response
      chatInterface.pendingResultBatches = [];  // Collect result batches
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
    
    // Always clear all temp_intermediate divs when ANY new message arrives
    if (chatInterface.bubble) {
      const tempDivs = chatInterface.bubble.querySelectorAll('.temp_intermediate');
      tempDivs.forEach(div => div.remove());
    }
    
    // Store all messages for debug mode
    if (chatInterface.debugMessages) {
      chatInterface.debugMessages.push({
        type: messageType,
        data: data,
        timestamp: new Date().toISOString()
      });
    }
    
    console.log('Processing message type:', messageType);
    
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
        // Keep details separate from description
        const mappedData = {
          ...data,
          details: data.details,  // Keep details as-is
          description: Array.isArray(data.details) ? '' : (data.description || (data.schema_object && data.schema_object.description) || '')
        };
        
        const items = {
          "results": [mappedData]
        }
        this.handleResultBatch(items, chatInterface);
        break;
      case "result_batch":
        chatInterface.noResponse = false;
        // Process results immediately for display
        this.handleResultBatch(data, chatInterface);
        // Also collect for debug output
        if (chatInterface.pendingResultBatches && data.results) {
          chatInterface.pendingResultBatches.push(...data.results);
        }
        break;
      case "intermediate_message":
        chatInterface.noResponse = false;
        // Create a temporary container for intermediate content
        const tempContainer = document.createElement('div');
        tempContainer.className = 'temp_intermediate';
        
        // Handle both results data and text messages
        if (data.results) {
          // Use the same rendering as result_batch
          const resultsHtml = chatInterface.renderItems(data.results);
          tempContainer.innerHTML = resultsHtml;
        } else if (typeof data.message === 'string') {
          // Handle text-only intermediate messages in italics
          const textDiv = document.createElement('div');
          textDiv.style.fontStyle = 'italic';
          textDiv.textContent = data.message;
          tempContainer.appendChild(textDiv);
        }
        
        chatInterface.bubble.appendChild(tempContainer);
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
      case "decontextualized_query":
        // Display the decontextualized query in the chat
        if (data.decontextualized_query && data.original_query && 
            data.decontextualized_query !== data.original_query) {
          const message = `Query interpreted as: "${data.decontextualized_query}"`;
          const decontextDiv = chatInterface.createIntermediateMessageHtml(message);
          decontextDiv.style.fontStyle = 'italic';
          decontextDiv.style.color = '#666';
          decontextDiv.style.marginBottom = '10px';
          // Store it so it survives resort
          chatInterface.thisRoundDecontextQuery = decontextDiv;
          chatInterface.bubble.appendChild(decontextDiv);
        }
        break;
      case "tool_selection":
        // Display tool selection info
        if (data.selected_tool) {
          const toolMessage = `Using ${data.selected_tool} tool`;
          const toolDiv = chatInterface.createIntermediateMessageHtml(toolMessage);
          toolDiv.style.fontSize = '0.9em';
          toolDiv.style.color = '#888';
          toolDiv.style.fontStyle = 'italic';
          toolDiv.style.marginBottom = '8px';
          
          // Store it so it survives resort
          chatInterface.thisRoundToolSelection = toolDiv;
          chatInterface.bubble.appendChild(toolDiv);
        }
        break;
      case "substitution_suggestions":
        chatInterface.noResponse = false;
        this.handleSubstitutionSuggestions(data, chatInterface);
        break;
      case "chart_result":
        chatInterface.noResponse = false;
        this.handleChartResult(data, chatInterface);
        break;
      case "results_map":
        console.log('=== RESULTS_MAP MESSAGE RECEIVED ===');
        console.log('Message data:', JSON.stringify(data, null, 2));
        chatInterface.noResponse = false;
        this.handleResultsMap(data, chatInterface);
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
        // Add merged results to debug messages if any were collected
        if (chatInterface.pendingResultBatches && chatInterface.pendingResultBatches.length > 0) {
          if (chatInterface.debugMessages) {
            chatInterface.debugMessages.push({
              type: 'merged_results',
              data: {
                message_type: 'merged_results',
                results: chatInterface.pendingResultBatches,
                count: chatInterface.pendingResultBatches.length
              },
              timestamp: new Date().toISOString()
            });
          }
        }
        
        chatInterface.resortResults();
        // Add this check to display a message when no results found
        if (chatInterface.noResponse) {
          const noResultsMessage = chatInterface.createIntermediateMessageHtml("No results were found");
          chatInterface.bubble.appendChild(noResultsMessage);
        }
        
        // Compile last answers from current items
        const newAnswers = [];
        for (const [item, domItem] of chatInterface.currentItems) {
          if (item.title && item.url) {
            newAnswers.push({
              title: item.title,
              url: item.url
            });
          } else if (item.name && item.url) {
            newAnswers.push({
              title: item.name,
              url: item.url
            });
          }
        }
        
        // Update lastAnswers array (keep only last 20)
        chatInterface.lastAnswers = [...newAnswers, ...chatInterface.lastAnswers].slice(0, 20);
        
        chatInterface.scrollDiv.scrollIntoView();
        this.close();
        break;
      // Header messages - handle silently
      case "api_version":
      case "user_agent":
      case "data_retention":
      case "header":
      case "time-to-first-result":
        // These are header/metadata messages, no action needed
        break;
      case "api_key":
        // Handle API key configuration
        if (data.key_name === 'google_maps' && data.key_value) {
          // Store the Google Maps API key globally
          window.GOOGLE_MAPS_API_KEY = data.key_value;
          console.log('Received Google Maps API key from server');
        }
        break;
      default:
        console.log("Unknown message type:", messageType);
        console.log("Full message data:", data);
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
   * Extracts an image URL from a schema object
   * 
   * @param {Object} schema_object - The schema object
   * @returns {string|null} - The image URL or null
   */
  extractImageUrl(schema_object) {
    if (!schema_object) return null;
    
    // Check various possible image fields
    if (schema_object.image) {
      return this.extractImageUrlFromField(schema_object.image);
    } else if (schema_object.images && Array.isArray(schema_object.images) && schema_object.images.length > 0) {
      return this.extractImageUrlFromField(schema_object.images[0]);
    } else if (schema_object.thumbnailUrl) {
      return this.extractImageUrlFromField(schema_object.thumbnailUrl);
    } else if (schema_object.thumbnail) {
      return this.extractImageUrlFromField(schema_object.thumbnail);
    }
    
    return null;
  }
  
  /**
   * Extracts an image URL from various image field formats
   * 
   * @param {*} imageField - The image field data
   * @returns {string|null} - The image URL or null
   */
  extractImageUrlFromField(imageField) {
    // Handle string URLs
    if (typeof imageField === 'string') {
      return imageField;
    }
    
    // Handle object with url property
    if (typeof imageField === 'object' && imageField !== null) {
      if (imageField.url) {
        return imageField.url;
      }
      if (imageField.contentUrl) {
        return imageField.contentUrl;
      }
      if (imageField['@id']) {
        return imageField['@id'];
      }
    }
    
    // Handle array of images
    if (Array.isArray(imageField) && imageField.length > 0) {
      return this.extractImageUrlFromField(imageField[0]);
    }
    
    return null;
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
    
    // Create a flex container for content and image
    const flexContainer = document.createElement('div');
    flexContainer.style.cssText = 'display: flex; gap: 15px; align-items: center;';
    
    // Content container (goes first, on the left)
    const contentContainer = document.createElement('div');
    contentContainer.style.cssText = 'flex-grow: 1;';
    
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
    contentContainer.appendChild(categoryBadge);
    
    // Name with hyperlink
    const nameContainer = document.createElement('h4');
    nameContainer.style.cssText = 'margin: 10px 0;';
    
    // Get URL from item or schema_object
    const itemUrl = item.url || (item.schema_object && item.schema_object.url);
    
    if (itemUrl) {
      const nameLink = document.createElement('a');
      nameLink.href = itemUrl;
      nameLink.textContent = item.name;
      nameLink.target = '_blank';
      nameLink.style.cssText = 'color: #0066cc; text-decoration: none; font-weight: bold;';
      nameLink.onmouseover = function() { this.style.textDecoration = 'underline'; };
      nameLink.onmouseout = function() { this.style.textDecoration = 'none'; };
      nameContainer.appendChild(nameLink);
    } else {
      nameContainer.textContent = item.name;
      nameContainer.style.color = '#333';
    }
    
    contentContainer.appendChild(nameContainer);
    
    // Description
    const description = document.createElement('p');
    description.textContent = item.description;
    description.style.cssText = 'color: #666; margin: 10px 0; line-height: 1.5;';
    contentContainer.appendChild(description);
    
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
    contentContainer.appendChild(whySection);
    
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
      
      contentContainer.appendChild(detailsSection);
    }
    
    // Additional info from schema_object
    if (item.schema_object) {
      // Price
      if (item.schema_object.price || (item.schema_object.offers && item.schema_object.offers.price)) {
        const priceDiv = document.createElement('div');
        priceDiv.style.cssText = 'margin-top: 10px; font-weight: bold; color: #28a745;';
        const price = item.schema_object.price || item.schema_object.offers.price;
        priceDiv.textContent = `Price: ${typeof price === 'object' ? price.value : price}`;
        contentContainer.appendChild(priceDiv);
      }
      
      // Rating
      if (item.schema_object.aggregateRating) {
        const rating = item.schema_object.aggregateRating;
        const ratingValue = rating.ratingValue || rating.value;
        const reviewCount = rating.reviewCount || rating.ratingCount || rating.count;
        
        if (ratingValue) {
          const ratingDiv = document.createElement('div');
          ratingDiv.style.cssText = 'margin-top: 5px; color: #f39c12;';
          const stars = '★'.repeat(Math.round(ratingValue));
          const reviewText = reviewCount ? ` (${reviewCount} reviews)` : '';
          ratingDiv.textContent = `Rating: ${stars} ${ratingValue}/5${reviewText}`;
          contentContainer.appendChild(ratingDiv);
        }
      }
    }
    
    // Append content container to flex container
    flexContainer.appendChild(contentContainer);
    
    // Add image from schema_object if available (on the right side)
    if (item.schema_object) {
      const imageUrl = this.extractImageUrl(item.schema_object);
      
      if (imageUrl) {
        const imageContainer = document.createElement('div');
        imageContainer.style.cssText = 'flex-shrink: 0; display: flex; align-items: center;';
        
        const image = document.createElement('img');
        image.src = imageUrl;
        image.alt = item.name;
        image.style.cssText = 'width: 120px; height: 120px; object-fit: cover; border-radius: 6px;';
        imageContainer.appendChild(image);
        flexContainer.appendChild(imageContainer);
      }
    }
    
    // Append flex container to card
    card.appendChild(flexContainer);
    
    return card;
  }

  /**
   * Handles chart result messages (Data Commons web components)
   * 
   * @param {Object} data - The message data containing chart HTML
   * @param {Object} chatInterface - The chat interface instance
   */
  handleChartResult(data, chatInterface) {
    console.log('=== Chart Result Handler Called ===');
    console.log('Received data:', data);
    
    // Validate data
    if (!data || typeof data.html !== 'string') {
      console.error('Invalid chart result data');
      return;
    }
    
    console.log('HTML content to insert:', data.html);
    
    // Create container for the chart
    const chartContainer = document.createElement('div');
    chartContainer.className = 'chart-result-container';
    chartContainer.style.cssText = 'margin: 15px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px;';
    
    // Parse and inject the HTML content
    // The HTML should contain the Data Commons web component and script tag
    // SECURITY NOTE: This HTML comes from the backend and should be sanitized server-side
    // It contains Data Commons web components that require specific HTML structure
    chartContainer.innerHTML = data.html;
    
    console.log('Container element created:', chartContainer);
    console.log('Container innerHTML after setting:', chartContainer.innerHTML);
    
    // Append to chat interface
    chatInterface.bubble.appendChild(chartContainer);
    
    console.log('Chart container appended to bubble');
    console.log('Bubble contents:', chatInterface.bubble.innerHTML);
    
    // The Data Commons script should automatically initialize the web component
    // when it's added to the DOM
  }

  /**
   * Handles results map messages
   * 
   * @param {Object} data - The message data containing locations
   * @param {Object} chatInterface - The chat interface instance
   */
  handleResultsMap(data, chatInterface) {
    console.log('=== handleResultsMap Called ===');
    console.log('Received data:', data);
    console.log('chatInterface:', chatInterface);
    console.log('chatInterface.bubble:', chatInterface.bubble);
    console.log('Current Google Maps API Key:', window.GOOGLE_MAPS_API_KEY || 'Not set');
    
    // Validate data
    if (!data || !data.locations || !Array.isArray(data.locations) || data.locations.length === 0) {
      console.error('Invalid results map data - validation failed');
      console.log('data:', data);
      console.log('data.locations:', data ? data.locations : 'data is null/undefined');
      return;
    }
    
    console.log('Data validation passed, creating map container...');
    
    // Create container for the map
    const mapContainer = document.createElement('div');
    mapContainer.className = 'results-map-container';
    mapContainer.style.cssText = 'margin: 15px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px;';
    
    // Create the map div
    const mapDiv = document.createElement('div');
    mapDiv.id = 'results-map-' + Date.now(); // Unique ID for each map
    mapDiv.style.cssText = 'width: 100%; height: 400px; border-radius: 6px;';
    
    // Add a title
    const mapTitle = document.createElement('h3');
    mapTitle.textContent = 'Result Locations';
    mapTitle.style.cssText = 'margin: 0 0 10px 0; color: #333; font-size: 1.1em;';
    
    mapContainer.appendChild(mapTitle);
    mapContainer.appendChild(mapDiv);
    
    console.log('Map container created, appending to bubble...');
    
    // Append to chat interface
    chatInterface.bubble.appendChild(mapContainer);
    
    console.log('Map container appended to bubble, initializing map...');
    console.log('Map div ID:', mapDiv.id);
    console.log('Locations to display:', data.locations);
    
    // Initialize the map
    this.initializeGoogleMap(mapDiv, data.locations);
  }
  
  /**
   * Initialize Google Map with markers
   * 
   * @param {HTMLElement} mapDiv - The map container element
   * @param {Array} locations - Array of location objects with title and address
   */
  initializeGoogleMap(mapDiv, locations) {
    console.log('=== initializeGoogleMap Called ===');
    console.log('mapDiv:', mapDiv);
    console.log('locations:', locations);
    
    // Check if API key is configured
    const apiKey = window.GOOGLE_MAPS_API_KEY || 
                  document.body.getAttribute('data-google-maps-api-key') || 
                  'YOUR_API_KEY';
    
    console.log('API Key found:', apiKey);
    
    if (apiKey === 'YOUR_API_KEY' || !apiKey || apiKey === 'GOOGLE_MAPS_API_KEY') {
      console.warn('Google Maps API key not configured, showing location list instead');
      // Show location list instead of map
      this.showLocationList(mapDiv, locations);
      return;
    }
    
    // Check if Google Maps API is loaded
    if (typeof google === 'undefined' || !google.maps) {
      console.log('Google Maps API not loaded, loading now...');
      this.loadGoogleMapsAPI().then(() => {
        this.createMap(mapDiv, locations);
      }).catch(error => {
        console.error('Failed to load Google Maps API:', error);
        // Fallback to showing location list
        this.showLocationList(mapDiv, locations);
      });
    } else {
      this.createMap(mapDiv, locations);
    }
  }
  
  /**
   * Load Google Maps API dynamically
   * 
   * @returns {Promise} Promise that resolves when API is loaded
   */
  loadGoogleMapsAPI() {
    return new Promise((resolve, reject) => {
      // Check if already loading
      if (window.googleMapsAPILoading) {
        // Wait for existing load to complete
        const checkInterval = setInterval(() => {
          if (typeof google !== 'undefined' && google.maps) {
            clearInterval(checkInterval);
            resolve();
          }
        }, 100);
        return;
      }
      
      window.googleMapsAPILoading = true;
      
      // Create script element
      const script = document.createElement('script');
      
      // Get API key from various sources
      const apiKey = window.GOOGLE_MAPS_API_KEY || 
                    document.body.getAttribute('data-google-maps-api-key') || 
                    'YOUR_API_KEY';
      
      // Validate API key format (alphanumeric and dashes, 39-40 characters typical for Google Maps API keys)
      const apiKeyPattern = /^[A-Za-z0-9\-_]{39,40}$/;
      if (!apiKeyPattern.test(apiKey) || apiKey === 'YOUR_API_KEY' || apiKey === 'GOOGLE_MAPS_API_KEY') {
        console.error('Invalid or missing Google Maps API key. Please set GOOGLE_MAPS_API_KEY environment variable or configure it in config_nlweb.yaml');
        mapDiv.innerHTML = `
          <div style="text-align: center; padding: 20px; color: #666;">
            <p><strong>Map unavailable</strong></p>
            <p style="font-size: 0.9em;">Invalid or missing Google Maps API key.</p>
          </div>
        `;
        reject(new Error('Invalid or missing API key'));
        return;
      }
      
      console.log('Loading Google Maps API with key:', apiKey.substring(0, 10) + '...');
      
      // Validate and encode the API key for security
      if (!/^[a-zA-Z0-9_-]+$/.test(apiKey)) {
        console.error('Invalid API key format');
        reject(new Error('Invalid API key format'));
        return;
      }
      
      script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=places`;
      script.async = true;
      script.defer = true;
      
      script.onload = () => {
        window.googleMapsAPILoading = false;
        resolve();
      };
      
      script.onerror = () => {
        window.googleMapsAPILoading = false;
        reject(new Error('Failed to load Google Maps API'));
      };
      
      document.head.appendChild(script);
    });
  }
  
  /**
   * Create the Google Map with markers
   * 
   * @param {HTMLElement} mapDiv - The map container element
   * @param {Array} locations - Array of location objects
   */
  createMap(mapDiv, locations) {
    // Initialize the map
    const map = new google.maps.Map(mapDiv, {
      zoom: 10,
      center: { lat: 0, lng: 0 }, // Will be updated based on markers
      mapTypeId: 'roadmap'
    });
    
    // Geocoding service to convert addresses to coordinates
    const geocoder = new google.maps.Geocoder();
    const bounds = new google.maps.LatLngBounds();
    const markers = [];
    let geocodedCount = 0;
    
    // Process each location
    locations.forEach((location, index) => {
      // Use setTimeout to avoid rate limiting
      setTimeout(() => {
        geocoder.geocode({ address: location.address }, (results, status) => {
          if (status === 'OK' && results[0]) {
            const position = results[0].geometry.location;
            
            // Create marker
            const marker = new google.maps.Marker({
              position: position,
              map: map,
              title: location.title,
              label: {
                text: (index + 1).toString(),
                color: 'white',
                fontWeight: 'bold'
              }
            });
            
            // Create info window
            const infoWindow = new google.maps.InfoWindow({
              content: `
                <div style="padding: 5px;">
                  <h4 style="margin: 0 0 5px 0; color: #333;">${location.title}</h4>
                  <p style="margin: 0; color: #666; font-size: 0.9em;">${location.address}</p>
                </div>
              `
            });
            
            // Add click listener to marker
            marker.addListener('click', () => {
              infoWindow.open(map, marker);
            });
            
            markers.push(marker);
            bounds.extend(position);
            
            geocodedCount++;
            
            // If all locations are geocoded, fit the map to show all markers
            if (geocodedCount === locations.length) {
              map.fitBounds(bounds);
              
              // Adjust zoom if only one marker
              if (locations.length === 1) {
                map.setZoom(15);
              }
            }
          } else {
            console.error('Geocode failed for location:', location.address, 'Status:', status);
            geocodedCount++;
          }
        });
      }, index * 200); // 200ms delay between requests
    });
    
    // Add a legend showing numbered locations
    const legendDiv = document.createElement('div');
    legendDiv.style.cssText = `
      background: white;
      padding: 10px;
      margin: 10px;
      border: 1px solid #ccc;
      border-radius: 5px;
      font-size: 14px;
      max-height: 200px;
      overflow-y: auto;
    `;
    
    const legendTitle = document.createElement('div');
    legendTitle.innerHTML = ''; // Clear content
    const titleStrong = document.createElement('strong');
    titleStrong.textContent = 'Locations:';
    legendTitle.appendChild(titleStrong);
    legendTitle.style.marginBottom = '5px';
    legendDiv.appendChild(legendTitle);
    
    locations.forEach((location, index) => {
      const legendItem = document.createElement('div');
      legendItem.style.cssText = 'padding: 2px 0;';
      legendItem.innerHTML = ''; // Clear content
      const indexStrong = document.createElement('strong');
      indexStrong.textContent = `${index + 1}.`;
      legendItem.appendChild(indexStrong);
      legendItem.appendChild(document.createTextNode(` ${location.title}`));
      legendDiv.appendChild(legendItem);
    });
    
    map.controls[google.maps.ControlPosition.RIGHT_TOP].push(legendDiv);
  }
  
  /**
   * Show location list as a fallback when map cannot be displayed
   * 
   * @param {HTMLElement} mapDiv - The container element
   * @param {Array} locations - Array of location objects with title and address
   */
  showLocationList(mapDiv, locations) {
    console.log('=== showLocationList Called ===');
    console.log('mapDiv:', mapDiv);
    console.log('locations:', locations);
    console.log('Number of locations:', locations.length);
    
    mapDiv.style.height = 'auto';
    mapDiv.innerHTML = '';
    
    // Create a styled list container
    const listContainer = document.createElement('div');
    listContainer.style.cssText = `
      background: #f9f9f9;
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 15px;
    `;
    
    // Add a header
    const header = document.createElement('h4');
    header.textContent = 'Location Addresses:';
    header.style.cssText = 'margin: 0 0 15px 0; color: #333;';
    listContainer.appendChild(header);
    
    // Create the location list
    const list = document.createElement('div');
    list.style.cssText = 'display: flex; flex-direction: column; gap: 10px;';
    
    locations.forEach((location, index) => {
      const locationItem = document.createElement('div');
      locationItem.style.cssText = `
        background: white;
        padding: 12px;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        display: flex;
        align-items: flex-start;
        gap: 10px;
      `;
      
      // Number badge
      const numberBadge = document.createElement('div');
      numberBadge.textContent = (index + 1).toString();
      numberBadge.style.cssText = `
        background: #4285f4;
        color: white;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 12px;
        flex-shrink: 0;
      `;
      
      // Location details
      const details = document.createElement('div');
      details.style.cssText = 'flex: 1;';
      
      const title = document.createElement('div');
      title.textContent = location.title;
      title.style.cssText = 'font-weight: 600; color: #333; margin-bottom: 5px;';
      
      const address = document.createElement('div');
      // Clean up the address if needed
      let cleanAddress = location.address;
      if (cleanAddress.includes('{')) {
        cleanAddress = cleanAddress.split(', {')[0];
      }
      address.textContent = cleanAddress;
      address.style.cssText = 'color: #666; font-size: 0.9em; line-height: 1.4;';
      
      details.appendChild(title);
      details.appendChild(address);
      
      locationItem.appendChild(numberBadge);
      locationItem.appendChild(details);
      
      list.appendChild(locationItem);
    });
    
    listContainer.appendChild(list);
    
    // Add a note about the map
    const note = document.createElement('p');
    note.textContent = 'Map view requires a Google Maps API key to be configured.';
    note.style.cssText = 'margin: 15px 0 0 0; font-size: 0.85em; color: #888; font-style: italic;';
    listContainer.appendChild(note);
    
    mapDiv.appendChild(listContainer);
    
    console.log('Location list created and appended successfully');
    console.log('Final mapDiv contents:', mapDiv.innerHTML);
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
      // SECURITY NOTE: This content should be sanitized server-side before sending
      // as it contains structured HTML for recipe substitutions
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