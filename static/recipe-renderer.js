/**
 * Renderer for recipes
 */
export class RecipeRenderer {
    /**
     * Creates a new RecipeRenderer
     * 
     * @param {JsonRenderer} jsonRenderer - The parent JSON renderer
     */
    constructor(jsonRenderer) {
      this.jsonRenderer = jsonRenderer;
    }
  
    /**
     * Types that this renderer can handle
     * 
     * @returns {Array<string>} - The types this renderer can handle
     */
    static get supportedTypes() {
      return ["Recipe"];
    }
    
    /**
     * Renders a recipe item
     * 
     * @param {Object} item - The item to render
     * @returns {HTMLElement} - The rendered HTML
     */
    render(item) {
      // Use the default item HTML as a base
      const element = this.jsonRenderer.createDefaultItemHtml(item);
      
      // Find the content div
      const contentDiv = element.querySelector('.item-content');
      if (!contentDiv || !item.schema_object) return element;
      
      // Add recipe specific details
      const detailsDiv = this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
      if (!detailsDiv) return element;
      
      detailsDiv.className = 'item-recipe-details';
      
      const schema = item.schema_object;
      
      // Add author if available
      if (schema.author) {
        const authorDiv = document.createElement('div');
        authorDiv.className = 'recipe-author';
        
        // Safe user data handling: properly fetch and validate the author name
        let authorName = '';
        
        // Handle different author formats
        if (typeof schema.author === 'string') {
          // Author is a simple string
          authorName = schema.author;
        } else if (Array.isArray(schema.author) && schema.author.length > 0) {
          // Author is an array
          if (typeof schema.author[0] === 'object' && schema.author[0].name) {
            authorName = schema.author[0].name;
          } else if (typeof schema.author[0] === 'string') {
            authorName = schema.author[0];
          }
        } else if (typeof schema.author === 'object' && schema.author.name) {
          // Author is an object with name property
          authorName = schema.author.name;
        }
        
        if (authorName) {
          // Decode HTML entities in author name
          const decodedAuthorName = this.jsonRenderer.htmlUnescape(authorName);
          authorDiv.textContent = `By ${decodedAuthorName}`;
          authorDiv.style.fontSize = '0.85em';
          authorDiv.style.color = '#666';
          authorDiv.style.marginTop = '5px';
          authorDiv.style.marginBottom = '5px';
          
          detailsDiv.appendChild(authorDiv);
        }
      }
      
      // Add rating as stars
      if (schema.aggregateRating) {
        let rating = 0;
        let reviewCount = 0;
        
        // Safe data handling for rating value
        if (schema.aggregateRating.ratingValue !== undefined) {
          const ratingValue = parseFloat(schema.aggregateRating.ratingValue);
          if (!isNaN(ratingValue)) {
            rating = ratingValue;
          }
        }
        
        // Safe data handling for review count
        const reviewArrayCount = schema.review && Array.isArray(schema.review) ? schema.review.length : 0;
        let ratingObjectCount = 0;
        
        if (schema.aggregateRating.ratingCount !== undefined) {
          const parsedCount = parseInt(schema.aggregateRating.ratingCount, 10);
          if (!isNaN(parsedCount)) {
            ratingObjectCount = parsedCount;
          }
        }
        
        reviewCount = Math.max(reviewArrayCount, ratingObjectCount);
        
        const ratingDiv = document.createElement('div');
        ratingDiv.className = 'recipe-rating';
        ratingDiv.style.marginTop = '8px';
        ratingDiv.style.marginBottom = '8px';
        
        // Create star rating display
        const starsSpan = document.createElement('span');
        starsSpan.className = 'recipe-stars';
        starsSpan.textContent = this.generateStars(rating);
        starsSpan.style.color = '#FFD700'; // Gold color
        starsSpan.style.fontSize = '0.85em';
        ratingDiv.appendChild(starsSpan);
        
        // Add review count
        const reviewSpan = document.createElement('span');
        reviewSpan.className = 'recipe-reviews';
        reviewSpan.textContent = ` (${reviewCount} ${reviewCount === 1 ? 'review' : 'reviews'})`;
        reviewSpan.style.fontSize = '0.85em';
        reviewSpan.style.color = '#666';
        ratingDiv.appendChild(reviewSpan);
        
        detailsDiv.appendChild(ratingDiv);
      }
      
      // Add preparation/total time
      const timeValue = this.getTimeInfo(schema);
      if (timeValue) {
        const prepTimeDiv = document.createElement('div');
        prepTimeDiv.className = 'recipe-prep-time';
        prepTimeDiv.textContent = timeValue;
        prepTimeDiv.style.fontSize = '0.85em';
        prepTimeDiv.style.color = '#666';
        prepTimeDiv.style.marginTop = '5px';
        prepTimeDiv.style.marginBottom = '5px';
        
        detailsDiv.appendChild(prepTimeDiv);
      }
      
      return element;
    }
    
    /**
     * Extracts and formats time information from schema
     * 
     * @param {Object} schema - The recipe schema
     * @returns {string} - Formatted time information
     */
    getTimeInfo(schema) {
      // Check schema is valid
      if (!schema || typeof schema !== 'object') return '';
      
      // Check for different time properties in order of preference
      if (typeof schema.prepTime === 'string' && typeof schema.cookTime === 'string') {
        return `Prep: ${this.formatDuration(schema.prepTime)}, Cook: ${this.formatDuration(schema.cookTime)}`;
      } else if (typeof schema.prepTime === 'string') {
        return `Preparation time: ${this.formatDuration(schema.prepTime)}`;
      } else if (typeof schema.totalTime === 'string') {
        return `Total time: ${this.formatDuration(schema.totalTime)}`;
      } else if (typeof schema.cookTime === 'string') {
        return `Cooking time: ${this.formatDuration(schema.cookTime)}`;
      }
      return '';
    }
    
    /**
     * Generates a star rating display
     * 
     * @param {number} rating - The rating value (0-5)
     * @returns {string} - Star characters representing the rating
     */
    generateStars(rating) {
      // Convert rating to a number and ensure it's between 0 and 5
      const numRating = parseFloat(rating) || 0;
      const clampedRating = Math.max(0, Math.min(5, numRating));
      
      const fullStars = Math.floor(clampedRating);
      const halfStar = clampedRating % 1 >= 0.5;
      const emptyStars = 5 - fullStars - (halfStar ? 1 : 0);
      
      return '★'.repeat(fullStars) + (halfStar ? '½' : '') + '☆'.repeat(emptyStars);
    }
    
    /**
     * Formats an ISO 8601 duration string to human-readable format
     * 
     * @param {string} duration - ISO 8601 duration string (e.g., PT1H30M)
     * @returns {string} - Human-readable duration
     */
    formatDuration(duration) {
      if (!duration || typeof duration !== 'string') return 'Not specified';
      
      // Basic parsing of ISO 8601 duration
      const matches = duration.match(/P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/i);
      if (!matches) return duration; // Return original if can't parse
      
      const days = matches[1] ? parseInt(matches[1], 10) : 0;
      const hours = matches[2] ? parseInt(matches[2], 10) : 0;
      const minutes = matches[3] ? parseInt(matches[3], 10) : 0;
      const seconds = matches[4] ? parseInt(matches[4], 10) : 0;
      
      const parts = [];
      if (days > 0) parts.push(`${days} day${days > 1 ? 's' : ''}`);
      if (hours > 0) parts.push(`${hours} hour${hours > 1 ? 's' : ''}`);
      if (minutes > 0) parts.push(`${minutes} minute${minutes > 1 ? 's' : ''}`);
      if (seconds > 0) parts.push(`${seconds} second${seconds > 1 ? 's' : ''}`);
      
      return parts.join(', ') || 'Instant';
    }
  }