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
    border: 1px solid #e0e0e0;
    padding: 10px;
    border-radius: 0 0 5px 5px; /* Rounded corners only on bottom */
    background-color: #ffffff; /* Clean white background like TripAdvisor */
    flex-shrink: 0; /* Don't allow to shrink */
    min-height: 60px; /* Slightly shorter height */
    box-sizing: border-box;
    align-items: center; /* Center items vertically */
  }

  .input-area_full {
    display: flex;
    gap: 10px;
    width: 100%;
    border: 1px solid #e0e0e0;
    padding: 10px;
    border-radius: 0 0 5px 5px; /* Rounded corners only on bottom */
    background-color: #ffffff; /* Clean white background like TripAdvisor */
    flex-shrink: 0; /* Don't allow to shrink */
    min-height: 60px; /* Slightly shorter height */
    box-sizing: border-box;
    align-items: center; /* Center items vertically */
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
    background: #229269;
    color: white;
  }
  
  .assistant-message .message-bubble {
    background: #f9f9f9;
    color: black;
    box-shadow: 0 1px 2px rgba(0,0,0,0.1);
  }
  
  /* Input field styles - TripAdvisor-like */
  .message-input {
    flex-grow: 1;
    padding: 12px 15px;
    border: 1px solidrgb(0, 0, 0);
    border-radius: 4px; 
    font-size: 12px;
    min-height: 30px;
    resize: none;

    transition: all 0.2s ease;
    font-family: sans-serif;
  }
  
  .message-input:focus {
    outline: none;
    border-color: #229269; /* TripAdvisor green */
    box-shadow: 0 1px 4px rgba(0,170,108,0.2);
  }
  
  .message-input::placeholder {
    color: #717171;
    opacity: 1;
  }
  
  /* Item styles */
  .item-container {
    display: flex;
    flex-direction: row; /* Ensure image is on the left */
    margin-bottom: 1.5em;
    gap: 16px; /* Increased spacing between image and content */
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    background-color: white;
    width: 100%;
    max-width: 650px;
    box-sizing: border-box;
  }
  
  // .item-content {
  //   flex: 1;
  //   display: flex;
  //   flex-direction: column;
  //   justify-content: space-between; 
  // }
  
  .item-title-row {
    display: flex;
    align-items: center;
    gap: 0.5em;
    margin-bottom: 0.8em;
  }
  
  .item-title-link {
    font-weight: 600;
    text-decoration: none;
    color: #000;
    font-size: 1.1em;
    line-height: 1.3;
  }
  
  .item-info-icon {
    font-size: 0.5em;
    position: relative;
  }
  
  .item-info-icon img {
    width: 16px;
    height: 16px;
    opacity: 0.5;
  }
  
  .item-description {
    font-size: 0.9em;
    color: #555;
    margin-bottom: 0.8em;
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
    width: 220px;
    height: 160px;
    object-fit: cover;
    border-radius: 6px;
    flex-shrink: 0;
  }
  
  .item-details-text {
    font-size: 0.85em;
    color: #555;
    line-height: 1.5;
  }
  
  .item-explanation {
    font-size: 0.95em;
    color: #333333;
    margin-bottom: 1em;
  }
  
  .item-real-estate-details {
    margin-top: 0.5em;
  }
  
  /* Event-specific styles */
  .item-event-details {
    display: flex;
    flex-direction: column;
    gap: 0.4em;
    margin-top: 0.5em;
  }
  
  .event-datetime {
    font-weight: 500;
    color: #555;
  }
  
  .event-location {
    color: #666;
  }
  
  .event-price {
    font-weight: 500;
    color: #333;
    margin-top: 0.3em;
  }
  
  /* Additional icons and actions */
  .item-action-row {
    display: flex;
    gap: 1em;
    margin-top: auto;
    padding-top: 0.8em;
  }
  
  .item-action-icon {
    width: 18px;
    height: 18px;
    opacity: 0.6;
    cursor: pointer;
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
    background: #00aa6c; /* TripAdvisor green */
    color: white;
    border: none;
    border-radius: 24px; /* Rounded button like TripAdvisor */
    cursor: pointer;
    font-weight: 500;
    font-size: 14px;
    height: 42px; /* Match input height */
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 80px;
  }
  
  .send-button:hover {
    background: #008f5b; /* Slightly darker green on hover */
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

  /* TripAdvisor-style item container */
  .item-container {
    display: flex;
    flex-direction: row;
    align-items: flex-start;
    background: #fff;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    padding: 16px;
    margin-bottom: 20px;
    gap: 16px;
    min-width: 400px;
    max-width: 650px;
  }

  .item-image {
    width: 220px;
    height: 160px;
    object-fit: cover;
    border-radius: 6px;
    flex-shrink: 0;
  }

  .item-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    min-width: 0;
    text-align: left;
  }

  .item-label {
    display: inline-block;
    background:rgb(255, 255, 255);
    // border: 1px solid #000000;
    color:rgb(169, 169, 169);
    font-size: 10px;
    font-weight: 400;
    border-radius: 4px;
    // padding: 3px 10px;
    margin-bottom: 8px;
    text-transform: uppercase;
     /* text wrapping */
  }

  .item-title {
    font-size: 20px;
    font-weight: 700;
    color: #000;
    margin-bottom: 6px;
    line-height: 1.2;
    text-decoration: none;
    display: inline-block;
  }

  .item-rating-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
  }

  .item-rating-stars {
    display: inline-flex;
    vertical-align: middle;
  }

  .item-rating-score {
    color: #00aa6c; /* TripAdvisor green */
    font-weight: 700;
    font-size: 16px;
  }

  .item-reviews {
    color: #717171;
    font-size: 14px;
  }

  .item-location {
    color: #333;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 8px;
  }

  .item-description {
    color: #333;
    font-size: 14px;
    line-height: 1.5;
    margin-top: 6px;
    max-height: 4.5em; /* Show about 3 lines */
    overflow: hidden;
  }

  /* Remove old item-action-row, item-info-icon, etc. for clean look */
  .item-action-row, .item-info-icon, .item-site-link, .item-explanation, .item-event-details, .event-datetime, .event-location, .event-price, .item-title-row, .item-details-text, .item-real-estate-details {
    display: none !important;
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