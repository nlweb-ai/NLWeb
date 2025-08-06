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
        // For ensemble results, render the items as regular results
        if (data.result && data.result.recommendations && data.result.recommendations.items) {
          // Add ensemble items to results
          allResults = allResults.concat(data.result.recommendations.items);
          bubble.innerHTML = messageContent + this.renderItems(allResults);
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
}