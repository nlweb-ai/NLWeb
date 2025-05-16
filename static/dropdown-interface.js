/**
 * DropdownInterface Class
 * Handles the dropdown UI elements for site selection and options
 * for the debug interface.
 * 
 */

import { escapeHtml } from './utils.js';

export class DropdownInterface {
  /**
   * Creates a new DropdownInterface
   * 
   * @param {Object} chatInterface - The main chat interface instance
   * @param {HTMLElement} container - The container element to append to
   */
  constructor(chatInterface, container) {
    this.chatInterface = chatInterface;
    this.container = container;
    
    // Create the dropdown interface
    this.createSelectors();
  }

  /**
   * Creates selector controls
   */
  createSelectors() {
    // Create selectors container
    const selector = document.createElement('div');
    this.selector = selector;
    selector.className = 'site-selector';

    // Create site selector
    this.createSiteSelector();
    
    // Create generate mode selector
    this.createGenerateModeSelector();
    
    // Create database selector if enabled
    if (this.chatInterface.enableDatabaseSelector) {
      this.createDatabaseSelector();
    }
     
    // Create clear chat icon
    this.addClearChatIcon();

    // Create debug icon
    this.addDebugIcon();

    // Create context URL input
    this.addContextUrlInput();

    // Add to container - this will place it at the top of the container
    this.container.prepend(this.selector);
  }
  
  /**
   * Creates the site selector dropdown
   */
  createSiteSelector() {
    const siteSelect = document.createElement('select');
    this.siteSelect = siteSelect;
    
    this.getSites().forEach(site => {
      const option = document.createElement('option');
      option.value = escapeHtml(site);
      option.textContent = escapeHtml(site);
      siteSelect.appendChild(option);
    });
    
    this.selector.appendChild(this.makeSelectorLabel("Site"));
    this.selector.appendChild(siteSelect);
    
    siteSelect.addEventListener('change', () => {
      this.chatInterface.site = siteSelect.value;
      this.chatInterface.resetChatState();
    });
    
    // Set initial value if chatInterface has a site
    if (this.chatInterface.site) {
      siteSelect.value = escapeHtml(this.chatInterface.site);
    }
    
    // Make siteSelect accessible to chatInterface
    this.chatInterface.siteSelect = siteSelect;
  }
  
  /**
   * Creates the generate mode selector dropdown
   */
  createGenerateModeSelector() {
    const generateModeSelect = document.createElement('select');
    this.generateModeSelect = generateModeSelect;
    
    this.getGenerateModes().forEach(mode => {
      const option = document.createElement('option');
      option.value = escapeHtml(mode);
      option.textContent = escapeHtml(mode);
      generateModeSelect.appendChild(option);
    });
    
    this.selector.appendChild(this.makeSelectorLabel("Mode"));
    this.selector.appendChild(generateModeSelect);
    
    generateModeSelect.addEventListener('change', () => {
      this.chatInterface.generate_mode = generateModeSelect.value;
      this.chatInterface.resetChatState();
    });
    
    // Set initial value
    generateModeSelect.value = escapeHtml(this.chatInterface.generate_mode);
    
    // Make generateModeSelect accessible to chatInterface
    this.chatInterface.generateModeSelect = generateModeSelect;
  }
  
  /**
   * Creates the database selector dropdown
   */
  createDatabaseSelector() {
    const dbSelect = document.createElement('select');
    this.dbSelect = dbSelect;
    
    this.getDatabases().forEach(db => {
      const option = document.createElement('option');
      option.value = escapeHtml(db.id);
      option.textContent = escapeHtml(db.name);
      dbSelect.appendChild(option);
    });
    
    this.selector.appendChild(this.makeSelectorLabel("Database"));
    this.selector.appendChild(dbSelect);
    
    dbSelect.addEventListener('change', () => {
      this.chatInterface.database = dbSelect.value;
      this.chatInterface.resetChatState();
    });
    
    // Set initial value to preferred endpoint from config
    dbSelect.value = "azure_ai_search";
    this.chatInterface.database = "azure_ai_search";
    
    // Make dbSelect accessible to chatInterface
    this.chatInterface.dbSelect = dbSelect;
  }
  
  /**
   * Adds the clear chat icon
   */
  addClearChatIcon() {
    const clearIcon = document.createElement('span');
    const imgElement = document.createElement('img');
    imgElement.src = 'images/clear.jpeg';
    imgElement.className = 'selector-icon';
    imgElement.alt = 'Clear';
    clearIcon.appendChild(imgElement);
    
    clearIcon.title = "Clear chat history";
    clearIcon.addEventListener('click', () => {
      this.chatInterface.resetChatState();
    });
    this.selector.appendChild(clearIcon);
  }
  
  /**
   * Adds the debug icon
   */
  addDebugIcon() {
    const debugIcon = document.createElement('span');
    const imgElement = document.createElement('img');
    imgElement.src = 'images/debug.png';
    imgElement.className = 'selector-icon';
    imgElement.alt = 'Debug';
    debugIcon.appendChild(imgElement);
    
    debugIcon.title = "Debug";
    debugIcon.addEventListener('click', () => {
      if (this.chatInterface.debug_mode) {
        this.chatInterface.debug_mode = false;
        this.chatInterface.bubble.innerHTML = '';
        this.chatInterface.resortResults();
      } else {
        this.chatInterface.debug_mode = true;
        this.chatInterface.bubble.innerHTML = this.chatInterface.createDebugString();
      }
    });
    this.selector.appendChild(debugIcon);
  }
  
  /**
   * Adds the context URL input
   */
  addContextUrlInput() {
    const contextUrlDiv = document.createElement('div');
    contextUrlDiv.id = 'context_url_div';
    contextUrlDiv.className = 'context-url-container';
        
    const contextUrlInput = document.createElement('input');
    contextUrlInput.type = 'text';
    contextUrlInput.id = 'context_url';
    contextUrlInput.placeholder = 'Enter Context URL';
    contextUrlInput.className = 'context-url-input';
        
    contextUrlDiv.appendChild(this.makeSelectorLabel("Context URL"));
    contextUrlDiv.appendChild(contextUrlInput);
    this.selector.appendChild(contextUrlDiv);
    
    // Make context_url accessible to chatInterface
    this.chatInterface.context_url = contextUrlInput;
  }
  
  /**
   * Makes a label for selectors
   * 
   * @param {string} label - The label text
   * @returns {HTMLElement} - The label element
   */
  makeSelectorLabel(label) {
    const labelDiv = document.createElement('span');
    labelDiv.textContent = escapeHtml(label);
    labelDiv.className = 'selector-label';
    return labelDiv;
  }

  /**
   * Gets the available sites for the selector
   * 
   * @returns {Array} - Array of site names
   * If you would like a site to show up in the dropdown, please add it here.
   * For now, we will leave it with just the launch partners who
   * are making their data available
   */
  getSites() {
    return [
      'scifi_movies', 'verge','oreilly', 'eventbrite','all'
    ];
  }

  /**
   * Gets the available generate modes for the selector
   * 
   * @returns {Array} - Array of generate mode names
   */
  getGenerateModes() {
    return ['list', 'summarize', 'generate'];
  }
  
  /**
   * Gets the available databases for the selector
   * 
   * @returns {Array} - Array of database configurations
   */
  getDatabases() {
    return [
      { id: 'azure_ai_search', name: 'NLWeb_Crawl' },
      { id: 'milvus_1', name: 'Milvus' },
      { id: 'qdrant_local', name: 'Qdrant Local' },
      { id: 'qdrant_url', name: 'Qdrant URL' },
      { id: 'snowflake_cortex_search_1', name: 'Snowflake_Cortex_Search' }
    ];
  }
}