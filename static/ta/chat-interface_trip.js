/**
 * ChatInterface Class
 * Handles the UI and message processing for the chat interface
 */

import { ManagedEventSource } from './managed-event-source.js';
import { jsonLdToHtml } from './utils.js';


export class ChatInterface {
  /**
   * Creates a new ChatInterface
   * 
   * @param {string} site - The site to use for search
   * @param {string} display_mode - The display mode
   * @param {string} generate_mode - The generate mode
   * @param {boolean} appendElements - Whether to append interface elements immediately
   */
  constructor(site = null, display_mode = "dropdown", generate_mode = "list", appendElements = true) {
    // Initialize properties
    this.site = site;
    this.display_mode = display_mode;
    this.generate_mode = generate_mode;
    this.eventSource = null;
    this.dotsStillThere = false;
    this.debug_mode = false;
    
    // Parse URL parameters
    this.parseUrlParams();
    
    // Create UI elements but don't append yet if appendElements is false
    this.createInterface(display_mode, appendElements);
    this.bindEvents();
    
    // Reset state
    this.resetChatState();
    
    // Process initial query if provided in URL
    if (this.initialQuery) {
      this.sendMessage(decodeURIComponent(this.initialQuery));
    }
  }

  /**
   * Parses URL parameters for configuration
   */
  parseUrlParams() {
    const urlParams = new URLSearchParams(window.location.search);
    this.initialQuery = urlParams.get('query');
    const prevMessagesStr = urlParams.get('prev');
    const contextUrl = urlParams.get('context_url');
    const urlGenerateMode = urlParams.get('generate_mode');
    
    if (urlGenerateMode) {
      this.generate_mode = urlGenerateMode;
    }
    
    this.prevMessages = prevMessagesStr ? JSON.parse(decodeURIComponent(prevMessagesStr)) : [];
  }

  /**
   * Resets the chat state
   */
  resetChatState() {
    if (this.messagesArea) {
      this.messagesArea.innerHTML = '';
    }
    this.messages = [];
    this.prevMessages = this.prevMessages || [];
    this.currentMessage = [];
    this.currentItems = [];
    this.itemToRemember = [];
    this.thisRoundSummary = null;
    this.num_results_sent = 0;
  }

  /**
   * Creates the interface elements
   * 
   * @param {string} display_mode - The display mode
   * @param {boolean} appendElements - Whether to append elements immediately
   */
  createInterface(display_mode = "dropdown", appendElements = true) {
    // Get main container reference but don't append to it yet
    this.container = document.getElementById('chat-container');
    
    // Create messages area
    this.messagesArea = document.createElement('div');
    this.messagesArea.className = (display_mode === "dropdown" ? 'messages' : 'messages_full');
    
    // Create input area
    this.inputArea = document.createElement('div');
    this.inputArea.className = (display_mode === "dropdown" ? 'input-area' : 'input-area_full');

    // Create input field
    this.input = document.createElement('textarea');
    this.input.className = 'message-input';
    this.input.placeholder = 'Type your message...';
    this.input.style.minHeight = '60px'; // Set minimum height
    this.input.style.height = '60px'; // Initial height
    this.input.rows = 1; // Start with one row
    this.input.style.resize = 'none'; // Prevent manual resizing
    this.input.style.overflow = 'hidden'; // Hide scrollbar

    // Create send button
    this.sendButton = document.createElement('button');
    this.sendButton.className = 'send-button';
    this.sendButton.textContent = 'Send';

    // Assemble the input area
    this.inputArea.appendChild(this.input);
    this.inputArea.appendChild(this.sendButton);
    
    // Append to container if requested
    if (appendElements) {
      this.appendInterfaceElements(this.container);
    }
  }
  
  /**
   * Appends the interface elements to the specified container
   * 
   * @param {HTMLElement} container - The container to append to
   */
  appendInterfaceElements(container) {
    container.appendChild(this.messagesArea);
    container.appendChild(this.inputArea);
  }

  /**
   * Binds event handlers to UI elements
   */
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
    
    // Auto-resize textarea based on content
    this.input.addEventListener('input', () => {
      // Reset height to auto first to correctly calculate new height
      this.input.style.height = 'auto';
      
      // Set new height based on scrollHeight, with a minimum height
      const newHeight = Math.max(60, Math.min(this.input.scrollHeight, 150));
      this.input.style.height = newHeight + 'px';
    });
  }

  /**
   * Sends a message
   * 
   * @param {string} query - The message to send
   */
  sendMessage(query = null) {
    const message = query || this.input.value.trim();
    if (!message) return;

    // Add user message
    this.addMessage(message, 'user');
    this.currentMessage = message;
    
    // Clear input and reset placeholder text
    this.input.value = '';
    this.input.placeholder = 'Type your message...';
    
    // Reset input field height
    this.input.style.height = '60px';

    // Get response
    this.getResponse(message);
  }

  /**
   * Adds a message to the chat
   * 
   * @param {string} content - The message content
   * @param {string} sender - The sender (user or assistant)
   */
  addMessage(content, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    if (sender === "user") {
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
    
    if (Array.isArray(parsedContent)) {
      bubble.innerHTML = parsedContent.map(obj => {
        return this.createJsonItemHtml(obj).outerHTML;
      }).join('<br><br>');
    } else {
      bubble.textContent = content;
    }

    messageDiv.appendChild(bubble);
    this.messagesArea.appendChild(messageDiv);
    
    // Scroll to the bottom to show the new message
    this.scrollToBottom();

    this.messages.push({ content, sender });
    this.currentMessage = "";
  }
  
  /**
   * Scrolls the message area to the bottom
   */
  scrollToBottom() {
    this.messagesArea.scrollTop = this.messagesArea.scrollHeight;
  }

  /**
   * Gets a response for the user's message
   * 
   * @param {string} message - The user's message
   */
  async getResponse(message) {
    // Add loading state
    const loadingDots = '...';
    this.addMessage(loadingDots, 'assistant');
    this.dotsStillThere = true;
 
    try {
      console.log("generate_mode", this.generate_mode);
      const selectedSite = (this.site || (this.siteSelect && this.siteSelect.value));
      const prev = JSON.stringify(this.prevMessages);
      const generate_mode = this.generate_mode;
      const context_url = this.context_url && this.context_url.value ? this.context_url.value : '';
      
      // Generate a unique query ID
      const timestamp = new Date().getTime();
      const queryId = `query_${timestamp}_${Math.floor(Math.random() * 1000)}`;
      console.log("Generated query ID:", queryId);
      
      // Build query parameters
      const queryParams = new URLSearchParams();
      queryParams.append('query_id', queryId);
      queryParams.append('query', message);
      queryParams.append('site', selectedSite);
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
    } catch (error) {
      console.error('Error fetching response:', error);
    }
  }

  /**
   * Handles the first message by removing loading dots
   */
  handleFirstMessage() {
    this.dotsStillThere = false;
    this.messagesArea.removeChild(this.messagesArea.lastChild);
  }

  /**
   * Creates HTML for a JSON item (TripAdvisor chat style)
   * @param {Object} item - The item data
   * @returns {HTMLElement} - The HTML element
   */
  createJsonItemHtml(item) {
    const container = document.createElement('div');
    container.className = 'item-container';

    // Image (left)
    let imgURL = null;
    if (item.schema_object) {
      imgURL = this.extractImage(item.schema_object);
    }
    if (imgURL) {
      const img = document.createElement('img');
      //update and find the actual image link
      //img.src = imgURL;
      img.src =  this.extractOriginalPngUrl(imgURL);
      img.className = 'item-image';
      img.alt = item.name || '';
      container.appendChild(img);
    }

    // Content (right)
    const contentDiv = document.createElement('div');
    contentDiv.className = 'item-content';

    // Label (e.g. HOTEL, THINGS TO DO)
    let label = '';
    if (item.schema_object && item.schema_object['@type']) {
      const type = item.schema_object['@type'];
      if (typeof type === 'string') label = type;
      else if (Array.isArray(type)) label = type[0];
      // Map schema types to display labels
      if (label.toLowerCase().includes('hotel')) label = 'HOTEL';
      else if (label.toLowerCase().includes('thing')) label = 'THINGS TO DO';
      else label = label.toUpperCase();
    }
    if (label) {
      const labelDiv = document.createElement('div');
      labelDiv.className = 'item-label';
      labelDiv.textContent = label;
      contentDiv.appendChild(labelDiv);
    }

    // Title (bold, link if url exists)
    const title = item.name || (item.schema_object && item.schema_object.name) || '';
    if (title) {
      const titleEl = document.createElement(item.url ? 'a' : 'span');
      titleEl.className = 'item-title';
      titleEl.textContent = title;
      if (item.url) {
        titleEl.href = item.url;
        titleEl.target = '_blank';
        titleEl.rel = 'noopener noreferrer';
      }
      contentDiv.appendChild(titleEl);
    }

    // Rating row (stars, score, reviews)
    const ratingRow = document.createElement('div');
    ratingRow.className = 'item-rating-row';
    // Score (e.g. 5.0)
    let score = '';
    if (item.schema_object && item.schema_object.aggregateRating && item.schema_object.aggregateRating.ratingValue) {
      score = item.schema_object.aggregateRating.ratingValue;
    } else if (item.rating) {
      score = item.rating;
    }
    if (score) {
      const scoreSpan = document.createElement('span');
      scoreSpan.className = 'item-rating-score';
      scoreSpan.textContent = score;
      ratingRow.appendChild(scoreSpan);
    }
    // Stars (SVG)
    if (score) {
      const starsSpan = document.createElement('span');
      starsSpan.className = 'item-rating-stars';
      const fullStars = Math.floor(Number(score));
      const halfStar = Number(score) - fullStars >= 0.5;
      let starsHTML = '';
      for (let i = 0; i < fullStars; i++) {
        starsHTML += '<svg width="16" height="16" viewBox="0 0 24 24" fill="#34e0a1" stroke="none"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>';
      }
      if (halfStar) {
        starsHTML += '<svg width="16" height="16" viewBox="0 0 24 24" fill="#34e0a1" stroke="none"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2v15.27z"/></svg>';
      }
      starsSpan.innerHTML = starsHTML;
      ratingRow.appendChild(starsSpan);
    }
    // Reviews (e.g. (693 reviews))
    let reviews = '';
    if (item.schema_object && item.schema_object.aggregateRating && item.schema_object.aggregateRating.reviewCount) {
      reviews = item.schema_object.aggregateRating.reviewCount;
    } else if (item.reviews) {
      reviews = item.reviews;
    }
    if (reviews) {
      const reviewsSpan = document.createElement('span');
      reviewsSpan.className = 'item-reviews';
      reviewsSpan.textContent = `(${reviews} reviews)`;
      ratingRow.appendChild(reviewsSpan);
    }
    if (score || reviews) {
      contentDiv.appendChild(ratingRow);
    }

    // Location (green)
    let location = '';
    if (item.schema_object && item.schema_object.address && item.schema_object.address.addressLocality) {
      location = item.schema_object.address.addressLocality;
    } else if (item.location) {
      location = item.location;
    } else if (item.schema_object && item.schema_object.location && typeof item.schema_object.location === 'string') {
      location = item.schema_object.location;
    }
    if (location) {
      const locationDiv = document.createElement('div');
      locationDiv.className = 'item-location';
      locationDiv.textContent = location;
      contentDiv.appendChild(locationDiv);
    }

    // Description (gray)
    const desc = item.description || (item.schema_object && item.schema_object.description) || '';
    if (desc) {
      const descDiv = document.createElement('div');
      descDiv.className = 'item-description';
      descDiv.textContent = desc;
      contentDiv.appendChild(descDiv);
    }

    container.appendChild(contentDiv);
    return container;
  }

  /**
   * Adds event details to the content div
   * 
   * @param {Object} item - The item data
   * @param {HTMLElement} contentDiv - The content div
   */
  addEventDetails(item, contentDiv) {
    const eventDetailsDiv = document.createElement('div');
    eventDetailsDiv.className = 'item-event-details';
    
    // Extract event details from schema or description
    let dateTime = '';
    let location = '';
    let price = '';
    
    // Try to extract from schema object first
    if (item.schema_object) {
      const schema = item.schema_object;
      
      // Get date and time
      if (schema.startDate) {
        const date = new Date(schema.startDate);
        const options = { weekday: 'long', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' };
        dateTime = date.toLocaleDateString('en-US', options);
      }
      
      // Get location
      if (schema.location) {
        if (typeof schema.location === 'object') {
          location = schema.location.name || '';
        } else {
          location = schema.location;
        }
      }
      
      // Get price
      if (schema.offers && schema.offers.price) {
        price = typeof schema.offers.price === 'number' ? 
          `From $${schema.offers.price.toFixed(2)}` : 
          `From ${schema.offers.price}`;
      }
    }
    
    // If no schema or missing data, try to extract from item description or other properties
    if (!dateTime && (item.name && item.name.toLowerCase().includes('tomorrow'))) {
      dateTime = 'Tomorrow, 7:30 PM';
    }
    
    if (!location && item.venue) {
      location = item.venue;
    }
    
    if (!price && item.price) {
      price = item.price;
    }
    
    // Fallback to simple data extraction from the item
    if (!dateTime) {
      dateTime = item.dateTime || 'Tomorrow, 7:30 PM';
    }
    
    if (!location) {
      location = item.location || '';
    }
    
    if (!price) {
      price = item.price || (item.explanation && item.explanation.includes('$') ? 
              'From ' + item.explanation.match(/\$[\d\.]+/)[0] : '');
    }
    
    // Create and append elements if we have data
    if (dateTime) {
      const dateTimeElement = document.createElement('div');
      dateTimeElement.className = 'event-datetime';
      dateTimeElement.textContent = dateTime;
      eventDetailsDiv.appendChild(dateTimeElement);
    }
    
    if (location) {
      const locationElement = document.createElement('div');
      locationElement.className = 'event-location';
      locationElement.textContent = location;
      eventDetailsDiv.appendChild(locationElement);
    }
    
    if (price) {
      const priceElement = document.createElement('div');
      priceElement.className = 'event-price';
      priceElement.textContent = price;
      eventDetailsDiv.appendChild(priceElement);
    }
    
    // Only append the details div if it has content
    if (eventDetailsDiv.children.length > 0) {
      contentDiv.appendChild(eventDetailsDiv);
    } else {
      // If no specific event details were found, fall back to explanation
      this.possiblyAddExplanation(item, contentDiv);
    }
  }
  
  /**
   * Adds an action row with interactive icons
   * 
   * @param {HTMLElement} contentDiv - The content div
   */
  addActionRow(contentDiv) {
    const actionRow = document.createElement('div');
    actionRow.className = 'item-action-row';
    
    // Add share icon
    const shareIcon = document.createElement('img');
    shareIcon.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLXNoYXJlLTIiPjxjaXJjbGUgY3g9IjE4IiBjeT0iNSIgcj0iMyIvPjxjaXJjbGUgY3g9IjYiIGN5PSIxMiIgcj0iMyIvPjxjaXJjbGUgY3g9IjE4IiBjeT0iMTkiIHI9IjMiLz48bGluZSB4MT0iOC41OSIgeTE9IjEzLjUxIiB4Mj0iMTUuNDIiIHkyPSIxNy40OSIvPjxsaW5lIHgxPSIxNS40MSIgeTE9IjYuNTEiIHgyPSI4LjU5IiB5Mj0iMTAuNDkiLz48L3N2Zz4=';
    shareIcon.className = 'item-action-icon';
    shareIcon.alt = 'Share';
    shareIcon.title = 'Share';
    
    // Add save icon
    const saveIcon = document.createElement('img');
    saveIcon.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWJvb2ttYXJrIj48cGF0aCBkPSJNMTkgMjFsLTctNS03IDVWNWEyIDIgMCAwIDEgMi0yaDEwYTIgMiAwIDAgMSAyIDJ6Ii8+PC9zdmc+';
    saveIcon.className = 'item-action-icon';
    saveIcon.alt = 'Save';
    saveIcon.title = 'Save';
    
    // Add heart/like icon
    const likeIcon = document.createElement('img');
    likeIcon.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGNsYXNzPSJsdWNpZGUgbHVjaWRlLWhlYXJ0Ij48cGF0aCBkPSJNMTkgMTRjMS40OS0xLjQ2IDMtMy44IDMtNS41QTUuNSA1LjUgMCAwIDAgMTYuNSAzYy0xLjggMC0zIDEtNCAyLjUtMSAtMS41LTIuMi0yLjUtNC0yLjVBNS41IDUuNSAwIDAgMCAzIDguNWMwIDEuNyAxLjUxIDQuMDQgMyA1LjVMMTIgMjBsNi02WiIvPjwvc3ZnPg==';
    likeIcon.className = 'item-action-icon';
    likeIcon.alt = 'Like';
    likeIcon.title = 'Like';
    
    // Append icons to action row
    actionRow.appendChild(shareIcon);
    actionRow.appendChild(saveIcon); 
    actionRow.appendChild(likeIcon);
    
    contentDiv.appendChild(actionRow);
  }

  /**
   * Creates a title row for an item
   * 
   * @param {Object} item - The item data
   * @param {HTMLElement} contentDiv - The content div
   */
  createTitleRow(item, contentDiv) {
    const titleRow = document.createElement('div');
    titleRow.className = 'item-title-row';

    // Title/link
    const titleLink = document.createElement('a');
    titleLink.href = item.url;
    const itemName = this.getItemName(item);
    titleLink.textContent = this.htmlUnescape(itemName);
    titleLink.className = 'item-title-link';
    titleRow.appendChild(titleLink);

    // Info icon
    const infoIcon = document.createElement('span');
    infoIcon.innerHTML = '<img src="images/info.png">';
    infoIcon.className = 'item-info-icon';
    infoIcon.title = item.explanation + "(score=" + item.score + ")" + "(Ranking time=" + item.time + ")";
    titleRow.appendChild(infoIcon);

    contentDiv.appendChild(titleRow);
  }
  
  /**
   * Adds a visible URL to the content div
   * 
   * @param {Object} item - The item data
   * @param {HTMLElement} contentDiv - The content div
   */
  addVisibleUrl(item, contentDiv) {
    const visibleUrlLink = document.createElement("a");
    visibleUrlLink.href = item.siteUrl;
    visibleUrlLink.textContent = item.site;
    visibleUrlLink.className = 'item-site-link';
    contentDiv.appendChild(visibleUrlLink);
  }
  
  /**
   * Adds an image to the item if available
   * 
   * @param {Object} item - The item data
   * @param {HTMLElement} container - The container element
   */
  addImageIfAvailable(item, container) {
    if (item.schema_object) {
      const imgURL = this.extractImage(item.schema_object);
      if (imgURL) {
        const img = document.createElement('img');
        img.src = imgURL;
        img.className = 'item-image';
        container.insertBefore(img, container.firstChild); // Ensure image is on the left
      }
    }
  }
  
  /**
   * Gets the name of an item
   * 
   * @param {Object} item - The item data
   * @returns {string} - The item name
   */
  getItemName(item) {
    if (item.name) {
      return item.name;
    } else if (item.schema_object && item.schema_object.keywords) {
      return item.schema_object.keywords;
    }
    return item.url;
  }
  
  /**
   * Adds type-specific content to the item
   * 
   * @param {Object} item - The item data
   * @param {HTMLElement} contentDiv - The content div
   */
  typeSpecificContent(item, contentDiv) {
    if (!item.schema_object) {
      return;
    }
    
    const objType = item.schema_object['@type'];
    const houseTypes = ["SingleFamilyResidence", "Apartment", "Townhouse", "House", "Condominium", "RealEstateListing"];
    
    if (objType === "PodcastEpisode") {
      this.possiblyAddExplanation(item, contentDiv, true);
      return;
    }
    
    if (houseTypes.includes(objType)) {
      this.addRealEstateDetails(item, contentDiv);
    }
  }
  
  /**
   * Adds real estate details to an item
   * 
   * @param {Object} item - The item data
   * @param {HTMLElement} contentDiv - The content div
   */
  addRealEstateDetails(item, contentDiv) {
    const detailsDiv = this.possiblyAddExplanation(item, contentDiv, true);
    detailsDiv.className = 'item-real-estate-details';
    
    const schema = item.schema_object;
    const price = schema.price;
    const address = schema.address;
    const numBedrooms = schema.numberOfRooms;
    const numBathrooms = schema.numberOfBathroomsTotal;
    const sqft = schema.floorSize?.value;
    
    let priceValue = price;
    if (typeof price === 'object') {
      priceValue = price.price || price.value || price;
      priceValue = Math.round(priceValue / 100000) * 100000;
      priceValue = priceValue.toLocaleString('en-US');
    }

    detailsDiv.appendChild(this.makeAsSpan(address.streetAddress + ", " + address.addressLocality));
    detailsDiv.appendChild(document.createElement('br'));
    detailsDiv.appendChild(this.makeAsSpan(`${numBedrooms} bedrooms, ${numBathrooms} bathrooms, ${sqft} sqft`));
    detailsDiv.appendChild(document.createElement('br'));
    
    if (priceValue) {
      detailsDiv.appendChild(this.makeAsSpan(`Listed at ${priceValue}`));
    }
  }
  
  /**
   * Creates a span element with the given content
   * 
   * @param {string} content - The content for the span
   * @returns {HTMLElement} - The span element
   */
  makeAsSpan(content) {
    const span = document.createElement('span');
    span.textContent = content;
    span.className = 'item-details-text';
    return span;
  }

  /**
   * Adds an explanation to an item
   * 
   * @param {Object} item - The item data
   * @param {HTMLElement} contentDiv - The content div
   * @param {boolean} force - Whether to force adding the explanation
   * @returns {HTMLElement} - The details div
   */
  possiblyAddExplanation(item, contentDiv, force = false) {
    const detailsDiv = document.createElement('div'); 
    contentDiv.appendChild(document.createElement('br'));
    const explSpan = this.makeAsSpan(item.explanation);
    explSpan.className = 'item-explanation';
    detailsDiv.appendChild(explSpan);
    contentDiv.appendChild(detailsDiv);
    return detailsDiv;
  }

  /**
   * Extracts an image URL from a schema object
   * 
   * @param {Object} schema_object - The schema object
   * @returns {string|null} - The image URL or null
   */
  extractImage(schema_object) {
    if (schema_object && schema_object.image) {
      return this.extractImageInternal(schema_object.image);
    }
    return null;
  }

  /**
   * Extracts an image URL from various image formats
   * 
   * @param {*} image - The image data
   * @returns {string|null} - The image URL or null
   */
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


  /**
   * Fix:allbirds image high res
   * 
   * @param {url} imageurl - The low-res image url
   * @returns {string|null} - The actual image URL or null
   */
  extractOriginalPngUrl(url) {
    if (!url || typeof url !== 'string') {
      return '';
    }
    
    // Find the position of .png or .jpg/.jpeg in the URL (case insensitive)
    const pngIndex = url.toLowerCase().indexOf('.png');
    const jpgIndex = url.toLowerCase().indexOf('.jpg');
    const jpegIndex = url.toLowerCase().indexOf('.jpeg');
    
    // Get the appropriate index based on which extension was found
    let extensionIndex = -1;
    let extensionLength = 0;
    
    if (pngIndex !== -1) {
      extensionIndex = pngIndex;
      extensionLength = 4; // .png
    } else if (jpegIndex !== -1) {
      extensionIndex = jpegIndex;
      extensionLength = 5; // .jpeg
    } else if (jpgIndex !== -1) {
      extensionIndex = jpgIndex;
      extensionLength = 4; // .jpg
    }
    
    // If none of the extensions were found, return the original URL
    if (extensionIndex === -1) {
      return url;
    }
    
    // Return the URL up to and including the extension
    return url.substring(0, extensionIndex + extensionLength);
  }



  /**
   * Unescapes HTML entities in a string
   * 
   * @param {string} str - The string to unescape
   * @returns {string} - The unescaped string
   */
  htmlUnescape(str) {
    const div = document.createElement("div");
    div.innerHTML = str;
    return div.textContent || div.innerText;
  }

  /**
   * Generates a quick hash for a string
   * 
   * @param {string} string - The string to hash
   * @returns {number} - The hash value
   */
  quickHash(string) {
    let hash = 0;
    for (let i = 0; i < string.length; i++) {
      const char = string.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash |= 0; // Convert to 32-bit integer
    }
    return hash;
  }

  /**
   * Creates an HTML element for an intermediate message
   * 
   * @param {string} message - The message
   * @returns {HTMLElement} - The HTML element
   */
  createIntermediateMessageHtml(message) {
    const container = document.createElement('div');
    container.className = 'intermediate-container';
    container.textContent = message;
    return container;
  }

  /**
   * Displays a memory message
   * 
   * @param {string} itemToRemember - The item to remember
   * @param {Object} chatInterface - The chat interface instance
   * @returns {HTMLElement} - The message element
   */
  memoryMessage(itemToRemember, chatInterface) { 
    if (itemToRemember) {
      const messageDiv = document.createElement('div');
      messageDiv.className = 'remember-message';
      messageDiv.textContent = itemToRemember;
      chatInterface.thisRoundRemembered = messageDiv;
      chatInterface.bubble.appendChild(messageDiv);
      return messageDiv;
    }
  }

  /**
   * Displays an ask user message
   * 
   * @param {string} message - The message
   * @param {Object} chatInterface - The chat interface instance
   */
  askUserMessage(message, chatInterface) { 
    console.log("askUserMessage", message);
    const messageDiv = document.createElement('div');
    messageDiv.className = 'ask-user-message';
    messageDiv.textContent = message;
    chatInterface.bubble.appendChild(messageDiv);
  }

  /**
   * Displays a site is irrelevant to query message
   * 
   * @param {string} message - The message
   * @param {Object} chatInterface - The chat interface instance
   */
  siteIsIrrelevantToQuery(message, chatInterface) { 
    console.log("siteIsIrrelevantToQuery", message);
    const messageDiv = document.createElement('div');
    messageDiv.className = 'site-is-irrelevant-to-query';
    messageDiv.textContent = message;
    chatInterface.bubble.appendChild(messageDiv);
  }

  /**
   * Displays an item details message
   * 
   * @param {string} itemDetails - The item details
   * @param {Object} chatInterface - The chat interface instance
   * @returns {HTMLElement} - The message element
   */
  itemDetailsMessage(itemDetails, chatInterface) { 
    if (itemDetails) {
      const messageDiv = document.createElement('div');
      messageDiv.className = 'item-details-message';
      messageDiv.textContent = itemDetails;
      chatInterface.thisRoundRemembered = messageDiv;
      chatInterface.bubble.appendChild(messageDiv);
      return messageDiv;
    }
  }

  /**
   * Annotates the user query with decontextualized query
   * 
   * @param {string} decontextualizedQuery - The decontextualized query
   */
  possiblyAnnotateUserQuery(decontextualizedQuery) {
    const msgDiv = this.lastUserMessageDiv;
    if (msgDiv) {
      // Optional: Uncomment to show decontextualized query
      // msgDiv.innerHTML = this.currentMessage + "<br><span class=\"decontextualized-query\">" + decontextualizedQuery + "</span>";
    }
  }
  
  /**
   * Resorts the results by score
   */
  resortResults() {
    if (this.currentItems.length > 0) {
      // Sort by score in descending order
      this.currentItems.sort((a, b) => b[0].score - a[0].score);
      
      // Clear existing children
      while (this.bubble.firstChild) {
        this.bubble.removeChild(this.bubble.firstChild);
      }
      
      // Add sorted content back in proper order
      if (this.thisRoundRemembered) {
        this.bubble.appendChild(this.thisRoundRemembered);
      }
      
      if (this.sourcesMessage) {
        this.bubble.appendChild(this.sourcesMessage);
      }
      
      if (this.thisRoundSummary) {
        this.bubble.appendChild(this.thisRoundSummary);
      }
      
      // Add sorted result items
      for (const [item, domItem] of this.currentItems) {
        this.bubble.appendChild(domItem);
      }
    }
  }

  /**
   * Creates HTML for insufficient results message
   * 
   * @returns {HTMLElement} - The HTML element
   */
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

  /**
   * Creates a debug string for the current items
   * 
   * @returns {string} - The debug string
   */
  createDebugString() {
    return jsonLdToHtml(this.currentItems);
  }
}