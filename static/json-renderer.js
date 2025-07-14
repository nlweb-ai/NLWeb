/**
 * Base class for rendering JSON to HTML
 */
export class JsonRenderer {
  /**
   * Creates a new JsonRenderer instance
   * 
   * @param {Object} options - Configuration options
   */
  constructor(options = {}) {
    this.options = {
      colorize: true,
      ...options
    };
    
    // Registry for type-specific renderers
    this.typeRenderers = {};
  }
  
  /**
   * Registers a renderer for a specific type
   * 
   * @param {string} type - The type to register for
   * @param {Function} renderer - The renderer function
   */
  registerTypeRenderer(type, renderer) {
    this.typeRenderers[type] = renderer;
  }
  
  /**
   * Renders JSON as HTML for display
   * 
   * @param {Object|string} json - The JSON to render
   * @returns {string} - HTML representation of the JSON
   */
  render(json) {
    // Print JSON to console for debugging
    try {
      const parsed = (typeof json === 'string') ? JSON.parse(json) : json;
      const formatted = this.formatObject(parsed);
      
      if (this.options.colorize) {
        return this.wrapWithStyles(formatted);
      }
      
      return `<pre class="json-ld"><code>${formatted}</code></pre>`;
    } catch (error) {
      return `<pre class="json-ld error">Error: ${this.escapeHtml(error.message)}</pre>`;
    }
  }
  
  /**
   * Creates an HTML element for a JSON item
   * 
   * @param {Object} item - The item data
   * @returns {HTMLElement} - The HTML element
   */
  createJsonItemHtml(item) {
    // Check if there's a type-specific renderer
    // Handle array/list items by using first element

    if (item.schema_object && Array.isArray(item.schema_object) && item.schema_object.length > 0) {
      item.schema_object = item.schema_object[0];
    }
    if (item.schema_object && item.schema_object['@type']) {
      const type = item.schema_object['@type'];
      if (Object.prototype.hasOwnProperty.call(this.typeRenderers, type) && 
             typeof this.typeRenderers[type] === 'function') {
        return this.typeRenderers[type](item, this);
      } 
    }
    
    return this.createDefaultItemHtml(item);
  }
  
  /**
   * Creates default HTML for a JSON item
   * 
   * @param {Object} item - The item data
   * @returns {HTMLElement} - The HTML element
   */
  createDefaultItemHtml(item) {
    // Safely create container elements
    const container = document.createElement('div');
    container.className = 'item-container';

    // Left content div (title + description)
    const contentDiv = document.createElement('div');
    contentDiv.className = 'item-content';

    // Title row with link and info icon
    this.createTitleRow(item, contentDiv);

    // Description
    const description = document.createElement('div');
    description.className = 'item-description';
    
    // Check if we have a details array (like ingredients)
    if (item.details && Array.isArray(item.details)) {
      // Create table for arrays (like ingredients)
      const table = document.createElement('table');
      table.style.cssText = 'width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.9em;';
      
      // Create header
      const thead = document.createElement('thead');
      const headerRow = document.createElement('tr');
      const headerCell = document.createElement('th');
      headerCell.textContent = 'Ingredients';
      headerCell.style.cssText = 'text-align: left; padding: 10px; background-color: #f0f0f0; border: 1px solid #ddd; font-weight: 600;';
      headerRow.appendChild(headerCell);
      thead.appendChild(headerRow);
      table.appendChild(thead);
      
      // Create body with alternating row colors
      const tbody = document.createElement('tbody');
      item.details.forEach((ingredient, index) => {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.textContent = ingredient;
        cell.style.cssText = `padding: 8px 10px; border: 1px solid #ddd; ${index % 2 === 0 ? 'background-color: #ffffff;' : 'background-color: #f9f9f9;'}`;
        row.appendChild(cell);
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      
      description.appendChild(table);
      
      // Don't add the regular description if we already displayed details as a table
      // This prevents duplicate display of ingredients
    } else {
      // Use regular description
      const descContent = item.description || item.details || '';
      if (Array.isArray(descContent)) {
        // Fallback for arrays in description field
        const list = document.createElement('ul');
        list.style.cssText = 'margin: 8px 0; padding-left: 20px;';
        descContent.forEach(item => {
          const li = document.createElement('li');
          li.textContent = item;
          li.style.cssText = 'margin: 4px 0;';
          list.appendChild(li);
        });
        description.appendChild(list);
      } else {
        // Use textContent for safe insertion of description
        description.textContent = descContent;
      }
    }
    
    contentDiv.appendChild(description);

    // Add explanation if available
    this.possiblyAddExplanation(item, contentDiv);

    container.appendChild(contentDiv);

    // Add image if available
    this.addImageIfAvailable(item, container);

    return container;
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
    // FIX: Use sanitizeUrl instead of just escapeHtml for URLs
    titleLink.href = item.url ? this.sanitizeUrl(item.url) : '#';
    const itemName = this.htmlUnescape(this.getItemName(item));
    // Safe text insertion
    titleLink.textContent = itemName;
    titleLink.className = 'item-title-link';
    titleRow.appendChild(titleLink);

   
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
    // FIX: Use sanitizeUrl for URL attributes
    visibleUrlLink.href = item.siteUrl ? this.sanitizeUrl(item.siteUrl) : '#';
    // Use textContent for safe insertion
    visibleUrlLink.textContent = item.site || '';
    visibleUrlLink.className = 'item-site-link';
    contentDiv.appendChild(visibleUrlLink);
  }
  
  /**
   * Gets the name of an item
   * 
   * @param {Object} item - The item data
   * @returns {string} - The item name
   */
  getItemName(item) {
    let name = '';
    if (item.name) {
      name = item.name;
    } else if (item.schema_object && item.schema_object.keywords) {
      name = item.schema_object.keywords;
    } else if (item.url) {
      name = item.url;
    }
    return name;
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
        const imageDiv = document.createElement('div');
        const img = document.createElement('img');
        // FIX: Use sanitizeUrl for image src
        img.src = this.sanitizeUrl(imgURL);
        img.alt = 'Item image';
        img.className = 'item-image';
        imageDiv.appendChild(img);
        container.appendChild(imageDiv);
      }
    }
  }
  
  /**
   * Extracts an image URL from a schema object
   * 
   * @param {Object} schema_object - The schema object
   * @returns {string|null} - The image URL or null
   */
  extractImage(schema_object) {
    // Handle array of schema objects
    if (Array.isArray(schema_object)) {
      // Look for ImageObject first
      const imageObj = schema_object.find(obj => obj['@type'] === 'ImageObject');
      if (imageObj && imageObj.url) {
        return imageObj.url;
      }
      
      // Look for Recipe object with image
      const recipeObj = schema_object.find(obj => obj['@type'] === 'Recipe');
      if (recipeObj && recipeObj.image) {
        return this.extractImageInternal(recipeObj.image);
      }
      
      // Look for Article object with thumbnailUrl
      const articleObj = schema_object.find(obj => obj['@type'] === 'Article');
      if (articleObj && articleObj.thumbnailUrl) {
        return articleObj.thumbnailUrl;
      }
      
      // Check first object for any image property
      if (schema_object[0]) {
        schema_object = schema_object[0];
      }
    }
    
    // Handle single schema object
    if (schema_object) {
      // Check for direct image property
      if (schema_object.image) {
        return this.extractImageInternal(schema_object.image);
      }
      // Check for thumbnailUrl property
      if (schema_object.thumbnailUrl) {
        return schema_object.thumbnailUrl;
      }
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
    } else if (Array.isArray(image)) {
      if (image[0] && typeof image[0] === 'string') {
        return image[0];
      } else if (image[0] && typeof image[0] === 'object') {
        return this.extractImageInternal(image[0]);
      }
    } 
    return null;
  }
  
  /**
   * Creates a span element with the given content
   * 
   * @param {string} content - The content for the span
   * @returns {HTMLElement} - The span element
   */
  makeAsSpan(content) {
    const span = document.createElement('span');
    // Use textContent for safe insertion
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
    if (!item.explanation && !force) return null;
    
    const detailsDiv = document.createElement('div'); 
    contentDiv.appendChild(document.createElement('br'));
    const explSpan = this.makeAsSpan(item.explanation || '');
    explSpan.className = 'item-explanation';
    detailsDiv.appendChild(explSpan);
    contentDiv.appendChild(detailsDiv);
    return detailsDiv;
  }
  
  /**
   * Formats an object as HTML
   * 
   * @param {Object} obj - The object to format
   * @param {number} indent - The indentation level
   * @returns {string} - HTML representation of the object
   */
  formatObject(obj, indent = 0) {
    const spaces = '  '.repeat(indent);
    
    if (!obj || Object.keys(obj).length === 0) return '{}';
    
    const entries = Object.entries(obj).map(([key, value]) => {
      // Special handling for JSON-LD keywords (starting with @)
      const keySpan = key.startsWith('@') 
        ? `<span class="keyword">"${this.escapeHtml(key)}"</span>`
        : `<span class="key">"${this.escapeHtml(key)}"</span>`;
        
      return `${spaces}  ${keySpan}: ${this.formatValue(value, indent + 1)}`;
    });
    
    return `{\n${entries.join(',\n')}\n${spaces}}`;
  }
  
  /**
   * Formats a value as HTML
   * 
   * @param {*} value - The value to format
   * @param {number} indent - The indentation level
   * @returns {string} - HTML representation of the value
   */
  formatValue(value, indent) {
    const spaces = '  '.repeat(indent);
    
    if (value === null) {
      return `<span class="null">null</span>`;
    }
    
    switch (typeof value) {
      case 'string':
        // Special handling for URLs and IRIs in JSON-LD
        if (value.startsWith('http://') || value.startsWith('https://')) {
          return `<span class="string url">"${this.escapeHtml(value)}"</span>`;
        }
        return `<span class="string">"${this.escapeHtml(value)}"</span>`;
      case 'number':
        return `<span class="number">${value}</span>`;
      case 'boolean':
        return `<span class="boolean">${value}</span>`;
      case 'object':
        if (Array.isArray(value)) {
          if (value.length === 0) return '[]';
          const items = value.map(item => 
            `${spaces}  ${this.formatValue(item, indent + 1)}`
          ).join(',\n');
          return `[\n${items}\n${spaces}]`;
        }
        return this.formatObject(value, indent);
      default:
        return `<span class="unknown">${this.escapeHtml(String(value))}</span>`;
    }
  }
  
  /**
   * Wraps formatted HTML with CSS styles
   * 
   * @param {string} content - The formatted content
   * @returns {string} - The wrapped content with styles
   */
  wrapWithStyles(content) {
    return `<pre class="json-ld"><code>${content}</code></pre>
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
.json-ld .unknown { color: #607d8b; }
</style>`;
  }
  
  /**
   * Escapes HTML special characters in a string
   * 
   * @param {string} str - The string to escape
   * @returns {string} - The escaped string
   */
  escapeHtml(str) {
    if (typeof str !== 'string') return '';
    
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
  
  /**
   * Sanitizes a URL to prevent javascript: protocol and other potentially dangerous URLs
   * 
   * @param {string} url - The URL to sanitize
   * @returns {string} - The sanitized URL
   */
  sanitizeUrl(url) {
    if (!url || typeof url !== 'string') return '#';
    
    // Remove leading and trailing whitespace
    const trimmedUrl = url.trim();
    
    // Check for javascript: protocol or other dangerous protocols
    const protocolPattern = /^(javascript|data|vbscript|file):/i;
    if (protocolPattern.test(trimmedUrl)) {
      return '#';
    }
    
    return trimmedUrl;
  }
  
  /**
   * Unescapes HTML entities in a string, safely converting entities like &amp; to &
   * without executing any HTML/scripts.
   * 
   * @param {string} str - The string with HTML entities to unescape
   * @returns {string} - The unescaped string with only text content
   */
  htmlUnescape(str) {
    if (!str || typeof str !== 'string') return '';
    
    // This is a safe way to unescape HTML entities
    // It parses the HTML but only returns the text content, not any executable HTML/scripts
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<!DOCTYPE html><body>${str}`, 'text/html');
    return doc.body.textContent || '';
  }
}
