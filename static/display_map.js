/**
 * Display Map Module
 * Handles Google Maps integration for displaying location results
 */

export class MapDisplay {
  /**
   * Initialize a map with location markers
   * @param {HTMLElement} mapDiv - The div element to render the map in
   * @param {Array} locations - Array of location objects with title and address
   */
  static initializeResultsMap(mapDiv, locations) {
    console.log('=== initializeResultsMap Called ===');
    console.log('mapDiv:', mapDiv);
    console.log('locations:', locations);
    console.log('window.GOOGLE_MAPS_API_KEY at map init time:', window.GOOGLE_MAPS_API_KEY);
    console.log('typeof window.GOOGLE_MAPS_API_KEY:', typeof window.GOOGLE_MAPS_API_KEY);
    console.log('window.GOOGLE_MAPS_API_KEY === undefined?', window.GOOGLE_MAPS_API_KEY === undefined);
    
    // Check if API key is configured
    const apiKey = window.GOOGLE_MAPS_API_KEY || 
                  document.body.getAttribute('data-google-maps-api-key') || 
                  'YOUR_API_KEY';
    
    console.log('API Key resolution:');
    console.log('  - window.GOOGLE_MAPS_API_KEY:', window.GOOGLE_MAPS_API_KEY);
    console.log('  - data-google-maps-api-key:', document.body.getAttribute('data-google-maps-api-key'));
    console.log('  - Final apiKey:', apiKey);
    
    if (apiKey === 'YOUR_API_KEY' || !apiKey || apiKey === 'GOOGLE_MAPS_API_KEY') {
      console.warn('Google Maps API key not configured, showing location list instead');
      // Show location list instead of map
      this.showLocationList(mapDiv, locations);
      return;
    }
    
    // Check if Google Maps API is loaded
    if (typeof google === 'undefined' || !google.maps) {
      console.log('Google Maps API not loaded, loading now...');
      this.loadGoogleMapsAPI(apiKey).then(() => {
        this.createMap(mapDiv, locations);
      }).catch(error => {
        console.error('Failed to load Google Maps API:', error);
        // Fallback to showing location list
        this.showLocationList(mapDiv, locations);
      });
    } else {
      this.createMap(mapDiv, locations);
    }
  }
  
  /**
   * Load Google Maps API dynamically
   * @param {string} apiKey - The Google Maps API key
   * @returns {Promise} Promise that resolves when API is loaded
   */
  static loadGoogleMapsAPI(apiKey) {
    return new Promise((resolve, reject) => {
      // Check if already loading
      if (window.googleMapsAPILoading) {
        // Wait for existing load to complete
        const checkInterval = setInterval(() => {
          if (typeof google !== 'undefined' && google.maps) {
            clearInterval(checkInterval);
            resolve();
          }
        }, 100);
        return;
      }
      
      window.googleMapsAPILoading = true;
      
      // Create script element
      const script = document.createElement('script');
      script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places`;
      script.async = true;
      script.defer = true;
      
      script.onload = () => {
        window.googleMapsAPILoading = false;
        resolve();
      };
      
      script.onerror = () => {
        window.googleMapsAPILoading = false;
        reject(new Error('Failed to load Google Maps API'));
      };
      
      document.head.appendChild(script);
    });
  }
  
  /**
   * Create the Google Map with markers
   * @param {HTMLElement} mapDiv - The map container element
   * @param {Array} locations - Array of location objects
   */
  static createMap(mapDiv, locations) {
    console.log('=== createMap Called ===');
    
    // Initialize the map
    const map = new google.maps.Map(mapDiv, {
      zoom: 10,
      center: { lat: 0, lng: 0 }, // Will be updated based on markers
      mapTypeId: 'roadmap'
    });
    
    // Geocoding service to convert addresses to coordinates
    const geocoder = new google.maps.Geocoder();
    const bounds = new google.maps.LatLngBounds();
    const markers = [];
    let geocodedCount = 0;
    
    // Process each location
    locations.forEach((location, index) => {
      // Clean up the address if needed
      let cleanAddress = location.address;
      if (cleanAddress.includes('{')) {
        cleanAddress = cleanAddress.split(', {')[0];
      }
      
      console.log(`Geocoding location ${index + 1}: ${cleanAddress}`);
      
      // Use setTimeout to avoid rate limiting
      setTimeout(() => {
        geocoder.geocode({ address: cleanAddress }, (results, status) => {
          if (status === 'OK' && results[0]) {
            const position = results[0].geometry.location;
            
            // Create marker
            const marker = new google.maps.Marker({
              position: position,
              map: map,
              title: location.title,
              label: {
                text: (index + 1).toString(),
                color: 'white',
                fontWeight: 'bold'
              }
            });
            
            // Create info window
            const infoWindow = new google.maps.InfoWindow({
              content: `
                <div style="padding: 5px;">
                  <h4 style="margin: 0 0 5px 0; color: #333;">${location.title}</h4>
                  <p style="margin: 0; color: #666; font-size: 0.9em;">${cleanAddress}</p>
                </div>
              `
            });
            
            // Add click listener to marker
            marker.addListener('click', () => {
              infoWindow.open(map, marker);
            });
            
            markers.push(marker);
            bounds.extend(position);
            
            geocodedCount++;
            
            // If all locations are geocoded, fit the map to show all markers
            if (geocodedCount === locations.length) {
              map.fitBounds(bounds);
              
              // Adjust zoom if only one marker
              if (locations.length === 1) {
                map.setZoom(15);
              }
            }
          } else {
            console.error('Geocode failed for location:', cleanAddress, 'Status:', status);
            geocodedCount++;
          }
        });
      }, index * 200); // 200ms delay between requests
    });
  }
  
  /**
   * Show location list as a fallback when map cannot be displayed
   * @param {HTMLElement} mapDiv - The container element
   * @param {Array} locations - Array of location objects with title and address
   */
  static showLocationList(mapDiv, locations) {
    console.log('=== showLocationList Called ===');
    console.log('Number of locations:', locations.length);
    
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
    
    // Add a note about the map
    const note = document.createElement('p');
    note.textContent = 'Map view requires a Google Maps API key to be configured.';
    note.style.cssText = 'margin: 15px 0 0 0; font-size: 0.85em; color: #888; font-style: italic;';
    listContainer.appendChild(note);
    
    mapDiv.appendChild(listContainer);
    
    console.log('Location list created and appended successfully');
  }
}