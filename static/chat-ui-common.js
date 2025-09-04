/**
 * Common Chat UI Library
 * Shared rendering and UI methods for chat interfaces
 */

import { JsonRenderer } from './json-renderer.js';
import { TypeRendererFactory } from './type-renderers.js';
import { RecipeRenderer } from './recipe-renderer.js';

export class ChatUICommon {
  constructor() {
    this.debugMessages = [];
    this.lastAnswers = [];
    this.num_results_sent = 0;
    
    // Initialize JsonRenderer with type-specific renderers
    this.jsonRenderer = new JsonRenderer();
    TypeRendererFactory.registerAll(this.jsonRenderer);
    TypeRendererFactory.registerRenderer(RecipeRenderer, this.jsonRenderer);
    
    // Register CricketStatistics renderer
    this.jsonRenderer.registerTypeRenderer('CricketStatistics', (item) => this.renderCricketStatistics(item));
  }

  /**
   * Render multiple items/results
   */
  renderItems(items) {
    if (!items || items.length === 0) return '';
    
    // Don't sort - keep items in the order they were received
    const sortedItems = [...items];
    
    // Create a container for all results
    const resultsContainer = document.createElement('div');
    resultsContainer.className = 'search-results';
    
    // Render each item using JsonRenderer
    sortedItems.forEach(item => {
      // Use JsonRenderer to create the item HTML
      const itemElement = this.jsonRenderer.createJsonItemHtml(item);
      resultsContainer.appendChild(itemElement);
    });
    
    // Return the outer HTML of the container
    return resultsContainer.outerHTML;
  }

  /**
   * Render schema object (recipes, products, etc.)
   */
  renderSchemaObject(schemaObj) {
    if (!schemaObj) return null;
    
    const container = document.createElement('div');
    container.className = 'schema-details';
    
    // Recipe-specific rendering
    if (schemaObj['@type'] === 'Recipe' || schemaObj.recipeYield) {
      const details = [];
      
      if (schemaObj.totalTime || schemaObj.cookTime || schemaObj.prepTime) {
        const time = schemaObj.totalTime || schemaObj.cookTime || schemaObj.prepTime;
        details.push(`⏱️ ${time}`);
      }
      
      if (schemaObj.recipeYield) {
        details.push(`🍽️ Serves: ${schemaObj.recipeYield}`);
      }
      
      if (schemaObj.nutrition && schemaObj.nutrition.calories) {
        details.push(`🔥 ${schemaObj.nutrition.calories} cal`);
      }
      
      if (details.length > 0) {
        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'recipe-details';
        detailsDiv.innerHTML = details.join(' • ');
        container.appendChild(detailsDiv);
      }
    }
    
    // Image
    const imageUrl = this.extractImageUrl(schemaObj);
    if (imageUrl) {
      const img = document.createElement('img');
      img.src = imageUrl;
      img.className = 'item-image';
      img.loading = 'lazy';
      img.onerror = function() { this.style.display = 'none'; };
      container.appendChild(img);
    }
    
    // Rating
    if (schemaObj.aggregateRating) {
      const rating = schemaObj.aggregateRating;
      const ratingValue = rating.ratingValue || rating.value;
      const reviewCount = rating.reviewCount || rating.ratingCount;
      
      if (ratingValue) {
        const ratingDiv = document.createElement('div');
        ratingDiv.className = 'item-rating';
        const stars = '★'.repeat(Math.round(ratingValue));
        const emptyStars = '☆'.repeat(5 - Math.round(ratingValue));
        ratingDiv.innerHTML = `${stars}${emptyStars} ${ratingValue}/5`;
        if (reviewCount) {
          ratingDiv.innerHTML += ` (${reviewCount} reviews)`;
        }
        container.appendChild(ratingDiv);
      }
    }
    
    // Price
    if (schemaObj.offers && schemaObj.offers.price) {
      const priceDiv = document.createElement('div');
      priceDiv.className = 'item-price';
      priceDiv.textContent = `Price: ${schemaObj.offers.price}`;
      if (schemaObj.offers.priceCurrency) {
        priceDiv.textContent += ` ${schemaObj.offers.priceCurrency}`;
      }
      container.appendChild(priceDiv);
    }
    
    return container.children.length > 0 ? container : null;
  }

  /**
   * Extract image URL from various schema formats
   */
  extractImageUrl(schemaObj) {
    if (!schemaObj) return null;
    
    // Check various possible image fields
    if (schemaObj.image) {
      if (typeof schemaObj.image === 'string') {
        return schemaObj.image;
      } else if (schemaObj.image.url) {
        return schemaObj.image.url;
      } else if (schemaObj.image['@id'] && schemaObj.image['@id'].startsWith('http')) {
        // Only use @id if it's an actual URL, not a fragment
        return schemaObj.image['@id'];
      } else if (Array.isArray(schemaObj.image) && schemaObj.image.length > 0) {
        return this.extractImageUrl({ image: schemaObj.image[0] });
      }
    }
    
    // Always check thumbnailUrl as it often contains the actual image URL
    if (schemaObj.thumbnailUrl) {
      return schemaObj.thumbnailUrl;
    }
    
    if (schemaObj.images && Array.isArray(schemaObj.images) && schemaObj.images.length > 0) {
      return this.extractImageUrl({ image: schemaObj.images[0] });
    }
    
    return null;
  }

  /**
   * Render ensemble results
   */
  renderEnsembleResult(result) {
    if (!result || !result.recommendations) return '';
    
    const recommendations = result.recommendations;
    
    // Create container
    let html = '<div class="ensemble-result-container">';
    html += '<div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 10px 0;">';
    
    // Theme header
    if (recommendations.theme) {
      html += `<h3 style="color: #333; margin-bottom: 20px; font-size: 1.2em;">${recommendations.theme}</h3>`;
    }
    
    // Items
    if (recommendations.items && Array.isArray(recommendations.items)) {
      html += '<div style="display: grid; gap: 15px;">';
      
      recommendations.items.forEach(item => {
        html += this.renderEnsembleItem(item);
      });
      
      html += '</div>';
    }
    
    // Overall tips
    if (recommendations.overall_tips && Array.isArray(recommendations.overall_tips)) {
      html += '<div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #dee2e6;">';
      html += '<h4 style="color: #555; margin-bottom: 10px; font-size: 1.1em;">Planning Tips</h4>';
      html += '<ul style="margin: 0; padding-left: 20px;">';
      
      recommendations.overall_tips.forEach(tip => {
        html += `<li style="color: #666; margin-bottom: 5px;">${tip}</li>`;
      });
      
      html += '</ul>';
      html += '</div>';
    }
    
    html += '</div>';
    html += '</div>';
    
    return html;
  }

  /**
   * Render a single ensemble item
   */
  renderEnsembleItem(item) {
    let html = '<div style="background: white; padding: 15px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">';
    
    // Category badge
    const badgeColor = item.category === 'Garden' ? '#28a745' : '#007bff';
    html += `<span style="display: inline-block; padding: 4px 12px; background-color: ${badgeColor}; color: white; border-radius: 20px; font-size: 0.85em; margin-bottom: 10px;">${item.category}</span>`;
    
    // Name with link
    html += '<h4 style="margin: 10px 0;">';
    const itemUrl = item.url || (item.schema_object && item.schema_object.url);
    if (itemUrl) {
      html += `<a href="${itemUrl}" target="_blank" style="color: #0066cc; text-decoration: none;">${item.name}</a>`;
    } else {
      html += item.name;
    }
    html += '</h4>';
    
    // Description
    html += `<p style="color: #666; margin: 10px 0; line-height: 1.5;">${item.description}</p>`;
    
    // Why recommended
    html += '<div style="background-color: #e8f4f8; padding: 10px; border-radius: 4px; margin: 10px 0;">';
    html += `<strong style="color: #0066cc;">Why recommended: </strong>`;
    html += `<span style="color: #555;">${item.why_recommended}</span>`;
    html += '</div>';
    
    // Details
    if (item.details && Object.keys(item.details).length > 0) {
      html += '<div style="margin-top: 10px; font-size: 0.9em;">';
      Object.entries(item.details).forEach(([key, value]) => {
        const formattedKey = key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ');
        html += `<div style="color: #777; margin: 3px 0;"><strong style="color: #555;">${formattedKey}: </strong>${value}</div>`;
      });
      html += '</div>';
    }
    
    html += '</div>';
    return html;
  }

  /**
   * Create intermediate message HTML
   */
  createIntermediateMessageHtml(message) {
    const div = document.createElement('div');
    div.className = 'intermediate-message';
    div.textContent = message;
    return div;
  }


  /**
   * Handle message processing for different message types
   */
  processMessageByType(data, bubble, context = {}) {
    let messageContent = context.messageContent || '';
    let allResults = context.allResults || [];
    
    
    // Extra logging right before switch
    
    switch(data.message_type) {
      case 'asking_sites':
        // Handle both old format (data.content) and new format (data.sites)
        if (data.sites && Array.isArray(data.sites)) {
          // New format with clickable sites
          const siteLinks = data.sites.map((site, index, array) => {
            const query = data.query || '';
            const encodedQuery = encodeURIComponent(query);
            const encodedSite = encodeURIComponent(site.domain);
            const href = `/?site=${encodedSite}&query=${encodedQuery}`;
            // Add comma inside the link for better spacing, except for last item
            const siteName = index < array.length - 1 ? `${site.name},` : site.name;
            return `<a href="${href}" target="_blank" style="color: #0066cc; text-decoration: none; margin-right: 6px;">${siteName}</a>`;
          }).join(' ');
          messageContent = `Searching: ${siteLinks}\n\n`;
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        } else if (data.content) {
          // Old format fallback
          messageContent = `Searching: ${data.content}\n\n`;
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
        break;
        
      case 'decontextualized_query':
        // Display the decontextualized query if different from original
        if (data.decontextualized_query && data.original_query && 
            data.decontextualized_query !== data.original_query) {
          const decontextMsg = `<div style="font-style: italic; color: #666; margin-bottom: 10px;">Query interpreted as: "${data.decontextualized_query}"</div>`;
          messageContent = messageContent + decontextMsg;
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
        break;
        
      case 'result':
        if (data.content && Array.isArray(data.content)) {
          allResults = allResults.concat(data.content);
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
        break;
        
      case 'nlws':
        if (data.answer && typeof data.answer === 'string') {
          messageContent = data.answer + '\n\n';
        }
        if (data.items && Array.isArray(data.items)) {
          allResults = data.items;
        }
        bubble.innerHTML = messageContent + this.renderItems(allResults);
        break;
        
      case 'summary':
        if (data.content) {
          const summaryDiv = this.createIntermediateMessageHtml(data.content);
          bubble.innerHTML = messageContent + this.renderItems(allResults);
          bubble.appendChild(summaryDiv);
        }
        break;
        
      case 'ensemble_result':
        // Handle ensemble result message type
        if (data.result && data.result.recommendations) {
          const ensembleHtml = this.renderEnsembleResult(data.result);
          bubble.innerHTML = messageContent + ensembleHtml + this.renderItems(allResults);
        }
        break;
        
      case 'item_details':
        // Handle item_details message type
        // Map details to description for proper rendering
        let description = data.details;
        
        // If details is an object (like nutrition info), format it as a string
        if (typeof data.details === 'object' && data.details !== null) {
          description = Object.entries(data.details)
            .map(([key, value]) => `${key}: ${value}`)
            .join(', ');
        }
        
        const mappedData = {
          ...data,
          description: description
        };
        
        // Add to results array
        allResults.push(mappedData);
        bubble.innerHTML = messageContent + this.renderItems(allResults);
        break;
        
      case 'intermediate_message':
        // Handle intermediate messages with temp_intermediate class
        const tempContainer = document.createElement('div');
        tempContainer.className = 'temp_intermediate';
        
        if (data.content) {
          // Use the same rendering as result
          tempContainer.innerHTML = this.renderItems(data.content);
        } else if (data.content) {
          tempContainer.textContent = data.content;
        }
        
        bubble.innerHTML = messageContent + this.renderItems(allResults);
        bubble.appendChild(tempContainer);
        break;
        
      case 'ask_user':
        if (data.content) {
          messageContent += data.content + '\n';
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
        break;
        
      case 'remember':
        if (data.item_to_remember) {
          // Handle remember message
          const rememberMsg = `<div style="background-color: #e8f4f8; padding: 10px; border-radius: 6px; margin-bottom: 10px; color: #0066cc;">I will remember that</div>`;
          messageContent = rememberMsg + messageContent;
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
        break;
        
      case 'multi_site_complete':
        // Rerank results for diversity when all sites complete
        if (allResults && allResults.length > 0 && context.selectedSite === 'all') {
          const rerankedResults = this.rerankResults(allResults);
          allResults = rerankedResults;
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        } else {
        }
        break;
        
      case 'query_analysis':
        // Handle query analysis which may include decontextualized query
        if (data.decontextualized_query && data.original_query && 
            data.decontextualized_query !== data.original_query) {
          const decontextMsg = `<div style="font-style: italic; color: #666; margin-bottom: 10px;">Query interpreted as: "${data.decontextualized_query}"</div>`;
          messageContent = messageContent + decontextMsg;
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
        
        // Also check for item_to_remember in query_analysis
        if (data.item_to_remember) {
          const rememberMsg = `<div style="background-color: #e8f4f8; padding: 10px; border-radius: 6px; margin-bottom: 10px; color: #0066cc;">I will remember that: "${data.item_to_remember}"</div>`;
          messageContent = rememberMsg + messageContent;
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
        break;
        
      case 'chart_result':
        // Handle chart result (web components)
        if (data.html) {
          // Ensure DataCommons script is loaded (only once)
          if (!document.querySelector('script[src*="datacommons.org/datacommons.js"]')) {
            const script = document.createElement('script');
            script.src = 'https://datacommons.org/datacommons.js';
            script.async = true;
            document.head.appendChild(script);
          }
          
          // Create container for the chart
          const chartContainer = document.createElement('div');
          chartContainer.className = 'chart-result-container';
          chartContainer.style.cssText = 'margin: 15px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px; min-height: 400px;';
          
          // Parse the HTML to extract just the web component (remove script tags)
          const parser = new DOMParser();
          const doc = parser.parseFromString(data.html, 'text/html');
          
          // Find all datacommons elements
          const datacommonsElements = doc.querySelectorAll('[datacommons-scatter], [datacommons-bar], [datacommons-line], [datacommons-pie], [datacommons-map], datacommons-scatter, datacommons-bar, datacommons-line, datacommons-pie, datacommons-map, datacommons-highlight, datacommons-ranking');
          
          // Append each web component directly
          datacommonsElements.forEach(element => {
            // Clone the element to ensure we get all attributes
            const clonedElement = element.cloneNode(true);
            chartContainer.appendChild(clonedElement);
          });
          
          // If no datacommons elements found, try to add the raw HTML (excluding scripts)
          if (datacommonsElements.length === 0) {
            const allElements = doc.body.querySelectorAll('*:not(script)');
            allElements.forEach(element => {
              chartContainer.appendChild(element.cloneNode(true));
            });
          }
          
          // Append the chart to the message content
          bubble.innerHTML = messageContent + this.renderItems(allResults);
          bubble.appendChild(chartContainer);
          
          // Force re-initialization of Data Commons components if available
          if (window.datacommons && window.datacommons.init) {
            setTimeout(() => {
              window.datacommons.init();
            }, 100);
          }
        }
        break;
        
      case 'results_map':
        // Handle results map
        if (data.locations && Array.isArray(data.locations) && data.locations.length > 0) {
          // Create container for the map
          const mapContainer = document.createElement('div');
          mapContainer.className = 'results-map-container';
          mapContainer.style.cssText = 'margin: 15px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px;';
          
          // Create the map div
          const mapDiv = document.createElement('div');
          mapDiv.id = 'results-map-' + Date.now();
          mapDiv.style.cssText = 'width: 100%; height: 250px; border-radius: 6px;';
          
          // Add a title
          const mapTitle = document.createElement('h3');
          mapTitle.textContent = 'Result Locations';
          mapTitle.style.cssText = 'margin: 0 0 10px 0; color: #333; font-size: 1.1em;';
          
          mapContainer.appendChild(mapTitle);
          mapContainer.appendChild(mapDiv);
          
          // Prepend map BEFORE the results
          bubble.innerHTML = ''; // Clear existing content
          bubble.appendChild(mapContainer); // Add map first
          
          // Then add the message content and results
          const contentDiv = document.createElement('div');
          contentDiv.innerHTML = messageContent + this.renderItems(allResults);
          bubble.appendChild(contentDiv);
        }
        break;
        
      case 'complete':
        // Completion handled elsewhere
        break;
        
      default:
        // For other message types, just update if there's content
        if (data.content) {
          messageContent += data.content + '\n';
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
    }
    
    // Preserve all context properties when returning
    return { ...context, messageContent, allResults };
  }

  renderEnsembleResult(result) {
    if (!result || !result.recommendations) return '';
    
    const recommendations = result.recommendations;
    
    // Create ensemble result container
    const container = document.createElement('div');
    container.className = 'ensemble-result-container';
    container.style.cssText = 'background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 16px 0;';
    
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
    
    return container.outerHTML;
  }
  
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
    if (item.category) {
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
    }
    
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
    if (item.description) {
      const description = document.createElement('p');
      description.textContent = item.description;
      description.style.cssText = 'color: #666; margin: 10px 0; line-height: 1.5;';
      contentContainer.appendChild(description);
    }
    
    // Why recommended
    if (item.why_recommended) {
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
    }
    
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
    
    // Add content container to flex container
    flexContainer.appendChild(contentContainer);
    
    // Add flex container to card
    card.appendChild(flexContainer);
    
    return card;
  }

  /**
   * Render Cricket Statistics with formatted table
   */
  renderCricketStatistics(item) {
    const container = document.createElement('div');
    container.className = 'cricket-stats-container';
    container.style.cssText = 'background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 10px 0;';
    
    // Add title
    if (item.name) {
      const title = document.createElement('h3');
      title.textContent = item.name;
      title.style.cssText = 'color: #333; margin: 0 0 15px 0; font-size: 1.1em;';
      container.appendChild(title);
    }
    
    // Parse and render the description which contains the formatted table
    if (item.description) {
      const lines = item.description.split('\n');
      let inTable = false;
      let tableHtml = '';
      let preContent = '';
      let headerFound = false;
      
      let rowCount = 0;
      for (const line of lines) {
        // Skip "KEY INSIGHTS" section entirely
        if (line.includes('=== KEY INSIGHTS')) {
          break; // Stop processing once we hit insights section
        }
        
        // Skip header lines we don't want
        if (line.includes('=== CRICKET STATISTICS ANALYSIS ===') ||
            line.includes('=== DATA TABLE ===') ||
            line.startsWith('Query Type:') ||
            line.startsWith('Total Records:') ||
            line.startsWith('Tournament:')) {
          continue;
        }
        
        // Skip pure separator lines (only contains -, +, |, and spaces)
        if (line.match(/^[\s\-+|]+$/)) {
          continue;
        }
        
        // Check if this is a table line (contains | but not just separator)
        if (line.includes('|')) {
          if (!inTable) {
            // Start of table
            if (preContent) {
              const pre = document.createElement('div');
              pre.style.cssText = 'margin-bottom: 15px; color: #666;';
              pre.textContent = preContent;
              container.appendChild(pre);
              preContent = '';
            }
            inTable = true;
            tableHtml = '<table style="width: 100%; border-collapse: collapse; background: white; border-radius: 4px; overflow: hidden;">';
            rowCount = 0;
          }
          
          const cells = line.split('|').map(cell => cell.trim()).filter(cell => cell);
          if (cells.length > 0) {
            // Only first row with actual content is header
            const isHeader = !headerFound;
            if (isHeader) {
              headerFound = true;
            }
            
            const cellTag = isHeader ? 'th' : 'td';
            let rowStyle = '';
            
            if (isHeader) {
              rowStyle = 'background: #0066cc; color: white;';
            } else {
              // Alternating row backgrounds for data rows
              rowStyle = rowCount % 2 === 0 ? 'background: #f9f9f9;' : 'background: white;';
              rowCount++;
            }
            
            tableHtml += `<tr style="${rowStyle}">`;
            for (const cell of cells) {
              const cellStyle = isHeader 
                ? 'padding: 10px; text-align: left; font-weight: 600;' 
                : 'padding: 10px; text-align: left; border-bottom: 1px solid #e9e9e9;';
              tableHtml += `<${cellTag} style="${cellStyle}">${this.escapeHtml(cell)}</${cellTag}>`;
            }
            tableHtml += '</tr>';
          }
        } else {
          // Not a table line
          if (inTable) {
            // End of table
            tableHtml += '</table>';
            const tableContainer = document.createElement('div');
            tableContainer.style.cssText = 'overflow-x: auto; margin: 15px 0;';
            tableContainer.innerHTML = tableHtml;
            container.appendChild(tableContainer);
            inTable = false;
            tableHtml = '';
            headerFound = false;
          }
          
          if (line.trim() && !line.includes('=== KEY INSIGHTS')) {
            preContent += (preContent ? '\n' : '') + line;
          }
        }
      }
      
      // Handle any remaining table
      if (inTable && tableHtml) {
        tableHtml += '</table>';
        const tableContainer = document.createElement('div');
        tableContainer.style.cssText = 'overflow-x: auto; margin: 15px 0;';
        tableContainer.innerHTML = tableHtml;
        container.appendChild(tableContainer);
      }
      
      // Don't show remaining content if it's just whitespace
      if (preContent && preContent.trim()) {
        const post = document.createElement('div');
        post.style.cssText = 'margin-top: 15px; color: #666; white-space: pre-wrap;';
        post.textContent = preContent;
        container.appendChild(post);
      }
    }
    
    // Add metadata footer if available
    if (item.metadata) {
      const footer = document.createElement('div');
      footer.style.cssText = 'margin-top: 15px; padding-top: 10px; border-top: 1px solid #e0e0e0; font-size: 0.9em; color: #666;';
      footer.textContent = `Source: ${item.metadata.source || 'CricketLens'}`;
      container.appendChild(footer);
    }
    
    return container;
  }
  
  /**
   * Escape HTML to prevent XSS
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  /**
   * Rerank results to ensure top 3 are from different sites for diversity
   */
  rerankResults(items) {
    if (!items || items.length === 0) return items;
    
    // Create a copy to avoid mutating original
    let results = items.map(item => ({ ...item }));
    
    // Sort by score initially
    results.sort((a, b) => (b.score || 0) - (a.score || 0));
    
    // If we have less than 3 results, just return sorted
    if (results.length <= 3) return results;
    
    const rerankedResults = [];
    const usedSites = new Set();
    const remainingResults = [...results];
    
    // Pick top 3 from different sites
    for (let position = 0; position < 3 && remainingResults.length > 0; position++) {
      let selectedIndex = -1;
      
      // Find the highest scoring result from a site not yet used
      for (let i = 0; i < remainingResults.length; i++) {
        const site = remainingResults[i].site || remainingResults[i].siteUrl || '';
        
        // If this is from a new site (or the first result), select it
        if (!usedSites.has(site)) {
          selectedIndex = i;
          usedSites.add(site);
          break;
        }
      }
      
      // If we couldn't find a result from a new site, just take the highest scoring one
      if (selectedIndex === -1) {
        selectedIndex = 0;
        const site = remainingResults[0].site || remainingResults[0].siteUrl || '';
        usedSites.add(site);
      }
      
      // Add the selected result and remove it from remaining
      rerankedResults.push(remainingResults[selectedIndex]);
      remainingResults.splice(selectedIndex, 1);
    }
    
    // Add all remaining results in score order (they're already sorted)
    rerankedResults.push(...remainingResults);
    
    // Log diversity metrics for debugging
    const topThreeSites = rerankedResults.slice(0, 3).map(r => r.site || r.siteUrl || 'unknown');
    const uniqueTopSites = new Set(topThreeSites).size;
    
    return rerankedResults;
  }
}
