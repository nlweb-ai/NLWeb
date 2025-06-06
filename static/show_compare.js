/**
 * show_compare.js
 * Handles the display of comparison messages between two items
 */

export function handleCompareItems(data, chatInterface) {
  // Basic validation
  if (!data || typeof data !== 'object') return;
  
  // Clear existing content safely
  while (chatInterface.bubble.firstChild) {
    chatInterface.bubble.removeChild(chatInterface.bubble.firstChild);
  }
  
  // Display the comparison summary with expand/collapse functionality
  if (typeof data.comparison === 'string') {
    const summaryContainer = document.createElement('div');
    summaryContainer.style.marginBottom = '15px';
    
    // Create a temporary element to measure text height
    const measureDiv = document.createElement('div');
    measureDiv.style.position = 'absolute';
    measureDiv.style.visibility = 'hidden';
    measureDiv.style.width = '100%';
    measureDiv.style.lineHeight = '1.5';
    measureDiv.innerHTML = data.comparison;
    document.body.appendChild(measureDiv);
    
    // Calculate approximate number of lines (assuming ~1.5em line height)
    const lineHeight = parseFloat(window.getComputedStyle(measureDiv).lineHeight) || 24;
    const totalHeight = measureDiv.offsetHeight;
    const estimatedLines = Math.ceil(totalHeight / lineHeight);
    document.body.removeChild(measureDiv);
    
    // If more than 4 lines, create expandable version
    if (estimatedLines > 4) {
      const summaryDiv = document.createElement('div');
      summaryDiv.style.lineHeight = '1.5';
      summaryDiv.style.position = 'relative';
      
      // Create collapsed version
      const collapsedDiv = document.createElement('div');
      collapsedDiv.style.overflow = 'hidden';
      collapsedDiv.style.maxHeight = `${lineHeight * 4}px`;
      collapsedDiv.innerHTML = data.comparison;
      
      // Create expanded version (hidden initially)
      const expandedDiv = document.createElement('div');
      expandedDiv.style.display = 'none';
      expandedDiv.innerHTML = data.comparison;
      
      // Create more/less links
      const moreLink = document.createElement('a');
      moreLink.href = '#';
      moreLink.textContent = '...more';
      moreLink.style.color = '#0066cc';
      moreLink.style.textDecoration = 'none';
      moreLink.style.marginLeft = '5px';
      moreLink.onclick = (e) => {
        e.preventDefault();
        collapsedDiv.style.display = 'none';
        moreLink.style.display = 'none';
        expandedDiv.style.display = 'block';
        lessLink.style.display = 'inline';
      };
      
      const lessLink = document.createElement('a');
      lessLink.href = '#';
      lessLink.textContent = '...less';
      lessLink.style.color = '#0066cc';
      lessLink.style.textDecoration = 'none';
      lessLink.style.marginLeft = '5px';
      lessLink.style.display = 'none';
      lessLink.onclick = (e) => {
        e.preventDefault();
        collapsedDiv.style.display = 'block';
        moreLink.style.display = 'inline';
        expandedDiv.style.display = 'none';
        lessLink.style.display = 'none';
      };
      
      summaryDiv.appendChild(collapsedDiv);
      summaryDiv.appendChild(moreLink);
      summaryDiv.appendChild(expandedDiv);
      summaryDiv.appendChild(lessLink);
      summaryContainer.appendChild(summaryDiv);
    } else {
      // If 4 lines or less, just display normally
      const summaryDiv = chatInterface.createIntermediateMessageHtml(data.comparison);
      summaryContainer.appendChild(summaryDiv);
    }
    
    chatInterface.bubble.appendChild(summaryContainer);
  }
  
  // Create a container for the two items
  const comparisonContainer = document.createElement('div');
  comparisonContainer.style.display = 'grid';
  comparisonContainer.style.gridTemplateColumns = '1fr 1fr';
  comparisonContainer.style.gap = '20px';
  comparisonContainer.style.marginTop = '20px';
  
  // Helper function to truncate text
  const truncateText = (text, maxLength = 50) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };
  
  // Helper function to extract image from schema
  const extractImage = (schemaStr) => {
    try {
      const parsed = JSON.parse(schemaStr);
      if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].image) {
        return parsed[0].image;
      }
    } catch (e) {
      console.error('Error extracting image:', e);
    }
    return null;
  };
  
  // Process item1
  if (data.item1) {
    const item1Container = document.createElement('div');
    item1Container.style.border = '1px solid #e0e0e0';
    item1Container.style.borderRadius = '8px';
    item1Container.style.padding = '15px';
    
    // Create header with item name
    const item1Header = document.createElement('h4');
    const item1Name = data.item1.name || 'Item 1';
    item1Header.textContent = truncateText(item1Name);
    item1Header.title = item1Name; // Show full name on hover
    item1Header.style.marginBottom = '10px';
    item1Header.style.fontSize = '16px';
    item1Header.style.fontWeight = 'bold';
    item1Container.appendChild(item1Header);
    
    // Add image if available
    const item1Image = extractImage(data.item1.schema_object);
    if (item1Image) {
      const img1 = document.createElement('img');
      img1.src = item1Image;
      img1.style.width = '100%';
      img1.style.maxHeight = '150px';
      img1.style.objectFit = 'cover';
      img1.style.borderRadius = '4px';
      img1.style.marginBottom = '10px';
      item1Container.appendChild(img1);
    }
    
    // Parse and display schema object
    let item1Data = data.item1.schema_object;
    if (typeof item1Data === 'string') {
      try {
        item1Data = JSON.parse(item1Data);
      } catch (e) {
        console.error('Error parsing item1 schema:', e);
      }
    }
    
    // If it's an array, take the first item
    if (Array.isArray(item1Data) && item1Data.length > 0) {
      item1Data = item1Data[0];
    }
    
    // Create HTML for item1
    const item1Html = chatInterface.createJsonItemHtml(item1Data);
    item1Container.appendChild(item1Html);
    
    // Add URL link if available
    if (data.item1.url) {
      const link1 = document.createElement('a');
      link1.href = data.item1.url;
      link1.target = '_blank';
      link1.textContent = 'View Recipe →';
      link1.style.display = 'inline-block';
      link1.style.marginTop = '10px';
      link1.style.color = '#0066cc';
      link1.style.textDecoration = 'none';
      item1Container.appendChild(link1);
    }
    
    comparisonContainer.appendChild(item1Container);
  }
  
  // Process item2
  if (data.item2) {
    const item2Container = document.createElement('div');
    item2Container.style.border = '1px solid #e0e0e0';
    item2Container.style.borderRadius = '8px';
    item2Container.style.padding = '15px';
    
    // Create header with item name
    const item2Header = document.createElement('h4');
    const item2Name = data.item2.name || 'Item 2';
    item2Header.textContent = truncateText(item2Name);
    item2Header.title = item2Name; // Show full name on hover
    item2Header.style.marginBottom = '10px';
    item2Header.style.fontSize = '16px';
    item2Header.style.fontWeight = 'bold';
    item2Container.appendChild(item2Header);
    
    // Add image if available
    const item2Image = extractImage(data.item2.schema_object);
    if (item2Image) {
      const img2 = document.createElement('img');
      img2.src = item2Image;
      img2.style.width = '100%';
      img2.style.maxHeight = '150px';
      img2.style.objectFit = 'cover';
      img2.style.borderRadius = '4px';
      img2.style.marginBottom = '10px';
      item2Container.appendChild(img2);
    }
    
    // Parse and display schema object
    let item2Data = data.item2.schema_object;
    if (typeof item2Data === 'string') {
      try {
        item2Data = JSON.parse(item2Data);
      } catch (e) {
        console.error('Error parsing item2 schema:', e);
      }
    }
    
    // If it's an array, take the first item
    if (Array.isArray(item2Data) && item2Data.length > 0) {
      item2Data = item2Data[0];
    }
    
    // Create HTML for item2
    const item2Html = chatInterface.createJsonItemHtml(item2Data);
    item2Container.appendChild(item2Html);
    
    // Add URL link if available
    if (data.item2.url) {
      const link2 = document.createElement('a');
      link2.href = data.item2.url;
      link2.target = '_blank';
      link2.textContent = 'View Recipe →';
      link2.style.display = 'inline-block';
      link2.style.marginTop = '10px';
      link2.style.color = '#0066cc';
      link2.style.textDecoration = 'none';
      item2Container.appendChild(link2);
    }
    
    comparisonContainer.appendChild(item2Container);
  }
  
  // Append the comparison container
  chatInterface.bubble.appendChild(comparisonContainer);
}