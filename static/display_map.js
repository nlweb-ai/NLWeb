/**
 * Display Map Module
 * Handles displaying location results as a list
 */

export class MapDisplay {
  /**
   * Display locations as a list
   * @param {HTMLElement} mapDiv - The div element to render the list in
   * @param {Array} locations - Array of location objects with title and address
   */
  static initializeResultsMap(mapDiv, locations) {
    
    // Always show location list (Google Maps removed)
    this.showLocationList(mapDiv, locations);
  }
  
  /**
   * Show location list
   * @param {HTMLElement} mapDiv - The container element
   * @param {Array} locations - Array of location objects with title and address
   */
  static showLocationList(mapDiv, locations) {
    
    mapDiv.style.height = 'auto';
    mapDiv.innerHTML = '';
    
    // Create a styled list container
    const listContainer = document.createElement('div');
    listContainer.style.cssText = `
      background: #f9f9f9;
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 15px;
    `;
    
    // Add a header
    const header = document.createElement('h4');
    header.textContent = 'Location Addresses:';
    header.style.cssText = 'margin: 0 0 15px 0; color: #333;';
    listContainer.appendChild(header);
    
    // Create the location list
    const list = document.createElement('div');
    list.style.cssText = 'display: flex; flex-direction: column; gap: 10px;';
    
    locations.forEach((location, index) => {
      const locationItem = document.createElement('div');
      locationItem.style.cssText = `
        background: white;
        padding: 12px;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        display: flex;
        align-items: flex-start;
        gap: 10px;
      `;
      
      // Number badge
      const numberBadge = document.createElement('div');
      numberBadge.textContent = (index + 1).toString();
      numberBadge.style.cssText = `
        background: #4285f4;
        color: white;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 12px;
        flex-shrink: 0;
      `;
      
      // Location details
      const details = document.createElement('div');
      details.style.cssText = 'flex: 1;';
      
      const title = document.createElement('div');
      title.textContent = location.title;
      title.style.cssText = 'font-weight: 600; color: #333; margin-bottom: 5px;';
      
      const address = document.createElement('div');
      // Clean up the address if needed
      let cleanAddress = location.address;
      if (cleanAddress.includes('{')) {
        cleanAddress = cleanAddress.split(', {')[0];
      }
      address.textContent = cleanAddress;
      address.style.cssText = 'color: #666; font-size: 0.9em; line-height: 1.4;';
      
      details.appendChild(title);
      details.appendChild(address);
      
      locationItem.appendChild(numberBadge);
      locationItem.appendChild(details);
      
      list.appendChild(locationItem);
    });
    
    listContainer.appendChild(list);
    mapDiv.appendChild(listContainer);
    
  }
}
