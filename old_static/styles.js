/**
 * CSS Styles for the streaming chat interface
 * Exported as a module for better organization
 */

// Main CSS styles for the chat interface
export const STYLES = `
  /* Container styles */
  .chat-container {
    height: 600px; /* Fixed overall container height */
    width: 80%;
    margin: 0 auto;
    padding: 20px;
    font-family: sans-serif;
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
  }
  
  /* Selector styles */
  .site-selector {
    margin-bottom: 20px;
    flex-shrink: 0; /* Don't allow to shrink */
  }

  .site-selector select {
    padding: 8px;
    font-size: 14px;
    border-radius: 4px;
    border: 1px solid #ccc;
  }
  
  .selector-label {
    margin: 0 5px;
  }
  
  .selector-icon {
    vertical-align: middle;
    cursor: pointer;
    margin-left: 8px;
    width: 16px;
    height: 16px;
  }
  
  /* Messages area styles */
  .messages {
    height: calc(100% - 80px); /* Subtract input area height */
    width: 100%;
    overflow-y: auto;
    border: 1px solid #ccc;
    border-bottom: none; /* Remove bottom border */
    padding: 20px;
    padding-bottom: 10px; /* Add padding at bottom */
    flex-grow: 1; /* Allow to grow and take available space */
    border-radius: 5px 5px 0 0; /* Rounded corners only on top */
    box-sizing: border-box;
  }

  .messages_full {
    height: calc(100% - 80px); /* Subtract input area height */
    width: 100%;
    overflow-y: auto;
    border: 1px solid #ccc;
    border-bottom: none; /* Remove bottom border */
    padding: 20px;
    padding-bottom: 10px; /* Add padding at bottom */
    flex-grow: 1; /* Allow to grow and take available space */
    border-radius: 5px 5px 0 0; /* Rounded corners only on top */
    box-sizing: border-box;
  }
  
  /* Input area styles - connected to messages area */
  .input-area {
    display: flex;
    gap: 10px;
    width: 100%;
    border: 1px solid #ccc;
    border-top: 1px solid #e0e0e0; /* Lighter border for separation */
    padding: 10px;
    border-radius: 0 0 5px 5px; /* Rounded corners only on bottom */
    background-color: #f9f9f9; /* Slight background difference */
    flex-shrink: 0; /* Don't allow to shrink */
    min-height: 80px; /* Taller fixed height */
    box-sizing: border-box;
  }

  .input-area_full {
    display: flex;
    gap: 10px;
    width: 100%;
    border: 1px solid #ccc;
    border-top: 1px solid #e0e0e0; /* Lighter border for separation */
    padding: 10px;
    border-radius: 0 0 5px 5px; /* Rounded corners only on bottom */
    background-color: #f9f9f9; /* Slight background difference */
    flex-shrink: 0; /* Don't allow to shrink */
    min-height: 80px; /* Taller fixed height */
    box-sizing: border-box;
  }
  
  /* Message styles */
  .message {
    margin-bottom: 15px;
    display: flex;
  }
  
  .user-message {
    justify-content: flex-end;
  }
  
  .assistant-message {
    justify-content: flex-start;
  }

  .remember-message {
    font-weight: bold;
    color: #333333;
    justify-content: flex-start;
    margin-bottom: 1em;
  }

  .item-details-message {
    font-size: 0.95em; 
    color: #333333;
    justify-content: flex-start;
    margin-bottom: 2em;
    display: flex;
    font-family: sans-serif;
  }
  
  .message-bubble {
    max-width: 90%;
    padding: 10px 15px;
    border-radius: 15px;
  }

  .user-message .message-bubble {
    background: #007bff;
    color: white;
  }
  
  .assistant-message .message-bubble {
    background: #f9f9f9;
    color: black;
  }
  
  /* Item styles */
  .item-container {
    display: flex;
    margin-bottom: 1em;
    gap: 1em;
  }
  
  .item-content {
    flex: 1;
  }
  
  .item-title-row {
    display: flex;
    align-items: center;
    gap: 0.5em;
    margin-bottom: 0.5em;
  }
  
  .item-title-link {
    font-weight: 600;
    text-decoration: none;
    color: #2962ff;
  }
  
  .item-info-icon {
    font-size: 0.5em;
    position: relative;
  }
  
  .item-info-icon img {
    width: 16px;
    height: 16px;
  }
  
  .item-description {
    font-size: 0.9em;
  }
  
  .item-site-link {
    font-size: 0.9em;
    text-decoration: none;
    color: #2962ff;
    font-weight: 500;
    padding: 8px 0;
    display: inline-block;
  }
  
  .item-image {
    width: 80px;
    height: 80px;
    object-fit: cover;
  }
  
  .item-details-text {
    font-size: 0.85em;
  }
  
  .item-explanation {
    font-size: 0.95em;
    color: #333333;
    margin-bottom: 1em;
  }
  
  .item-real-estate-details {
    margin-top: 0.5em;
  }
  
  .message-input {
    flex-grow: 1;
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 20px; /* Rounded input field like ChatGPT */
    font-size: 16px;
    min-height: 60px; /* Taller input for more text */
    resize: none; /* Prevent manual resizing */
  }
  
  .send-button {
    padding: 10px 20px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    align-self: flex-end; /* Align button to bottom */
  }
  
  .send-button:hover {
    background: #0056b3;
  }

  .intermediate-container {
    padding: 20px 0;
    font-weight: bold;
    font-size: 0.95em;
    color: #333333;
  }
  
  /* Context URL styles */
  .context-url-container {
    margin-top: 8px;
    display: none;
  }
  
  .context-url-input {
    width: 200px;
    padding: 5px;
    border: 1px solid #ccc;
    border-radius: 4px;
  }
  
  /* Special message types */
  .ask-user-message {
    font-style: italic;
    color: #555;
    margin-bottom: 1em;
  }
  
  .site-is-irrelevant-to-query {
    color: #d32f2f;
    font-weight: bold;
    margin-bottom: 1em;
  }
`;

/**
 * Applies the CSS styles to the document
 */
export function applyStyles() {
  const styleSheet = document.createElement("style");
  styleSheet.textContent = STYLES;
  document.head.appendChild(styleSheet);
}