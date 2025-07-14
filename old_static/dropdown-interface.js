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
   * @param {Object} options - Configuration options
   * @param {boolean} [options.useTextInputForSite=false] - Whether to use a text input instead of dropdown for site selection
   */
  constructor(chatInterface, container, options = {}) {
    this.chatInterface = chatInterface;
    this.container = container;
    this.options = {
      useTextInputForSite: false,
      ...options
    };
    
    // Create the dropdown interface
    this.createSelectors();
  }

  /**
   * Creates selector controls
   */
  async createSelectors() {
    // Create selectors container
    const selector = document.createElement('div');
    this.selector = selector;
    selector.className = 'site-selector';

    // Create site selector (dropdown or text input based on options)
    if (this.options.useTextInputForSite) {
      this.createSiteTextInput();
    } else {
      await this.createSiteDropdown();
    }
    
    // Create generate mode selector
    this.createGenerateModeSelector();
    
    // Create database selector if enabled
    // Commented out - database selector functionality
    // if (this.chatInterface.enableDatabaseSelector) {
    //   this.createDatabaseSelector();
    // }
     
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
  async createSiteDropdown() {
    const siteSelect = document.createElement('select');
    this.siteSelect = siteSelect;
    
    // Add a loading option temporarily
    const loadingOption = document.createElement('option');
    loadingOption.value = '';
    loadingOption.textContent = 'Loading sites...';
    loadingOption.disabled = true;
    siteSelect.appendChild(loadingOption);
    
    this.selector.appendChild(this.makeSelectorLabel("Site"));
    this.selector.appendChild(siteSelect);
    
    // Fetch sites asynchronously
    try {
      const sites = await this.getSites();
      
      // Clear the loading option
      siteSelect.innerHTML = '';
      
      // Add the fetched sites
      sites.forEach(site => {
        const option = document.createElement('option');
        option.value = escapeHtml(site);
        option.textContent = escapeHtml(site);
        siteSelect.appendChild(option);
      });
      
      // Set initial value if chatInterface has a site
      if (this.chatInterface.site && sites.includes(this.chatInterface.site)) {
        siteSelect.value = escapeHtml(this.chatInterface.site);
      } else if (sites.length > 0) {
        // Default to first site if no site is set or site not in list
        siteSelect.value = escapeHtml(sites[0]);
        this.chatInterface.site = sites[0];
      }
    } catch (error) {
      console.error('Error creating site dropdown:', error);
      // Clear loading option and add fallback sites
      siteSelect.innerHTML = '';
      const fallbackSites = ['all', 'eventbrite', 'oreilly', 'scifi_movies', 'verge'];
      fallbackSites.forEach(site => {
        const option = document.createElement('option');
        option.value = escapeHtml(site);
        option.textContent = escapeHtml(site);
        siteSelect.appendChild(option);
      });
    }
    
    siteSelect.addEventListener('change', () => {
      this.chatInterface.site = siteSelect.value;
      this.chatInterface.resetChatState();
    });
    
    // Make siteSelect accessible to chatInterface
    this.chatInterface.siteSelect = siteSelect;
  }

  /**
   * Creates the site text input
   */
  createSiteTextInput() {
    const siteInput = document.createElement('input');
    this.siteInput = siteInput;
    siteInput.type = 'text';
    siteInput.placeholder = 'Enter site name (defaults to "all")';
    siteInput.className = 'site-input';
    
    // Make the input taller
    siteInput.style.height = '28px';
    siteInput.style.lineHeight = '28px';
    siteInput.style.fontSize = '14px';
    siteInput.style.padding = '0 8px';
    
    this.selector.appendChild(this.makeSelectorLabel("Site"));
    this.selector.appendChild(siteInput);
    
    siteInput.addEventListener('change', () => {
      // If input is empty, default to 'all'
      this.chatInterface.site = siteInput.value.trim() || 'all';
      this.chatInterface.resetChatState();
    });
    
    // Add blur event for when user clicks away
    siteInput.addEventListener('blur', () => {
      // If input is empty, default to 'all'
      this.chatInterface.site = siteInput.value.trim() || 'all';
      this.chatInterface.resetChatState();
    });
    
    // Set initial value if chatInterface has a site
    if (this.chatInterface.site) {
      siteInput.value = this.chatInterface.site;
    } else {
      // Default to 'all' if no site is specified
      this.chatInterface.site = 'all';
    }
    
    // Make siteInput accessible to chatInterface
    this.chatInterface.siteInput = siteInput;
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
   * @returns {Promise<Array>} - Promise that resolves to array of site names
   * Fetches sites from the server using the /sites endpoint
   */
  async getSites() {
    try {
      const response = await fetch('/sites?streaming=false');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      
      // Check if we have the expected response structure
      if (data && data['message-type'] === 'sites' && Array.isArray(data.sites)) {
        let sites = data.sites;
        
        // Sort sites alphabetically
        sites.sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
        
        // Add 'all' to the beginning of the list if not already present
        if (!sites.includes('all')) {
          sites.unshift('all');
        } else {
          // If 'all' exists, remove it and add it to the beginning
          sites = sites.filter(site => site !== 'all');
          sites.unshift('all');
        }
        return sites;
      } else {
        console.error('Unexpected response format from /sites endpoint:', data);
        // Fall back to default sites (alphabetized with 'all' first)
        return ['all', 'eventbrite', 'oreilly', 'scifi_movies', 'verge'];
      }
    } catch (error) {
      console.error('Error fetching sites:', error);
      // Fall back to default sites if the request fails (alphabetized with 'all' first)
      return ['all', 'eventbrite', 'oreilly', 'scifi_movies', 'verge'];
    }
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