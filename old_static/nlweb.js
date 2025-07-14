/**
 * Main entry file for the streaming chat application
 * Imports and initializes all components
 */

// Import modules
import { applyStyles } from './styles.js';
import { ManagedEventSource } from './managed-event-source.js';
import { ChatInterface } from './chat-interface.js';
import { escapeHtml } from './utils.js';

// Initialize styles
applyStyles();

// Make ChatInterface available globally
window.ChatInterface = ChatInterface;
window.ManagedEventSource = ManagedEventSource;
window.escapeHtml = escapeHtml; // Make the escapeHtml function available globally

// Initialize the chat interface when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  // You can add initialization code here if needed
  console.log('Chat interface ready');
  
  // Add basic XSS protection for the entire document
  // This helps mitigate XSS in areas we might have missed
  document.addEventListener('DOMNodeInserted', (event) => {
    // Skip non-element nodes and pre/code blocks (which might contain HTML syntax)
    if (event.target.nodeType !== Node.ELEMENT_NODE || 
        event.target.tagName === 'PRE' || 
        event.target.tagName === 'CODE' ||
        event.target.classList.contains('json-ld')) {
      return;
    }
    
    // Check for potential script injections
    const scripts = event.target.querySelectorAll('script');
    scripts.forEach(script => script.remove());
    
    // Remove potentially dangerous attributes
    const allElements = event.target.querySelectorAll('*');
    allElements.forEach(el => {
      if (el.hasAttribute('onerror') || 
          el.hasAttribute('onload') || 
          el.hasAttribute('onclick') ||
          el.hasAttribute('onmouseover')) {
        Array.from(el.attributes).forEach(attr => {
          if (attr.name.startsWith('on')) {
            el.removeAttribute(attr.name);
          }
        });
      }
    });
  });
});