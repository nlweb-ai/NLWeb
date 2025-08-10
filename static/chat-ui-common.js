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
  }

  /**
   * Render multiple items/results
   */
  renderItems(items) {
    if (!items || items.length === 0) return '';
    
    // Sort items by score in descending order
    const sortedItems = [...items].sort((a, b) => {
      const scoreA = a.score || 0;
      const scoreB = b.score || 0;
      return scoreB - scoreA;
    });
    
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
      } else if (schemaObj.image['@id']) {
        return schemaObj.image['@id'];
      } else if (Array.isArray(schemaObj.image) && schemaObj.image.length > 0) {
        return this.extractImageUrl({ image: schemaObj.image[0] });
      }
    }
    
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
    
    switch(data.message_type) {
      case 'asking_sites':
        if (data.message) {
          messageContent = `Searching: ${data.message}\n\n`;
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
        break;
        
      case 'decontextualized_query':
        // Display the decontextualized query if different from original
        if (data.decontextualized_query && data.original_query && 
            data.decontextualized_query !== data.original_query) {
          const decontextMsg = `<div style="font-style: italic; color: #666; margin-bottom: 10px;">Query interpreted as: "${data.decontextualized_query}"</div>`;
          messageContent = decontextMsg + messageContent;
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
        break;
        
      case 'result_batch':
        if (data.results && Array.isArray(data.results)) {
          allResults = allResults.concat(data.results);
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
        if (data.message) {
          const summaryDiv = this.createIntermediateMessageHtml(data.message);
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
        
        if (data.results) {
          // Use the same rendering as result_batch
          tempContainer.innerHTML = this.renderItems(data.results);
        } else if (data.message) {
          tempContainer.textContent = data.message;
        }
        
        bubble.innerHTML = messageContent + this.renderItems(allResults);
        bubble.appendChild(tempContainer);
        break;
        
      case 'ask_user':
        if (data.message) {
          messageContent += data.message + '\n';
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
        
      case 'query_analysis':
        // Handle query analysis which may include decontextualized query
        if (data.decontextualized_query && data.original_query && 
            data.decontextualized_query !== data.original_query) {
          const decontextMsg = `<div style="font-style: italic; color: #666; margin-bottom: 10px;">Query interpreted as: "${data.decontextualized_query}"</div>`;
          messageContent = decontextMsg + messageContent;
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
          // Create container for the chart
          const chartContainer = document.createElement('div');
          chartContainer.className = 'chart-result-container';
          chartContainer.style.cssText = 'margin: 15px 0; padding: 15px; background-color: #f8f9fa; border-radius: 8px; min-height: 400px;';
          
          // Parse the HTML to extract just the web component (remove script tags)
          const parser = new DOMParser();
          const doc = parser.parseFromString(data.html, 'text/html');
          
          // Find all datacommons elements
          const datacommonsElements = doc.querySelectorAll('[datacommons-scatter], [datacommons-bar], [datacommons-line], [datacommons-pie], [datacommons-map], datacommons-scatter, datacommons-bar, datacommons-line, datacommons-pie, datacommons-map');
          
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
        if (data.message) {
          messageContent += data.message + '\n';
          bubble.innerHTML = messageContent + this.renderItems(allResults);
        }
    }
    
    return { messageContent, allResults };
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
}
