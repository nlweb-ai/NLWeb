/**
 * Streaming chat interface implementation
 */

import { applyStyles } from './styles.js';
import { ManagedEventSource } from './managed-event-source.js';

// Apply styles from the dedicated styles module
applyStyles();

// Add spinner styles 
const spinnerStyles = `
  .loading-dots {
    display: inline-block;
  }
  .loading-dots span {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #333;
    margin: 0 2px;
    animation: bounce 1.4s infinite ease-in-out both;
  }
  .loading-dots span:nth-child(1) {
    animation-delay: -0.32s;
  }
  .loading-dots span:nth-child(2) {
    animation-delay: -0.16s;
  }
  @keyframes bounce {
    0%, 80%, 100% {
      transform: scale(0);
      opacity: 0.5;
    }
    40% {
      transform: scale(1);
      opacity: 1;
    }
  }
`;

// Add spinner styles to document
const spinnerStyleSheet = document.createElement('style');
spinnerStyleSheet.textContent = spinnerStyles;
document.head.appendChild(spinnerStyleSheet);

// Chat interface class

class ChatInterface {
  constructor(site="all", mode="single_site", display_style="list") {
    this.messagesArea = null;
    this.sendButton = null;
    this.inputField = null;
    this.prevQueries = [];
    this.itemToRemember = [];
    this.lastAnswers = [];
    this.decontextualizedQuery = null;
    this.bubble = null;
    this.dotsStillThere = true;
    this.currentItems = []
    this.sourcesMessage = null;
    this.thisRoundRemembered = null
    this.maxDistance = 0;
    this.num_results_sent = 0;
    this.display_style = display_style;
    if (site == "") {
      this.site = "all";
    } else {
      this.site = site
    }
    if (mode == "") {
      this.mode = "single_site";
    } else {
      this.mode = mode;
    }
    this.initializeElements();
    this.setupEventListeners();
  }

  ensureChatContainer() {
    let container = document.getElementById('chat-container');
    if (!container) {
      // Create container if it doesn't exist
      container = document.createElement('div');
      container.id = 'chat-container';
      container.innerHTML = `
        <div class="messages"></div>
        <div class="chat-footer">
          <input type="text" id="message-input" placeholder="Type your message..." />
          <button id="send-button">Send</button>
        </div>
      `;
      document.body.appendChild(container);
    }
    return container;
  }

  initializeElements() {
    // Ensure container exists
    const container = this.ensureChatContainer();
    
    // Site selector handling
    this.siteSelector = document.getElementById('site-selector');
    if (!this.siteSelector && this.mode === "single_site") {
      // Create a hidden selector for single site mode
      const selector = document.createElement('select');
      selector.id = 'site-selector';
      selector.className = 'site-selector';
      selector.style.display = 'none';
      
      const option = document.createElement('option');
      option.value = this.site;
      option.textContent = this.site;
      option.selected = true;
      selector.appendChild(option);
      
      container.appendChild(selector);
      this.siteSelector = selector;
    }
    
    // Get other elements, handling missing gracefully
    this.messagesArea = document.querySelector('.messages') || this.createMessagesArea();
    this.sendButton = document.getElementById('send-button') || this.createSendButton();
    this.inputField = document.getElementById('message-input') || this.createInputField();
    
    // Create invisible scroll anchor
    this.scrollDiv = document.createElement('div');
    this.scrollDiv.id = 'scroll-anchor';
    this.scrollDiv.style.height = '1px';
    this.messagesArea.appendChild(this.scrollDiv);
  }

  createMessagesArea() {
    const area = document.createElement('div');
    area.className = 'messages';
    document.getElementById('chat-container').appendChild(area);
    return area;
  }

  createSendButton() {
    const button = document.createElement('button');
    button.id = 'send-button';
    button.textContent = 'Send';
    const footer = document.querySelector('.chat-footer') || document.getElementById('chat-container');
    footer.appendChild(button);
    return button;
  }

  createInputField() {
    const input = document.createElement('input');
    input.type = 'text';
    input.id = 'message-input';
    input.placeholder = 'Type your message...';
    const footer = document.querySelector('.chat-footer') || document.getElementById('chat-container');
    footer.appendChild(input);
    return input;
  }

  setupEventListeners() {
    if (this.sendButton) {
      this.sendButton.addEventListener('click', () => this.sendMessage());
    }
    if (this.inputField) {
      this.inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          this.sendMessage();
        }
      });
    }
  }

  sendMessage(messageText = null) {
    const message = messageText || (this.inputField ? this.inputField.value.trim() : '');
    if (!message) return;

    // Display user message
    this.appendMessage(message, 'user');
    
    if (this.inputField) {
      this.inputField.value = '';
    }

    // Show loading animation
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant-message';
    const loadingBubble = document.createElement('div');
    loadingBubble.className = 'message-bubble';
    loadingBubble.innerHTML = '<div class="loading-dots"><span></span><span></span><span></span></div>';
    loadingDiv.appendChild(loadingBubble);
    this.messagesArea.appendChild(loadingDiv);
    this.scrollDiv.scrollIntoView();

    // Send request to server
    this.streamMessage(message);
  }

  streamMessage(message) {
    let site = this.site;
    if (this.siteSelector && this.siteSelector.value) {
      site = this.siteSelector.value;
    }
    let url = `/?site=${site}&mode=${this.mode}&generate_mode=none&query=${encodeURIComponent(message)}&streaming=true`;
    if (this.prevQueries.length > 0) {
      let stringifiedPrevQueries = JSON.stringify(this.prevQueries);
      url += `&prev=${encodeURIComponent(stringifiedPrevQueries)}`;
    }
    if (this.lastAnswers.length > 0) {
      let stringifiedlastAnswers = JSON.stringify(this.lastAnswers);
      url += `&last_ans=${encodeURIComponent(stringifiedlastAnswers)}`;
    }
    this.prevQueries.push(message);
    const eventSource = new ManagedEventSource(url);
    eventSource.query_id = null;
    eventSource.connect(this);
  }

  appendMessage(message, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = message;
    messageDiv.appendChild(bubble);
    this.messagesArea.appendChild(messageDiv);
    this.scrollDiv.scrollIntoView();
  }

  possiblyAnnotateUserQuery(decontextualizedQuery) {
    // deprecated
  }

  handleFirstMessage() {
    // Remove loading animation
    const loadingMessages = this.messagesArea.querySelectorAll('.assistant-message');
    if (loadingMessages.length > 0) {
      const lastLoading = loadingMessages[loadingMessages.length - 1];
      lastLoading.remove();
    }
    this.dotsStillThere = false;
  }

  createJsonItemHtml(jsonItem) {
    const itemDiv = document.createElement('div');
    itemDiv.className = 'nlweb-item';
    
    // Extract schema object (handle both array and direct object formats)
    const schema = jsonItem.schema_object || jsonItem;
    
    if (!schema || typeof schema !== 'object') {
      console.warn('Invalid item data:', jsonItem);
      return itemDiv;
    }
    
    // Safely extract values with defaults
    const schemaName = schema.name || schema.headline || schema.title || 'Untitled';
    const schemaUrl = jsonItem.url || schema.url || '';
    const schemaScore = jsonItem.score || 100;
    const schemaDescription = jsonItem.description || schema.description || '';
    const schemaImages = schema.images || schema.image || [];
    const schemaTotalTime = schema.totalTime || '';
    const schemaNutrition = schema.nutrition || null;
    const schemaAggregateRating = schema.aggregateRating || null;
    const schemaRecipeYield = schema.recipeYield || '';
    const schemaDatePublished = schema.datePublished || '';
    const schemaAuthor = schema.author || null;
    const schemaDuration = schema.duration || '';
    
    // Create link
    const link = document.createElement('a');
    link.href = schemaUrl;
    link.target = '_blank';
    link.textContent = schemaName;
    link.className = 'nlweb-item-link';
    
    // Title with score
    const titleDiv = document.createElement('div');
    titleDiv.className = 'nlweb-item-title';
    titleDiv.appendChild(link);
    if (this.display_style === "distance" && schemaScore !== undefined) {
      const scoreSpan = document.createElement('span');
      scoreSpan.className = 'nlweb-item-score';
      scoreSpan.textContent = ` (${schemaScore.toFixed(2)})`;
      titleDiv.appendChild(scoreSpan);
    }
    itemDiv.appendChild(titleDiv);
    
    // Description
    if (schemaDescription) {
      const descDiv = document.createElement('div');
      descDiv.className = 'nlweb-item-description';
      descDiv.textContent = schemaDescription.substring(0, 200) + (schemaDescription.length > 200 ? '...' : '');
      itemDiv.appendChild(descDiv);
    }
    
    // Metadata container
    const metadataDiv = document.createElement('div');
    metadataDiv.className = 'nlweb-item-metadata';
    
    // Add recipe-specific metadata
    if (schemaTotalTime) {
      metadataDiv.appendChild(this.createMetadataItem('Time', schemaTotalTime));
    }
    
    if (schemaAggregateRating) {
      const rating = schemaAggregateRating.ratingValue || schemaAggregateRating.value;
      const count = schemaAggregateRating.reviewCount || schemaAggregateRating.ratingCount || schemaAggregateRating.count;
      if (rating) {
        const ratingText = count ? `${rating}/5 (${count} reviews)` : `${rating}/5`;
        metadataDiv.appendChild(this.createMetadataItem('Rating', ratingText));
      }
    }
    
    if (schemaRecipeYield) {
      metadataDiv.appendChild(this.createMetadataItem('Servings', schemaRecipeYield));
    }
    
    if (schemaNutrition && schemaNutrition.calories) {
      metadataDiv.appendChild(this.createMetadataItem('Calories', schemaNutrition.calories));
    }
    
    if (schemaAuthor) {
      const authorName = typeof schemaAuthor === 'string' ? schemaAuthor : schemaAuthor.name;
      if (authorName) {
        metadataDiv.appendChild(this.createMetadataItem('Author', authorName));
      }
    }
    
    if (schemaDatePublished) {
      const date = new Date(schemaDatePublished).toLocaleDateString();
      metadataDiv.appendChild(this.createMetadataItem('Published', date));
    }
    
    if (schemaDuration) {
      metadataDiv.appendChild(this.createMetadataItem('Duration', schemaDuration));
    }
    
    if (metadataDiv.children.length > 0) {
      itemDiv.appendChild(metadataDiv);
    }
    
    // Add image if available
    const imageUrl = this.extractImageUrl(schema);
    if (imageUrl) {
      const imgContainer = document.createElement('div');
      imgContainer.className = 'nlweb-item-image-container';
      const img = document.createElement('img');
      img.src = imageUrl;
      img.alt = schemaName;
      img.className = 'nlweb-item-image';
      img.onerror = function() { this.style.display = 'none'; };
      imgContainer.appendChild(img);
      itemDiv.appendChild(imgContainer);
    }
    
    return itemDiv;
  }

  extractImageUrl(schema) {
    // Check various possible image fields
    if (schema.image) {
      if (typeof schema.image === 'string') {
        return schema.image;
      } else if (Array.isArray(schema.image) && schema.image.length > 0) {
        return this.extractImageUrlFromImageObject(schema.image[0]);
      } else if (typeof schema.image === 'object') {
        return this.extractImageUrlFromImageObject(schema.image);
      }
    } else if (schema.images && Array.isArray(schema.images) && schema.images.length > 0) {
      return this.extractImageUrlFromImageObject(schema.images[0]);
    }
    return null;
  }

  extractImageUrlFromImageObject(imageObj) {
    if (typeof imageObj === 'string') {
      return imageObj;
    } else if (imageObj.url) {
      return imageObj.url;
    } else if (imageObj['@id']) {
      return imageObj['@id'];
    }
    return null;
  }

  createMetadataItem(label, value) {
    const span = document.createElement('span');
    span.className = 'nlweb-metadata-item';
    span.innerHTML = `<strong>${label}:</strong> ${value}`;
    return span;
  }

  memoryMessage(message, chatInterface) {
    if (!chatInterface.thisRoundRemembered) {
      chatInterface.thisRoundRemembered = document.createElement('div');
      chatInterface.thisRoundRemembered.className = 'memory-message';
      chatInterface.thisRoundRemembered.innerHTML = `<div class="memory-header">From previous conversations:</div>`;
      chatInterface.bubble.appendChild(chatInterface.thisRoundRemembered);
    }
    const memItem = document.createElement('div');
    memItem.className = 'memory-item';
    memItem.textContent = `• ${message}`;
    chatInterface.thisRoundRemembered.appendChild(memItem);
  }

  siteIsIrrelevantToQuery(message, chatInterface) {
    const messageDiv = chatInterface.createIntermediateMessageHtml(message);
    chatInterface.bubble.appendChild(messageDiv);
  }

  askUserMessage(message, chatInterface) {
    const messageDiv = chatInterface.createIntermediateMessageHtml(message);
    chatInterface.bubble.appendChild(messageDiv);
  }

  createIntermediateMessageHtml(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'intermediate-message';
    messageDiv.textContent = message;
    return messageDiv;
  }

  itemDetailsMessage(message, chatInterface) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'item-details-message';
    messageDiv.textContent = message;
    chatInterface.bubble.appendChild(messageDiv);
  }

  resortResults() {
    if (!this.currentItems || this.currentItems.length === 0) return;
    
    // Remove all current items from DOM
    const itemElements = this.currentItems.map(([item, domItem]) => {
      if (domItem && domItem.parentNode) {
        domItem.parentNode.removeChild(domItem);
      }
      return domItem;
    });
    
    // Clear the bubble
    while (this.bubble.firstChild) {
      this.bubble.removeChild(this.bubble.firstChild);
    }
    
    // Add back in correct order: memory, sources, items, summary
    if (this.thisRoundRemembered) {
      this.bubble.appendChild(this.thisRoundRemembered);
    }
    
    if (this.sourcesMessage) {
      this.bubble.appendChild(this.sourcesMessage);
    }
    
    // Re-add all items
    itemElements.forEach(domItem => {
      if (domItem) {
        this.bubble.appendChild(domItem);
      }
    });
    
    if (this.thisRoundSummary) {
      this.bubble.appendChild(this.thisRoundSummary);
    }
  }
}

export { ChatInterface };