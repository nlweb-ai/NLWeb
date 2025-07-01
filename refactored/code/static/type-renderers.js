/**
 * Type-specific renderers for JSON objects
 */

/**
 * Base class for type-specific renderers
 */
export class TypeRenderer {
  /**
   * Creates a new TypeRenderer
   * 
   * @param {JsonRenderer} jsonRenderer - The parent JSON renderer
   */
  constructor(jsonRenderer) {
    this.jsonRenderer = jsonRenderer;
  }
  
  /**
   * Renders an item
   * 
   * @param {Object} item - The item to render
   * @returns {HTMLElement} - The rendered HTML
   */
  render(item) {
    // To be implemented by subclasses
    return null;
  }
}

/**
 * Renderer for real estate listings
 */
export class RealEstateRenderer extends TypeRenderer {
  /**
   * Types that this renderer can handle
   * 
   * @returns {Array<string>} - The types this renderer can handle
   */
  static get supportedTypes() {
    return [
      "SingleFamilyResidence", 
      "Apartment", 
      "Townhouse", 
      "House", 
      "Condominium", 
      "RealEstateListing"
    ];
  }
  
  /**
   * Renders a real estate item
   * 
   * @param {Object} item - The item to render
   * @returns {HTMLElement} - The rendered HTML
   */
  render(item) {
    // Use the default item HTML as a base
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    
    // Find the content div
    const contentDiv = element.querySelector('.item-content');
    if (!contentDiv) return element;
    
    // Add real estate specific details
    const detailsDiv = this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
    if (!detailsDiv) return element;
    
    detailsDiv.className = 'item-real-estate-details';
    
    const schema = item.schema_object;
    if (!schema) return element;
    
    const price = schema.price;
    const address = schema.address || {};
    const numBedrooms = schema.numberOfRooms;
    const numBathrooms = schema.numberOfBathroomsTotal;
    const sqft = schema.floorSize?.value;
    
    let priceValue = price;
    if (typeof price === 'object') {
      priceValue = price.price || price.value || price;
      if (typeof priceValue === 'number') {
        priceValue = Math.round(priceValue / 100000) * 100000;
        priceValue = priceValue.toLocaleString('en-US');
      }
    }

    const streetAddress = address.streetAddress || '';
    const addressLocality = address.addressLocality || '';
    detailsDiv.appendChild(this.jsonRenderer.makeAsSpan(`${streetAddress}, ${addressLocality}`));
    detailsDiv.appendChild(document.createElement('br'));
    
    const bedroomsText = numBedrooms || '0';
    const bathroomsText = numBathrooms || '0';
    const sqftText = sqft || '0';
    detailsDiv.appendChild(this.jsonRenderer.makeAsSpan(`${bedroomsText} bedrooms, ${bathroomsText} bathrooms, ${sqftText} sqft`));
    detailsDiv.appendChild(document.createElement('br'));
    
    if (priceValue) {
      detailsDiv.appendChild(this.jsonRenderer.makeAsSpan(`Listed at ${priceValue}`));
    }
    
    return element;
  }
}

/**
 * Renderer for podcast episodes
 */
export class PodcastEpisodeRenderer extends TypeRenderer {
  /**
   * Types that this renderer can handle
   * 
   * @returns {Array<string>} - The types this renderer can handle
   */
  static get supportedTypes() {
    return ["PodcastEpisode"];
  }
  
  /**
   * Renders a podcast episode item
   * 
   * @param {Object} item - The item to render
   * @returns {HTMLElement} - The rendered HTML
   */
  render(item) {
    // Use the default item HTML as a base
    const element = this.jsonRenderer.createDefaultItemHtml(item);
    
    // Find the content div
    const contentDiv = element.querySelector('.item-content');
    if (!contentDiv) return element;
    
    // Add podcast specific details - in this case just ensure explanation is shown
    this.jsonRenderer.possiblyAddExplanation(item, contentDiv, true);
    
    return element;
  }
}

/**
 * Factory for creating type renderers
 */
export class TypeRendererFactory {
  /**
   * Registers all type renderers with a JSON renderer
   * 
   * @param {JsonRenderer} jsonRenderer - The JSON renderer to register with
   */
  static registerAll(jsonRenderer) {
    TypeRendererFactory.registerRenderer(RealEstateRenderer, jsonRenderer);
    TypeRendererFactory.registerRenderer(PodcastEpisodeRenderer, jsonRenderer);
    // RecipeRenderer will be registered separately
    // Add more renderers here as needed
  }
  
  /**
   * Registers a specific renderer with a JSON renderer
   * 
   * @param {Function} RendererClass - The renderer class
   * @param {JsonRenderer} jsonRenderer - The JSON renderer to register with
   */
  static registerRenderer(RendererClass, jsonRenderer) {
    const renderer = new RendererClass(jsonRenderer);
    
    RendererClass.supportedTypes.forEach(type => {
      jsonRenderer.registerTypeRenderer(type, (item) => renderer.render(item));
    });
  }
}