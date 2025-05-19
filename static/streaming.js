/**
 * Streaming chat interface implementation
 */

import { applyStyles } from './styles.js';

// Apply styles from the dedicated styles module
applyStyles();

class ManagedEventSource {
  constructor(url, options = {}) {
    this.url = url;
    this.options = options;
    this.maxRetries = options.maxRetries || 3;
    this.retryCount = 0;
    this.eventSource = null;
    this.isStopped = false;
  }

  connect(chatInterface) {
    if (this.isStopped) {
      return;
    }
    this.eventSource = new EventSource(this.url);
    this.eventSource.chatInterface = chatInterface;
    this.eventSource.onopen = () => {
    //  console.log('Connection established');
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
    }

    this.eventSource.onmessage = function(event) {
      if (this.chatInterface.dotsStillThere) {
        this.chatInterface.handleFirstMessage(event);
        const messageDiv = document.createElement('div');
        messageDiv.className = `message assistant-message`;
        const bubble = document.createElement('div'); 
        bubble.className = 'message-bubble';
        messageDiv.appendChild(bubble);
        this.chatInterface.bubble = bubble;
        this.chatInterface.messagesArea.appendChild(messageDiv);
        this.chatInterface.currentItems = []
        this.chatInterface.thisRoundRemembered = null;
      }
      const data = JSON.parse(event.data);
      // check that the query_id on this object and message match
      if (this.query_id && data.query_id && this.query_id !== data.query_id) {
        console.log("Query ID mismatch, ignoring message");
        return;
      }
      if (data && data.message_type == "query_analysis") {
        this.chatInterface.itemToRemember.push(data.item_to_remember);
        this.chatInterface.decontextualizedQuery = data.decontextualized_query;
        this.chatInterface.possiblyAnnotateUserQuery(this.chatInterface, data.decontextualized_query);
        if (this.chatInterface.itemToRemember) {
          this.chatInterface.memoryMessage(data.item_to_remember, this.chatInterface)
        }
      } else if (data && data.message_type == "remember") {
        this.chatInterface.memoryMessage(data.message, this.chatInterface)    
      } else if (data && data.message_type == "asking_sites") {
        this.chatInterface.sourcesMessage = this.chatInterface.createIntermediateMessageHtml(data.message);
        this.chatInterface.bubble.appendChild(this.chatInterface.sourcesMessage);
      } else if (data && data.message_type == "site_is_irrelevant_to_query") {
        this.chatInterface.siteIsIrrelevantToQuery(data.message, this.chatInterface)  
      } else if (data && data.message_type == "ask_user") {
        this.chatInterface.askUserMessage(data.message, this.chatInterface)    
      } else if (data && data.message_type == "item_details") {
        this.chatInterface.itemDetailsMessage(data.message, this.chatInterface)    
      } else if (data && data.message_type == "result_batch") {
        for (const item of data.results) {
          const domItem = this.chatInterface.createJsonItemHtml(item)
          this.chatInterface.currentItems.push([item, domItem])
          this.chatInterface.bubble.appendChild(domItem);
          this.chatInterface.num_results_sent++;
        }
        this.chatInterface.resortResults(this.chatInterface);
      } else if (data && data.message_type == "intermediate_message") {
        this.chatInterface.bubble.appendChild(this.chatInterface.createIntermediateMessageHtml(data.message));
      } else if (data && data.message_type == "summary") {
        this.chatInterface.thisRoundSummary = this.chatInterface.createIntermediateMessageHtml(data.message);
        this.chatInterface.resortResults(this.chatInterface);
      } else if (data && data.message_type == "nlws") {
        while (this.chatInterface.bubble.firstChild) {
          this.chatInterface.bubble.removeChild(this.chatInterface.bubble.firstChild);
        }
        this.chatInterface.itemDetailsMessage(data.answer, this.chatInterface);
        for (const item of data.items) {
          const domItem = this.chatInterface.createJsonItemHtml(item)
          this.chatInterface.currentItems.push([item, domItem])
          this.chatInterface.bubble.appendChild(domItem);
        }
      } else if (data && data.message_type == "complete") {
        this.chatInterface.resortResults(this.chatInterface);
        this.chatInterface.scrollDiv.scrollIntoView();
        this.close();
      }
    }
  }
      

  stop() {
    this.isStopped = true;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  // Method to manually reset and reconnect
  reset() {
    this.retryCount = 0;
    this.isStopped = false;
    this.stop();
    this.connect();
  }
};

// Usage example:
const eventSourceOptions = {
  maxRetries: 3,
  eventListeners: {
    message: (event) => console.log('Received message:', event.data),
    customEvent: (event) => console.log('Custom event:', event.data)
  }
};

//const source = new ManagedEventSource('/api/events', eventSourceOptions);
//source.connect();

// To stop the connection:
// source.stop();

// To reset and reconnect:
// source.reset();



// Chat interface class

class ChatInterface {
    constructor(site=null, display_mode="dropdown", generate_mode="list") {
        if (site) {
            this.site = site;
        }
        // Parse URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const query = urlParams.get('query');
        const prevMessagesStr = urlParams.get('prev');
        const contextUrl = urlParams.get('context_url');
        const url_generate_mode = urlParams.get('generate_mode');
        if (url_generate_mode) {
          this.generate_mode = url_generate_mode;
        } 
        this.generate_mode = generate_mode;
        this.display_mode = display_mode;
       
        this.prevMessages = prevMessagesStr ? JSON.parse(decodeURIComponent(prevMessagesStr)) : [];
        this.createInterface(display_mode);
        this.bindEvents();
        this.eventSource = null;
        this.dotsStillThere = false;
        this.resetChatState();
        // Add message if query parameter exists
        if (query) {
            this.sendMessage(decodeURIComponent(query));
        }
    }

    resetChatState() {
      this.messagesArea.innerHTML = '';
      this.messages = [];
      this.prevMessages = [];
      this.currentMessage = [];
      this.currentItems = [];
      this.itemToRemember = [];
      this.thisRoundSummary = null;
    }
  
    makeSelectorLabel(label) {
      const labelDiv = document.createElement('span');
      labelDiv.textContent = " "+ label + " ";
      return labelDiv;
    }

    sites () {
      return ['imdb', 'nytimes', 'alltrails', 'allbirds', 'seriouseats', 'npr podcasts', 'backcountry', 'bc_product', 'neurips', 'zillow',
      'tripadvisor', 'woksoflife', 'cheftariq', 'hebbarskitchen', 'latam_recipes', 'spruce', 'med podcast', 'all'];
    }

    generateModes () {
      return ['list', 'summarize', 'generate'];
    }

    createSelectors() {
        // Create selectors
      const selector = document.createElement('div');
      this.selector = selector;
      selector.className = 'site-selector';
  
      // Create site selector
      const siteSelect = document.createElement('select');
      this.siteSelect = siteSelect;
      this.sites().forEach(site => {
        const option = document.createElement('option');
        option.value = site;
        option.textContent = site;
        siteSelect.appendChild(option);
      });
      this.selector.appendChild(this.makeSelectorLabel("Site"))
      this.selector.appendChild(siteSelect);
      siteSelect.addEventListener('change', () => {
          this.resetChatState();
      });

      const generateModeSelect = document.createElement('select');
      this.generateModeSelect = generateModeSelect;
      this.selector.appendChild(this.makeSelectorLabel("Mode"))
      this.generateModes().forEach(mode => {
        const option = document.createElement('option');
        option.value = mode;
        option.textContent = mode;
        generateModeSelect.appendChild(option);
      });
      generateModeSelect.addEventListener('change', () => {
        this.generate_mode = generateModeSelect.value;
        this.resetChatState();
      });
      this.selector.appendChild(generateModeSelect);
     
      // Create clear chat icon
      const clearIcon = document.createElement('span');
      clearIcon.innerHTML = '<img src="/html/clear.jpeg" width="16" height="16" style="vertical-align: middle; cursor: pointer; margin-left: 8px;">';
      clearIcon.title = "Clear chat history";
      clearIcon.addEventListener('click', () => {
        this.resetChatState();
      });
      this.selector.appendChild(clearIcon);

      // Create debug icon
      const debugIcon = document.createElement('span');
      debugIcon.innerHTML = '<img src="/html/debug.png" width="16" height="16" style="vertical-align: middle; cursor: pointer; margin-left: 8px;">';
      debugIcon.title = "Debug";
      debugIcon.addEventListener('click', () => {
        if (this.debug_mode) {
          this.debug_mode = false;
          this.bubble.innerHTML = '';
          this.resortResults(this);
        } else {
          this.debug_mode = true;
          this.bubble.innerHTML = this.createDebugString();
        }
      });
      this.selector.appendChild(debugIcon);

      const contextUrlDiv = document.createElement('div');
      contextUrlDiv.id = 'context_url_div';
      contextUrlDiv.style.display = 'none';
      contextUrlDiv.style.marginTop = '8px';
          
      const contextUrlInput = document.createElement('input');
      contextUrlInput.type = 'text';
      contextUrlInput.id = 'context_url';
      contextUrlInput.placeholder = 'Enter Context URL';
      contextUrlInput.style.width = '200px';
          
      contextUrlDiv.appendChild(this.makeSelectorLabel("Context URL"));
      contextUrlDiv.appendChild(contextUrlInput);
      this.selector.appendChild(contextUrlDiv);
      this.context_url = contextUrlInput;

      this.container.appendChild(this.selector);
    }
  
    createInterface(display_mode="dropdown") {
      // Create main container
      this.container = document.getElementById('chat-container');

      if (display_mode == "dropdown") {
        this.createSelectors();
      }
      // Create messages area
      
      this.messagesArea = document.createElement('div');
      this.messagesArea.className = (display_mode == "dropdown" ? 'messages' : 'messages_full');
      
      // Create input area
      this.inputArea = document.createElement('div');
      this.inputArea.className = (display_mode == "dropdown" ? 'input-area' : 'input-area_full');
  
      // Create input field
      this.input = document.createElement('textarea');
      this.input.className = 'message-input';
      this.input.placeholder = 'Type your message...';
  
      // Create send button
      this.sendButton = document.createElement('button');
      this.sendButton.className = 'send-button';
      this.sendButton.textContent = 'Send';
  
      // Assemble the interface
      this.inputArea.appendChild(this.input);
      this.inputArea.appendChild(this.sendButton);
      this.container.appendChild(this.messagesArea);
      this.container.appendChild(this.inputArea);
  
      // Add to document
     // document.body.appendChild(this.container);
    }
  
    bindEvents() {
      // Send message on button click
      this.sendButton.addEventListener('click', () => this.sendMessage());
  
      // Send message on Enter (but allow Shift+Enter for new lines)
      this.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
    }
  
    sendMessage(query=null) {
      const message = query || this.input.value.trim();
      if (!message) return;
  
      // Add user message
      this.addMessage(message, 'user');
      this.currentMessage = message;
      this.input.value = '';
  
      // Simulate assistant response
      this.getResponse(message);
    }
  
    extractImage(schema_object) {
      if (schema_object && schema_object.image) {
        return this.extractImageInternal(schema_object.image);
      }
    }

    extractImageInternal(image) {
      if (typeof image === 'string') {
          return image;
      } else if (typeof image === 'object' && image.url) {
          return image.url;
      } else if (typeof image === 'object' && image.contentUrl) {
          return image.contentUrl;
      } else if (image instanceof Array) {
        if (image[0] && typeof image[0] === 'string') {
          return image[0];
        } else if (image[0] && typeof image[0] === 'object') {
          return this.extractImageInternal(image[0]);
        }
      } 
      return null;
    }
    
    htmlUnescape(str) {
      // Return empty string for null/undefined values
      if (!str) return '';
      
      // Check if input is a string
      if (typeof str !== 'string') {
        return String(str);
      }

      // Use the browser's built-in text decoder functionality
      // This safely decodes HTML entities without execution risks
      const textarea = document.createElement('textarea');
      textarea.textContent = str;
      return textarea.value;
    }
  
    addMessage(content, sender) {
      const messageDiv = document.createElement('div');
      messageDiv.className = `message ${sender}-message`;
      if (sender == "user") {
        this.lastUserMessageDiv = messageDiv;
        const scrollDiv = document.createElement('span');
        scrollDiv.id = this.quickHash(content.toString());
        messageDiv.appendChild(scrollDiv);
        messageDiv.appendChild(document.createElement('br'));
        messageDiv.appendChild(document.createElement('br'));
        this.scrollDiv = scrollDiv;
      }
      const bubble = document.createElement('div');
      bubble.className = 'message-bubble';
      let parsedContent;
      try {
          parsedContent = JSON.parse(content);
      } catch (e) {
          parsedContent = content;
      }
      
      // FIX: Replace innerHTML with safer DOM manipulation
      if (Array.isArray(parsedContent)) {
          // Clear any existing content
          while (bubble.firstChild) {
              bubble.removeChild(bubble.firstChild);
          }
          
          // Append each item
          parsedContent.forEach(obj => {
              const itemElement = this.createJsonItemHtml(obj);
              bubble.appendChild(itemElement);
              
              // Add line breaks between items if not the last one
              if (parsedContent.indexOf(obj) < parsedContent.length - 1) {
                  bubble.appendChild(document.createElement('br'));
                  bubble.appendChild(document.createElement('br'));
              }
          });
      } else {
          bubble.textContent = content;
      }
  
      messageDiv.appendChild(bubble);
      this.messagesArea.appendChild(messageDiv);
      this.messagesArea.scrollTop = this.messagesArea.scrollHeight;
  
      this.messages.push({ content, sender });
     
      this.currentMessage = "";
    }

    makeAsSpan(content) {
      const span = document.createElement('span');
      span.textContent = content;
      span.style.fontSize = '0.85em';
     // span.className = 'item-details-message';
      return span;
    }

    possiblyAddExplanation(item, contentDiv, force=false) {
        const detailsDiv = document.createElement('div'); 
        contentDiv.appendChild(document.createElement('br'));
        const expl_span = this.makeAsSpan(item.explanation);
        expl_span.className = 'item-details-message';
        detailsDiv.appendChild(expl_span);
        contentDiv.appendChild(detailsDiv);
        return detailsDiv;
    }

    typeSpecificContent(item, contentDiv) {
      const houseTypes = ["SingleFamilyResidence", "Apartment", "Townhouse", "House", "Condominium", "RealEstateListing"]
      if (!item.schema_object) {
        return;
      }
      const objType = item.schema_object['@type'];
      if (objType == "PodcastEpisode") {
        this.possiblyAddExplanation(item, contentDiv, true);
        return;
      }
      if (houseTypes.includes(objType)) {
        const detailsDiv = this.possiblyAddExplanation(item, contentDiv, true);
        const price = item.schema_object.price;
        const address = item.schema_object.address;
        const numBedrooms = item.schema_object.numberOfRooms;
        const numBathrooms = item.schema_object.numberOfBathroomsTotal;
        const sqft = item.schema_object.floorSize?.value;
        let priceValue = price;
        if (typeof price === 'object') {
          priceValue = price.price || price.value || price;
          priceValue = Math.round(priceValue / 100000) * 100000;
          priceValue = priceValue.toLocaleString('en-US');
        }

        if (address?.streetAddress && address?.addressLocality) {
          detailsDiv.appendChild(this.makeAsSpan(address.streetAddress + ", " + address.addressLocality));
          detailsDiv.appendChild(document.createElement('br'));
        }
        
        if (numBedrooms && numBathrooms && sqft) {
          detailsDiv.appendChild(this.makeAsSpan(`${numBedrooms} bedrooms, ${numBathrooms} bathrooms, ${sqft} sqft`));
          detailsDiv.appendChild(document.createElement('br'));
        }
        
        if (priceValue) {
          detailsDiv.appendChild(this.makeAsSpan(`Listed at ${priceValue}`));
        }
      }
    }

    clearHistory() {
      this.messagesArea.innerHTML = "";
      this.messages = [];
      this.prevMessages = [];
    }
  
    getItemName(item) {
      if (item.name) {
        return item.name;
      } else if (item.schema_object && item.schema_object.keywords) {
        return item.schema_object.keywords;
      }
      return item.url;
    }

    createJsonItemHtml(item) {
      const container = document.createElement('div');
      container.style.display = 'flex';
      container.style.marginBottom = '1em';
      container.style.gap = '1em';
  
      // Left content div (title + description)
      const contentDiv = document.createElement('div');
      contentDiv.style.flex = '1';
  
      // Title row with link and question mark
      const titleRow = document.createElement('div');
      titleRow.style.display = 'flex';
      titleRow.style.alignItems = 'center';
      titleRow.style.gap = '0.5em';
      titleRow.style.marginBottom = '0.5em';
  
      // Title/link
      const titleLink = document.createElement('a');
      // FIX: Use sanitizeUrl for URL attributes and add additional security measures
      const sanitizedUrl = item.url ? this.sanitizeUrl(item.url) : '#';
      titleLink.href = sanitizedUrl;
      // Add rel="noopener noreferrer" for external links
      if (sanitizedUrl !== '#' && !sanitizedUrl.startsWith(window.location.origin)) {
          titleLink.rel = "noopener noreferrer";
          // Optional: Open external links in new tab
          titleLink.target = "_blank";
      }
      const itemName = this.getItemName(item);
      titleLink.textContent = this.htmlUnescape(`${itemName}`);
      titleLink.style.fontWeight = '600';
      titleLink.style.textDecoration = 'none';
      titleLink.style.color = '#2962ff';
      titleRow.appendChild(titleLink);
  
      // info icon
      const infoIcon = document.createElement('span');
      const imgElement = document.createElement('img');
      imgElement.src = this.sanitizeUrl('static/images/info.png');
      imgElement.width = 16;
      imgElement.height = 16;
      imgElement.alt = 'Info';
      infoIcon.appendChild(imgElement);
      infoIcon.style.fontSize = '0.5em';
      infoIcon.style.position = 'relative';
      
      // Create popup element
      infoIcon.title = `${item.explanation || ''} (score=${item.score || 0}) (Ranking time=${item.time || 0})`;
      titleRow.appendChild(infoIcon);
  
      contentDiv.appendChild(titleRow);
  
      // Description
      const description = document.createElement('div');
      description.textContent = item.description || '';
      description.style.fontSize = '0.9em';
      contentDiv.appendChild(description);

      if (this.display_mode == "nlwebsearch") {
          // visible url
          const visibleUrl = document.createElement("div");
          const visibleUrlLink = document.createElement("a");
          // FIX: Use sanitizeUrl for URL attributes and add security attributes
          const sanitizedSiteUrl = item.siteUrl ? this.sanitizeUrl(item.siteUrl) : '#';
          visibleUrlLink.href = sanitizedSiteUrl;
          // Add rel="noopener noreferrer" for external links
          if (sanitizedSiteUrl !== '#' && !sanitizedSiteUrl.startsWith(window.location.origin)) {
              visibleUrlLink.rel = "noopener noreferrer";
              visibleUrlLink.target = "_blank";
          }
          // Sanitize the site text content to prevent XSS
          visibleUrlLink.textContent = this.htmlUnescape(item.site || '');
          visibleUrlLink.style.fontSize = "0.9em";
          visibleUrlLink.style.textDecoration = "none";
          visibleUrlLink.style.color = "#2962ff";
          visibleUrlLink.style.fontWeight = "500";
          visibleUrlLink.style.padding = "8px 0";
          visibleUrlLink.style.display = "inline-block";
          contentDiv.appendChild(visibleUrlLink);
      }
      this.typeSpecificContent(item, contentDiv);

      // Feedback icons
      const feedbackDiv = document.createElement('div');
      feedbackDiv.style.display = 'flex';
      feedbackDiv.style.gap = '0.5em';
      feedbackDiv.style.marginTop = '0.5em';

      const thumbsUp = document.createElement('span');
      thumbsUp.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="#D3D3D3">
        <path d="M2 20h2c.55 0 1-.45 1-1v-9c0-.55-.45-1-1-1H2v11zm19.83-7.12c.11-.25.17-.52.17-.8V11c0-1.1-.9-2-2-2h-5.5l.92-4.65c.05-.22.02-.46-.08-.66-.23-.45-.52-.86-.88-1.22L14 2 7.59 8.41C7.21 8.79 7 9.3 7 9.83v7.84C7 18.95 8.05 20 9.34 20h8.11c.7 0 1.36-.37 1.72-.97l2.66-6.15z"/>
      </svg>`;
      thumbsUp.style.fontSize = '0.8em';
      thumbsUp.style.cursor = 'pointer';

      const thumbsDown = document.createElement('span');
      thumbsDown.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="#D3D3D3">
        <path d="M15 3H6c-.83 0-1.54.5-1.84 1.22l-3.02 7.05c-.09.23-.14.47-.14.73v2c0 1.1.9 2 2 2h6.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L9.83 23l6.59-6.59c.36-.36.58-.86.58-1.41V5c0-1.1-.9-2-2-2zm4 0v12h4V3h-4z"/>
      </svg>`;
      thumbsDown.style.fontSize = '0.8em'; 
      thumbsDown.style.cursor = 'pointer';

      feedbackDiv.appendChild(thumbsUp);
      feedbackDiv.appendChild(thumbsDown);
      contentDiv.appendChild(feedbackDiv);
  
      container.appendChild(contentDiv);
  
      // Check for image in schema object
      if (item.schema_object) {
          const imgURL = this.extractImage(item.schema_object);
          if (imgURL) {
              const imageDiv = document.createElement('div');
              const img = document.createElement('img');
              // FIX: Sanitize URL and verify it's an acceptable image URL
              const sanitizedUrl = this.sanitizeUrl(imgURL);
              if (sanitizedUrl !== '#') {
                  img.src = sanitizedUrl;
                  img.width = 80;
                  img.height = 80;
                  img.style.objectFit = 'cover';
                  img.alt = 'Item image';
                  // Add onerror handler to handle broken images
                  img.onerror = function() {
                      this.style.display = 'none';
                  };
                  imageDiv.appendChild(img);
                  container.appendChild(imageDiv);
              }
          }
      }
  
      return container;
    }
  
    // Add sanitizeUrl function if it doesn't exist
    sanitizeUrl(url) {
      // Return a safe default if input is null, undefined, or not a string
      if (!url || typeof url !== 'string') return '#';
      
      // Remove leading and trailing whitespace
      const trimmedUrl = url.trim();
      
      try {
        // Check for dangerous protocols using a more comprehensive approach
        const dangerousProtocols = /^(javascript|data|vbscript|file):/i;
        if (dangerousProtocols.test(trimmedUrl)) {
          return '#';
        }
        
        // Try to parse the URL - this will throw for malformed URLs
        const parsedUrl = new URL(trimmedUrl, window.location.origin);
        
        // Only allow specific protocols
        if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
          return '#';
        }
        
        // Return the sanitized URL
        return parsedUrl.toString();
      } catch (e) {
        // If URL parsing fails or any other error occurs, return a safe default
        console.warn("Invalid URL detected and sanitized:", url);
        return '#';
      }
    }

    quickHash(string) {
      let hash = 0;
      for (let i = 0; i < string.length; i++) {
          const char = string.charCodeAt(i);
          hash = (hash << 5) - hash + char;
          hash |= 0; // Convert to 32-bit integer
      }
      return hash;
  }

   possiblyAnnotateUserQuery(chatInterface, decontextualizedQuery) {
    const msgDiv = chatInterface.lastUserMessageDiv;
    if (msgDiv) {
 //     msgDiv.innerHTML = chatInterface.currentMessage + "<br><span class=\"decontextualized-query\">" + decontextualizedQuery + "</span>";
    }
  }

  createIntermediateMessageHtml(message) {
    const container = document.createElement('div');
    container.className = 'intermediate-container';
    container.textContent = message;
    return container;
  }

  memoryMessage(itemToRemember, chatInterface) { 
    if (itemToRemember) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `remember-message`;
        messageDiv.textContent = itemToRemember;
        chatInterface.thisRoundRemembered = messageDiv;
        chatInterface.bubble.appendChild(messageDiv);
        return messageDiv;
    }
  }

  askUserMessage(message, chatInterface) { 
    console.log("askUserMessage", message);
    const messageDiv = document.createElement('div');
    messageDiv.className = `ask-user-message`;
    messageDiv.textContent = message;
    chatInterface.bubble.appendChild(messageDiv);
  }

  siteIsIrrelevantToQuery(message, chatInterface) { 
    console.log("siteIsIrrelevantToQuery", message);
    const messageDiv = document.createElement('div');
    messageDiv.className = `site-is-irrelevant-to-query`;
    messageDiv.textContent = message;
    chatInterface.bubble.appendChild(messageDiv);
  }

  itemDetailsMessage(itemDetails, chatInterface) { 
     if (itemDetails) {
         const messageDiv = document.createElement('div');
         messageDiv.className = `item-details-message`;
         messageDiv.textContent = itemDetails;
         chatInterface.thisRoundRemembered = messageDiv;
         chatInterface.bubble.appendChild(messageDiv);
         return messageDiv;
     }
   }
  
    resortResults(chatInterface) {
      if (chatInterface.currentItems.length > 0) {
        chatInterface.currentItems.sort((a, b) => b[0].score - a[0].score);
      // Clear existing children
        while (chatInterface.bubble.firstChild) {
          chatInterface.bubble.removeChild(chatInterface.bubble.firstChild);
        }
        if (chatInterface.thisRoundRemembered) {
          chatInterface.bubble.appendChild(chatInterface.thisRoundRemembered)
        }
        if (chatInterface.sourcesMessage) {
          chatInterface.bubble.appendChild(chatInterface.sourcesMessage)
        }
        if (chatInterface.thisRoundSummary) {
          chatInterface.bubble.appendChild(chatInterface.thisRoundSummary)
        }
        // Add sorted domItems back to bubble
        for (const [item, domItem] of chatInterface.currentItems) {
          chatInterface.bubble.appendChild(domItem);
        }
      }
    }


    createInsufficientResultsHtml() {
      const container = document.createElement('div');
      container.className = 'intermediate-container';
      container.appendChild(document.createElement('br'));
      if (this.currentItems.length > 0) {
        container.textContent = "I couldn't find any more results that are relevant to your query.";
      } else {
        container.textContent = "I couldn't find any results that are relevant to your query.";
      }
      container.appendChild(document.createElement('br'));
      return container;
    }
  
    handleFirstMessage(event) {
      this.dotsStillThere = false;
      this.messagesArea.removeChild(this.messagesArea.lastChild);
    }
  
    async getResponse(message) {
      // Add loading state
      const loadingDots = '...';
      this.addMessage(loadingDots, 'assistant');
      this.dotsStillThere = true;
   
      try {
        console.log("generate_mode", this.generate_mode);
        const selectedSite = this.site || (this.siteSelect && this.siteSelect.value ? this.siteSelect.value : '');
        const prev = JSON.stringify(this.prevMessages);
        const generate_mode = this.generate_mode;
        const context_url = this.context_url && this.context_url.value ? this.context_url.value : '';
        // Generate a unique query ID based on query arguments and current timestamp
        const timestamp = new Date().getTime();
        const queryId = `query_${timestamp}_${Math.floor(Math.random() * 1000)}`;
        console.log("Generated query ID:", queryId);
        
        // Add the query ID to the request parameters
        const queryParams = new URLSearchParams();
        queryParams.append('query_id', queryId);
        queryParams.append('query', message);
        if (selectedSite) {
          queryParams.append('site', selectedSite);
        } 
        queryParams.append('generate_mode', generate_mode);
        queryParams.append('prev', prev);
        queryParams.append('item_to_remember', this.itemToRemember || '');
        queryParams.append('context_url', context_url);
        
        const queryString = queryParams.toString();
        const url = `/ask?${queryString}`;
        console.log("url", url);
        this.eventSource = new ManagedEventSource(url);
        this.eventSource.query_id = queryId;
        this.eventSource.connect(this);
        this.prevMessages.push(message);
        return
      } catch (error) {
        console.error('Error fetching response:', error);
      }
    }

    createDebugString() {
      return jsonLdToHtml(this.currentItems);
    }
  }

    function jsonLdToHtml(jsonLd) {
      // Helper function to escape HTML special characters
      const escapeHtml = (str) => {
          return str
              .replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#039;');
      };
  
      // Helper function to format a single value
      const formatValue = (value, indent) => {
          const spaces = '  '.repeat(indent);
          
          if (value === null) {
              return `<span class="null">null</span>`;
          }
          
          switch (typeof value) {
              case 'string':
                  // Special handling for URLs and IRIs in JSON-LD
                  if (value.startsWith('http://') || value.startsWith('https://')) {
                      return `<span class="string url">"${escapeHtml(value)}"</span>`;
                  }
                  return `<span class="string">"${escapeHtml(value)}"</span>`;
              case 'number':
                  return `<span class="number">${value}</span>`;
              case 'boolean':
                  return `<span class="boolean">${value}</span>`;
              case 'object':
                  if (Array.isArray(value)) {
                      if (value.length === 0) return '[]';
                      const items = value.map(item => 
                          `${spaces}  ${formatValue(item, indent + 1)}`
                      ).join(',\n');
                      return `[\n${items}\n${spaces}]`;
                  }
                  return formatObject(value, indent);
          }
      };
  
      // Helper function to format an object
      const formatObject = (obj, indent = 0) => {
          const spaces = '  '.repeat(indent);
          
          if (Object.keys(obj).length === 0) return '{}';
          
          const entries = Object.entries(obj).map(([key, value]) => {
              // Special handling for JSON-LD keywords (starting with @)
              const keySpan = key.startsWith('@') 
                  ? `<span class="keyword">"${escapeHtml(key)}"</span>`
                  : `<span class="key">"${escapeHtml(key)}"</span>`;
                  
              return `${spaces}  ${keySpan}: ${formatValue(value, indent + 1)}`;
          });
          
          return `{\n${entries.join(',\n')}\n${spaces}}`;
      };
  
      // Main formatting logic
      try {
          const parsed = (typeof jsonLd === 'string') ? JSON.parse(jsonLd) : jsonLd;
          const formatted = formatObject(parsed);
          
          // Return complete HTML with styling
          return `<pre class="json-ld"><code>${formatted}</code></pre>
  <style>
  .json-ld {
      background-color: #f5f5f5;
      padding: 1em;
      border-radius: 4px;
      font-family: monospace;
      line-height: 1.5;
  }
  .json-ld .keyword { color: #e91e63; }
  .json-ld .key { color: #2196f3; }
  .json-ld .string { color: #4caf50; }
  .json-ld .string.url { color: #9c27b0; }
  .json-ld .number { color: #ff5722; }
  .json-ld .boolean { color: #ff9800; }
  .json-ld .null { color: #795548; }
  </style>`;
      } catch (error) {
          return `<pre class="json-ld error">Error: ${error.message}</pre>`;
      }
  }

export { ChatInterface, ManagedEventSource };