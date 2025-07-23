/**
 * Utility functions for the streaming chat interface
 */

// Import the JsonRenderer and type renderer classes
import { JsonRenderer } from './json-renderer.js';
import { TypeRendererFactory } from './type-renderers.js';

/**
 * Escapes HTML special characters in a string
 * 
 * @param {string} str - The string to escape
 * @returns {string} - The escaped string
 */
export function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Formats JSON-LD data as colored HTML for display
 * 
 * @param {Object|string} jsonLd - The JSON-LD data to format
 * @returns {string} - HTML representation of the JSON-LD
 */
export function jsonLdToHtml(jsonLd) {
  const renderer = new JsonRenderer();
  TypeRendererFactory.registerAll(renderer);
  return renderer.render(jsonLd);
}

/**
 * Safely unescapes HTML entities in a string
 * 
 * @param {string} str - The string to unescape
 * @returns {string} - The unescaped string
 */
export function htmlUnescape(str) {
  if (!str || typeof str !== 'string') return '';
  
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<!DOCTYPE html><body>${str}`, 'text/html');
  return doc.body.textContent || '';
}

// Re-export the JsonRenderer and type renderer classes
export { JsonRenderer } from './json-renderer.js';
export { TypeRenderer, RealEstateRenderer, PodcastEpisodeRenderer, TypeRendererFactory } from './type-renderers.js';

/**
 * Creates a random ID
 * 
 * @param {number} length - The length of the ID
 * @returns {string} - The random ID
 */
export function createRandomId(length = 8) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  
  return result;
}

/**
 * Debounces a function
 * 
 * @param {Function} func - The function to debounce
 * @param {number} wait - The debounce wait time
 * @returns {Function} - The debounced function
 */
export function debounce(func, wait) {
  let timeout;
  
  return function(...args) {
    const context = this;
    clearTimeout(timeout);
    
    timeout = setTimeout(() => {
      func.apply(context, args);
    }, wait);
  };
}

/**
 * Throttles a function
 * 
 * @param {Function} func - The function to throttle
 * @param {number} limit - The throttle limit time
 * @returns {Function} - The throttled function
 */
export function throttle(func, limit) {
  let inThrottle;
  
  return function(...args) {
    const context = this;
    
    if (!inThrottle) {
      func.apply(context, args);
      inThrottle = true;
      
      setTimeout(() => {
        inThrottle = false;
      }, limit);
    }
  };
}

/**
 * Sanitizes a URL to prevent javascript: protocol and other potentially dangerous URLs
 * 
 * @param {string} url - The URL to sanitize
 * @returns {string} - The sanitized URL
 */
export function sanitizeUrl(url) {
  if (!url || typeof url !== 'string') return '#';
  
  // Remove leading and trailing whitespace
  const trimmedUrl = url.trim();
  
  // Check for javascript: protocol or other dangerous protocols
  const protocolPattern = /^(javascript|data|vbscript|file):/i;
  if (protocolPattern.test(trimmedUrl)) {
    return '#';
  }
  
  // For relative URLs or http/https, return as is
  return trimmedUrl;
}